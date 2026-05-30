import os
import asyncio
import yt_dlp
import re
import hashlib
import uuid
import tempfile

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# ================= التوكن =================
BOT_TOKEN = os.getenv("BOT_TOKEN")
print("DEBUG BOT_TOKEN:", BOT_TOKEN)  # للتأكد من قراءة التوكن في الـ Logs

# ================= الإعدادات =================
DOWNLOAD_DIR = "/home/amrsanbul/downloads"
COOKIES_CONTENT = os.environ.get("COOKIES_CONTENT", "")

if COOKIES_CONTENT:
    _tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False)
    _tmp.write(COOKIES_CONTENT)
    _tmp.close()
    COOKIES_FILE = _tmp.name
else:
    COOKIES_FILE = os.path.join(os.path.dirname(__file__), "cookies.txt")

os.makedirs(DOWNLOAD_DIR, exist_ok=True)

MAX_PARALLEL = 2
TIMEOUT = 180

# ================= دوال مساعدة =================
def clean_youtube_url(url):
    if "/shorts/" in url:
        match = re.search(r'/shorts/([a-zA-Z0-9_-]+)', url)
        if match:
            url = f"https://www.youtube.com/watch?v={match.group(1)}"
    if "?" in url:
        match = re.search(r'v=([a-zA-Z0-9_-]+)', url)
        if match:
            url = f"https://www.youtube.com/watch?v={match.group(1)}"
        else:
            url = url.split('?')[0]
    return url

def clean_markdown(text):
    special_chars = r'[_*`\[\]()~>#+\-=|{}.!]'
    return re.sub(special_chars, '', str(text))

def sanitize_filename(name):
    return re.sub(r'[\\/*?:"<>|]', "", str(name))

# ================= أوامر البوت =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("المواقع المدعومة", callback_data="sites")]]
    welcome_text = """
◤━━━━━━━━━━━━━━━━━━━━━◥
    SYSTEM READY
◣━━━━━━━━━━━━━━━━━━━━━◢

STATUS: ONLINE
BOT: ACTIVATED
READY: YES

SEND VIDEO LINK
START DOWNLOAD NOW

POWERED BY AI
    """
    await update.message.reply_text(welcome_text, reply_markup=InlineKeyboardMarkup(keyboard))

async def show_sites(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    sites_text = """
◤━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━◥
        SUPPORTED PLATFORMS
◣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━◢

SOCIAL & VIDEO:
YouTube - TikTok - Instagram
Facebook - Twitter - Snapchat

MUSIC & AUDIO:
SoundCloud - Spotify - Anghami
Apple Music - Deezer

LIVE STREAMING:
Twitch - Kick - Rumble

100+ PLATFORMS SUPPORTED
    """
    await query.message.reply_text(sites_text)

# (باقي الدوال زي ما هي من الكود الأصلي: download_single, handle_url, download_handler)

# ================= تشغيل البوت =================
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(show_sites, pattern="^sites$"))
    app.add_handler(CallbackQueryHandler(download_handler, pattern=r"^dl\|"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))
    print("BOT IS RUNNING!")
    app.run_polling()

if __name__ == "__main__":
    main()
