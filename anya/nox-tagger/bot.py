import asyncio
import json
import os
import random
import time
from pyrogram import Client, filters, enums
from pyrogram.types import Message, ChatPermissions
from pyrogram.errors import UserAdminInvalid, ChatAdminRequired, FloodWait
from aiohttp import web

# --- Configuration (Render dashboard > Environment me set karo, file me secret mat likho) ---
API_ID = int(os.environ.get("API_ID", "0"))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
OWNER_ID = int(os.environ.get("OWNER_ID", "0"))

if not API_ID or not API_HASH or not BOT_TOKEN or not OWNER_ID:
    raise SystemExit("API_ID / API_HASH / BOT_TOKEN / OWNER_ID env vars missing hai - Render dashboard me set karo")

app = Client("ultimate_tagger_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN,
             no_updates=(os.environ.get("NO_UPDATES", "0") == "1"))
# NO_UPDATES=1 matlab: Telegram polling band, sirf /members + health chalega.
# Ye mode tab use karo jab SAME token ka main bot (Anya) kahin aur chal raha ho,
# warna dono getUpdates ke liye ladenge (409 Conflict).

# Databases (In-Memory Sets & Dicts)
active_tags = {}
gbanned_users = set()
gmuted_users = set()
warns_db = {}  # {chat_id: {user_id: count}}

# Broadcast Databases
SERVED_USERS = set()
SERVED_CHATS = set()

# Anti-Spam Tracker: {user_id: [timestamps]}
user_msg_tracker = {}

# --- Simple JSON persistence (Render free restart par memory wipe hoti hai, isliye disk backup) ---
DATA_FILE = "nox_data.json"


def load_data():
    try:
        with open(DATA_FILE) as f:
            d = json.load(f)
        SERVED_USERS.update(d.get("users", []))
        SERVED_CHATS.update(d.get("chats", []))
        gbanned_users.update(d.get("gbans", []))
        gmuted_users.update(d.get("gmutes", []))
        for k, v in d.get("warns", {}).items():
            warns_db[int(k)] = {int(u): c for u, c in v.items()}
    except Exception:
        pass


def save_data():
    try:
        with open(DATA_FILE, "w") as f:
            json.dump({
                "users": list(SERVED_USERS),
                "chats": list(SERVED_CHATS),
                "gbans": list(gbanned_users),
                "gmutes": list(gmuted_users),
                "warns": warns_db,
            }, f)
    except Exception:
        pass

# --- BAD WORDS / VULGAR WORDS LIST ---
BAD_WORDS = [
    "gand", "gaand", "choot", "chut", "lauda", "loda", "lund", "bhosdike",
    "mc", "bc", "madarchod", "bhenchod", "behenchod", "bhosda", "chutiya",
    "randi", "harami", "fuck", "bitch", "pussy", "dick", "porn", "sex", "18+", "sala", "mkc", "bkl", "bsdk", "chod", "chud", "boobs", "bur", "sale", "sexy", "gay", "lesbian", "chhinar", "chinar", "cud", "jhat", "chuchi", "pel", "kela", "kiss", "chudai", "hot", "chest", "rndi", "ramdi", "rmdi"
]

# --- Fun Roast Messages for Non-Admins ---
ROAST_MESSAGES = [
    "Aaye bade Admin banne waale! Pehle Admin ka tag toh le aao! 🤡",
    "Bhai tu command mat chala, tere bas ki baat nahi hai! 😂",
    "Jitni teri aukaat nahi utne bade command de raha hai! 🖐️",
    "Oye hero! Group me shanti se reh, Admin banne ki koshish mat kar! 🛑",
    "Tu wahi hai na jo school me monitor banne ke liye maam ki chat-ta tha? 🦎",
    "Kyun ungli kar raha hai bhai? Command sirf Admins ke liye hai! ❌",
    "Aise command chalane se tu cool nahi ban jayega! Aaram se baith! 🧊"
]

