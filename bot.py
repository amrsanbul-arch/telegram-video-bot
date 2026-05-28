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
BOT_TOKEN = "8855988682:AAG7cLR0rpMUPGthBCcf-Ky_JwPIO1urH7I"

# ================= الإعدادات =================
DOWNLOAD_DIR = "/data/data/com.termux/files/home/telegram-video-bot/downloads"
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

▹▹▹▹▹▹▹▹▹▹▹▹▹▹▹▹▹▹

STATUS: ONLINE
BOT: ACTIVATED
READY: YES

▹▹▹▹▹▹▹▹▹▹▹▹▹▹▹▹▹▹

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

▹▹▹▹▹▹▹▹▹▹▹▹▹▹▹▹▹▹▹▹▹▹▹▹

100+ PLATFORMS SUPPORTED
    """
    await query.message.reply_text(sites_text)

async def download_single(url, quality, chat_id, context, status_msg=None):
    try:
        url = clean_youtube_url(url)

        if quality == "best":
            fmt = 'best[filesize<50M]/bestvideo[filesize<50M]+bestaudio/best'
        elif quality == "720":
            fmt = 'bestvideo[height<=720][filesize<50M]+bestaudio/best[height<=720][filesize<50M]/best'
        elif quality == "360":
            fmt = 'bestvideo[height<=360][filesize<50M]+bestaudio/best[height<=360][filesize<50M]/best'
        elif quality == "audio":
            fmt = 'bestaudio/best'
        else:
            fmt = 'best[filesize<50M]/best'

        unique_id = str(uuid.uuid4())[:8]

        ydl_opts = {
            'format': fmt,
            'outtmpl': f'{DOWNLOAD_DIR}/%(title)s_{unique_id}.%(ext)s',
            'quiet': True,
            'noplaylist': True,
            'ignoreerrors': False,
            'no_warnings': True,
            'extract_flat': False,
            'merge_output_format': 'mp4',
            'retries': 5,
            'fragment_retries': 5,
            'cookiefile': COOKIES_FILE,  # 🔑 الكوكيز رجعت
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            },
        }

        if quality == "audio":
            ydl_opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '320',
            }]

        loop = asyncio.get_running_loop()

        def do_download():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                if not info:
                    raise Exception("Failed to extract media")
                filename = ydl.prepare_filename(info)
                if quality == "audio":
                    filename = filename.rsplit('.', 1)[0] + '.mp3'
                else:
                    if not os.path.exists(filename):
                        for f in os.listdir(DOWNLOAD_DIR):
                            if unique_id in f and f.endswith('.mp4'):
                                filename = os.path.join(DOWNLOAD_DIR, f)
                                break
                title = sanitize_filename(info.get('title', 'VIDEO'))[:40]
                return filename, title

        if status_msg:
            try:
                await status_msg.edit_text("DOWNLOADING...")
            except Exception:
                pass

        try:
            filename, title = await asyncio.wait_for(loop.run_in_executor(None, do_download), timeout=TIMEOUT)
        except asyncio.TimeoutError:
            if status_msg:
                try:
                    await status_msg.edit_text("TIMEOUT ERROR")
                except Exception:
                    pass
            return False

        if not os.path.exists(filename):
            for f in os.listdir(DOWNLOAD_DIR):
                if f.endswith(('.mp4', '.mp3')) and unique_id in f:
                    filename = os.path.join(DOWNLOAD_DIR, f)
                    break
            else:
                if status_msg:
                    try:
                        await status_msg.edit_text("FILE NOT FOUND")
                    except Exception:
                        pass
                return False

        file_size = os.path.getsize(filename) / (1024 * 1024)
        if file_size > 50:
            if status_msg:
                try:
                    await status_msg.edit_text(f"SIZE LIMIT {file_size:.1f}MB/50MB")
                except Exception:
                    pass
            if os.path.exists(filename):
                os.remove(filename)
            return False

        if status_msg:
            try:
                await status_msg.edit_text(f"UPLOADING {file_size:.1f}MB...")
            except Exception:
                pass

        with open(filename, 'rb') as f:
            if quality == "audio":
                await context.bot.send_audio(chat_id=chat_id, audio=f, title=title)
            else:
                await context.bot.send_video(chat_id=chat_id, video=f, caption=title)

        if os.path.exists(filename):
            os.remove(filename)

        if status_msg:
            try:
                await status_msg.edit_text("COMPLETED SUCCESSFULLY")
                await status_msg.delete()
            except Exception:
                pass

        return True

    except Exception as e:
        error_msg = str(e)
        if status_msg:
            try:
                await status_msg.edit_text(f"ERROR: {error_msg[:100]}")
            except Exception:
                pass
        return False

async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    urls = [line.strip() for line in text.splitlines() if line.strip().startswith(("http://", "https://"))]

    if not urls:
        await update.message.reply_text("INVALID URL - Send correct link")
        return

    if len(urls) == 1:
        url = clean_youtube_url(urls[0])
        msg = await update.message.reply_text("SCANNING VIDEO...")

        try:
            loop = asyncio.get_running_loop()

            def get_info():
                ydl_params = {
                    'quiet': True,
                    'noplaylist': True,
                    'no_warnings': True,
                    'ignoreerrors': False,
                    'cookiefile': COOKIES_FILE,  # 🔑 الكوكيز هنا برضه
                    'http_headers': {'User-Agent': 'Mozilla/5.0'},
                }
                with yt_dlp.YoutubeDL(ydl_params) as ydl:
                    return ydl.extract_info(url, download=False)

            info = await asyncio.wait_for(loop.run_in_executor(None, get_info), timeout=15)

            if not info:
                raise Exception("Failed to fetch info")

            title = clean_markdown(info.get('title', 'VIDEO')[:50])
            duration = info.get('duration', 0)
            if duration and isinstance(duration, (int, float)):
                mins = int(duration // 60)
                secs = int(duration % 60)
                duration_str = f"{mins}:{secs:02d}"
            else:
                duration_str = "UNKNOWN"

            uploader = clean_markdown(info.get('uploader', 'UNKNOWN'))
            views = info.get('view_count', 0)
            likes = info.get('like_count', 0)

            views_str = f"{int(float(views)):,}" if views else "N/A"
            likes_str = f"{int(float(likes)):,}" if likes else "N/A"

            url_hash = hashlib.md5(url.encode()).hexdigest()[:10]
            context.user_data[url_hash] = url

            result_text = f"""
