#!/bin/bash
# Ek hi Render service me dono: python (member API, polling band) + node (Anya bot)
# Isse free 750 hours/month quota me rehta hai (2 service 24x7 = quota khatam).
export NO_UPDATES=1
export MEMBER_LOCAL_PORT=8051
NO_UPDATES=1 PORT=8051 python nox-tagger/bot.py &
exec node server.js