# --- High Bold & Respectful Good Morning Messages ---
GM_MESSAGES = [
    "☀️ **SUBAH KI NAYI ROSHNI! AAPKA DIN KHUSHIYON SE BHARA RAHE!** ☕",
    "🌸 **GOOD MORNING! NAYI UMANG AUR NAYI SOCH KE SATH AAGE BADHO!** 🍀",
    "☕ **CHAI KI CHUSKI! EK PYARI SI SUBAH AUR AAPKI PYARI SI MUSKAAN!** 🌄",
    "🚀 **NAYA DIN NAYI SHURUAT! AAJ KA DIN AAPKE SARE SAPNE PURE KARE!** ✨",
    "🌻 **FRESH MORNING! HAMESHA KHUSH RAHO AUR SABKO KHUSHIYAN BAANTO!** 🌺",
    "💡 **WAKE UP GREAT SOUL! HAR NAYA DIN EK NAYA MAUKA LEKAR AATA HAI!** 🔥",
    "🎨 **COLOURFUL DAY! AAPKI ZINDAGI ME SIRF RANG AUR KHUSHIYAN HON!** 🌈",
    "🕊️ **SMILE ALWAYS! AAPKI EK MUSKAAN KISI KA DIN BANA SAKTI HAI!** ⚡",
    "⚡ **RISE AND SHINE! AAP ME BOHOT CAPABILITY HAI, AAGE BADHO!** ⏰",
    "🌟 **NEW DAY NEW GOALS! AAJ KA DIN AAPKE LIYE BOHOT KHAAS HO!** 🖌️",
    "👑 **CHAMPIONS! MEHNAT KARTE RAHO, KAMYABI AAPKE KADAM CHUMEGI!** 💪",
    "🌸 **HAPPY MORNING! DIL ME ACHHI SOCH AUR CHEHRE PAR KHUSHI RAKHO!** 😊",
    "🍀 **GOOD LUCK! AAJ JO BHI KAAM KARO USME SAFALTA MILE!** ✨",
    "🌞 **SUNRISE VIBES! THANDI HAWA AUR SUKOON BHARI SUBAH MUBARAK!** 🔔",
    "💫 **POSITIVE ENERGY! AAJ KA DIN AAPKO HAR MUSHIKIL SE DOOR RAKHE!** 🌿",
    "🎯 **FOCUS ON GROWTH! HAR ROZ THODA THODA BEHTAR BANO!** 🚀",
    "🌺 **CHILL AND SMILE! TENSION KO BYE BOLO AUR DIN ENJOY KARO!** 😎",
    "🦋 **FLY HIGH! APNE SAPNON KO NAYI UDAAN DO AAJ!** 🌅",
    "☀️ **BLESSED MORNING! ISHWAR AAPKO HAMESHA SWASTH AUR KHUSH RAKHE!** 🙏",
    "🎉 **AMAZING DAY! TODAY IS GOING TO BE WONDERFUL AND PEACEFUL!** 🎁"
]

# --- High Bold & Respectful Good Night Messages ---
GN_MESSAGES = [
    "🌙 **SO JAO SABHI! TAARON KI CHHAON ME SUKOON BHARI NEEND AAYE!** ⭐",
    "😴 **SWEET DREAMS! DIN BHAR KI THAKAN KO BHOOL KAR AARAM KARO!** 🌃",
    "🌟 **LIGHTS OFF! CHAAND KI THANDI ROSHNI AAPKO SUKOON DE!** 🔮",
    "💤 **NO MORE STRESS! KAL EK NAYA AUR HASEEN DIN AAPKA INTEZAAR KAR RAHA HAI!** 🛋️",
    "☁️ **DREAMLAND! MEETHE SAPNON KI DUNIYA ME KHO JAANE KA WAQT HAI!** 🌌",
    "🛌 **REST TIME! AB PHONE SIDE ME RAKHO AUR RELAXING NEEND LO!** 📱❌",
    "✨ **NEW HOPES! AAJ KI RAAT AAPKE DIL KO SHAANTI AUR SUKOON DE!** 🌠",
    "⭐ **SUKOON KI RAAT! SABHI TENSION KO DOOR KARKE SO JAO!** 🕊️",
    "🌃 **GOOD NIGHT! ZINDAGI ME HAR RAAT SUKOON LEKAR AAYE!** 🌙",
    "🧸 **SLEEP TIGHT! MEETHE-MEETHE SAPNE AUR PYARI NEEND MUBARAK!** 🛌",
    "🌌 **NIGHT VIBES! TAARON KI MEHFIL AUR PYARI SI RAAT!** ✨",
    "🕊️ **CALM MIND! DIMAAG KO SHANTI DO AUR AARAAM SE SO JAO!** 🌙",
    "🌠 **MAKE A WISH! AAJ KI RAAT AAPKI HAR MANOKAMNA PURI HO!** ⭐",
    "😴 **SEE YOU TOMORROW! KAL PHIR EK NAYI AUR ENERGETIC SHURUAT KARENGE!** 🚀",
    "🌙 **CHAAND NIKAL AAYA! SABSE PEHLE AARAAM KARNA ZAROORI HAI!** 🌃",
    "✨ **DAY IS OVER! AAJ KA DIN CHAHE JAISA GAYA, KAL NAYA DIN HOGA!** 📚",
    "🌟 **HAPPY DREAMS! KHUSHIYON SE BHARE SAPNE AAYEIN AAPKO!** 🎈",
    "💤 **SCREEN OFF! AANKHEIN BAND KARO AUR DIL SE SHUKRIYA KAHO!** 😴",
    "🔮 **MAGICAL NIGHT! PEACE, REST AND HAPPY THOUGHTS TO ALL!** 🌌",
    "✨ **GOODNIGHT! SLEEP WELL, TAKE CARE AND WAKE UP FRESH TOMORROW!** 🌠"
]

