import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)

from config import BOT_TOKEN, REQUIRED_CHANNELS, MESSAGES
from database import init_db, add_user, add_to_playlist, get_playlist
from downloader import is_valid_url, extract_url, download_video, download_audio, cleanup_file, get_video_info

# Logging sozlash
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Foydalanuvchi ma'lumotlarini saqlash
user_last_url = {}
user_selected_quality = {}

def get_channel_keyboard():
    """Kanallar tugmalari"""
    keyboard = []
    for i, channel in enumerate(REQUIRED_CHANNELS, 1):
        channel_name = channel.replace('@', '')
        keyboard.append([InlineKeyboardButton(
            f"📢 {i}-Kanal: {channel_name}", 
            url=f"https://t.me/{channel_name}"
        )])
    keyboard.append([InlineKeyboardButton("✅ Tekshirish", callback_data="check_sub")])
    return InlineKeyboardMarkup(keyboard)

def get_quality_keyboard():
    """Sifat tanlash tugmalari"""
    keyboard = [
        [
            InlineKeyboardButton("📱 360p", callback_data="quality_360p"),
            InlineKeyboardButton("📺 480p", callback_data="quality_480p"),
        ],
        [
            InlineKeyboardButton("🖥 720p HD", callback_data="quality_720p"),
            InlineKeyboardButton("🎬 1080p FHD", callback_data="quality_1080p"),
        ],
        [
            InlineKeyboardButton("⭐ Eng yaxshi sifat", callback_data="quality_best"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_video_keyboard():
    """Video tugmalari"""
    keyboard = [
        [
            InlineKeyboardButton("📂 Saqlash", callback_data="save_playlist"),
            InlineKeyboardButton("🎵 Musiqa", callback_data="download_audio"),
        ],
        [
            InlineKeyboardButton("📤 Do'stlarga ulashish", switch_inline_query="")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_main_keyboard():
    """Asosiy menyu tugmalari"""
    keyboard = [
        [
            InlineKeyboardButton("📂 Playlistim", callback_data="show_playlist"),
            InlineKeyboardButton("❓ Yordam", callback_data="help")
        ],
        [
            InlineKeyboardButton("📢 Kanal", url="https://t.me/oltiariq_999_magazin_oqboyra")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start buyrug'i"""
    user = update.effective_user
    await add_user(user.id, user.username, user.first_name)
    
    welcome_msg = MESSAGES["welcome"].format(name=user.first_name or "do'stim")
    await update.message.reply_text(
        welcome_msg,
        reply_markup=get_channel_keyboard(),
        parse_mode="HTML"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Yordam buyrug'i"""
    await update.message.reply_text(
        MESSAGES["help"],
        parse_mode="HTML",
        reply_markup=get_main_keyboard()
    )

async def playlist_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Playlist ko'rish"""
    user_id = update.effective_user.id
    playlist = await get_playlist(user_id)
    
    if not playlist:
        await update.message.reply_text(
            MESSAGES["playlist_empty"],
            parse_mode="HTML"
        )
        return
    
    await update.message.reply_text(
        MESSAGES["playlist_header"],
        parse_mode="HTML"
    )
    
    for item in playlist[:10]:
        try:
            if item['file_type'] == 'video':
                await context.bot.send_video(
                    chat_id=user_id,
                    video=item['file_id'],
                    caption=f"📹 {item['title']}"
                )
            else:
                await context.bot.send_audio(
                    chat_id=user_id,
                    audio=item['file_id'],
                    caption=f"🎵 {item['title']}"
                )
        except Exception as e:
            logger.error(f"Playlist yuborishda xatolik: {e}")

async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """URL qayta ishlash - sifat tanlash"""
    user = update.effective_user
    text = update.message.text
    
    # URL ajratib olish
    url = extract_url(text)
    if not url or not is_valid_url(url):
        await update.message.reply_text(
            MESSAGES["invalid_url"],
            parse_mode="HTML"
        )
        return
    
    # URL'ni saqlash
    user_last_url[user.id] = url
    
    # Sifat tanlash menyusi
    quality_msg = """
╔══════════════════════════════╗
   🎬 <b>SIFATNI TANLANG</b>
╚══════════════════════════════╝

📹 Video uchun sifatni tanlang:

▫️ <b>360p</b> - Kichik hajm (~5-15 MB)
▫️ <b>480p</b> - O'rta sifat (~15-30 MB)
▫️ <b>720p HD</b> - Yaxshi sifat (~30-60 MB)
▫️ <b>1080p FHD</b> - Yuqori sifat (~60-150 MB)
▫️ <b>Eng yaxshi</b> - Maksimal sifat

⚠️ <i>Katta fayllar (50MB+) biroz sekin yuklanadi</i>
"""
    
    await update.message.reply_text(
        quality_msg,
        parse_mode="HTML",
        reply_markup=get_quality_keyboard()
    )

async def download_and_send(query, context, user_id: int, url: str, quality: str):
    """Video yuklab yuborish"""
    
    status_msg = await query.message.reply_text(
        f"⏳ <b>Yuklanmoqda... ({quality})</b>\n\nIltimos, kuting...",
        parse_mode="HTML"
    )
    
    try:
        # Video yuklab olish
        result = await download_video(url, user_id, quality)
        
        if not result['success']:
            error_text = f"""
❌ <b>Xatolik!</b>

{result.get('error', 'Video yuklab olinmadi')}

💡 <b>Maslahat:</b>
▫️ Boshqa sifatni tanlang
▫️ Video mavjudligini tekshiring
"""
            await status_msg.edit_text(error_text, parse_mode="HTML")
            return
        
        file_path = result['file_path']
        file_size_mb = result['file_size'] / (1024 * 1024)
        
        # Fayl hajmi haqida xabar
        if file_size_mb > 50:
            await status_msg.edit_text(
                f"📤 <b>Yuborilmoqda...</b>\n\nHajmi: {file_size_mb:.1f} MB\n⚠️ Katta fayl, biroz kuting...",
                parse_mode="HTML"
            )
        else:
            await status_msg.edit_text(
                f"📤 <b>Yuborilmoqda...</b>\n\nHajmi: {file_size_mb:.1f} MB",
                parse_mode="HTML"
            )
        
        # Caption
        caption = f"""
🎬 <b>{result['title']}</b>

📊 Sifat: {quality}
📁 Hajmi: {file_size_mb:.1f} MB

━━━━━━━━━━━━━━━━━━━━━━━━━━
📥 @OLTIN_SAQLAYDI_BOT orqali yuklandi
"""
        
        # Rasm yoki Video yuborish
        if result.get('is_photo'):
            with open(file_path, 'rb') as photo_file:
                sent_message = await query.message.reply_photo(
                    photo=photo_file,
                    caption=caption,
                    parse_mode="HTML",
                    reply_markup=get_video_keyboard()
                )
            
            context.user_data['last_video'] = {
                'file_id': sent_message.photo[-1].file_id,
                'title': result['title'],
                'url': url,
                'is_photo': True
            }
        else:
            with open(file_path, 'rb') as video_file:
                sent_message = await query.message.reply_video(
                    video=video_file,
                    caption=caption,
                    parse_mode="HTML",
                    reply_markup=get_video_keyboard(),
                    supports_streaming=True
                )
            
            context.user_data['last_video'] = {
                'file_id': sent_message.video.file_id,
                'title': result['title'],
                'url': url,
                'is_photo': False
            }
        
        await status_msg.delete()
        cleanup_file(file_path)
        
    except Exception as e:
        logger.error(f"Video yuborishda xatolik: {e}")
        
        # 50MB dan katta bo'lsa maxsus xabar
        if "Request Entity Too Large" in str(e) or "file is too big" in str(e).lower():
            await status_msg.edit_text(
                f"""
❌ <b>Fayl juda katta!</b>

Telegram 50MB dan katta fayllarni qabul qilmaydi.

💡 <b>Yechim:</b>
Pastroq sifatni tanlang (360p yoki 480p)
""",
                parse_mode="HTML",
                reply_markup=get_quality_keyboard()
            )
        else:
            await status_msg.edit_text(
                MESSAGES["download_error"],
                parse_mode="HTML"
            )

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback tugmalar"""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    data = query.data
    
    if data == "check_sub":
        await query.edit_message_text(
            MESSAGES["subscribed"],
            parse_mode="HTML",
            reply_markup=get_main_keyboard()
        )
    
    # Sifat tanlash
    elif data.startswith("quality_"):
        quality = data.replace("quality_", "")
        url = user_last_url.get(user.id)
        
        if not url:
            await query.answer("❌ URL topilmadi. Iltimos, qaytadan yuboring.", show_alert=True)
            return
        
        # Sifatni saqlash
        user_selected_quality[user.id] = quality
        
        # Yuklab yuborish
        await download_and_send(query, context, user.id, url, quality)
    
    elif data == "save_playlist":
        last_video = context.user_data.get('last_video')
        if last_video:
            await add_to_playlist(
                user_id=user.id,
                file_id=last_video['file_id'],
                file_type='photo' if last_video.get('is_photo') else 'video',
                title=last_video['title'],
                url=last_video['url']
            )
            await query.answer("✅ Playlistga saqlandi!", show_alert=True)
        else:
            await query.answer("❌ Video topilmadi", show_alert=True)
    
    elif data == "download_audio":
        url = user_last_url.get(user.id)
        if not url:
            await query.answer("❌ URL topilmadi", show_alert=True)
            return
        
        await query.answer("🎵 Musiqa yuklanmoqda...")
        status_msg = await query.message.reply_text(
            "⏳ <b>Musiqa yuklab olinmoqda...</b>",
            parse_mode="HTML"
        )
        
        try:
            result = await download_audio(url, user.id)
            
            if result['success']:
                caption = f"""
🎵 <b>{result['title']}</b>

━━━━━━━━━━━━━━━━━━━━━━━━━━
📥 @OLTIN_SAQLAYDI_BOT orqali yuklandi
"""
                
                with open(result['file_path'], 'rb') as audio_file:
                    sent_audio = await query.message.reply_audio(
                        audio=audio_file,
                        caption=caption,
                        parse_mode="HTML"
                    )
                
                context.user_data['last_audio'] = {
                    'file_id': sent_audio.audio.file_id,
                    'title': result['title'],
                    'url': url
                }
                
                await status_msg.delete()
                cleanup_file(result['file_path'])
            else:
                await status_msg.edit_text(
                    "❌ Musiqa yuklab olinmadi. FFmpeg o'rnatilmagan bo'lishi mumkin.",
                    parse_mode="HTML"
                )
        except Exception as e:
            logger.error(f"Audio xatolik: {e}")
            await status_msg.edit_text(
                MESSAGES["download_error"],
                parse_mode="HTML"
            )
    
    elif data == "show_playlist":
        playlist = await get_playlist(user.id)
        
        if not playlist:
            await query.answer(MESSAGES["playlist_empty"], show_alert=True)
            return
        
        await query.message.reply_text(
            MESSAGES["playlist_header"],
            parse_mode="HTML"
        )
        
        for item in playlist[:10]:
            try:
                if item['file_type'] == 'video':
                    await context.bot.send_video(
                        chat_id=user.id,
                        video=item['file_id'],
                        caption=f"📹 {item['title']}"
                    )
                elif item['file_type'] == 'photo':
                    await context.bot.send_photo(
                        chat_id=user.id,
                        photo=item['file_id'],
                        caption=f"📸 {item['title']}"
                    )
                else:
                    await context.bot.send_audio(
                        chat_id=user.id,
                        audio=item['file_id'],
                        caption=f"🎵 {item['title']}"
                    )
            except Exception as e:
                logger.error(f"Playlist item xatolik: {e}")
    
    elif data == "help":
        await query.message.reply_text(
            MESSAGES["help"],
            parse_mode="HTML",
            reply_markup=get_main_keyboard()
        )

async def post_init(application):
    """Bot ishga tushganda"""
    await init_db()
    logger.info("Bot ishga tushdi!")

def main():
    """Asosiy funksiya"""
    application = Application.builder().token(BOT_TOKEN).post_init(post_init).build()
    
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("playlist", playlist_command))
    application.add_handler(CallbackQueryHandler(callback_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))
    
    logger.info("Bot ishga tushmoqda...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
