import os
import asyncio
from pathlib import Path
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import FSInputFile
from moviepy.editor import VideoFileClip

# تحميل المتغيرات
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise ValueError("لم يتم العثور على BOT_TOKEN في ملف .env")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

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
        "👋 أهلاً بك في بوت تقسيم الفيديو!\n\n"
        "📤 أرسل لي أي فيديو وسأقوم بتقسيمه إلى أجزاء مدة كل جزء 1:30 دقيقة.\n\n"
        "⚠️ ملاحظة: الحد الأقصى لحجم الملف المرفوع هو 50MB (للمستخدمين العاديين)."
    )

# === معالجة رفع الفيديو ===
@dp.message(F.video | F.document)
async def handle_video_upload(message: types.Message):
    # تحديد نوع الملف (فيديو مباشر أو ملف وثيقة يحتوي على فيديو)
    file_obj = message.video or message.document
    
    # التأكد أن الملف فيديو (بامتداد mp4 أو mkv أو webm)
    if file_obj.mime_type and 'video' not in file_obj.mime_type:
        # إذا كان document، نتحقق من الامتداد يدوياً إذا أمكن
        if message.document and not message.document.file_name.lower().endswith(('.mp4', '.mkv', '.webm')):
             await message.reply("❌ يرجى إرسال ملف فيديو فقط (.mp4, .mkv, .webm).")
             return

    msg = await message.reply("⏳ جاري تحميل الفيديو...")
    
    try:
        # 1. تحميل الملف من تيليجرام
        file_info = await bot.get_file(file_obj.file_id)
        downloaded_file = await bot.download_file(file_info.file_path)
        
        # حفظ الملف مؤقتاً
        temp_dir = Path("temp_uploads")
        temp_dir.mkdir(exist_ok=True)
        original_filename = file_obj.file_name or f"video_{message.from_user.id}.mp4"
        local_path = temp_dir / original_filename
        
        with open(local_path, 'wb') as new_file:
            new_file.write(downloaded_file.read())
            
        await msg.edit_text("✅ تم التحميل. جاري تقسيم الفيديو إلى أجزاء (1:30)...")
        
        # 2. تقسيم الفيديو
        parts = await asyncio.to_thread(split_video, local_path, chunk_duration=90)
        
        if not parts:
            await msg.edit_text("❌ فشل في تقسيم الفيديو. تأكد أن الملف صالح.")
            return
        
        # 3. إرسال الأجزاء
        await msg.edit_text(f"📦 جاري إرسال {len(parts)} أجزاء...")
        
        for i, part_path in enumerate(parts):
            part_caption = f"الجزء {i+1}/{len(parts)}"
            video_file = FSInputFile(part_path)
            
            # إرسال كـ Video لضمان التشغيل المباشر
            await message.reply_video(video_file, caption=part_caption)
            
            # حذف الجزء المؤقت
            try:
                part_path.unlink()
            except:
                pass
        
        await msg.delete() # حذف رسالة الحالة
        
    except Exception as e:
        await msg.edit_text(f"⚠️ حدث خطأ: {e}")
    finally:
        # تنظيف الملف الأصلي
        if 'local_path' in locals() and local_path.exists():
            try:
                local_path.unlink()
            except:
                pass

# === تشغيل البوت ===
async def main():
    print("✅ بوت تقسيم الفيديو يعمل الآن...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