# Helper: Check Cancel
def is_cancelled(chat_id):
    return active_tags.get(chat_id, False) == False

# Helper: Admin Checker + Roast Function
async def is_admin(client: Client, message: Message):
    if message.chat.type in [enums.ChatType.PRIVATE]:
        return True
    member = await client.get_chat_member(message.chat.id, message.from_user.id)
    if member.status in [enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER]:
        return True

    # Roast Non-Admins
    roast = random.choice(ROAST_MESSAGES)
    mention = f"[{message.from_user.first_name}](tg://user?id={message.from_user.id})"
    await message.reply_text(f"{mention} {roast}")
    return False

# Helper: Extract User for Mod Commands
async def get_target_user(client: Client, message: Message):
    if message.reply_to_message:
        return message.reply_to_message.from_user.id
    elif len(message.command) > 1:
        user_input = message.command[1]
        try:
            user = await client.get_users(user_input)
            return user.id
        except Exception:
            return None
    return None

# --- Served tracker (broadcast ke liye: har chat/user auto-save, warna broadcast khaali jayega) ---
@app.on_message(filters.group, group=2)
async def track_chats(client: Client, message: Message):
    SERVED_CHATS.add(message.chat.id)
    if message.from_user:
        SERVED_USERS.add(message.from_user.id)

@app.on_message(filters.private)
async def track_users(client: Client, message: Message):
    if message.from_user:
        SERVED_USERS.add(message.from_user.id)

# --- Global Enforcement Handler, Anti-Link & Anti-18+ Filter ---
@app.on_message(filters.group, group=-1)
async def global_enforcer(client: Client, message: Message):
    if not message.from_user:
        return
    user_id = message.from_user.id

    # Global Ban/Mute Enforcement
    if user_id in gbanned_users:
        try:
            await client.ban_chat_member(message.chat.id, user_id)
            await message.delete()
            return
        except Exception:
            pass
    elif user_id in gmuted_users:
        try:
            await message.delete()
            return
        except Exception:
            pass

    # Check if User is Admin (Admins are bypassed from filters)
    member = await client.get_chat_member(message.chat.id, user_id)
    if member.status in [enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER]:
        return

    # 1. Anti-Link Filter
    if message.text and ("http://" in message.text or "https://" in message.text or "t.me/" in message.text):
        try:
            await message.delete()
            await message.reply_text(f"❌ [{message.from_user.first_name}](tg://user?id={user_id}) Group me links allow nahi hain!")
            return
        except Exception:
            pass

    # 2. Anti-Bad Words / Bad Speech Filter
    text_to_check = (message.text or message.caption or "").lower()
    if any(bad_word in text_to_check for bad_word in BAD_WORDS):
        try:
            await message.delete()
            warn_msg = await message.reply_text(
                f"🚫 **🚨 WARNING! [{message.from_user.first_name}](tg://user?id={user_id})**\n"
                f"Group me gandi baatein / bad words allow nahi hain! Aapka message delete kar diya gaya hai."
            )
            await asyncio.sleep(5)
            await warn_msg.delete()
            return
        except Exception:
            pass

    # 3. Anti-NSFW Spoiler / Sensitive Video Check (Media filter)
    if message.video or message.photo or message.animation:
        if message.has_media_spoiler:  # Often used for sensitive/18+ media
            try:
                await message.delete()
                await message.reply_text(f"🔞 [{message.from_user.first_name}](tg://user?id={user_id}) 18+/Sensitive media allow nahi hai!")
            except Exception:
                pass

