# Anya — Telegram AI Chatbot (Cloudflare Workers)

`worker.js` me poora bot hai: AI chat (Gemini), group moderation, nox-style
tagging (`/utag` `/atag` `/gmtag` `/gntag`), reminders, notes, birthdays,
broadcast, XP/levels. `nox-tagger/` me live member-list ke liye companion
MTProto service hai (Render par host hoti hai).

## Deploy (Render — Node service)

Cloudflare ki jagah Render par chalana ho to (same `worker.js`, zero change):

```bash
# Root Directory: anya
# Build: pip install -r nox-tagger/requirements.txt
# Start: bash start.sh
```

Env vars (Render dashboard → Environment):

```text
BOT_TOKEN=...
GEMINI_API_KEY=...
MEMBER_API_URL=https://tumhari-anya-service.onrender.com
MEMBER_API_KEY=... (koi lamba random secret, khud banao)
NO_UPDATES=1
```

Ek hi service me dono chalte hai (`start.sh`): node = Anya bot, python =
sirf member API (`/members` andar hi proxy hota hai). Isliye free hours quota
(750/month) me rehta hai. `MEMBER_API_URL` me **khud isi service ka URL** dalo.

Storage: `env.ANYA_KV` file me chalta hai (`./data/kv.json` — restart par file
udni na jaye isliye Render me **Disk** add karo ya backup lete raho).
Crons (`server.js` me ticker) reminders/greetings chalate hai.

Deploy ke baad webhook Render URL par set karo:

```text
https://api.telegram.org/bot<TOKEN>/setWebhook?url=https://tumhari-anya.onrender.com
```

UptimeRobot se sirf isi service ka URL ping karo (ek hi service hai ab).
Free 750 hours/month me rehta hai (~730 lagte hai) — headroom kam hai,
month-end par suspend ho to paid ($7) ya VPS sochna.

## Deploy (Cloudflare — purana tareeka)

```bash
npm install -g wrangler
wrangler login

# 1. KV banao, jo ID mile wrangler.toml me daalo
wrangler kv namespace create ANYA_KV

# 2. Secrets dalo (file me KABHI mat likhna)
wrangler secret put BOT_TOKEN
wrangler secret put GEMINI_API_KEY
wrangler secret put MEMBER_API_KEY

# 3. Deploy
wrangler deploy
```

Deploy ke baad jo worker URL mile (`https://anya.tumhara.workers.dev`),
Telegram webhook set karo (bot token wala):

```text
https://api.telegram.org/bot<TOKEN>/setWebhook?url=https://anya.tumhara.workers.dev
```

## Config (worker.js ke upar)

- `BOT_USERNAME`, `OWNER_USER_ID`, `OWNER_USERNAME` — apne hisab se badlo
- `GEMINI_MODEL` — model ka naam
- Baaki limits/quota constants file ke upar CONFIG section me hai

## Live member list (automatic — same service me hai)

Bot API poori member list nahi deta, isliye `/utag` live list andar chal rahe
python (`nox-tagger/`) se leta hai. `MEMBER_API_URL` me khud isi service ka URL
dalo. Na mile to bot tracked IDs par gir jayega (fallback automatic).

## Cron

`wrangler.toml` me 5 triggers hai (reminders, RSS, greetings, birthdays).
Dashboard → Workers → Triggers me deploy ke baad dikhenge.

## Files

| File | Kaam |
| ---- | ---- |
| `worker.js` | Poora bot (single file Worker) |
| `server.js` | Node adapter — webhook + cron + member proxy |
| `kvstore.js` | File storage (KV ki jagah) |
| `start.sh` | Ek service me node + python dono chalata hai |
| `wrangler.toml` | KV binding, crons, vars (Cloudflare wala tareeka) |
| `nox-tagger/` | Member-list companion (same service me chalta hai) |
