import os
from telegram.ext import ApplicationBuilder, CommandHandler

# قراءة التوكن من Environment Variables
BOT_TOKEN = os.getenv("BOT_TOKEN")

# طباعة التوكن في الـ Logs للتأكد إنه اتقرأ صح
print("DEBUG BOT_TOKEN:", BOT_TOKEN)

# إنشاء التطبيق
app = ApplicationBuilder().token(BOT_TOKEN).build()

# أمر /start للتأكد إن البوت بيرد
async def start(update, context):
    await update.message.reply_text("البوت شغال ✅")

# إضافة الهاندلر للأوامر
app.add_handler(CommandHandler("start", start))

# تشغيل البوت
if __name__ == "__main__":
    print("BOT IS RUNNING!")
    app.run_polling()
