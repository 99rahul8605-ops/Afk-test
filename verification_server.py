import os
import json
import hmac
import hashlib
import logging
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from flask import Flask, jsonify, request, send_from_directory
from pymongo import MongoClient, ASCENDING, DESCENDING


# ============================================================
# Configuration
# ============================================================

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
MONGODB_URI = os.getenv("MONGODB_URI", "").strip()
OWNER_ID = int(os.getenv("OWNER_ID", "0") or 0)

VERIFY_HOST = os.getenv("VERIFY_HOST", "0.0.0.0")
VERIFY_PORT = int(os.getenv("VERIFY_PORT", os.getenv("PORT", "8081")))

# initData freshness. 15 minutes is a sensible verification window.
INITDATA_MAX_AGE = int(os.getenv("INITDATA_MAX_AGE", "900"))

# Exact-device banned match auto-ban switch. Kept under the old env name for backward compatibility.
AUTO_BAN_HIGH_RISK = os.getenv("AUTO_BAN_HIGH_RISK", "true").lower() in {
    "1", "true", "yes", "on"
}

# Trust reverse-proxy headers only when your deployment actually uses them.
TRUST_PROXY_HEADERS = os.getenv("TRUST_PROXY_HEADERS", "true").lower() in {
    "1", "true", "yes", "on"
}

# Number of prior matching records inspected per verification.
MATCH_LIMIT = max(5, min(int(os.getenv("MATCH_LIMIT", "40")), 100))

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is required.")
if not MONGODB_URI:
    raise RuntimeError("MONGODB_URI is required.")


# ============================================================
# Logging / Mongo
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - verification - %(levelname)s - %(message)s",
)
logger = logging.getLogger("verification")

mongo = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=10000)
db = mongo.afk_db

verification_events = db.verification_events
verification_actions = db.verification_actions
ip_geo_cache = db.verification_ip_geo_cache
verification_groups = db.verification_groups
verification_pending = db.verification_pending

# Helpful indexes. These collections are separate from the existing AFK bot.
verification_events.create_index([("telegram_user_id", ASCENDING), ("created_at", DESCENDING)])
verification_events.create_index([("fingerprint", ASCENDING), ("created_at", DESCENDING)])
verification_events.create_index([("ip", ASCENDING), ("created_at", DESCENDING)])
verification_events.create_index([("group_ids", ASCENDING)])
verification_events.create_index([("decision", ASCENDING), ("created_at", DESCENDING)])
verification_actions.create_index([("telegram_user_id", ASCENDING), ("created_at", DESCENDING)])
ip_geo_cache.create_index([("ip", ASCENDING)], unique=True)


# ============================================================
# Flask
# ============================================================

app = Flask(__name__)
BASE_DIR = Path(__file__).resolve().parent


# ============================================================
# Dynamic verification-group configuration
# ============================================================

def get_verification_group_ids():
    return [
        int(doc["chat_id"])
        for doc in verification_groups.find({"enabled": {"$ne": False}}, {"chat_id": 1}).sort("added_at", ASCENDING)
        if doc.get("chat_id") is not None
    ]

def is_configured_group(group_id: int) -> bool:
    return verification_groups.find_one({"chat_id": int(group_id), "enabled": {"$ne": False}}) is not None


# ============================================================
# Telegram helpers
# ============================================================

def telegram_api(method: str, payload: Optional[dict] = None, timeout: int = 12):
    """Call Telegram Bot API without starting another Pyrogram client."""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"
    data = urllib.parse.urlencode(payload or {}).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:
            body = json.loads(res.read().decode("utf-8"))
    except Exception as e:
        logger.warning("Telegram API %s failed: %s", method, e)
        return {"ok": False, "description": str(e)}

    return body


def get_chat_member(group_id: int, user_id: int):
    return telegram_api(
        "getChatMember",
        {"chat_id": group_id, "user_id": user_id},
    )


def is_banned_in_group(group_id: int, user_id: int):
    result = get_chat_member(group_id, user_id)
    if not result.get("ok"):
        return False, None

    member = result.get("result") or {}
    # Bot API returns "kicked" for banned users.
    return member.get("status") == "kicked", member


