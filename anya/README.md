# Anya — Telegram AI Chatbot (Cloudflare Workers)

`worker.js` me poora bot hai: AI chat (Gemini), group moderation, nox-style
tagging (`/utag` `/atag` `/gmtag` `/gntag`), reminders, notes, birthdays,
broadcast, XP/levels. `nox-tagger/` me live member-list ke liye companion
MTProto service hai (Render par host hoti hai).

## Deploy (Cloudflare)

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

## Live member list (optional par recommended)

Bot API poori member list nahi deta, isliye `/utag` live list `nox-tagger/`
service se leta hai. Bina iske bot tracked IDs par gir jayega.

1. `nox-tagger/README.md` padh ke Render par deploy karo
2. Dono taraf same `MEMBER_API_KEY`, Anya me `MEMBER_API_URL` set karo

## Cron

`wrangler.toml` me 5 triggers hai (reminders, RSS, greetings, birthdays).
Dashboard → Workers → Triggers me deploy ke baad dikhenge.

## Files

| File | Kaam |
| ---- | ---- |
| `worker.js` | Poora bot (single file Worker) |
| `wrangler.toml` | KV binding, crons, vars (ID bharna hai) |
| `nox-tagger/` | Member-list companion service (Render) |
