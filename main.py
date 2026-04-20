import os
import requests
import json
import logging
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# --- إعدادات ---
# إعداد نظام التسجيل لعرض الأحداث والأخطاء
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- قراءة الأسرار من متغيرات البيئة ---
# هذا هو الجزء الآمن، حيث لا نكتب الأسرار في الكود
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TIKTOK_COOKIES = (os.environ.get("TIKTOK_COOKIES") or "").strip()
SCRAPER_API_KEY = os.environ.get("SCRAPER_API_KEY")

# --- قاموس لترجمة رموز الدول إلى أسماء وأعلام ---
country_codes = {
    "SA": "🇸🇦 - السعودية", "AE": "🇦🇪 - الإمارات", "KW": "🇰🇼 - الكويت",
    "BH": "🇧🇭 - البحرين", "QA": "🇶🇦 - قطر", "OM": "🇴🇲 - عمان",
    "EG": "🇪🇬 - مصر", "IQ": "🇮🇶 - العراق", "JO": "🇯🇴 - الأردن",
    "LB": "🇱🇧 - لبنان", "PS": "🇵🇸 - فلسطين", "SY": "🇸🇾 - سوريا",
    "YE": "🇾🇪 - اليمن", "DZ": "🇩🇿 - الجزائر", "MA": "🇲🇦 - المغرب",
    "TN": "🇹🇳 - تونس", "LY": "🇱🇾 - ليبيا", "SD": "🇸🇩 - السودان"
}

# --- معالج أمر /start ---
# هذه الدالة تستجيب عندما يضغط المستخدم على /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("أهلاً بك! أرسل لي اسم مستخدم تيك توك (بدون @) وسأجلب لك معلوماته.")

# --- معالج الرسائل النصية ---
# هذه هي الدالة الرئيسية التي تعالج اسم المستخدم الذي يرسله المستخدم
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    username = update.message.text.strip().replace('@', '')

    # إرسال رسالة انتظار وحفظها لحذفها لاحقًا
    waiting_msg = await context.bot.send_message(chat_id=chat_id, text=f"⏳ جاري البحث عن {username}...")
    
    try:
        # --- الجزء الخاص بـ ScraperAPI ---
        tiktok_url = f"https://www.tiktok.com/@{username}"
        
        # إعداد الطلب الذي سنرسله إلى ScraperAPI
        scraper_payload = {
            'api_key': SCRAPER_API_KEY,
            'url': tiktok_url,
            'keep_headers': 'true' # مهم لتمرير الكوكيز الخاصة بنا
        }
        
        # إعداد الهيدرز التي سيمررها ScraperAPI إلى تيك توك
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36",
            "Cookie": TIKTOK_COOKIES
        }
        
        logger.info(f"ScraperAPI يزور الرابط: {tiktok_url}")
        
        # إرسال الطلب إلى خادم ScraperAPI
        response = requests.post(
            'http://api.scraperapi.com',
            json=scraper_payload,
            headers=headers,
            timeout=60 # نعطي الخدمة وقتًا كافيًا (60 ثانية)
        )
        # التأكد من أن الطلب نجح (لم يرجع خطأ 4xx أو 5xx)
        response.raise_for_status()
        html = response.text
        # --- نهاية جزء ScraperAPI ---

        # --- الجزء الخاص بتحليل الصفحة ---
        script_tag = '<script id="SIGI_STATE" type="application/json">'
        if script_tag not in html:
            logger.error("فشل في العثور على SIGI_STATE في الصفحة التي أعادتها ScraperAPI.")
            raise Exception("لم يتم العثور على بيانات المستخدم.")

        start_index = html.find(script_tag) + len(script_tag)
        end_index = html.find('</script>', start_index)
        json_data = json.loads(html[start_index:end_index])

        # استخراج البيانات من الـ JSON المعقد
        user_module = json_data.get("UserModule", {})
        user_data = user_module.get("users", {}).get(username)
        stats = user_module.get("stats", {}).get(username)

        if not user_data or not stats:
            raise Exception("فشل في تحليل البيانات من SIGI_STATE.")

        # تنسيق البيانات
        create_date = datetime.fromtimestamp(user_data.get("createTime", 0)).strftime('%Y-%m-%d')
        region = user_data.get("region", "غير محدد")
        country = country_codes.get(region, region)

        # بناء نص الرسالة النهائية
        result_text = f"""
✅ **تم العثور على معلومات الحساب:**

👤 **الاسم:** {user_data.get('nickname')}
🔖 **المعرف:** `@{user_data.get('uniqueId')}`
🆔 **ID:** `{user_data.get('id')}`

🌍 **الدولة:** {country}
✍️ **الوصف:** {user_data.get('signature') or "لا يوجد"}

📊 **إحصائيات:**
- **المتابِعون:** {stats.get('followerCount', 0)}
- **يتابع:** {stats.get('followingCount', 0)}
- **الإعجابات:** {stats.get('heartCount', 0)}
- **الفيديوهات:** {stats.get('videoCount', 0)}

🗓️ **تاريخ إنشاء الحساب:** {create_date}
        """
        # حذف رسالة الانتظار وإرسال النتيجة
        await context.bot.delete_message(chat_id=chat_id, message_id=waiting_msg.message_id)
        await context.bot.send_message(chat_id=chat_id, text=result_text, parse_mode='Markdown')

    except Exception as e:
        # في حال حدوث أي خطأ، يتم تسجيله وإرسال رسالة للمستخدم
        logger.error(f"!!! خطأ في البحث عن {username}: {e}", exc_info=True)
        await context.bot.delete_message(chat_id=chat_id, message_id=waiting_msg.message_id)
        await context.bot.send_message(chat_id=chat_id, text="❌ حدث خطأ: تأكد من أن اسم المستخدم صحيح وغير خاص.")

# --- الدالة الرئيسية لتشغيل البوت ---
def main():
    # التأكد من وجود الأسرار قبل البدء
    if not TOKEN or not SCRAPER_API_KEY:
        logger.error("توكن التليجرام أو مفتاح ScraperAPI غير موجود في متغيرات البيئة!")
        return

    logger.info("🚀 البوت يبدأ بنظام Polling مع ScraperAPI...")
    
    # إعداد تطبيق البوت
    application = Application.builder().token(TOKEN).build()
    
    # إضافة المعالجات (الأوامر والرسائل)
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # بدء تشغيل البوت بنظام Polling (التحقق من الرسائل الجديدة بشكل دوري)
    application.run_polling()

# --- نقطة انطلاق البرنامج ---
if __name__ == "__main__":
    main()
