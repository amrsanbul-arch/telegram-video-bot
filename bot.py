import os
import asyncio
import yt_dlp
import re
import hashlib
import uuid
import tempfile
import base64

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)

from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes
)

BOT_TOKEN = os.environ.get(
    "BOT_TOKEN",
    "8855988682:AAG7cLR0rpMUPGthBCcf-Ky_JwPIO1urH7I"
)

DOWNLOAD_DIR = os.path.expanduser("~/videobot/downloads")

COOKIES_BASE64 = os.environ.get("COOKIES_BASE64", "")

if COOKIES_BASE64:
    _tmp = tempfile.NamedTemporaryFile(mode='wb', suffix='.txt', delete=False)
    _tmp.write(base64.b64decode(COOKIES_BASE64))
    _tmp.close()
    COOKIES_FILE = _tmp.name
else:
    COOKIES_FILE = os.path.expanduser("~/videobot/cookies.txt")

os.makedirs(DOWNLOAD_DIR, exist_ok=True)

MAX_PARALLEL = 2
TIMEOUT = 90


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
    special_chars = r'[_*`\[\]()\~>#+\-=|{}.!]'
    return re.sub(special_chars, '', str(text))


def sanitize_filename(name):
    return re.sub(r'[\\/*?:"<>|]', "", str(name))


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("المواقع المدعومة", callback_data="sites")]]
    
    welcome_text = """
◤━━━━━━━━━━━━━━━━━━━━━◥
    SYSTEM READY
◣━━━━━━━━━━━━━━━━━━━━━◢

SEND VIDEO LINK
START DOWNLOAD NOW
    """
    await update.message.reply_text(welcome_text, reply_markup=InlineKeyboardMarkup(keyboard))


async def show_sites(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    sites_text = """
◤━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━◥
                                         SUPPORTED PLATFORMS
◣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━◢

YouTube • TikTok • Instagram • Twitter/X • Facebook + 1800+ Platforms
    """
    await query.message.reply_text(sites_text)


async def download_single(url, quality, chat_id, context, status_msg=None):
    try:
        url = clean_youtube_url(url)
        unique_id = str(uuid.uuid4())[:8]
        output_template = f'{DOWNLOAD_DIR}/%(title)s_{unique_id}.%(ext)s'

        # إعدادات الجودة
        if quality == "1080":
            fmt = 'bestvideo[height<=1080][filesize<50M]+bestaudio/best[height<=1080][filesize<50M]/best'
        elif quality == "720":
            fmt = 'bestvideo[height<=720][filesize<50M]+bestaudio/best[height<=720][filesize<50M]/best'
        elif quality == "480":
            fmt = 'bestvideo[height<=480][filesize<50M]+bestaudio/best[height<=480][filesize<50M]/best'
        elif quality == "360":
            fmt = 'bestvideo[height<=360][filesize<50M]+bestaudio/best[height<=360][filesize<50M]/best'
        elif quality == "best":
            fmt = 'best[filesize<50M]/bestvideo[filesize<50M]+bestaudio/best'
        else:
            fmt = 'best[filesize<50M]/best'

        ydl_opts = {
            'format': fmt,
            'outtmpl': output_template,
            'quiet': True,
            'noplaylist': True,
            'merge_output_format': 'mp4',
            'retries': 5,
            'fragment_retries': 5,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            },
        }

        if os.path.exists(COOKIES_FILE):
            ydl_opts["cookiefile"] = COOKIES_FILE

        if status_msg:
            await status_msg.edit_text("▹▹▹ DOWNLOADING ▹▹▹")

        loop = asyncio.get_running_loop()

        def do_download():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)
                return filename, info

        filename, info = await asyncio.wait_for(
            loop.run_in_executor(None, do_download), timeout=TIMEOUT
        )

        file_size = os.path.getsize(filename) / (1024 * 1024)
        if file_size > 50:
            if status_msg:
                await status_msg.edit_text(f"❌ SIZE LIMIT ({file_size:.1f}MB)")
            os.remove(filename)
            return False

        title = sanitize_filename(info.get('title', 'Unknown'))[:60]

        if status_msg:
            await status_msg.edit_text(f"▹▹▹ UPLOADING {file_size:.1f}MB ▹▹▹")

        with open(filename, 'rb') as f:
            await context.bot.send_video(
                chat_id=chat_id,
                video=f,
                caption=title,
                supports_streaming=True
            )

        if os.path.exists(filename):
            os.remove(filename)

        if status_msg:
            await status_msg.edit_text("✅ COMPLETED")
            await asyncio.sleep(2)
            await status_msg.delete()

        return True

    except Exception as e:
        print(f"Error: {str(e)}")
        if status_msg:
            await status_msg.edit_text(f"❌ ERROR: {str(e)[:100]}")
        return False


