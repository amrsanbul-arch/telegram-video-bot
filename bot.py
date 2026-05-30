import os
import asyncio
import yt_dlp
import re
import hashlib
import uuid
import tempfile
import aiohttp

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# ================= TOKEN =================
BOT_TOKEN = "8855988682:AAE-sjgsEUYVptZpD9ryE0Afw_DqwT9umsk"

# ================= SETTINGS =================
DOWNLOAD_DIR = "/tmp/videobot_downloads"
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
TIMEOUT = 300

# ================= HELPERS =================
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

# ================= BOT COMMANDS =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("Supported Sites", callback_data="sites")]]
    welcome_text = """
SYSTEM READY

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
SUPPORTED PLATFORMS

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

async def download_single(url, quality, chat_id, context, status_msg=None):
    try:
        url = clean_youtube_url(url)

        ydl_opts = {
            'quiet': True,
            'noplaylist': True,
            'ignoreerrors': False,
            'no_warnings': True,
            'cookiefile': COOKIES_FILE,
            'socket_timeout': 30,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36'
            },
        }

        loop = asyncio.get_running_loop()

        def get_url():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                formats = info.get('formats', [])
                for f in formats:
                    if f.get('ext') == 'mp4' and f.get('vcodec') != 'none':
                        return f.get('url'), info.get('title', 'VIDEO')
                return None, info.get('title', 'VIDEO')

        if status_msg:
            await status_msg.edit_text("Getting video URL...")

        video_url, title = await asyncio.wait_for(loop.run_in_executor(None, get_url), timeout=TIMEOUT)

        if not video_url:
            await status_msg.edit_text("No video URL found")
            return False

        async with aiohttp.ClientSession() as session:
            async with session.get(video_url) as resp:
                if resp.status != 200:
                    await status_msg.edit_text("Failed to download video")
                    return False
                
                file_size = int(resp.headers.get('content-length', 0)) / (1024 * 1024)
                if file_size > 50:
                    await status_msg.edit_text(f"SIZE LIMIT ({file_size:.1f}MB/50MB)")
                    return False
                
                filename = os.path.join(DOWNLOAD_DIR, f"{sanitize_filename(title[:40])}_{uuid.uuid4().hex[:8]}.mp4")
                
                await status_msg.edit_text(f"DOWNLOADING ({file_size:.1f}MB)")
                
                with open(filename, 'wb') as f:
                    async for chunk in resp.content.iter_chunked(1024 * 1024):
                        f.write(chunk)
                
                await status_msg.edit_text("UPLOADING")
                
                with open(filename, 'rb') as f:
                    await context.bot.send_video(chat_id=chat_id, video=f, caption=title[:100])
                
                os.remove(filename)
                await status_msg.edit_text("COMPLETED")
                await status_msg.delete()
                return True

    except Exception as e:
        if status_msg:
            await status_msg.edit_text(f"ERROR: {str(e)[:100]}")
        return False

async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    urls = [line.strip() for line in text.splitlines() if line.strip().startswith(("http://", "https://"))]

    if not urls:
        await update.message.reply_text("INVALID URL - Send correct link")
        return

    if len(urls) == 1:
        url = clean_youtube_url(urls[0])
        msg = await update.message.reply_text("SCANNING...")

        try:
            loop = asyncio.get_running_loop()

            def get_info():
                ydl_params = {
                    'quiet': True,
                    'noplaylist': True,
                    'no_warnings': True,
                    'ignoreerrors': False,
                    'cookiefile': COOKIES_FILE,
                    'socket_timeout': 30,
                    'http_headers': {'User-Agent': 'Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36'},
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
ANALYSIS COMPLETE

TITLE: {title}
DURATION: {duration_str}
UPLOADER: {uploader}
VIEWS: {views_str}
LIKES: {likes_str}
STATUS: READY

DOWNLOAD OPTIONS
            """

            keyboard = [
                [
                    InlineKeyboardButton("BEST QUALITY", callback_data=f"dl|best|{url_hash}"),
                ]
            ]

            await msg.edit_text(result_text, reply_markup=InlineKeyboardMarkup(keyboard))

        except asyncio.TimeoutError:
            try:
                await msg.edit_text("TIMEOUT - Try again")
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

# ================= RUN BOT =================
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
