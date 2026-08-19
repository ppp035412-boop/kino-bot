import sqlite3
import logging
import time
from datetime import datetime
import telebot
from telebot import types
import google.generativeai as genai

# ==================== SOZLAMALAR ====================
BOT_TOKEN = "8894810381:AAGjIe8Xvq6WzQzU9qlh8947HOt2UwLqvXQ" # Bot tokeningizni yozing
ADMIN_ID = 8513020688  # Sizning Admin ID raqamingiz
CHANNEL_USERNAME = "@Sasuke_uchiha_the_last"  # Majburiy obuna kanali
AI_TOKEN = "AQ.Ab8RN6LTNm_f5el-PLCuRWoLGYQE-6stFz7qQlkZDXJo7lGWng"  # Gemini AI Tokeni

# Google Gemini AI sozlamalari
genai.configure(api_key=AI_TOKEN)
ai_model = genai.GenerativeModel("gemini-1.5-flash")

# Logging sozlamalari
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

bot = telebot.TeleBot(BOT_TOKEN, parse_mode='HTML')

# Foydalanuvchilarning AI bilan muloqot holatini saqlash uchun vaqtinchalik xotira
ai_chat_mode = set()

# ==================== BAZA BILAN ISHLASH ====================
def init_db():
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    
    # Foydalanuvchilar jadvali
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            full_name TEXT,
            status TEXT DEFAULT 'oddiy',
            balance INTEGER DEFAULT 0,
            referred_by INTEGER,
            joined_date TEXT
        )
    ''')
    
    # Kinolar jadvali
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS movies (
            code TEXT PRIMARY KEY,
            title TEXT,
            description TEXT,
            file_id TEXT,
            category TEXT,
            rating REAL DEFAULT 0.0,
            views INTEGER DEFAULT 0
        )
    ''')
    
    conn.commit()
    conn.close()

init_db()

# ==================== YORDAMCHI FUNKSIYALAR ====================
def db_query(query, params=(), fetchone=False, fetchall=False):
    try:
        conn = sqlite3.connect('bot_database.db')
        cursor = conn.cursor()
        cursor.execute(query, params)
        data = None
        if fetchone:
            data = cursor.fetchone()
        elif fetchall:
            data = cursor.fetchall()
        conn.commit()
        conn.close()
        return data
    except Exception as e:
        logging.error(f"DB Xatolik: {e}")
        return None

# Majburiy obunani tekshirish
def check_subscription(user_id):
    if user_id == ADMIN_ID:
        return True
    try:
        member = bot.get_chat_member(CHANNEL_USERNAME, user_id)
        if member.status in ['member', 'administrator', 'creator']:
            return True
    except Exception as e:
        logging.error(f"Obunani tekshirishda xato: {e}")
    return False

# ==================== /START VA ASOSIY MENYU ====================
@bot.message_handler(commands=['start'])
def cmd_start(message):
    try:
        user_id = message.from_user.id
        username = message.from_user.username
        full_name = message.from_user.full_name
        
        # Referal kodni aniqlash
        args = message.text.split()
        referred_by = None
        if len(args) > 1 and args[1].isdigit():
            ref_id = int(args[1])
            if ref_id != user_id:
                referred_by = ref_id

        # Foydalanuvchi bazada bormi tekshiramiz
        user = db_query("SELECT * FROM users WHERE user_id = ?", (user_id,), fetchone=True)
        if not user:
            db_query(
                "INSERT INTO users (user_id, username, full_name, referred_by, joined_date) VALUES (?, ?, ?, ?, ?)",
                (user_id, username, full_name, referred_by, datetime.now().strftime("%Y-%m-%d %H:%M"))
            )
            if referred_by:
                db_query("UPDATE users SET balance = balance + 1 WHERE user_id = ?", (referred_by,))
                try:
                    bot.send_message(referred_by, "🎉 Sizning havolangiz orqali yangi foydalanuvchi qo'shildi va 1 ball bonus oldingiz!")
                except:
                    pass

        # Majburiy obunani tekshirish
        if not check_subscription(user_id):
            markup = types.InlineKeyboardMarkup(row_width=1)
            markup.add(
                types.InlineKeyboardButton("📢 Kanalga obuna bo'lish", url=f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}"),
                types.InlineKeyboardButton("✅ Obunani tekshirish", callback_data="check_sub")
            )
            bot.send_message(message.chat.id, "⚠️ Botdan foydalanish uchun avval quyidagi kanalimizga obuna bo'ling:", reply_markup=markup)
            return

        # Asosiy Reply Keyboard + AI tugmasi
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add("🎬 Kinolar", "🔥 Mashhur kinolar", "📂 Kategoriyalar")
        markup.add("👤 Kabinet", "⭐ Premium olish", "🤖 AI bilan muloqot")

        bot.send_message(message.chat.id, f"Salom, <b>{full_name}</b>! Kodli kino botiga xush kelibsiz.\nKino kodini yuboring yoki menyudan foydalaning:", reply_markup=markup)
    except Exception as e:
        logging.error(f"/start xatolik: {e}")