def ban_user(group_id: int, user_id: int):
    return telegram_api(
        "banChatMember",
        {
            "chat_id": group_id,
            "user_id": user_id,
            "revoke_messages": "true",
        },
    )


def send_owner_message(text: str):
    if not OWNER_ID:
        return {"ok": False, "description": "OWNER_ID not configured"}

    return telegram_api(
        "sendMessage",
        {
            "chat_id": OWNER_ID,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": "true",
        },
    )


# ============================================================
# Telegram Mini App initData validation
# ============================================================

def validate_init_data(init_data: str):
    if not init_data:
        return False, "missing_init_data", None

    try:
        parsed_pairs = urllib.parse.parse_qsl(
            init_data,
            keep_blank_values=True,
            strict_parsing=True,
        )
        parsed = dict(parsed_pairs)
    except Exception:
        return False, "invalid_init_data", None

    received_hash = parsed.pop("hash", None)
    if not received_hash:
        return False, "missing_hash", None

    data_check_string = "\n".join(
        f"{key}={value}"
        for key, value in sorted(parsed.items())
    )

    secret_key = hmac.new(
        b"WebAppData",
        BOT_TOKEN.encode("utf-8"),
        hashlib.sha256,
    ).digest()

    expected_hash = hmac.new(
        secret_key,
        data_check_string.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(expected_hash, received_hash):
        return False, "bad_signature", None

    try:
        auth_date = int(parsed.get("auth_date", "0"))
    except ValueError:
        return False, "bad_auth_date", None

    now = int(time.time())
    if auth_date <= 0 or abs(now - auth_date) > INITDATA_MAX_AGE:
        return False, "expired_init_data", None

    try:
        user = json.loads(parsed.get("user", "{}"))
        user_id = int(user["id"])
    except Exception:
        return False, "missing_user", None

    return True, None, {
        "user": user,
        "user_id": user_id,
        "auth_date": auth_date,
        "query_id": parsed.get("query_id"),
    }


# ============================================================
# IP / approximate location
# ============================================================

def client_ip():
    if TRUST_PROXY_HEADERS:
        cf = (request.headers.get("CF-Connecting-IP") or "").strip()
        if cf:
            return cf

        xff = (request.headers.get("X-Forwarded-For") or "").strip()
        if xff:
            return xff.split(",")[0].strip()

        real_ip = (request.headers.get("X-Real-IP") or "").strip()
        if real_ip:
            return real_ip

    return (request.remote_addr or "").strip()


def approximate_ip_location(ip: str):
    """
    Returns coarse city/state/country-level IP location.
    This is approximate network geolocation, not GPS.
    """
    if not ip:
        return {
            "city": None,
            "region": None,
            "country": None,
            "country_code": None,
            "asn": None,
            "org": None,
        }

    cached = ip_geo_cache.find_one({"ip": ip})
    if cached:
        return {
            "city": cached.get("city"),
            "region": cached.get("region"),
            "country": cached.get("country"),
            "country_code": cached.get("country_code"),
            "asn": cached.get("asn"),
            "org": cached.get("org"),
        }

    result = {
        "city": None,
        "region": None,
        "country": None,
        "country_code": None,
        "asn": None,
        "org": None,
    }

    try:
        safe_ip = urllib.parse.quote(ip, safe=":")
        url = f"https://ipwho.is/{safe_ip}"
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "AFKVerification/1.0"},
        )
        with urllib.request.urlopen(req, timeout=4) as res:
            data = json.loads(res.read().decode("utf-8"))

        if data.get("success", True):
            conn = data.get("connection") or {}
            result = {
                "city": data.get("city"),
                "region": data.get("region"),
                "country": data.get("country"),
                "country_code": data.get("country_code"),
                "asn": conn.get("asn"),
                "org": conn.get("org") or conn.get("isp"),
            }
    except Exception as e:
        logger.info("IP location lookup failed for %s: %s", ip, e)

    try:
        ip_geo_cache.update_one(
            {"ip": ip},
            {
                "$set": {
                    "ip": ip,
                    **result,
                    "updated_at": datetime.now(timezone.utc),
                }
            },
            upsert=True,
        )
    except Exception:
        pass

    return result