# --- Welcome New Members (Stylish with Name, Username & User ID) ---
@app.on_message(filters.new_chat_members)
async def welcome_member(client: Client, message: Message):
    for member in message.new_chat_members:
        if member.is_bot:
            continue

        # Username check (agar username na ho toh 'N/A' dikhayega)
        username = f"@{member.username}" if member.username else "N/A"

        welcome_text = (
            "┏━━━━━━━━━━━━━━━━━━━━━━━━━━┓\n"
            "✨ **WELCOME TO THE GROUP!** ✨\n"
            "┗━━━━━━━━━━━━━━━━━━━━━━━━━━┛\n\n"
            f"👤 **NAME:** [{member.first_name}](tg://user?id={member.id})\n"
            f"🏷️ **USERNAME:** {username}\n"
            f"🆔 **USER ID:** `{member.id}`\n"
            f"🏰 **GROUP:** **{message.chat.title}**\n\n"
            "━━━━━━❖ RULES & VIBES ❖━━━━━━\n"
            "📜 **1. RESPECT ALL MEMBERS**\n"
            "🚫 **2. NO SPAM & NO BAD WORDS**\n"
            "💬 **3. STAY ACTIVE & CHILL OUT!**\n"
            "━━━━━━❖━━━━━━━━━━━━━━❖━━━━━━\n\n"
            "🌟 **DIL SE SWAGAT HAI AAPKA! HAVE A GREAT TIME HERE!** 🎉"
        )

        await message.reply_text(welcome_text, disable_web_page_preview=True)

# --- BROADCAST COMMAND SYSTEM ---
@app.on_message(filters.command(["broadcast", "bc"]))
async def broadcast_handler(client: Client, message: Message):
    # Only Owner can broadcast
    if message.from_user.id != OWNER_ID:
        return await message.reply_text("❌ **Sirf Bot Owner hi Broadcast chala sakta hai!**")

    # Broadcast message determine karein
    msg_to_send = None
    if message.reply_to_message:
        msg_to_send = message.reply_to_message
    elif len(message.command) > 1:
        text_content = message.text.split(None, 1)[1]
    else:
        return await message.reply_text(
            "📌 **BROADCAST USAGE:**\n\n"
            "1️⃣ Message par reply karke likhein: `/broadcast` (Photo, Video, Document sab jayega)\n"
            "2️⃣ Direct message likhein: `/broadcast Hello everyone!`"
        )

    status_msg = await message.reply_text("📢 **Broadcast Shuru Ho Raha Hai... Kripya Wait Karein!**")

    user_success = 0
    user_failed = 0
    chat_success = 0
    chat_failed = 0

    # 1. Private Users me Send Karein
    for u_id in list(SERVED_USERS):
        try:
            if msg_to_send:
                await msg_to_send.copy(u_id)
            else:
                await client.send_message(u_id, text_content)
            user_success += 1
            await asyncio.sleep(0.1)
        except FloodWait as e:
            await asyncio.sleep(e.value)
            if msg_to_send: await msg_to_send.copy(u_id)
            else: await client.send_message(u_id, text_content)
            user_success += 1
        except Exception:
            user_failed += 1

    # 2. Groups me Send Karein
    for c_id in list(SERVED_CHATS):
        try:
            if msg_to_send:
                await msg_to_send.copy(c_id)
            else:
                await client.send_message(c_id, text_content)
            chat_success += 1
            await asyncio.sleep(0.1)
        except FloodWait as e:
            await asyncio.sleep(e.value)
            if msg_to_send: await msg_to_send.copy(c_id)
            else: await client.send_message(c_id, text_content)
            chat_success += 1
        except Exception:
            chat_failed += 1

    save_data()
    report = (
        "✅ **BROADCAST COMPLETED SUCCESSFULLY!**\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 **Private DMs:** `{user_success}` Sent | `{user_failed}` Failed\n"
        f"🏰 **Groups:** `{chat_success}` Sent | `{chat_failed}` Failed\n"
        "━━━━━━━━━━━━━━━━━━━━━━"
    )
    await status_msg.edit_text(report)

