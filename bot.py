import os
import asyncio
import yt_dlp
from pathlib import Path
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
import re
from aiogram.exceptions import TelegramBadRequest

# تحميل المتغيرات
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))
CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME", "fedny_dz")  # اسم القناة

# إنشاء البوت
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# دالة للتحقق من رابط تيك توك
TIKTOK_REGEX = re.compile(r"https?://(?:www\.)?(?:tiktok\.com/[@\w.-]+/video/|vm\.tiktok\.com/)(\w+)")

def extract_tiktok_url(url: str) -> str | None:
    match = TIKTOK_REGEX.search(url)
    return match.group(0) if match else None

# دالة تحميل الفيديو
def download_tiktok(url: str) -> Path | None:
    output_dir = Path("downloads")
    output_dir.mkdir(exist_ok=True)
    
    ydl_opts = {
        "outtmpl": f"{output_dir}/%(id)s.%(ext)s",
        "format": "best[ext=mp4]/best",
        "quiet": True,
        "no_warnings": True,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            return Path(filename)
    except Exception as e:
        print(f"خطأ في التحميل: {e}")
        return None

# ==================== التحقق من الاشتراك ====================

async def check_subscription(user_id: int) -> bool:
    """التحقق من اشتراك المستخدم في القناة"""
    try:
        member = await bot.get_chat_member(f"@{CHANNEL_USERNAME}", user_id)
        return member.status in ["member", "administrator", "creator"]
    except TelegramBadRequest:
        # القناة خاصة أو المستخدم ليس لديه صلاحية
        return False
    except Exception as e:
        print(f"خطأ في التحقق من الاشتراك: {e}")
        return False

def get_subscription_keyboard() -> InlineKeyboardMarkup:
    """إنشاء زر الاشتراك في القناة"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="🔰 القناة الأولى: fedny_dz 📢",
            url=f"https://t.me/{CHANNEL_USERNAME}"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="✅ اشتركت! اضغط هنا للتحقق /start",
            callback_data="check_subscription"
        )
    )
    return builder.as_markup()

async def send_subscription_message(message: types.Message):
    """إرسال رسالة الاشتراك الإلزامي"""
    await message.answer(
        "🟢| عذرًا، عليك الإشتراك بقنوات البوت أولاً لتتمكن من إستخدامه:🟢 \n\n"
        f"🔰 القناة الأولى: https://t.me/{CHANNEL_USERNAME}\n\n"
        "✅ | أشترك ثم أضغط /start ♻️",
        reply_markup=get_subscription_keyboard()
    )

# =================================================================

# رسالة البداية مع التحقق من الاشتراك
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    # المشرف يتجاوز التحقق
    if message.from_user.id == ADMIN_ID:
        await message.answer(
            "👋 أهلاً بك أيها المشرف!\n\n"
            "أرسل لي رابط فيديو تيك توك وسأقوم بتحميله بدون علامة مائية.\n\n"
            "📌 مثال: https://vm.tiktok.com/xxxxx/\n\n"
            "🔧 أوامر المشرف:\n"
            "/admin - لوحة التحكم\n"
            "/stats - الإحصائيات"
        )
        return
    
    # التحقق من الاشتراك
    is_subscribed = await check_subscription(message.from_user.id)
    
    if not is_subscribed:
        await send_subscription_message(message)
    else:
        await message.answer(
            "👋 أهلاً بك!\n\n"
            "أرسل لي رابط فيديو تيك توك وسأقوم بتحميله بدون علامة مائية.\n\n"
            "📌 مثال: https://vm.tiktok.com/xxxxx/"
        )

# معالجة زر التحقق من الاشتراك
@dp.callback_query(F.data == "check_subscription")
async def check_subscription_callback(callback: types.CallbackQuery):
    is_subscribed = await check_subscription(callback.from_user.id)
    
    if is_subscribed:
        await callback.message.answer(
            "✅ تم التحقق من اشتراكك بنجاح!\n\n"
            "الآن يمكنك استخدام البوت. أرسل رابط فيديو تيك توك."
        )
        await callback.message.delete()
    else:
        await callback.answer(
            "⚠️ لم يتم العثور على اشتراكك بعد.\n"
            "تأكد من الاشتراك في القناة ثم اضغط الزر مرة أخرى.",
            show_alert=True
        )

# معالجة الروابط والرسائل مع التحقق من الاشتراك
@dp.message(F.text)
async def handle_url(message: types.Message):
    # المشرف يتجاوز التحقق
    if message.from_user.id == ADMIN_ID:
        url = message.text.strip()
        clean_url = extract_tiktok_url(url)
        
        if not clean_url:
            await message.answer("❌ الرابط غير صحيح. يرجى إرسال رابط تيك توك صالح.")
            return

        msg = await message.answer("⏳ جاري التحميل...")
        
        # تحميل الفيديو
        file_path = await asyncio.to_thread(download_tiktok, clean_url)
        
        if not file_path or not file_path.exists():
            await msg.edit_text("😞 فشل تحميل الفيديو. تأكد من صحة الرابط.")
            return

        try:
            # إرسال الفيديو
            video = FSInputFile(file_path)
            await message.reply_video(video, caption="✅ تم التحميل بنجاح!")
            await msg.delete()
        except Exception as e:
            await msg.edit_text(f"⚠️ خطأ: {e}")
        finally:
            # حذف الملف المؤقت
            if file_path.exists():
                file_path.unlink()
        return
    
    # للمستخدمين العاديين: التحقق من الاشتراك أولاً
    is_subscribed = await check_subscription(message.from_user.id)
    
    if not is_subscribed:
        await send_subscription_message(message)
        return
    
    # إذا كان مشتركاً، عالج الرابط
    url = message.text.strip()
    clean_url = extract_tiktok_url(url)
    
    if not clean_url:
        await message.answer("❌ الرابط غير صحيح. يرجى إرسال رابط تيك توك صالح.")
        return

    msg = await message.answer("⏳ جاري التحميل...")
    
    # تحميل الفيديو
    file_path = await asyncio.to_thread(download_tiktok, clean_url)
    
    if not file_path or not file_path.exists():
        await msg.edit_text("😞 فشل تحميل الفيديو. تأكد من صحة الرابط.")
        return

    try:
        # إرسال الفيديو
        video = FSInputFile(file_path)
        await message.reply_video(video, caption="✅ تم التحميل بنجاح!")
        await msg.delete()
    except Exception as e:
        await msg.edit_text(f"⚠️ خطأ: {e}")
    finally:
        # حذف الملف المؤقت
        if file_path.exists():
            file_path.unlink()

# ==================== أوامر المشرف ====================

@dp.message(Command("admin"))
async def cmd_admin(message: types.Message):
    """التحقق من أن المستخدم مشرف"""
    if message.from_user.id == ADMIN_ID:
        await message.answer(
            "👤 لوحة تحكم المشرف\n\n"
            "الأوامر المتاحة:\n"
            "/stats - إحصائيات البوت\n"
            "/broadcast - إرسال إشعار للجميع (قريباً)\n"
            "/ping - اختبار البوت"
        )
    else:
        await message.answer("⛔ ليس لديك صلاحيات المشرف!")

@dp.message(Command("stats"))
async def cmd_stats(message: types.Message):
    """إحصائيات بسيطة"""
    if message.from_user.id == ADMIN_ID:
        await message.answer(f"📊 إحصائيات البوت:\n\n"
                           f"✅ البوت يعمل منذ: {__import__('datetime').datetime.now()}\n"
                           f"🔗 المستودع: github.com/fednydz/tiktok-bot\n"
                           f"📢 القناة: @{CHANNEL_USERNAME}")
    else:
        await message.answer("⛔ ليس لديك صلاحيات المشرف!")

@dp.message(Command("ping"))
async def cmd_ping(message: types.Message):
    """اختبار سرعة البوت"""
    if message.from_user.id == ADMIN_ID:
        import time
        start = time.time()
        msg = await message.answer("🏓 Pong!")
        end = time.time()
        await msg.edit_text(f"🏓 Pong! ({int((end-start)*1000)}ms)")
    else:
        await message.answer("⛔ ليس لديك صلاحيات المشرف!")

# =====================================================

# تشغيل البوت
async def main():
    print("✅ البوت يعمل الآن...")
    print(f"👤 Admin ID: {ADMIN_ID}")
    print(f"📢 Channel: @{CHANNEL_USERNAME}")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
