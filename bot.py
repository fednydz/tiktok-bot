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

# تحميل المتغيرات
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

# إنشاء البوت
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# === أنماط الروابط (مصححة) ===
TIKTOK_REGEX = re.compile(r"https?://(?:www\.)?(?:tiktok\.com/[@\w.-]+/video/|vm\.tiktok\.com/|vt\.tiktok\.com/)(\w+)")
YOUTUBE_REGEX = re.compile(r"https?://(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)([\w-]+)")
INSTAGRAM_REGEX = re.compile(r"https?://(?:www\.)?instagram\.com/(?:p|reel|tv)/([\w-]+)")
FACEBOOK_REGEX = re.compile(r"https?://(?:www\.)?(?:facebook\.com/(?:reel|watch|videos?/)|fb\.watch/)([\w./?=&-]+)")

# === دوال استخراج الروابط ===
def extract_url(url: str, platform: str) -> str | None:
    patterns = {
        "tiktok": TIKTOK_REGEX,
        "youtube": YOUTUBE_REGEX,
        "instagram": INSTAGRAM_REGEX,
        "facebook": FACEBOOK_REGEX
    }
    match = patterns.get(platform, re.compile("")).search(url)
    return match.group(0) if match else None

def detect_platform(url: str) -> str | None:
    if TIKTOK_REGEX.search(url): return "tiktok"
    if YOUTUBE_REGEX.search(url): return "youtube"
    if INSTAGRAM_REGEX.search(url): return "instagram"
    if FACEBOOK_REGEX.search(url): return "facebook"
    return None

# === دالة التحميل الموحدة ===
def download_video(url: str, platform: str) -> tuple[Path | None, dict | None]:
    output_dir = Path("downloads")
    output_dir.mkdir(exist_ok=True)
    
    ydl_opts = {
        "outtmpl": f"{output_dir}/%(id)s.%(ext)s",
        "format": "best[ext=mp4][height<=720]/best[ext=mp4]/best",
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            return Path(filename), {
                "title": info.get("title", "فيديو"),
                "uploader": info.get("uploader", ""),
                "duration": info.get("duration", 0)
            }
    except Exception as e:
        print(f"خطأ التحميل ({platform}): {e}")
        return None, None

# === أزرار المنصات ===
def get_platform_buttons() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🎵 تيك توك", callback_data="platform_tiktok"),
        InlineKeyboardButton(text="📺 يوتيوب", callback_data="platform_youtube")
    )
    builder.row(
        InlineKeyboardButton(text="📸 إنستقرام", callback_data="platform_instagram"),
        InlineKeyboardButton(text="📘 فيسبوك", callback_data="platform_facebook")
    )
    return builder.as_markup()

# === رسالة البداية ===
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "👋 أهلاً بك في بوت التحميل الشامل!\n\n"
        "أرسل لي رابط فيديو من:\n"
        "🎵 تيك توك | 📺 يوتيوب | 📸 إنستقرام | 📘 فيسبوك\n\n"
        "وسأقوم بتحميله لك بدون علامة مائية ✨\n\n"
        "💡 مثال:\n"
        "https://vm.tiktok.com/xxxxx/\n"
        "https://youtu.be/xxxxx",
        reply_markup=get_platform_buttons()
    )

# === معالجة الأزرار ===
@dp.callback_query(F.data.startswith("platform_"))
async def handle_platform_btn(callback: types.CallbackQuery):
    platform = callback.data.replace("platform_", "")
    platforms = {
        "tiktok": "🎵 تيك توك",
        "youtube": "📺 يوتيوب", 
        "instagram": "📸 إنستقرام",
        "facebook": "📘 فيسبوك"
    }
    await callback.answer(f"✅ اخترت: {platforms[platform]}", show_alert=True)

# === معالجة الروابط ===
@dp.message(F.text)
async def handle_url(message: types.Message):
    url = message.text.strip()
    platform = detect_platform(url)
    
    if not platform:
        await message.answer(
            "❌ لم أتعرّف على الرابط.\n"
            "تأكد أنه من إحدى المنصات المدعومة:\n"
            "🎵 تيك توك | 📺 يوتيوب | 📸 إنستقرام | 📘 فيسبوك",
            reply_markup=get_platform_buttons()
        )
        return

    platform_names = {
        "tiktok": "🎵 تيك توك",
        "youtube": "📺 يوتيوب",
        "instagram": "📸 إنستقرام", 
        "facebook": "📘 فيسبوك"
    }

    msg = await message.answer(f"⏳ جاري تحميل الفيديو من {platform_names[platform]}...")
    
    file_path, info = await asyncio.to_thread(download_video, url, platform)
    
    if not file_path or not file_path.exists():
        await msg.edit_text("😞 فشل التحميل. تأكد من:\n• أن الرابط صحيح\n• أن الفيديو عام (ليس خاص)\n• أن المنصة لا تمنع التحميل")
        return

    try:
        caption = f"✅ تم التحميل بنجاح!\n📌 {info['title']}"
        if info['uploader']:
            caption += f"\n👤 {info['uploader']}"
        
        video = FSInputFile(file_path)
        await message.reply_video(video, caption=caption)
        await msg.delete()
        
    except Exception as e:
        await msg.edit_text(f"⚠️ خطأ في الإرسال: {e}")
    finally:
        if file_path and file_path.exists():
            try:
                file_path.unlink()
            except:
                pass

# === تشغيل البوت ===
async def main():
    print("✅ البوت يعمل الآن...")
    print("🎵 تيك توك | 📺 يوتيوب | 📸 إنستقرام | 📘 فيسبوك")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