# --- Command: /help & /start ---
@app.on_message(filters.command(["help", "start"]))
async def send_help(client: Client, message: Message):
    help_text = (
        "🤖 **Ultimate Group Admin & Tagger Bot**\n\n"
        "📌 **Tagging Commands:**\n"
        "🔹 `/utag <msg>` - Sabhi members ko 5-5 ke group me tag karega.\n"
        "🔹 `/atag <msg>` - Group admins ko 5-5 ke group me tag karega.\n"
        "🔹 `/gmtag` - Members ko Good Morning msg ke sath tag karega.\n"
        "🔹 `/gntag` - Members ko Good Night msg ke sath tag karega.\n"
        "🔹 `/cancel` - Active tagging process ko rokne ke liye.\n\n"
        "🛡️ **Moderation Commands:**\n"
        "🔹 `/warn` | `/unwarn` | `/warns` - Warning System (3 warn = Mute).\n"
        "🔹 `/ban` | `/unban` - User ko ban/unban karega.\n"
        "🔹 `/mute` | `/unmute` - User ko mute/unmute karega.\n"
        "🔹 `/gban` | `/gunban` - Global Ban System.\n"
        "🔹 `/gmute` | `/gunmute` - Global Mute System.\n"
        "🔹 `/lock` | `/unlock` - Chat lock ya open karne ke liye.\n\n"
        "🛡️ **Auto Safety Filters:**\n"
        "⛔ Auto Anti-Link Filter\n"
        "⛔ Auto Bad Words & Bad Speech Deletion\n"
        "⛔ Auto 18+ / Sensitive Media Filter\n\n"
        "⚡ **Utility & Fun Commands:**\n"
        "🔹 `/ping` - Bot ki response speed check karein.\n"
        "🔹 `/dice` - Group me dice roll karein.\n"
        "🔹 `/slot` - Slot machine game khelein."
    )
    await message.reply_text(help_text)

# --- Utility & Fun Commands ---

@app.on_message(filters.command("ping"))
async def ping_cmd(client: Client, message: Message):
    start = time.time()
    msg = await message.reply_text("⚡ **Pinging...**")
    end = time.time()
    ms = round((end - start) * 1000, 2)
    await msg.edit_text(f"🚀 **Pong!**\n📶 **Bot Speed:** `{ms}ms`")

@app.on_message(filters.command("dice"))
async def roll_dice(client: Client, message: Message):
    await client.send_dice(message.chat.id, "🎲")

@app.on_message(filters.command("slot"))
async def slot_machine(client: Client, message: Message):
    await client.send_dice(message.chat.id, "🎰")

# --- TAGGING COMMANDS ---

@app.on_message(filters.command("cancel") & filters.group)
async def cancel_tagging(client: Client, message: Message):
    if not await is_admin(client, message): return
    chat_id = message.chat.id
    if chat_id in active_tags and active_tags[chat_id]:
        active_tags[chat_id] = False
        await message.reply_text("⛔ **Tagging process ko successfully rok diya gaya hai!**")
    else:
        await message.reply_text("❌ Koi active tagging process nahi chal raha hai.")

@app.on_message(filters.command("utag") & filters.group)
async def tag_all_users(client: Client, message: Message):
    if not await is_admin(client, message): return
    chat_id = message.chat.id

    if len(message.command) < 2:
        await message.reply_text("❌ Kripya koi message likhein!\nExample: `/utag Suno sab log`")
        return

    custom_text = message.text.split(None, 1)[1]
    active_tags[chat_id] = True
    await message.reply_text("🚀 **User tagging process shuru...**")

    usr_mentions = []
    try:
        async for member in client.get_chat_members(chat_id):
            if is_cancelled(chat_id): break
            if member.user.is_bot or member.user.is_deleted: continue

            usr_mentions.append(f"[{member.user.first_name}](tg://user?id={member.user.id})")

            if len(usr_mentions) == 5:
                try:
                    await client.send_message(chat_id, f"📢 **{custom_text}**\n\n" + " ".join(usr_mentions))
                    usr_mentions = []
                    await asyncio.sleep(2)
                except FloodWait as e:
                    await asyncio.sleep(e.value)

        if usr_mentions and not is_cancelled(chat_id):
            await client.send_message(chat_id, f"📢 **{custom_text}**\n\n" + " ".join(usr_mentions))
    except Exception as e:
        await message.reply_text(f"❌ Tagging me issue aaya: {e}")

    active_tags[chat_id] = False