◤━━━━━━━━━━━━━━━━━━━━━◥
     ANALYSIS COMPLETE
◣━━━━━━━━━━━━━━━━━━━━━◢

▹▹▹▹▹▹▹▹▹▹▹▹▹▹▹▹▹▹

TITLE: {title}
DURATION: {duration_str}
UPLOADER: {uploader}
VIEWS: {views_str}
LIKES: {likes_str}
STATUS: READY

▹▹▹▹▹▹▹▹▹▹▹▹▹▹▹▹▹▹

DOWNLOAD OPTIONS
            """

            keyboard = [
                [
                    InlineKeyboardButton("BEST QUALITY", callback_data=f"dl|best|{url_hash}"),
                    InlineKeyboardButton("720p HD", callback_data=f"dl|720|{url_hash}")
                ],
                [
                    InlineKeyboardButton("360p SD", callback_data=f"dl|360|{url_hash}"),
                    InlineKeyboardButton("AUDIO MP3", callback_data=f"dl|audio|{url_hash}")
                ]
            ]

            await msg.edit_text(result_text, reply_markup=InlineKeyboardMarkup(keyboard))

        except asyncio.TimeoutError:
            try:
                await msg.edit_text("TIMEOUT - Link is too slow, try again")
            except Exception:
                pass
        except Exception as e:
            try:
                await msg.edit_text(f"ERROR: {str(e)[:100]}")
            except Exception:
                pass
        return

    if len(urls) > MAX_PARALLEL:
        await update.message.reply_text(f"LIMIT - First {MAX_PARALLEL} links only")
        urls = urls[:MAX_PARALLEL]

    summary_msg = await update.message.reply_text(f"PARALLEL MODE - {len(urls)} links")
    status_msgs = []

    for i, url in enumerate(urls):
        msg = await update.message.reply_text(f"[{i + 1}] INITIALIZING...")
        status_msgs.append(msg)

    tasks = [download_single(url, "best", update.effective_chat.id, context, status_msgs[i]) for i, url in enumerate(urls)]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    success = sum(1 for r in results if r is True)
    failed = len(urls) - success

    try:
        await summary_msg.edit_text(f"COMPLETE - Success: {success} | Failed: {failed}")
    except Exception:
        pass

async def download_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    try:
        _, quality, url_hash = query.data.split("|", 2)
        url = context.user_data.get(url_hash)

        if not url:
            try:
                await query.message.edit_text("ERROR - Link not found")
            except Exception:
                pass
            return

        try:
            await query.message.edit_text("DOWNLOADING...")
        except Exception:
            pass

        await download_single(url, quality, query.message.chat.id, context, query.message)
        context.user_data.pop(url_hash, None)

    except Exception as e:
        try:
            await query.message.edit_text(f"ERROR: {str(e)[:100]}")
        except Exception:
            pass

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