async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    urls = [line.strip() for line in text.splitlines() if line.strip().startswith(("http://", "https://"))]

    if not urls:
        await update.message.reply_text("❌ INVALID URL - Send correct link")
        return

    if len(urls) == 1:
        url = clean_youtube_url(urls[0])
        msg = await update.message.reply_text("▹▹▹ SCANNING ▹▹▹")

        try:
            loop = asyncio.get_running_loop()

            def get_info():
                ydl_params = {
                    'quiet': True,
                    'noplaylist': True,
                    'no_warnings': True,
                    'http_headers': {'User-Agent': 'Mozilla/5.0'}
                }
                if os.path.exists(COOKIES_FILE):
                    ydl_params["cookiefile"] = COOKIES_FILE
                with yt_dlp.YoutubeDL(ydl_params) as ydl:
                    return ydl.extract_info(url, download=False)

            info = await asyncio.wait_for(loop.run_in_executor(None, get_info), timeout=20)

            title = clean_markdown(info.get('title', 'VIDEO')[:50])
            duration = info.get('duration', 0)
            mins = int(duration // 60) if duration else 0
            secs = int(duration % 60) if duration else 0
            duration_str = f"{mins}:{secs:02d}"

            url_hash = hashlib.md5(url.encode()).hexdigest()[:10]
            context.user_data[url_hash] = url

            result_text = f"""
◤━━━━━━━━━━━━━━━━━━━━━◥
    ANALYSIS COMPLETE
◣━━━━━━━━━━━━━━━━━━━━━◢

TITLE: {title}
DURATION: {duration_str}

CHOOSE QUALITY:
            """

            keyboard = [
                [
                    InlineKeyboardButton("1080p Full HD", callback_data=f"dl|1080|{url_hash}"),
                    InlineKeyboardButton("720p HD", callback_data=f"dl|720|{url_hash}")
                ],
                [
                    InlineKeyboardButton("480p", callback_data=f"dl|480|{url_hash}"),
                    InlineKeyboardButton("360p SD", callback_data=f"dl|360|{url_hash}")
                ],
                [
                    InlineKeyboardButton("Best Quality", callback_data=f"dl|best|{url_hash}")
                ]
            ]

            await msg.edit_text(result_text, reply_markup=InlineKeyboardMarkup(keyboard))

        except Exception as e:
            await msg.edit_text(f"❌ ERROR: {str(e)[:100]}")

    else:
        await update.message.reply_text("Multiple links support coming soon.")


async def download_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    try:
        _, quality, url_hash = query.data.split("|", 2)
        url = context.user_data.get(url_hash)

        if not url:
            await query.message.edit_text("❌ Link not found")
            return

        await query.message.edit_text("▹▹▹ DOWNLOADING ▹▹▹")
        await download_single(url, quality, query.message.chat.id, context, query.message)
        context.user_data.pop(url_hash, None)

    except Exception as e:
        await query.message.edit_text(f"❌ ERROR: {str(e)[:100]}")


def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(show_sites, pattern="^sites$"))
    app.add_handler(CallbackQueryHandler(download_handler, pattern=r"^dl\|"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))

    print("🤖 BOT IS RUNNING...")
    app.run_polling()


if __name__ == "__main__":
    main()