def location_text(doc: dict):
    geo = doc.get("geo") or {}
    parts = [
        geo.get("city"),
        geo.get("region"),
        geo.get("country"),
    ]
    return ", ".join(str(x) for x in parts if x) or "Unknown"


# ============================================================
# Risk matching
# ============================================================

def candidate_matches(current_user_id: int, fingerprint: str, ip: str):
    """
    Pull only exact fingerprint/IP candidates. We do not auto-ban from IP alone.
    """
    clauses = []
    if fingerprint:
        clauses.append({"fingerprint": fingerprint})
    if ip:
        clauses.append({"ip": ip})

    if not clauses:
        return []

    cursor = verification_events.find(
        {
            "telegram_user_id": {"$ne": current_user_id},
            "$or": clauses,
        }
    ).sort("created_at", DESCENDING).limit(MATCH_LIMIT)

    return list(cursor)


def banned_matches_for_current_user(
    current_user_id: int,
    fingerprint: str,
    ip: str,
    device: dict,
):
    """
    Return prior Telegram IDs that used the exact same device fingerprint and
    are currently banned in at least one configured verification group.

    IP and browser fields are retained only for logs/diagnostics. They never
    cause an automatic ban by themselves.
    """
    matches = []
    seen = set()

    for old in candidate_matches(current_user_id, fingerprint, ip):
        old_user_id = int(old.get("telegram_user_id", 0) or 0)
        if not old_user_id or old_user_id in seen:
            continue
        seen.add(old_user_id)

        fp_same = bool(
            fingerprint
            and old.get("fingerprint")
            and old.get("fingerprint") == fingerprint
        )

        # Core policy: only an exact same-device fingerprint can link the IDs.
        # Same IP, location, user-agent, screen, etc. are NOT enough.
        if not fp_same:
            continue

        ip_same = bool(ip and old.get("ip") and old.get("ip") == ip)
        old_device = old.get("device") or {}
        supporting = {
            "user_agent": bool(device.get("user_agent") and old_device.get("user_agent") == device.get("user_agent")),
            "screen": bool(device.get("screen") and old_device.get("screen") == device.get("screen")),
            "timezone": bool(device.get("timezone") and old_device.get("timezone") == device.get("timezone")),
            "language": bool(device.get("language") and old_device.get("language") == device.get("language")),
        }

        for group_id in get_verification_group_ids():
            banned, member = is_banned_in_group(group_id, old_user_id)
            if not banned:
                continue

            matches.append({
                "group_id": group_id,
                "matched_user_id": old_user_id,
                "score": 100,
                "level": "high",
                "reason": "same device fingerprint + matched Telegram ID is banned",
                "fingerprint_same": True,
                "ip_same": ip_same,
                "supporting": supporting,
                "old_event": old,
                "member": member,
            })

    matches.sort(key=lambda x: x["score"], reverse=True)
    return matches


# ============================================================
# Owner notification
# ============================================================

