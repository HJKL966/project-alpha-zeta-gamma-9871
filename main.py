import os
import logging
import requests
import json
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.constants import ParseMode

# --- إعدادات ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
SCRAPER_API_KEY = os.getenv("SCRAPER_API_KEY")

# --- دوال مساعدة ---
def get_country_flag(country_code):
    """تحويل رمز الدولة إلى علم ورمز."""
    if not country_code:
        return "غير محدد"
    # قاموس صغير لبعض الدول الشائعة
    countries = {
        "SA": "🇸🇦 - السعودية", "AE": "🇦🇪 - الإمارات", "KW": "🇰🇼 - الكويت",
        "QA": "🇶🇦 - قطر", "BH": "🇧🇭 - البحرين", "OM": "🇴🇲 - عمان",
        "EG": "🇪🇬 - مصر", "JO": "🇯🇴 - الأردن", "LB": "🇱🇧 - لبنان",
        "IQ": "🇮🇶 - العراق", "MA": "🇲🇦 - المغرب", "DZ": "🇩🇿 - الجزائر",
        "TN": "🇹🇳 - تونس", "US": "🇺🇸 - الولايات المتحدة", "GB": "🇬🇧 - بريطانيا",
    }
    return countries.get(country_code.upper(), country_code.upper())

def format_timestamp(ts):
    """تحويل timestamp إلى تاريخ مقروء."""
    if not ts:
        return "غير محدد"
    return datetime.fromtimestamp(int(ts)).strftime('%Y-%m-%d')

# --- دوال البوت الأساسية ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """دالة البدء."""
    await update.message.reply_text('أهلاً بك! أرسل لي اسم مستخدم تيك توك (بدون @) وسأجلب لك بياناته.')

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """الدالة الرئيسية لمعالجة الرسائل."""
    username = update.message.text.strip().replace('@', '')
    
    if not TELEGRAM_BOT_TOKEN or not SCRAPER_API_KEY:
        logger.error("توكن التليجرام أو مفتاح ScraperAPI غير موجود!")
        await update.message.reply_text("❌ خطأ في إعدادات البوت. تواصل مع المطور.")
        return

    waiting_message = await update.message.reply_text('⏳ جاري البحث...')

    try:
        # بناء رابط ScraperAPI مع تفعيل render
        payload = {
            'api_key': SCRAPER_API_KEY,
            'url': f'https://www.tiktok.com/@{username}',
            'render': 'true'
        }
        
        response = requests.get('http://api.scraperapi.com', params=payload, timeout=90) # زيادة مدة الانتظار
        response.raise_for_status()
        html_content = response.text

        # البحث عن البيانات واستخراجها
        if '__UNIVERSAL_DATA_FOR_REHYDRATION__' not in html_content:
            raise ValueError("لم يتم العثور على البيانات المطلوبة في الصفحة. قد يكون الحساب غير موجود.")

        start_str = '<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__" type="application/json">'
        end_str = '</script>'
        start_index = html_content.find(start_str) + len(start_str)
        end_index = html_content.find(end_str, start_index)
        json_str = html_content[start_index:end_index]
        
        data = json.loads(json_str)
        
        # التنقل في مسار البيانات المعقد
        user_data = data.get('__DEFAULT_SCOPE__', {}).get('webapp.user-detail', {}).get('userInfo', {})
        stats = user_data.get('stats', {})
        user_info = user_data.get('user', {})

        if not user_info:
             raise ValueError("فشل في استخراج بيانات المستخدم من JSON.")

        # تجميع البيانات في رسالة منسقة
        message = (
            f"👤 **معلومات حساب:** `{user_info.get('uniqueId', 'N/A')}`\n\n"
            f"🏷️ **الاسم:** {user_info.get('nickname', 'N/A')}\n"
            f"🆔 **ID المستخدم:** `{user_info.get('id', 'N/A')}`\n"
            f"🌍 **الدولة:** {get_country_flag(user_info.get('region'))}\n\n"
            f"📈 **الإحصائيات:**\n"
            f"  - **المتابعون:** {stats.get('followerCount', 0):,}\n"
            f"  - **يتابع:** {stats.get('followingCount', 0):,}\n"
            f"  - **الإعجابات:** {stats.get('heartCount', 0):,}\n"
            f"  - **الفيديوهات:** {stats.get('videoCount', 0):,}\n\n"
            f"📅 **تاريخ إنشاء الحساب:** {format_timestamp(user_info.get('createTime'))}\n"
            f"✅ **حساب موثق:** {'نعم' if user_info.get('verified') else 'لا'}\n"
            f"🔒 **حساب خاص:** {'نعم' if user_info.get('privateAccount') else 'لا'}\n\n"
            f"🔗 **الرابط:** [tiktok.com/@{user_info.get('uniqueId', '')}](https://www.tiktok.com/@{user_info.get('uniqueId', '')})"
        )
        
        await waiting_message.edit_text(message, parse_mode=ParseMode.MARKDOWN)

    except requests.exceptions.RequestException as e:
        logger.error(f"خطأ في طلب ScraperAPI: {e}")
        await waiting_message.edit_text('❌ حدث خطأ أثناء الاتصال بالشبكة. حاول مرة أخرى.')
    except Exception as e:
        logger.error(f"خطأ غير متوقع: {e}")
        await waiting_message.edit_text(f'❌ حدث خطأ: تأكد من أن اسم المستخدم صحيح وغير خاص.\n`{e}`')

def main() -> None:
    """تشغيل البوت."""
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("البوت بدأ التشغيل بالنسخة النهائية...")
    application.run_polling()

if __name__ == '__main__':
    main()
