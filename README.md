# Advanced AFK Bot + Verification Mini App

This merged package contains the original AFK bot plus the AFK Verification add-on.

## Main AFK features

- `/afk` or `brb` with optional reason.
- AFK with replied photo/GIF/sticker media.
- Mention/reply detection with AFK reason and elapsed duration.
- Automatic AFK removal when the user returns.
- Persistent MongoDB AFK storage.
- Force AFK: `/forceafk` auto-deletes that user's group messages until `/unafk`.
- Per-group bot-message auto-delete settings with 5/10/30/60 minute presets.
- User/group tracking and bot statistics.
- Top AFK leaderboard based on accumulated AFK time.
- Owner broadcast tools for users/groups, including pin options.
- Flask health endpoint for hosting/uptime checks.

## Verification add-on features

- `/verify` and a private-chat **Verify User** Mini App button when `VERIFY_URL` is configured.
- Server-side Telegram Mini App `initData` signature validation; browser-supplied Telegram IDs are not trusted.
- Stores verification events in the same `afk_db` MongoDB database.
- Browser/device fingerprint and request IP signals for repeat-account abuse checks.
- Coarse IP geolocation (city/state/country when available) with cache.
- Checks matched historical Telegram IDs against configured groups using Telegram `getChatMember`.
- Only treats an old account as banned when Telegram currently reports it as `kicked`.
- Device-ban inheritance: if the exact device fingerprint was previously used by any Telegram ID that is currently banned in a configured group, the new ID is auto-banned; otherwise it is approved. IP alone never auto-bans.
- Optional automatic ban across verification groups and detailed owner alerts.

Fingerprint/IP matching is probabilistic and can be affected by VPNs, proxies, mobile networks, CGNAT, shared devices, or browser changes. It should be treated as an abuse-prevention signal rather than identity proof.

## Environment

Copy `.env.example` values into your host's environment. Required bot values are `BOT_TOKEN`, `API_ID`, `API_HASH`, `BOT_USERNAME`, `MONGODB_URI`, and `OWNER_ID`.

For verification, `VERIFY_URL` is required. Verification groups are added and removed directly through the bot, so no group ID environment variable is needed. The bot must be an admin with permission to approve join requests and ban users in each verification group.

## Install

```bash
pip install -r requirements.txt
```

## Run on VPS

Run the AFK bot:

```bash
python3 main.py
```

Run the verification web service separately:

```bash
python3 verification_server.py
```

The bot health server defaults to port `8080`; verification defaults to `8081`. Reverse-proxy a public HTTPS domain/subdomain to port 8081 and set that public base URL as `VERIFY_URL`.

Example:

```env
VERIFY_URL=https://verify.example.com
```

Then add the bot as an admin in the target group and run `/addverifygroup` there. Use `/removeverifygroup` to remove it and `/verifygroups` to list all configured groups. New join requests are held until verification succeeds; successful verification triggers Telegram join-request approval automatically.

## Verification collections

The add-on uses these collections under `afk_db`:

- `verification_events`
- `verification_actions`
- `verification_ip_geo_cache`
- `verification_groups`
- `verification_pending`

Existing AFK collections remain unchanged.

## Files

- `main.py` — AFK bot
- `verification_server.py` — verification API/web server
- `verify.html` — Telegram Mini App UI
- `.env.example` — combined environment template
- `VERIFICATION_SETUP.md` — detailed verification notes
- `requirements.txt` — combined dependencies
- `Dockerfile`, `render.yaml` — deployment files

## Render note

The AFK bot and verification web app need separate public services because the verification Mini App must have its own reachable HTTPS endpoint. In the included `render.yaml`, the AFK bot now gets `VERIFY_URL` automatically from the `afk-verification` service's Render-provided `RENDER_EXTERNAL_URL`, so you do not need to type the verification URL manually. Use the same bot token and MongoDB URI for both services.