@app.on_message(filters.command("atag") & filters.group)
async def tag_all_admins(client: Client, message: Message):
    if not await is_admin(client, message): return
    chat_id = message.chat.id

    if len(message.command) < 2:
        await message.reply_text("❌ Kripya koi message likhein!\nExample: `/atag Admin Meeting`")
        return

    custom_text = message.text.split(None, 1)[1]
    active_tags[chat_id] = True
    await message.reply_text("⚡ **Admin tagging shuru...**")

    admin_mentions = []
    try:
        async for admin in client.get_chat_members(chat_id, filter=enums.ChatMembersFilter.ADMINISTRATORS):
            if is_cancelled(chat_id): break
            if admin.user.is_bot: continue

            admin_mentions.append(f"[{admin.user.first_name}](tg://user?id={admin.user.id})")

            if len(admin_mentions) == 5:
                try:
                    await client.send_message(chat_id, f"🚨 **ADMIN ALERT:** {custom_text}\n\n" + " ".join(admin_mentions))
                    admin_mentions = []
                    await asyncio.sleep(2)
                except FloodWait as e:
                    await asyncio.sleep(e.value)

        if admin_mentions and not is_cancelled(chat_id):
            await client.send_message(chat_id, f"🚨 **ADMIN ALERT:** {custom_text}\n\n" + " ".join(admin_mentions))
    except Exception as e:
        await message.reply_text(f"❌ Admin tagging me issue aaya: {e}")

    active_tags[chat_id] = False

@app.on_message(filters.command("gmtag") & filters.group)
async def gm_tagger(client: Client, message: Message):
    if not await is_admin(client, message): return
    chat_id = message.chat.id
    active_tags[chat_id] = True
    await message.reply_text("🌅 **Good Morning tagging shuru...**")

    try:
        async for member in client.get_chat_members(chat_id):
            if is_cancelled(chat_id): break
            if member.user.is_bot or member.user.is_deleted: continue

            msg = random.choice(GM_MESSAGES)
            mention = f"[{member.user.first_name}](tg://user?id={member.user.id})"

            try:
                await client.send_message(chat_id, f"{msg}\n👉 {mention}")
                await asyncio.sleep(2)
            except FloodWait as e:
                await asyncio.sleep(e.value)
    except Exception as e:
        await message.reply_text(f"❌ Error during GM tagging: {e}")

    active_tags[chat_id] = False

@app.on_message(filters.command("gntag") & filters.group)
async def gn_tagger(client: Client, message: Message):
    if not await is_admin(client, message): return
    chat_id = message.chat.id
    active_tags[chat_id] = True
    await message.reply_text("🌙 **Good Night tagging shuru...**")

    try:
        async for member in client.get_chat_members(chat_id):
            if is_cancelled(chat_id): break
            if member.user.is_bot or member.user.is_deleted: continue

            msg = random.choice(GN_MESSAGES)
            mention = f"[{member.user.first_name}](tg://user?id={member.user.id})"

            try:
                await client.send_message(chat_id, f"{msg}\n👉 {mention}")
                await asyncio.sleep(2)
            except FloodWait as e:
                await asyncio.sleep(e.value)
    except Exception as e:
        await message.reply_text(f"❌ Error during GN tagging: {e}")

    active_tags[chat_id] = False

# --- WARNING SYSTEM ---

