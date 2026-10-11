# Nox Tagger — Render par host karo

## 0. SABSE PEHLE: secrets rotate karo (zaruri!)

Tumhari purani file me bot token + api hash khula pada tha. Deploy se PEHLE:

1. Telegram me `@BotFather` → `/revoke` → purana token khatam, naya lo
2. `my.telegram.org` → API development tools → api_hash regenerate karo, api_id note karo
3. `/id` ke liye apni ID `@getidsbot` se lo (OWNER_ID)

Purane secrets se koi bhi tumhara bot chala sakta hai. Ye step skip mat karna.

## 1. Vercel kyu nahi?

Vercel serverless hai — pyrogram ko lagatar chalna hota hai, waha rukega nahi. **Render (ya Railway/Koyeb/VPS)** lo. Neeche Render ka tareeka hai.

## 2. Render deploy (free)

1. Ye folder GitHub repo me daalo (bot.py, requirements.txt, render.yaml, Procfile)
2. Render dashboard → New → Web Service → repo select karo
3. `render.yaml` dekh ke settings khud lag jayengi, ya manual:
   - Build: `pip install -r requirements.txt`
   - Start: `python bot.py`
4. Environment tab me 4 vars dalo: `API_ID`, `API_HASH`, `BOT_TOKEN`, `OWNER_ID`
5. Deploy → logs me `Bot Successfully Started!` aana chahiye

## 3. Free plan me sone se rokna

Render free service 15 min idle par sota hai (bot offline). Fix:

1. `uptimerobot.com` (free) → New Monitor → HTTP(s)
2. URL: tumhari Render service URL (jaise `https://nox-tagger.onrender.com`)
3. Interval 5 min — bot me `/` health endpoint pehle se hai

## 3b. NO_UPDATES mode (same token do jagah chal raha ho to)

Anya (node service) aur ye bot SAME token use karte hai to polling ladegi
(409 Conflict). Is service ko sirf `/members` API ke liye chalana ho to env me:

```text
NO_UPDATES=1
```

Is mode me Telegram polling band rehti hai (koi command jawab nahi dega),
sirf `/` health + `/members` chalta hai. Live `/utag` isi se aata hai.

## 4. Meri taraf se kya badla (logic same hai)

- Secrets file se nikal ke env vars me (security)
- Served users/chats auto-track hote hai — **bina iske `/broadcast` khaali jata tha** (purani file me ye missing tha, asli bug tha)
- Warns/bans `nox_data.json` me save (restart par wipe nahi honge)
- Health server sirf Render/UptimeRobot ke liye
- Saare commands, messages, tagging logic bilkul same

## 5. Anya se jodna (live full member list)

Anya ka Bot API member list nahi nikal sakta, isliye `/utag` `/gmtag` `/gntag`
live list yahi se lete hai (`GET /members?chat_id=...&key=...`):

1. Render env me ek aur var dalo: `MEMBER_API_KEY` = koi lamba random secret
2. Anya ke Worker me secrets/var set karo:
   - `MEMBER_API_URL` = `https://tumhari-service.onrender.com`
   - `MEMBER_API_KEY` = wahi secret
3. Dono set hai to `/utag` poori live list tag karega; nahi hai ya service
   soyi hai to Anya purane tracked IDs par gir jayegi (fallback automatic)

Note: Render free sone par pehla `/utag` slow/fallback ho sakta hai (cold start ~50 sec).
UptimeRobot lagane ke baad ye problem nahi hogi.

## 6. Dhyan rakhna

- `nox_data.json` Render free par restart me ud sakta hai (ephemeral disk) — warns backup chahiye to paid disk lo, warna chal jayega
- Pehli baar bot ko group me add karke `/utag test` maar ke dekho