# Obunani tasdiqlash tugmasi
@bot.callback_query_handler(func=lambda call: call.data == "check_sub")
def callback_check_sub(call):
    if check_subscription(call.from_user.id):
        bot.answer_callback_query(call.id, "Rahmat, obuna tasdiqlandi!")
        bot.edit_message_text("✅ Obuna tasdiqlandi! Endi botdan to'liq foydalanishingiz mumkin. /start buyrug'ini bosing.", chat_id=call.message.chat.id, message_id=call.message.message_id)
    else:
        bot.answer_callback_query(call.id, "Siz hali kanalga obuna bo'lmadingiz!", show_alert=True)

# ==================== KINO VA AI BILAN MULOQOT ====================
@bot.message_handler(func=lambda message: message.text and not message.text.startswith('/'))
def handle_text(message):
    user_id = message.from_user.id
    
    if not check_subscription(user_id):
        bot.reply_to(message, "⚠️ Avval kanalga obuna bo'ling! /start ni bosing.")
        return

    text = message.text.strip()

    # AI bilan muloqot rejimini yoqish/o'chirish
    if text == "🤖 AI bilan muloqot":
        if user_id in ai_chat_mode:
            ai_chat_mode.remove(user_id)
            bot.send_message(message.chat.id, "🔄 AI rejimi o'chirildi. Endi odatiy kino kodlarini yuborishingiz mumkin.")
        else:
            ai_chat_mode.add(user_id)
            bot.send_message(message.chat.id, "🤖 <b>AI rejimi yoqildi!</b>\nMen kinolar, ularning kodlari va tavsiflari bo'yicha barcha savollaringizga javob beraman. Chiqish uchun yana o'sha tugmani bosing.")
        return

    # Agar foydalanuvchi AI rejimida bo'lsa
    if user_id in ai_chat_mode:
        try:
            movies_list = db_query("SELECT code, title, description FROM movies", fetchall=True)
            movies_context = "Mavjud kinolar bazasi:\n"
            if movies_list:
                for m in movies_list:
                    movies_context += f"Kod: {m[0]}, Nomi: {m[1]}, Tavsif: {m[2]}\n"
            else:
                movies_context += "Hozircha baza bo'sh.\n"

            prompt = f"Sen kino botining aqlli yordamchisisan. Foydalanuvchining savoliga javob ber. Mana senga bazadagi kinolar ro'yxati:\n{movies_context}\nFoydalanuvchi savoli: {text}"
            
            response = ai_model.generate_content(prompt)
            bot.reply_to(message, response.text)
        except Exception as e:
            bot.reply_to(message, f"AI bilan bog'lanishda xatolik yuz berdi: {e}")
        return

    # Menyudagi boshqa tugmalar
    if text == "🎬 Kinolar":
        movies = db_query("SELECT code, title FROM movies ORDER BY views DESC LIMIT 10", fetchall=True)
        if movies:
            text_msg = "<b>🎬 So'nggi va mashhur kinolar:</b>\n\n" + "\n".join([f"Kod: <code>{m[0]}</code> — {m[1]}" for m in movies])
            bot.send_message(message.chat.id, text_msg)
        else:
            bot.send_message(message.chat.id, "Hozircha kinolar bazasi bo'sh.")
        return

    elif text == "👤 Kabinet":
        user = db_query("SELECT status, balance, joined_date FROM users WHERE user_id = ?", (user_id,), fetchone=True)
        if user:
            status, balance, joined = user
            ref_link = f"https://t.me/{bot.get_me().username}?start={user_id}"
            cabinet_text = (
                f"👤 <b>Sizning profilingiz:</b>\n\n"
                f"🆔 ID: <code>{user_id}</code>\n"
                f"👑 Status: <b>{status.upper()}</b>\n"
                f"💎 Balansingiz: {balance} ball\n"
                f"📅 Qo'shilgan sana: {joined}\n\n"
                f"🔗 Referal havolangiz:\n<code>{ref_link}</code>"
            )
            bot.send_message(message.chat.id, cabinet_text)
        return

    # Kino kodi orqali qidirish va yuborish
    movie = db_query("SELECT title, description, file_id, views FROM movies WHERE code = ?", (text,), fetchone=True)
    if movie:
        title, description, file_id, views = movie
        db_query("UPDATE movies SET views = views + 1 WHERE code = ?", (text,))
        
        caption = f"🎬 <b>{title}</b>\n\n📝 {description}\n\n👁 Ko'rishlar: {views + 1}"
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🤖 Kino haqida AI dan so'rash", callback_data=f"ai_ask_{text}"))

        try:
            bot.send_video(message.chat.id, file_id, caption=caption, reply_markup=markup)
        except:
            bot.send_document(message.chat.id, file_id, caption=caption, reply_markup=markup)
    else:
        bot.reply_to(message, "❌ Bunday kodli kino topilmadi. Iltimos, to'g'ri kod kiriting yoki <b>🤖 AI bilan muloqot</b> rejimida yordam oling.")

