import os
import logging
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# إعداد تسجيل الأحداث
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# جلب المتغيرات من البيئة
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
SCRAPER_API_KEY = os.getenv("SCRAPER_API_KEY")

# دالة لبدء التشغيل
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text('أهلاً بك! أرسل لي اسم مستخدم تيك توك (بدون @) وسأجلب لك بياناته.')

# دالة لمعالجة الرسائل
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    username = update.message.text.strip().replace('@', '')
    
    # التحقق من وجود المتغيرات
    if not TELEGRAM_BOT_TOKEN or not SCRAPER_API_KEY:
        logger.error("توكن التليجرام أو مفتاح ScraperAPI غير موجود في متغيرات البيئة!")
        await update.message.reply_text("❌ حدث خطأ في إعدادات البوت. يرجى التواصل مع المطور.")
        return

    # إرسال رسالة انتظار
    waiting_message = await update.message.reply_text('⏳ جاري البحث عن بيانات المستخدم...')

    try:
        # بناء رابط ScraperAPI مع تفعيل خيار render
        payload = {
            'api_key': SCRAPER_API_KEY,
            'url': f'https://www.tiktok.com/@{username}',
            'render': 'true'  # <-- هذا هو التعديل المهم
        }
        
        response = requests.get('http://api.scraperapi.com', params=payload, timeout=60) # زيادة مدة الانتظار
        response.raise_for_status()  # التأكد من أن الطلب نجح (لم يرجع 404, 500, etc.)

        # البحث عن البيانات داخل الصفحة
        if '__UNIVERSAL_DATA_FOR_REHYDRATION__' in response.text:
            # استخراج البيانات (هذه الطريقة قد تحتاج لتعديل إذا تغير هيكل الصفحة)
            # هنا سنكتفي بإعلام المستخدم أننا وجدنا البيانات
            await waiting_message.edit_text(f"✅ تم العثور على بيانات المستخدم {username}!\n\n(ملاحظة: استخراج وتنسيق البيانات قيد التطوير)")
            # في المستقبل، سنضيف هنا كود استخراج وتنسيق البيانات كما في النسخ السابقة
        else:
            raise ValueError("لم يتم العثور على البيانات المطلوبة في الصفحة.")

    except requests.exceptions.RequestException as e:
        logger.error(f"خطأ في طلب ScraperAPI: {e}")
        await waiting_message.edit_text('❌ حدث خطأ أثناء الاتصال بالشبكة. حاول مرة أخرى.')
    except Exception as e:
        logger.error(f"خطأ غير متوقع: {e}")
        await waiting_message.edit_text('❌ حدث خطأ: تأكد من أن اسم المستخدم صحيح وغير خاص.')

def main() -> None:
    """تشغيل البوت."""
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("البوت بدأ التشغيل...")
    application.run_polling()

if __name__ == '__main__':
    main()