@app.on_message(filters.command("warn") & filters.group)
async def warn_user(client: Client, message: Message):
    if not await is_admin(client, message): return
    user_id = await get_target_user(client, message)
    if not user_id:
        return await message.reply_text("❌ Reply karein ya Username/ID specify karein!")

    chat_id = message.chat.id
    if chat_id not in warns_db: warns_db[chat_id] = {}

    current_warns = warns_db[chat_id].get(user_id, 0) + 1
    warns_db[chat_id][user_id] = current_warns
    save_data()

    if current_warns >= 3:
        try:
            await client.restrict_chat_member(chat_id, user_id, ChatPermissions())
            warns_db[chat_id][user_id] = 0
            save_data()
            await message.reply_text(f"🚨 **User `{user_id}` ko 3 warnings milne par MUTE kar diya gaya hai!**")
        except Exception as e:
            await message.reply_text(f"❌ Mute karne me issue: {e}")
    else:
        await message.reply_text(f"⚠️ **User `{user_id}` ko warning di gayi! ({current_warns}/3)**")

@app.on_message(filters.command("unwarn") & filters.group)
async def unwarn_user(client: Client, message: Message):
    if not await is_admin(client, message): return
    user_id = await get_target_user(client, message)
    if not user_id: return await message.reply_text("❌ User specify karein!")

    chat_id = message.chat.id
    if chat_id in warns_db and user_id in warns_db[chat_id]:
        warns_db[chat_id][user_id] = max(0, warns_db[chat_id][user_id] - 1)
        save_data()
        await message.reply_text(f"✅ **User `{user_id}` ki 1 warning kam kar di gayi! ({warns_db[chat_id][user_id]}/3)**")
    else:
        await message.reply_text("❌ Iss user ki koi warning nahi hai.")

@app.on_message(filters.command("warns") & filters.group)
async def check_warns(client: Client, message: Message):
    user_id = await get_target_user(client, message) or message.from_user.id
    chat_id = message.chat.id
    count = warns_db.get(chat_id, {}).get(user_id, 0)
    await message.reply_text(f"📊 **User `{user_id}` ke paas `{count}/3` warnings hain.**")

# --- MODERATION COMMANDS ---

@app.on_message(filters.command("ban") & filters.group)
async def ban_user(client: Client, message: Message):
    if not await is_admin(client, message): return
    user_id = await get_target_user(client, message)
    if not user_id:
        return await message.reply_text("❌ Reply karein ya Username/ID specify karein!")

    try:
        await client.ban_chat_member(message.chat.id, user_id)
        await message.reply_text(f"🔨 **User `{user_id}` ko ban kar diya gaya hai!**")
    except Exception as e:
        await message.reply_text(f"❌ Error: {e}")

@app.on_message(filters.command("unban") & filters.group)
async def unban_user(client: Client, message: Message):
    if not await is_admin(client, message): return
    user_id = await get_target_user(client, message)
    if not user_id:
        return await message.reply_text("❌ Username/ID ya reply specify karein!")

    try:
        await client.unban_chat_member(message.chat.id, user_id)
        await message.reply_text(f"✅ **User `{user_id}` ko unban kar diya gaya hai!**")
    except Exception as e:
        await message.reply_text(f"❌ Error: {e}")

@app.on_message(filters.command("mute") & filters.group)
async def mute_user(client: Client, message: Message):
    if not await is_admin(client, message): return
    user_id = await get_target_user(client, message)
    if not user_id:
        return await message.reply_text("❌ Reply karein ya user specify karein!")

    try:
        await client.restrict_chat_member(message.chat.id, user_id, ChatPermissions())
        await message.reply_text(f"🔇 **User `{user_id}` ko mute kar diya gaya hai!**")
    except Exception as e:
        await message.reply_text(f"❌ Error: {e}")

@app.on_message(filters.command("unmute") & filters.group)
async def unmute_user(client: Client, message: Message):
    if not await is_admin(client, message): return
    user_id = await get_target_user(client, message)
    if not user_id:
        return await message.reply_text("❌ Reply karein ya user specify karein!")

    try:
        await client.restrict_chat_member(message.chat.id, user_id, ChatPermissions(can_send_messages=True))
        await message.reply_text(f"🔊 **User `{user_id}` ko unmute kar diya gaya hai!**")
    except Exception as e:
        await message.reply_text(f"❌ Error: {e}")

# --- GLOBAL MODERATION COMMANDS ---