@bot.callback_query_handler(func=lambda call: call.data.startswith("ai_ask_"))
def callback_ai_ask(call):
    code = call.data.replace("ai_ask_", "")
    movie = db_query("SELECT title, description FROM movies WHERE code = ?", (code,), fetchone=True)
    if movie:
        title, description = movie
        prompt = f"Bu kino haqida qiziqarli ma'lumot ber: Nomi: {title}, Tavsif: {description}"
        try:
            response = ai_model.generate_content(prompt)
            bot.answer_callback_query(call.id)
            bot.send_message(call.message.chat.id, f"🤖 <b>AI sharhi ({title}):</b>\n\n{response.text}")
        except Exception as e:
            bot.answer_callback_query(call.id, "Xatolik yuz berdi!", show_alert=True)

# ==================== ADMIN PANEL ====================
@bot.message_handler(commands=['admin'])
def admin_panel(message):
    if message.from_user.id != ADMIN_ID:
        return
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("➕ Kino qo'shish", callback_data="adm_add_movie"),
        types.InlineKeyboardButton("🗑 Kino o'chirish", callback_data="adm_del_movie"),
        types.InlineKeyboardButton("📊 Statistika", callback_data="adm_stats"),
        types.InlineKeyboardButton("📢 Reklama yuborish", callback_data="adm_broadcast")
    )
    bot.send_message(message.chat.id, "👑 <b>Admin panelga xush kelibsiz!</b>", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("adm_"))
def admin_callbacks(call):
    if call.from_user.id != ADMIN_ID:
        return
    
    if call.data == "adm_stats":
        users_count = db_query("SELECT COUNT(*) FROM users", fetchone=True)[0]
        movies_count = db_query("SELECT COUNT(*) FROM movies", fetchone=True)[0]
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, f"📊 <b>Statistika:</b>\n\n👥 Foydalanuvchilar: {users_count}\n🎬 Kinolar soni: {movies_count}")
    
    elif call.data == "adm_add_movie":
        bot.send_message(call.message.chat.id, "Kino qo'shish uchun quyidagi formatda yuboring:\n\n<code>KOD | NOMI | TAVSIFI | VIDEO_FILE_ID</code>")

# ==================== BOTNI ISHGA TUSHIRISH ====================
if __name__ == '__main__':
    logging.info("Bot ishga tushdi...")
    print("Bot ishga tushdi...")
    while True:
        try:
            bot.infinity_polling(skip_pending=True, timeout=60)
        except Exception as e:
            logging.error(f"Polling xatosi: {e}")
            time.sleep(3)
