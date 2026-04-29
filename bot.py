import os
import asyncio
import yt_dlp
from pathlib import Path
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import FSInputFile
from moviepy.editor import VideoFileClip
import re

# تحميل المتغيرات
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise ValueError("لم يتم العثور على BOT_TOKEN في ملف .env")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# === أنماط الروابط ===
TIKTOK_REGEX = re.compile(r"https?://(?:www\.)?(?:tiktok\.com/[@\w.-]+/video/|vm\.tiktok\.com/|vt\.tiktok\.com/)(\w+)")
YOUTUBE_REGEX = re.compile(r"https?://(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)([\w-]+)")
INSTAGRAM_REGEX = re.compile(r"https?://(?:www\.)?instagram\.com/(?:p|reel|tv)/([\w-]+)")
FACEBOOK_REGEX = re.compile(r"https?://(?:www\.)?(?:facebook\.com/(?:reel|watch|videos?/)|fb\.watch/)([\w./?=&-]+)")

def detect_platform(url: str) -> str | None:
    if TIKTOK_REGEX.search(url): return "tiktok"
    if YOUTUBE_REGEX.search(url): return "youtube"
    if INSTAGRAM_REGEX.search(url): return "instagram"
    if FACEBOOK_REGEX.search(url): return "facebook"
    return None

# === دالة التحميل ===
def download_video(url: str) -> tuple[Path | None, dict | None]:
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
            file_path = Path(filename)
            
            # التأكد من وجود الملف وتصحيح الامتداد إذا لزم الأمر
            if not file_path.exists():
                for ext in ['.mp4', '.webm', '.mkv']:
                    if file_path.with_suffix(ext).exists():
                        file_path = file_path.with_suffix(ext)
                        break
            
            return file_path, {
                "title": info.get("title", "فيديو"),
                "uploader": info.get("uploader", ""),
            }
    except Exception as e:
        print(f"خطأ التحميل: {e}")
        return None, None

# === دالة تقسيم الفيديو (90 ثانية) ===
def split_video(file_path: Path, chunk_duration: int = 90) -> list[Path]:
    """يقسم الفيديو إلى أجزاء مدة كل منها 90 ثانية"""
    clips = []
    output_dir = file_path.parent / "chunks"
    output_dir.mkdir(exist_ok=True)
    
    try:
        video = VideoFileClip(str(file_path))
        duration = video.duration
        total_chunks = int(duration // chunk_duration) + 1
        
        for i in range(total_chunks):
            start_time = i * chunk_duration
            end_time = min((i + 1) * chunk_duration, duration)
            
            if start_time >= duration:
                break
                
            clip = video.subclip(start_time, end_time)
            chunk_path = output_dir / f"{file_path.stem}_part{i+1}.mp4"
            
            # كتابة الملف بصيغة متوافقة مع تيليجرام
            clip.write_videofile(
                str(chunk_path), 
                codec="libx264", 
                audio_codec="aac", 
                verbose=False, 
                logger=None
            )
            clips.append(chunk_path)
            clip.close()
        
        video.close()
        return clips
    except Exception as e:
        print(f"خطأ في التقسيم: {e}")
        return []

# === رسالة البداية ===
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "👋 أهلاً بك في بوت التحميل والتقسيم!\n\n"
        "أرسل لي رابط فيديو من:\n"
        "🎵 تيك توك | 📺 يوتيوب | 📸 إنستقرام | 📘 فيسبوك\n\n"
        "سيتم تقسيم الفيديوهات الطويلة إلى أجزاء مدة كل جزء 1:30 دقيقة."
    )

# === معالجة الروابط ===
@dp.message(F.text)
async def handle_url(message: types.Message):
    url = message.text.strip()
    platform = detect_platform(url)
    
    if not platform:
        await message.answer("❌ لم أتعرّف على الرابط. تأكد أنه من المنصات المدعومة.")
        return

    platform_names = {
        "tiktok": "🎵 تيك توك",
        "youtube": "📺 يوتيوب",
        "instagram": "📸 إنستقرام", 
        "facebook": "📘 فيسبوك"
    }

    msg = await message.answer(f"⏳ جاري تحميل الفيديو من {platform_names[platform]}...")
    
    # 1. تحميل الفيديو
    file_path, info = await asyncio.to_thread(download_video, url)
    
    if not file_path or not file_path.exists():
        await msg.edit_text("😞 فشل التحميل. تأكد من صحة الرابط.")
        return

    await msg.edit_text("✅ تم التحميل. جاري التحقق من الحجم وتقسيم الفيديو إذا لزم الأمر...")

    try:
        # 2. فحص حجم الملف (بالبايت)
        file_size = file_path.stat().st_size
        MAX_SIZE = 45 * 1024 * 1024  # 45 MB (احتياطياً لتجنب حد 50MB)

        parts_to_send = []
        
        if file_size > MAX_SIZE:
            await msg.edit_text("📦 الفيديو كبير، جاري تقسيمه إلى أجزاء (1:30 دقيقة)...")
            parts = await asyncio.to_thread(split_video, file_path, chunk_duration=90)
            if not parts:
                await msg.edit_text("❌ فشل في تقسيم الفيديو.")
                return
            parts_to_send = parts
        else:
            parts_to_send = [file_path]

        # 3. إرسال الأجزاء
        caption_base = f"📌 {info['title']}"
        
        for i, part_path in enumerate(parts_to_send):
            part_caption = f"{caption_base}\n(الجزء {i+1}/{len(parts_to_send)})"
            video_file = FSInputFile(part_path)
            
            await message.reply_video(video_file, caption=part_caption)
            
            # حذف الجزء المؤقت بعد الإرسال لتوفير المساحة
            try:
                part_path.unlink()
            except:
                pass

        await msg.delete() # حذف رسالة الحالة النهائية
        
    except Exception as e:
        await msg.edit_text(f"⚠️ خطأ في المعالجة أو الإرسال: {e}")
    finally:
        # تنظيف الملفات الأصلية والمجلدات المؤقتة
        if file_path and file_path.exists():
            try:
                file_path.unlink()
            except:
                pass
        # يمكن إضافة كود لحذف مجلد chunks هنا إذا أردت

# === تشغيل البوت ===
async def main():
    print("✅ بوت التحميل والتقسيم يعمل الآن...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
