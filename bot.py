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

# ================= تحميل فيديو واحد =================
async def download_single(url, quality, chat_id, context, status_msg=None):
    try:
        url = clean_youtube_url(url)
        fmt = 'best[filesize<50M]/best'
        if quality == "720":
            fmt = 'bestvideo[height<=720][filesize<50M]+bestaudio/best'
        elif quality == "360":
            fmt = 'bestvideo[height<=360][filesize<50M]+bestaudio/best'
        elif quality == "audio":
            fmt = 'bestaudio/best'

        unique_id = str(uuid.uuid4())[:8]
        ydl_opts = {
            'format': fmt,
            'outtmpl': f'{DOWNLOAD_DIR}/%(title)s_{unique_id}.%(ext)s',
            'quiet': True,
            'cookiefile': COOKIES_FILE,
        }

        loop = asyncio.get_running_loop()
        def do_download():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)
                return filename, info.get('title', 'VIDEO')

        filename, title = await asyncio.wait_for(loop.run_in_executor(None, do_download), timeout=TIMEOUT)

        with open(filename, 'rb') as f:
            if quality == "audio":
                await context.bot.send_audio(chat_id=chat_id, audio=f, title=title)
            else:
                await context.bot.send_video(chat_id=chat_id, video=f, caption=title)

        os.remove(filename)
        return True

    except Exception as e:
        if status_msg:
            await status_msg.edit_text(f"ERROR: {str(e)[:100]}")
        return False

# ================= التعامل مع الروابط =================
async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    urls = [line for line in text.splitlines() if line.startswith(("http://", "https://"))]

    if not urls:
        await update.message.reply_text("INVALID URL - Send correct link")
        return

    msg = await update.message.reply_text("SCANNING VIDEO...")
    await msg.edit_text("تم استلام الرابط وجاري التحميل...")

# ================= تحميل من زرار الكيبورد =================
async def download_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    try:
        _, quality, url_hash = query.data.split("|", 2)
        url = context.user_data.get(url_hash)

        if not url:
            await query.message.edit_text("ERROR - Link not found")
            return

        await query.message.edit_text("DOWNLOADING...")
        await download_single(url, quality, query.message.chat.id, context, query.message)
        context.user_data.pop(url_hash, None)

    except Exception as e:
        await query.message.edit_text(f"ERROR: {str(e)[:100]}")

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
