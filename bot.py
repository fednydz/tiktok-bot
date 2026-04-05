import os
import asyncio
import yt_dlp
from pathlib import Path
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import FSInputFile
import re

# تحميل المتغيرات من ملف .env
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

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

# رسالة البداية
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "👋 أهلاً بك!\n\n"
        "أرسل لي رابط فيديو تيك توك وسأقوم بتحميله بدون علامة مائية.\n\n"
        "📌 مثال: https://vm-tiktok-com/xxxxx/"
    )

# معالجة الروابط
@dp.message(F.text)
async def handle_url(message: types.Message):
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

# تشغيل البوت
async def main():
    print("✅ البوت يعمل الآن...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