@app.on_message(filters.command("gban") & filters.group)
async def gban_user(client: Client, message: Message):
    if not await is_admin(client, message): return
    user_id = await get_target_user(client, message)
    if not user_id: return await message.reply_text("❌ User specify karein!")

    gbanned_users.add(user_id)
    save_data()
    try:
        await client.ban_chat_member(message.chat.id, user_id)
    except Exception:
        pass
    await message.reply_text(f"🚨 **User `{user_id}` Global Ban List me add ho gaya hai!**")

@app.on_message(filters.command("gunban") & filters.group)
async def gunban_user(client: Client, message: Message):
    if not await is_admin(client, message): return
    user_id = await get_target_user(client, message)
    if not user_id: return await message.reply_text("❌ User specify karein!")

    gbanned_users.discard(user_id)
    save_data()
    try:
        await client.unban_chat_member(message.chat.id, user_id)
    except Exception:
        pass
    await message.reply_text(f"✅ **User `{user_id}` ko GBan se hata diya gaya hai!**")

@app.on_message(filters.command("gmute") & filters.group)
async def gmute_user(client: Client, message: Message):
    if not await is_admin(client, message): return
    user_id = await get_target_user(client, message)
    if not user_id: return await message.reply_text("❌ User specify karein!")

    gmuted_users.add(user_id)
    save_data()
    await message.reply_text(f"🔇 **User `{user_id}` Global Mute ho gaya hai!**")

@app.on_message(filters.command("gunmute") & filters.group)
async def gunmute_user(client: Client, message: Message):
    if not await is_admin(client, message): return
    user_id = await get_target_user(client, message)
    if not user_id: return await message.reply_text("❌ User specify karein!")

    gmuted_users.discard(user_id)
    save_data()
    await message.reply_text(f"🔊 **User `{user_id}` GMute se bahar ho gaya hai!**")

# --- LOCK & UNLOCK COMMANDS ---

@app.on_message(filters.command("lock") & filters.group)
async def lock_chat(client: Client, message: Message):
    if not await is_admin(client, message): return
    try:
        await client.set_chat_permissions(message.chat.id, ChatPermissions())
        await message.reply_text("🔒 **Group chat locked! Ab sirf admins message bhej sakte hain.**")
    except Exception as e:
        await message.reply_text(f"❌ Lock karne me issue aaya: {e}")

@app.on_message(filters.command("unlock") & filters.group)
async def unlock_chat(client: Client, message: Message):
    if not await is_admin(client, message): return
    try:
        await client.set_chat_permissions(message.chat.id, ChatPermissions(can_send_messages=True))
        await message.reply_text("🔓 **Group chat unlocked! Ab sabhi log chat kar sakte hain.**")
    except Exception as e:
        await message.reply_text(f"❌ Unlock karne me issue aaya: {e}")

# --- Render health server (free web service soyi na rahe, UptimeRobot isko ping karega) ---
# --- + /members endpoint: Anya (Cloudflare Worker) live full member list yahi se leti hai ---
health_app = web.Application()
health_app.router.add_get("/", lambda request: web.Response(text="nox-tagger alive"))


async def members_endpoint(request):
    api_key = os.environ.get("MEMBER_API_KEY", "")
    if not api_key or request.query.get("key", "") != api_key:
        return web.json_response({"error": "forbidden"}, status=403)
    try:
        chat_id = int(request.query.get("chat_id", "0"))
    except ValueError:
        return web.json_response({"error": "bad chat_id"}, status=400)
    try:
        limit = min(int(request.query.get("limit", "400")), 1000)
    except ValueError:
        limit = 400
    admins_only = request.query.get("admins") == "1"
    out = []
    try:
        if admins_only:
            it = app.get_chat_members(chat_id, filter=enums.ChatMembersFilter.ADMINISTRATORS)
        else:
            it = app.get_chat_members(chat_id)
        async for m in it:
            u = m.user
            if not u or u.is_bot or u.is_deleted:
                continue
            out.append({"id": u.id, "first_name": u.first_name or "user"})
            if len(out) >= limit:
                break
        return web.json_response(out)
    except Exception as e:
        return web.json_response({"error": str(e)[:200]}, status=502)


health_app.router.add_get("/members", members_endpoint)


async def main():
    load_data()
    runner = web.AppRunner(health_app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", int(os.environ.get("PORT", "10000"))).start()
    await app.start()
    print("Bot Successfully Started!")
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(main())