def h(value):
    """Minimal HTML escaping for Telegram HTML messages."""
    return (
        str(value if value is not None else "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def short_fp(fp: str):
    if not fp:
        return "N/A"
    return f"{fp[:12]}…{fp[-8:]}" if len(fp) > 24 else fp


def notify_high_risk(current_doc: dict, match: dict, ban_results: list):
    old = match["old_event"]

    cur_name = current_doc.get("name") or "Unknown"
    old_name = old.get("name") or "Unknown"

    cur_username = current_doc.get("username")
    old_username = old.get("username")

    cur_user_label = (
        f"{cur_name}" + (f" (@{cur_username})" if cur_username else "")
    )
    old_user_label = (
        f"{old_name}" + (f" (@{old_username})" if old_username else "")
    )

    ban_lines = []
    for item in ban_results:
        ban_lines.append(
            f"• <code>{item['group_id']}</code>: "
            + ("✅ banned" if item["ok"] else f"❌ {h(item.get('error', 'failed'))}")
        )

    text = (
        "🚨 <b>High-Risk Verification Match</b>\n\n"
        f"<b>Risk:</b> {match['score']}/100 — {h(match['reason'])}\n\n"

        "<b>Current user</b>\n"
        f"👤 {h(cur_user_label)}\n"
        f"🆔 <code>{current_doc['telegram_user_id']}</code>\n"
        f"🌐 IP: <code>{h(current_doc.get('ip') or 'N/A')}</code>\n"
        f"📍 Approx: {h(location_text(current_doc))}\n"
        f"🧩 Fingerprint: <code>{h(short_fp(current_doc.get('fingerprint')))}</code>\n\n"

        "<b>Matched banned user</b>\n"
        f"👤 {h(old_user_label)}\n"
        f"🆔 <code>{old.get('telegram_user_id')}</code>\n"
        f"🌐 IP: <code>{h(old.get('ip') or 'N/A')}</code>\n"
        f"📍 Approx: {h(location_text(old))}\n"
        f"🧩 Fingerprint: <code>{h(short_fp(old.get('fingerprint')))}</code>\n"
        f"🚫 Banned in group: <code>{match['group_id']}</code>\n\n"

        "<b>Automatic action</b>\n"
        + ("\n".join(ban_lines) if ban_lines else "No ban action.")
    )

    send_owner_message(text)


# ============================================================
# Routes
# ============================================================

@app.get("/")
@app.get("/verify")
def verify_page():
    return send_from_directory(BASE_DIR, "verify.html")


@app.get("/health")
def health():
    return jsonify({"ok": True, "service": "verification"})


@app.post("/api/verify")
def verify_api():
    payload = request.get_json(silent=True) or {}

    try:
        target_group_id = int(payload.get("group_id") or 0)
    except Exception:
        target_group_id = 0
    if not target_group_id or not is_configured_group(target_group_id):
        return jsonify({
            "ok": False,
            "status": "failed",
            "message": "This verification group is not configured.",
        }), 400

    ok, err, init = validate_init_data(str(payload.get("initData") or ""))
    if not ok:
        return jsonify({
            "ok": False,
            "status": "failed",
            "message": "Verification could not be completed.",
            "code": err,
        }), 401

    telegram_user = init["user"]
    telegram_user_id = init["user_id"]

    # Never trust telegram_user_id sent separately by browser.
    claimed_id = payload.get("telegram_user_id")
    try:
        if claimed_id is not None and int(claimed_id) != telegram_user_id:
            return jsonify({
                "ok": False,
                "status": "failed",
                "message": "Verification could not be completed.",
            }), 401
    except Exception:
        return jsonify({
            "ok": False,
            "status": "failed",
            "message": "Verification could not be completed.",
        }), 401

    fingerprint = str(payload.get("fingerprint") or "").strip().lower()
    if len(fingerprint) != 64 or any(c not in "0123456789abcdef" for c in fingerprint):
        return jsonify({
            "ok": False,
            "status": "failed",
            "message": "Verification could not be completed.",
        }), 400

    ip = client_ip()
    geo = approximate_ip_location(ip)

    first_name = str(telegram_user.get("first_name") or "").strip()
    last_name = str(telegram_user.get("last_name") or "").strip()
    name = " ".join(x for x in [first_name, last_name] if x).strip() or "Unknown"

    device = {
        "user_agent": str(payload.get("user_agent") or "")[:1000],
        "screen": str(payload.get("screen") or "")[:100],
        "timezone": str(payload.get("timezone") or "")[:100],
        "language": str(payload.get("language") or "")[:100],
        "platform": str(payload.get("platform") or "")[:100],
        "hardware_concurrency": payload.get("hardware_concurrency"),
        "max_touch_points": payload.get("max_touch_points"),
    }

    current_doc = {
        "telegram_user_id": telegram_user_id,
        "name": name,
        "username": telegram_user.get("username"),
        "is_premium": telegram_user.get("is_premium"),
        "fingerprint": fingerprint,
        "ip": ip,
        "geo": geo,
        "device": device,
        "group_ids": get_verification_group_ids(),
        "target_group_id": target_group_id,
        "auth_date": init["auth_date"],
        "created_at": datetime.now(timezone.utc),
        "decision": "pending",
    }

    matches = banned_matches_for_current_user(
        current_user_id=telegram_user_id,
        fingerprint=fingerprint,
        ip=ip,
        device=device,
    )

    best = matches[0] if matches else None
    banned_device_match = bool(best)

    if banned_device_match and AUTO_BAN_HIGH_RISK:
        ban_results = []
        for group_id in get_verification_group_ids():
            result = ban_user(group_id, telegram_user_id)
            ban_results.append({
                "group_id": group_id,
                "ok": bool(result.get("ok")),
                "error": result.get("description"),
            })

        current_doc["decision"] = "auto_banned"
        current_doc["risk_level"] = "high"
        current_doc["risk_score"] = best["score"]
        current_doc["match_reason"] = best["reason"]
        current_doc["matched_user_id"] = best["matched_user_id"]
        current_doc["matched_group_id"] = best["group_id"]
        current_doc["ban_results"] = ban_results

        inserted = verification_events.insert_one(current_doc)

        verification_actions.insert_one({
            "event_id": inserted.inserted_id,
            "telegram_user_id": telegram_user_id,
            "action": "auto_ban_high_risk",
            "matched_user_id": best["matched_user_id"],
            "risk_score": best["score"],
            "reason": best["reason"],
            "ban_results": ban_results,
            "created_at": datetime.now(timezone.utc),
        })

        try:
            notify_high_risk(current_doc, best, ban_results)
        except Exception as e:
            logger.exception("Owner notification failed: %s", e)

        verification_pending.update_one(
            {"group_id": target_group_id, "user_id": telegram_user_id},
            {"$set": {"status": "auto_banned", "verified_at": datetime.now(timezone.utc)}},
            upsert=True,
        )

        # Keep user-facing response generic.
        return jsonify({
            "ok": False,
            "status": "restricted",
            "message": "Verification could not be approved.",
        }), 403

    # No banned Telegram ID was found for this exact device fingerprint: approve.
    current_doc["decision"] = "verified"
    current_doc["risk_level"] = best["level"] if best else "none"
    current_doc["risk_score"] = best["score"] if best else 0

    if best:
        current_doc["match_reason"] = best["reason"]
        current_doc["matched_user_id"] = best["matched_user_id"]
        current_doc["matched_group_id"] = best["group_id"]

    inserted = verification_events.insert_one(current_doc)

    approve_result = telegram_api(
        "approveChatJoinRequest",
        {"chat_id": target_group_id, "user_id": telegram_user_id},
    )
    approved = bool(approve_result.get("ok"))
    verification_pending.update_one(
        {"group_id": target_group_id, "user_id": telegram_user_id},
        {"$set": {
            "status": "approved" if approved else "verified_waiting_approval",
            "verified_at": datetime.now(timezone.utc),
            "verification_event_id": inserted.inserted_id,
            "approval_error": None if approved else approve_result.get("description"),
        }},
        upsert=True,
    )

    verification_actions.insert_one({
        "event_id": inserted.inserted_id,
        "telegram_user_id": telegram_user_id,
        "group_id": target_group_id,
        "action": "approve_join_request" if approved else "join_approval_failed",
        "error": None if approved else approve_result.get("description"),
        "created_at": datetime.now(timezone.utc),
    })

    return jsonify({
        "ok": True,
        "status": "verified",
        "approved": approved,
        "message": (
            "Verification completed successfully. Your join request has been approved."
            if approved else
            "Verification completed successfully. Your join request is waiting for approval."
        ),
    })


if __name__ == "__main__":
    logger.info(
        "Verification server starting on %s:%s for groups %s",
        VERIFY_HOST,
        VERIFY_PORT,
        get_verification_group_ids(),
    )
    app.run(
        host=VERIFY_HOST,
        port=VERIFY_PORT,
        threaded=True,
    )
