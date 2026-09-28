# AFK Bot Verification Add-on

This add-on is intentionally separate from the existing bot files.

Existing files such as `main.py`, `server.py`, `config.py`, and the AFK handlers are **not modified**.

## What it does

`verification_server.py` serves `verify.html` and exposes `POST /api/verify`.

For each Mini App verification it:

1. Validates Telegram Mini App `initData` server-side using the bot token.
2. Uses the verified Telegram user ID from `initData` (not an ID supplied by JavaScript).
3. Records a browser/device fingerprint and the request IP.
4. Looks up approximate IP location at city/state/country level and caches it.
5. Looks for previous verification records and links accounts only when the exact device fingerprint matches.
6. For matched Telegram IDs, checks live group membership using Telegram `getChatMember`.
7. Only treats a match as a banned-user match when Telegram says the old account is currently `kicked`.
8. Auto-bans the current ID when that exact device fingerprint has any Telegram ID that is currently banned in a configured group; otherwise verification is approved.
9. Sends the owner a detailed alert with both Telegram IDs, both IPs, approximate locations, fingerprints, matched banned group, reason, score, and ban result.

## Risk rules

The default rules are deliberately conservative:

- exact same device fingerprint + any matched Telegram ID is currently banned = **automatic ban**
- exact same device fingerprint + no matched banned Telegram ID = **approved**
- same IP only = **45 / low** (recorded, not auto-banned)

IP-only, location-only, user-agent-only, or other browser-field matches never trigger an automatic ban.

Browser fingerprinting and IP geolocation are probabilistic signals, not proof that two Telegram accounts belong to the same person.

## Files

- `verification_server.py`
- `verify.html`
- `.env.verification.example`
- `requirements-verification.txt`

## Environment

Copy `.env.verification.example` values into the environment of the verification service.

The bot must be an administrator in every verification group with permission to approve join requests and ban users. Group IDs are managed from Telegram, not environment variables.

## Run locally / VPS

```bash
pip install -r requirements-verification.txt
export BOT_TOKEN="..."
export MONGODB_URI="..."
export OWNER_ID="123456789"
python3 verification_server.py
```

Default verification server port is `8081`.

After both services are running, add the bot as an admin in a group and run:

```text
/addverifygroup
```

Use `/removeverifygroup` to remove the current group and `/verifygroups` to list configured groups.

The Mini App is opened by the bot with the correct group context automatically.

Telegram Mini Apps require HTTPS in production.

## Deployment note

Your current AFK project already runs its own Flask health server. This add-on therefore uses a separate port/service and does not alter the old server.

On Render, the cleanest setup is usually a second Web Service for `verification_server.py` because Render exposes one service port per Web Service. On a VPS you can run this on port 8081 and reverse-proxy a domain/subdomain to it.

## Mini App button

When you are ready to integrate the bot flow, point the Telegram Web App / Mini App button to:

```text
https://YOUR-VERIFICATION-DOMAIN/verify
```

The add-on backend itself does not require changes to the existing AFK bot to perform fingerprint matching, Telegram banned-member checks, automatic high-risk bans, or owner alerts.

## Approximate location

Location is IP-based and only coarse (city/state/country when the IP provider can resolve it). It is not GPS and can be wrong when the user uses mobile networks, VPNs, proxies, CGNAT, or privacy relays.

## Privacy

The page includes a short disclosure that account, device/browser, and network signals may be processed for abuse prevention. The UI does not expose your matching thresholds or detection logic.
