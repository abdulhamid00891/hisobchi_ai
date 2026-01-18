"""
Hisobchi Bot - O'zbekcha moliyaviy hisobchi Telegram bot
Barcha kodlar bitta faylda - Railway deploy uchun
"""
import os
import asyncio
import logging
import re
import tempfile
from datetime import datetime, date, timedelta

import aiosqlite
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ConversationHandler, ContextTypes, filters
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# ============== CONFIG ==============
BOT_TOKEN = os.getenv("BOT_TOKEN", "8450831935:AAGhmhvWFmQH-4AOrOUFyDfiv_ufJYvXztw")
REMINDER_DAYS = [3, 1, 0]
DB_PATH = "hisobchi.db"

# Logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Conversation states
(DEBT_SELECT_CONTACT, DEBT_NAME, DEBT_PHONE, DEBT_AMOUNT, DEBT_PAYMENT_TYPE, DEBT_GIVEN_DATE, 
 DEBT_DUE_DATE, DEBT_INSTALLMENTS, DEBT_CONFIRM, DEBT_PARTIAL_PAYMENT, DEBT_EDIT_FIELD, DEBT_EDIT_VALUE) = range(12)
EXPENSE_DESCRIPTION, EXPENSE_AMOUNT, EXPENSE_CATEGORY = range(12, 15)

# ============== KEYBOARDS ==============
def main_menu_keyboard():
    keyboard = [
        [KeyboardButton("💰 Qarz berdim"), KeyboardButton("💸 Qarz oldim")],
        [KeyboardButton("📝 Kunlik harajat"), KeyboardButton("📋 Harajatlar tarixi")],
        [KeyboardButton("📊 Statistika"), KeyboardButton("📋 Mening qarzlarim")],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def payment_type_keyboard():
    keyboard = [
        [InlineKeyboardButton("💵 Bir marta to'lash", callback_data="payment_one_time")],
        [InlineKeyboardButton("📅 Bo'lib to'lash", callback_data="payment_installment")]
    ]
    return InlineKeyboardMarkup(keyboard)

def date_keyboard():
    keyboard = [
        [InlineKeyboardButton("📅 Bugun", callback_data="date_today")],
        [InlineKeyboardButton("✏️ Boshqa sana", callback_data="date_custom")]
    ]
    return InlineKeyboardMarkup(keyboard)

def confirm_keyboard():
    keyboard = [
        [InlineKeyboardButton("✅ Tasdiqlash", callback_data="confirm_yes"),
         InlineKeyboardButton("❌ Bekor qilish", callback_data="confirm_no")]
    ]
    return InlineKeyboardMarkup(keyboard)

def my_debts_keyboard():
    keyboard = [
        [InlineKeyboardButton("💰 Bergan qarzlarim", callback_data="view_given")],
        [InlineKeyboardButton("💸 Olgan qarzlarim", callback_data="view_taken")],
        [InlineKeyboardButton("🔙 Orqaga", callback_data="back_main")]
    ]
    return InlineKeyboardMarkup(keyboard)

def expense_category_keyboard():
    keyboard = [
        [InlineKeyboardButton("🍔 Oziq-ovqat", callback_data="cat_food"),
         InlineKeyboardButton("🚗 Transport", callback_data="cat_transport")],
        [InlineKeyboardButton("🏠 Uy-joy", callback_data="cat_home"),
         InlineKeyboardButton("👕 Kiyim", callback_data="cat_clothes")],
        [InlineKeyboardButton("💊 Sog'liq", callback_data="cat_health"),
         InlineKeyboardButton("📦 Boshqa", callback_data="cat_other")]
    ]
    return InlineKeyboardMarkup(keyboard)

def installment_count_keyboard():
    keyboard = [
        [InlineKeyboardButton("2 oy", callback_data="inst_2"),
         InlineKeyboardButton("3 oy", callback_data="inst_3"),
         InlineKeyboardButton("6 oy", callback_data="inst_6")],
        [InlineKeyboardButton("12 oy", callback_data="inst_12")]
    ]
    return InlineKeyboardMarkup(keyboard)

def debt_list_keyboard(debts, page=0):
    keyboard = []
    for debt in debts[:10]:
        status = "✅" if debt['is_paid'] else "⏳"
        text = f"{status} {debt['person_name']} - {debt['amount']:,.0f} {debt['currency']}"
        keyboard.append([InlineKeyboardButton(text, callback_data=f"debt_{debt['id']}")])
    keyboard.append([InlineKeyboardButton("🔙 Orqaga", callback_data="back_main")])
    return InlineKeyboardMarkup(keyboard)

def debt_action_keyboard(debt_id, debt_type, is_paid=False):
    keyboard = []
    if not is_paid:
        # Repayment buttons based on debt type
        if debt_type == 'given':
            keyboard.append([InlineKeyboardButton("💵 Qarzini berdi", callback_data=f"repay_{debt_id}")])
        else:
            keyboard.append([InlineKeyboardButton("💵 Qarzimni berdim", callback_data=f"repay_{debt_id}")])
        keyboard.append([InlineKeyboardButton("✅ To'liq to'landi", callback_data=f"mark_paid_{debt_id}")])
    keyboard.append([InlineKeyboardButton("✏️ Tahrirlash", callback_data=f"edit_debt_{debt_id}")])
    keyboard.append([InlineKeyboardButton("🗑 O'chirish", callback_data=f"delete_debt_{debt_id}")])
    keyboard.append([InlineKeyboardButton("🔙 Orqaga", callback_data="back_debts")])
    return InlineKeyboardMarkup(keyboard)

def debt_edit_keyboard(debt_id):
    keyboard = [
        [InlineKeyboardButton("👤 Ismni o'zgartirish", callback_data=f"editfield_name_{debt_id}")],
        [InlineKeyboardButton("📱 Telefonni o'zgartirish", callback_data=f"editfield_phone_{debt_id}")],
        [InlineKeyboardButton("💵 Summani o'zgartirish", callback_data=f"editfield_amount_{debt_id}")],
        [InlineKeyboardButton("⏰ Muddatni o'zgartirish", callback_data=f"editfield_due_{debt_id}")],
        [InlineKeyboardButton("🔙 Orqaga", callback_data=f"debt_{debt_id}")]
    ]
    return InlineKeyboardMarkup(keyboard)

def delete_confirm_keyboard(debt_id):
    keyboard = [
        [InlineKeyboardButton("✅ Ha, o'chirish", callback_data=f"confirm_delete_{debt_id}"),
         InlineKeyboardButton("❌ Yo'q", callback_data=f"debt_{debt_id}")]
    ]
    return InlineKeyboardMarkup(keyboard)

def expense_list_keyboard(expenses):
    keyboard = []
    category_emojis = {'food': '🍔', 'transport': '🚗', 'home': '🏠', 'clothes': '👕', 'health': '💊', 'other': '📦'}
    for exp in expenses[:15]:
        emoji = category_emojis.get(exp.get('category', 'other'), '📦')
        exp_date = exp['expense_date'][:10] if exp.get('expense_date') else ""
        text = f"{emoji} {exp['description'][:15]} - {exp['amount']:,.0f}"
        keyboard.append([InlineKeyboardButton(text, callback_data=f"expense_{exp['id']}")])
    keyboard.append([InlineKeyboardButton("🔙 Orqaga", callback_data="back_main")])
    return InlineKeyboardMarkup(keyboard)

def expense_action_keyboard(expense_id):
    keyboard = [
        [InlineKeyboardButton("🗑 O'chirish", callback_data=f"delete_expense_{expense_id}")],
        [InlineKeyboardButton("🔙 Orqaga", callback_data="back_expenses")]
    ]
    return InlineKeyboardMarkup(keyboard)

def expense_delete_confirm_keyboard(expense_id):
    keyboard = [
        [InlineKeyboardButton("✅ Ha, o'chirish", callback_data=f"confirm_del_exp_{expense_id}"),
         InlineKeyboardButton("❌ Yo'q", callback_data=f"expense_{expense_id}")]
    ]
    return InlineKeyboardMarkup(keyboard)

# ============== UTILS ==============
def format_money(amount, currency):
    if currency == "UZS":
        return f"{amount:,.0f} so'm"
    return f"${amount:,.2f}"

def parse_amount(text):
    text = text.strip().upper()
    if '$' in text:
        amount = re.sub(r'[^\d.]', '', text)
        return float(amount) if amount else None, 'USD'
    if 'USD' in text:
        amount = re.sub(r'[^\d.]', '', text.replace('USD', ''))
        return float(amount) if amount else None, 'USD'
    if 'UZS' in text or "SO'M" in text or "SOM" in text:
        amount = re.sub(r'[^\d.]', '', text)
        return float(amount) if amount else None, 'UZS'
    amount = re.sub(r'[^\d.]', '', text)
    return (float(amount), 'UZS') if amount else (None, None)

def parse_date(text):
    formats = ['%d.%m.%Y', '%d/%m/%Y', '%d-%m-%Y', '%Y-%m-%d', '%d.%m.%y']
    for fmt in formats:
        try:
            return datetime.strptime(text.strip(), fmt).date()
        except ValueError:
            continue
    return None

def format_date(d):
    if d is None:
        return "Belgilanmagan"
    if isinstance(d, str):
        d = datetime.fromisoformat(d).date()
    return d.strftime('%d.%m.%Y')

def days_until(target_date):
    if isinstance(target_date, str):
        target_date = datetime.fromisoformat(target_date).date()
    return (target_date - date.today()).days

# ============== DATABASE ==============
async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE NOT NULL,
                full_name TEXT,
                username TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS debts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                person_name TEXT NOT NULL,
                phone_number TEXT,
                amount REAL NOT NULL,
                currency TEXT DEFAULT 'UZS',
                debt_type TEXT NOT NULL,
                payment_type TEXT DEFAULT 'one_time',
                given_date DATE,
                due_date DATE,
                is_paid INTEGER DEFAULT 0,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Add phone_number column if not exists (for existing databases)
        try:
            await db.execute("ALTER TABLE debts ADD COLUMN phone_number TEXT")
        except:
            pass
        await db.execute("""
            CREATE TABLE IF NOT EXISTS daily_expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                description TEXT,
                amount REAL NOT NULL,
                currency TEXT DEFAULT 'UZS',
                category TEXT,
                expense_date DATE DEFAULT CURRENT_DATE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()

async def get_or_create_user(telegram_id, full_name, username=None):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
        user = await cursor.fetchone()
        if user:
            return dict(user)
        await db.execute("INSERT INTO users (telegram_id, full_name, username) VALUES (?, ?, ?)",
                        (telegram_id, full_name, username))
        await db.commit()
        cursor = await db.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
        return dict(await cursor.fetchone())

async def add_debt(user_id, person_name, phone_number, amount, currency, debt_type, payment_type, given_date, due_date):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            INSERT INTO debts (user_id, person_name, phone_number, amount, currency, debt_type, payment_type, given_date, due_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (user_id, person_name, phone_number, amount, currency, debt_type, payment_type, given_date, due_date))
        await db.commit()
        return cursor.lastrowid

async def get_previous_contacts(user_id):
    """Get list of previous contacts (people user has given/taken debts from)"""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            SELECT DISTINCT person_name, phone_number FROM debts 
            WHERE user_id = ? 
            ORDER BY created_at DESC
            LIMIT 10
        """, (user_id,))
        return await cursor.fetchall()

async def get_debts_by_type(user_id, debt_type):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("""
            SELECT * FROM debts WHERE user_id = ? AND debt_type = ? AND is_paid = 0
            ORDER BY due_date ASC
        """, (user_id, debt_type))
        return [dict(row) for row in await cursor.fetchall()]

async def get_debt_by_id(debt_id):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM debts WHERE id = ?", (debt_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None

async def mark_debt_paid(debt_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE debts SET is_paid = 1 WHERE id = ?", (debt_id,))
        await db.commit()

async def delete_debt(debt_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM debts WHERE id = ?", (debt_id,))
        await db.commit()

async def update_debt_amount(debt_id, new_amount):
    """Update debt amount after partial payment"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE debts SET amount = ? WHERE id = ?", (new_amount, debt_id))
        await db.commit()

async def update_debt_field(debt_id, field, value):
    """Update a specific field of a debt"""
    allowed_fields = ['person_name', 'phone_number', 'amount', 'due_date']
    if field not in allowed_fields:
        return False
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(f"UPDATE debts SET {field} = ? WHERE id = ?", (value, debt_id))
        await db.commit()
        return True

async def add_expense(user_id, description, amount, currency, category):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO daily_expenses (user_id, description, amount, currency, category, expense_date)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, description, amount, currency, category, date.today()))
        await db.commit()

async def get_expenses(user_id, limit=20):
    """Get recent expenses for a user"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("""
            SELECT * FROM daily_expenses WHERE user_id = ? 
            ORDER BY expense_date DESC, id DESC LIMIT ?
        """, (user_id, limit))
        return [dict(row) for row in await cursor.fetchall()]

async def get_expense_by_id(expense_id):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM daily_expenses WHERE id = ?", (expense_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None

async def delete_expense(expense_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM daily_expenses WHERE id = ?", (expense_id,))
        await db.commit()

async def get_statistics(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        stats = {'given_active': {}, 'taken_active': {}, 'given_count': 0, 'taken_count': 0, 
                 'monthly_expenses': {}, 'today_expenses': {}}
        cursor = await db.execute("""
            SELECT currency, SUM(amount) FROM debts WHERE user_id = ? AND debt_type = 'given' AND is_paid = 0 GROUP BY currency
        """, (user_id,))
        stats['given_active'] = {row[0]: row[1] for row in await cursor.fetchall()}
        
        cursor = await db.execute("""
            SELECT currency, SUM(amount) FROM debts WHERE user_id = ? AND debt_type = 'taken' AND is_paid = 0 GROUP BY currency
        """, (user_id,))
        stats['taken_active'] = {row[0]: row[1] for row in await cursor.fetchall()}
        
        cursor = await db.execute("SELECT COUNT(*) FROM debts WHERE user_id = ? AND debt_type = 'given' AND is_paid = 0", (user_id,))
        stats['given_count'] = (await cursor.fetchone())[0]
        
        cursor = await db.execute("SELECT COUNT(*) FROM debts WHERE user_id = ? AND debt_type = 'taken' AND is_paid = 0", (user_id,))
        stats['taken_count'] = (await cursor.fetchone())[0]
        
        today = date.today()
        cursor = await db.execute("""
            SELECT currency, SUM(amount) FROM daily_expenses WHERE user_id = ? AND expense_date = ? GROUP BY currency
        """, (user_id, today))
        stats['today_expenses'] = {row[0]: row[1] for row in await cursor.fetchall()}
        
        cursor = await db.execute("""
            SELECT currency, SUM(amount) FROM daily_expenses WHERE user_id = ? AND strftime('%Y-%m', expense_date) = ? GROUP BY currency
        """, (user_id, today.strftime('%Y-%m')))
        stats['monthly_expenses'] = {row[0]: row[1] for row in await cursor.fetchall()}
        
        return stats

# ============== HANDLERS ==============
WELCOME_MESSAGE = """
🎉 <b>Assalomu alaykum, {name}!</b>

🤖 Men sizning shaxsiy <b>Hisobchi Bot</b>ingizman!

✨ <b>Mening afzalliklarim:</b>
• 💰 Qarz oldi-berdi hisobini yuritish
• 📝 Kunlik harajatlarni nazorat qilish
• 📊 Statistika va hisobotlar

<i>Quyidagi tugmalardan birini tanlang:</i>
"""

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await get_or_create_user(user.id, user.full_name, user.username)
    await update.message.reply_html(WELCOME_MESSAGE.format(name=user.first_name), reply_markup=main_menu_keyboard())
    return ConversationHandler.END

async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("❌ Bekor qilindi.", reply_markup=main_menu_keyboard())
    return ConversationHandler.END

# DEBT HANDLERS
def previous_contacts_keyboard(contacts):
    """Create keyboard with previous contacts"""
    keyboard = []
    for name, phone in contacts:
        phone_text = f" ({phone})" if phone else ""
        keyboard.append([InlineKeyboardButton(f"👤 {name}{phone_text}", callback_data=f"contact_{name}|{phone or ''}")])
    keyboard.append([InlineKeyboardButton("➕ Yangi kontakt", callback_data="contact_new")])
    return InlineKeyboardMarkup(keyboard)

async def debt_given_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['debt_type'] = 'given'
    context.user_data['debt_data'] = {}
    
    user = update.effective_user
    db_user = await get_or_create_user(user.id, user.full_name, user.username)
    contacts = await get_previous_contacts(db_user['id'])
    
    if contacts:
        await update.message.reply_text(
            "💰 <b>Qarz berdim</b>\n\nAvvalgi kontaktlardan tanlang yoki yangi kiriting:",
            parse_mode='HTML',
            reply_markup=previous_contacts_keyboard(contacts)
        )
        return DEBT_SELECT_CONTACT
    else:
        await update.message.reply_text("💰 <b>Qarz berdim</b>\n\nQarz oluvchining <b>ismini</b> kiriting:", parse_mode='HTML')
        return DEBT_NAME

async def debt_taken_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['debt_type'] = 'taken'
    context.user_data['debt_data'] = {}
    
    user = update.effective_user
    db_user = await get_or_create_user(user.id, user.full_name, user.username)
    contacts = await get_previous_contacts(db_user['id'])
    
    if contacts:
        await update.message.reply_text(
            "💸 <b>Qarz oldim</b>\n\nAvvalgi kontaktlardan tanlang yoki yangi kiriting:",
            parse_mode='HTML',
            reply_markup=previous_contacts_keyboard(contacts)
        )
        return DEBT_SELECT_CONTACT
    else:
        await update.message.reply_text("💸 <b>Qarz oldim</b>\n\nQarz beruvchining <b>ismini</b> kiriting:", parse_mode='HTML')
        return DEBT_NAME

async def debt_select_contact_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "contact_new":
        debt_type = context.user_data['debt_type']
        if debt_type == 'given':
            await query.edit_message_text("💰 <b>Qarz berdim</b>\n\nQarz oluvchining <b>ismini</b> kiriting:", parse_mode='HTML')
        else:
            await query.edit_message_text("💸 <b>Qarz oldim</b>\n\nQarz beruvchining <b>ismini</b> kiriting:", parse_mode='HTML')
        return DEBT_NAME
    
    # Parse selected contact
    data = query.data.replace("contact_", "")
    parts = data.split("|")
    name = parts[0]
    phone = parts[1] if len(parts) > 1 and parts[1] else None
    
    context.user_data['debt_data']['person_name'] = name
    context.user_data['debt_data']['phone_number'] = phone
    
    phone_text = phone if phone else "Raqam yo'q"
    await query.edit_message_text(
        f"👤 <b>{name}</b>\n📱 {phone_text}\n\nSummani kiriting:\n<i>Masalan: 100 USD, 500000</i>",
        parse_mode='HTML'
    )
    return DEBT_AMOUNT

async def debt_name_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    if len(name) < 2:
        await update.message.reply_text("❌ Ism juda qisqa!")
        return DEBT_NAME
    context.user_data['debt_data']['person_name'] = name
    await update.message.reply_text(
        f"👤 <b>{name}</b>\n\n📱 Telefon raqamini kiriting:\n<i>Masalan: +998901234567</i>\n\n<i>O'tkazib yuborish uchun \"yo'q\" yozing</i>",
        parse_mode='HTML'
    )
    return DEBT_PHONE

async def debt_phone_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phone = update.message.text.strip()
    
    # Skip if user types "yo'q" or similar
    if phone.lower() in ["yo'q", "yoq", "yo`q", "-", "0"]:
        context.user_data['debt_data']['phone_number'] = None
    else:
        # Clean phone number
        phone = re.sub(r'[^\d+]', '', phone)
        if len(phone) < 9:
            await update.message.reply_text("❌ Telefon raqamini to'g'ri kiriting!\n<i>Masalan: +998901234567</i>", parse_mode='HTML')
            return DEBT_PHONE
        context.user_data['debt_data']['phone_number'] = phone
    
    name = context.user_data['debt_data']['person_name']
    phone_display = context.user_data['debt_data'].get('phone_number') or "Kiritilmadi"
    await update.message.reply_text(
        f"👤 <b>{name}</b>\n📱 {phone_display}\n\nSummani kiriting:\n<i>Masalan: 100 USD, 500000</i>",
        parse_mode='HTML'
    )
    return DEBT_AMOUNT

async def debt_amount_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    amount, currency = parse_amount(update.message.text)
    if amount is None or amount <= 0:
        await update.message.reply_text("❌ Summani to'g'ri kiriting!")
        return DEBT_AMOUNT
    context.user_data['debt_data']['amount'] = amount
    context.user_data['debt_data']['currency'] = currency
    await update.message.reply_text(f"💵 {format_money(amount, currency)}\n\nTo'lov turini tanlang:", 
                                   parse_mode='HTML', reply_markup=payment_type_keyboard())
    return DEBT_PAYMENT_TYPE

async def debt_payment_type_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['debt_data']['payment_type'] = 'one_time' if query.data == "payment_one_time" else 'installment'
    await query.edit_message_text("Qarz berilgan sanani tanlang:", reply_markup=date_keyboard())
    return DEBT_GIVEN_DATE

async def debt_given_date_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "date_today":
        context.user_data['debt_data']['given_date'] = date.today()
        await query.edit_message_text(f"📅 Berilgan: {format_date(date.today())}\n\nQaytarish muddatini kiriting:\n<i>Masalan: 25.02.2026</i>", parse_mode='HTML')
        return DEBT_DUE_DATE
    await query.edit_message_text("Berilgan sanani kiriting:\n<i>Masalan: 17.01.2026</i>", parse_mode='HTML')
    return DEBT_GIVEN_DATE

async def debt_given_date_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    parsed = parse_date(update.message.text)
    if not parsed:
        await update.message.reply_text("❌ Sanani to'g'ri kiriting!")
        return DEBT_GIVEN_DATE
    context.user_data['debt_data']['given_date'] = parsed
    await update.message.reply_text(f"📅 Berilgan: {format_date(parsed)}\n\nQaytarish muddatini kiriting:", parse_mode='HTML')
    return DEBT_DUE_DATE

async def debt_due_date_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    parsed = parse_date(update.message.text)
    if not parsed:
        await update.message.reply_text("❌ Sanani to'g'ri kiriting!")
        return DEBT_DUE_DATE
    context.user_data['debt_data']['due_date'] = parsed
    
    if context.user_data['debt_data']['payment_type'] == 'installment':
        await update.message.reply_text("Necha oyga bo'lib to'lanadi?", reply_markup=installment_count_keyboard())
        return DEBT_INSTALLMENTS
    
    return await show_debt_confirmation(update, context)

async def debt_installments_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    months = int(query.data.replace("inst_", ""))
    context.user_data['debt_data']['installment_months'] = months
    return await show_debt_confirmation(update, context, is_callback=True)

async def show_debt_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE, is_callback=False):
    data = context.user_data['debt_data']
    debt_type = context.user_data['debt_type']
    type_text = "💰 QARZ BERDIM" if debt_type == 'given' else "💸 QARZ OLDIM"
    phone_display = data.get('phone_number') or "Kiritilmadi"
    
    text = f"""
<b>{type_text}</b>

👤 <b>Shaxs:</b> {data['person_name']}
📱 <b>Telefon:</b> {phone_display}
💵 <b>Summa:</b> {format_money(data['amount'], data['currency'])}
📅 <b>Berilgan:</b> {format_date(data['given_date'])}
⏰ <b>Muddat:</b> {format_date(data['due_date'])}

<b>Tasdiqlaysizmi?</b>
"""
    if is_callback:
        await update.callback_query.edit_message_text(text, parse_mode='HTML', reply_markup=confirm_keyboard())
    else:
        await update.message.reply_text(text, parse_mode='HTML', reply_markup=confirm_keyboard())
    return DEBT_CONFIRM

async def debt_confirm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "confirm_no":
        context.user_data.clear()
        await query.edit_message_text("❌ Bekor qilindi.")
        await query.message.reply_text("Asosiy menyu:", reply_markup=main_menu_keyboard())
        return ConversationHandler.END
    
    user = update.effective_user
    db_user = await get_or_create_user(user.id, user.full_name, user.username)
    data = context.user_data['debt_data']
    
    await add_debt(db_user['id'], data['person_name'], data.get('phone_number'), data['amount'], data['currency'],
                   context.user_data['debt_type'], data['payment_type'], data['given_date'], data['due_date'])
    
    context.user_data.clear()
    await query.edit_message_text("✅ <b>Saqlandi!</b>", parse_mode='HTML')
    await query.message.reply_text("Asosiy menyu:", reply_markup=main_menu_keyboard())
    return ConversationHandler.END

# EXPENSE HANDLERS
async def expense_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['expense_data'] = {}
    await update.message.reply_text("📝 <b>Kunlik harajat</b>\n\nTavsifini kiriting:\n<i>Masalan: Tushlik, Taksi</i>", parse_mode='HTML')
    return EXPENSE_DESCRIPTION

async def expense_description_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['expense_data']['description'] = update.message.text.strip()
    await update.message.reply_text("Summani kiriting:\n<i>Masalan: 50000, 10 USD</i>", parse_mode='HTML')
    return EXPENSE_AMOUNT

async def expense_amount_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    amount, currency = parse_amount(update.message.text)
    if amount is None or amount <= 0:
        await update.message.reply_text("❌ Summani to'g'ri kiriting!")
        return EXPENSE_AMOUNT
    context.user_data['expense_data']['amount'] = amount
    context.user_data['expense_data']['currency'] = currency
    await update.message.reply_text("Kategoriya tanlang:", reply_markup=expense_category_keyboard())
    return EXPENSE_CATEGORY

async def expense_category_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user = update.effective_user
    db_user = await get_or_create_user(user.id, user.full_name, user.username)
    data = context.user_data['expense_data']
    category = query.data.replace("cat_", "")
    
    await add_expense(db_user['id'], data['description'], data['amount'], data['currency'], category)
    context.user_data.clear()
    
    await query.edit_message_text(f"✅ <b>Saqlandi!</b>\n\n📝 {data['description']}\n💵 {format_money(data['amount'], data['currency'])}", parse_mode='HTML')
    await query.message.reply_text("Asosiy menyu:", reply_markup=main_menu_keyboard())
    return ConversationHandler.END

# VIEW HANDLERS
async def my_debts_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📋 <b>Mening qarzlarim</b>", parse_mode='HTML', reply_markup=my_debts_keyboard())

async def view_debts_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user = update.effective_user
    db_user = await get_or_create_user(user.id, user.full_name, user.username)
    
    debt_type = 'given' if query.data == "view_given" else 'taken'
    title = "💰 Bergan qarzlarim" if debt_type == 'given' else "💸 Olgan qarzlarim"
    context.user_data['current_debt_type'] = debt_type
    
    debts = await get_debts_by_type(db_user['id'], debt_type)
    
    if not debts:
        await query.edit_message_text(f"{title}\n\n📭 Qarz yo'q.", reply_markup=my_debts_keyboard())
        return
    
    total_usd = sum(d['amount'] for d in debts if d['currency'] == 'USD')
    total_uzs = sum(d['amount'] for d in debts if d['currency'] == 'UZS')
    
    text = f"<b>{title}</b>\n\n"
    if total_usd: text += f"💵 USD: {format_money(total_usd, 'USD')}\n"
    if total_uzs: text += f"💵 UZS: {format_money(total_uzs, 'UZS')}\n"
    text += f"\n📌 {len(debts)} ta qarz"
    
    await query.edit_message_text(text, parse_mode='HTML', reply_markup=debt_list_keyboard(debts))

async def view_debt_detail_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    debt_id = int(query.data.replace("debt_", ""))
    debt = await get_debt_by_id(debt_id)
    
    if not debt:
        await query.edit_message_text("❌ Qarz topilmadi.")
        return
    
    days = days_until(debt['due_date'])
    status = "✅ To'langan" if debt['is_paid'] else f"📆 {days} kun qoldi" if days >= 0 else f"🔴 {abs(days)} kun o'tdi"
    phone_display = debt.get('phone_number') or "Kiritilmagan"
    
    text = f"""
👤 <b>{debt['person_name']}</b>
📱 Telefon: {phone_display}
💰 {format_money(debt['amount'], debt['currency'])}
📅 Berilgan: {format_date(debt['given_date'])}
⏰ Muddat: {format_date(debt['due_date'])}
{status}
"""
    await query.edit_message_text(text, parse_mode='HTML', reply_markup=debt_action_keyboard(debt_id, debt['debt_type'], debt['is_paid']))

async def mark_debt_paid_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    debt_id = int(query.data.replace("mark_paid_", ""))
    await mark_debt_paid(debt_id)
    await query.edit_message_text("✅ <b>To'langan deb belgilandi!</b>", parse_mode='HTML')
    await query.message.reply_text("Asosiy menyu:", reply_markup=main_menu_keyboard())

async def delete_debt_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    debt_id = int(query.data.replace("delete_debt_", ""))
    debt = await get_debt_by_id(debt_id)
    if not debt:
        await query.edit_message_text("❌ Qarz topilmadi.")
        return
    await query.edit_message_text(
        f"⚠️ <b>O'chirishni tasdiqlang</b>\n\n👤 {debt['person_name']}\n💰 {format_money(debt['amount'], debt['currency'])}\n\nRostdan ham o'chirmoqchimisiz?",
        parse_mode='HTML',
        reply_markup=delete_confirm_keyboard(debt_id)
    )

async def confirm_delete_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    debt_id = int(query.data.replace("confirm_delete_", ""))
    await delete_debt(debt_id)
    await query.edit_message_text("🗑 <b>O'chirildi!</b>", parse_mode='HTML')
    await query.message.reply_text("Asosiy menyu:", reply_markup=main_menu_keyboard())

# REPAYMENT HANDLERS
async def repay_debt_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    debt_id = int(query.data.replace("repay_", ""))
    debt = await get_debt_by_id(debt_id)
    
    if not debt:
        await query.edit_message_text("❌ Qarz topilmadi.")
        return
    
    context.user_data['repay_debt_id'] = debt_id
    context.user_data['repay_debt'] = debt
    
    await query.edit_message_text(
        f"💵 <b>Qarzdorlikni so'ndirish</b>\n\n"
        f"👤 {debt['person_name']}\n"
        f"💰 Jami qarz: {format_money(debt['amount'], debt['currency'])}\n\n"
        f"Qancha to'landi? Summani kiriting:\n"
        f"<i>Masalan: 50000 yoki 100 USD</i>\n\n"
        f"<i>To'liq to'landi bo'lsa, summa o'rniga 'hammasi' yozing</i>",
        parse_mode='HTML'
    )
    return DEBT_PARTIAL_PAYMENT

async def repay_amount_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().lower()
    debt_id = context.user_data.get('repay_debt_id')
    debt = context.user_data.get('repay_debt')
    
    if not debt_id or not debt:
        await update.message.reply_text("❌ Xatolik yuz berdi.", reply_markup=main_menu_keyboard())
        return ConversationHandler.END
    
    if text in ['hammasi', 'hamma', 'toliq', "to'liq", 'all']:
        # Full payment
        await mark_debt_paid(debt_id)
        context.user_data.clear()
        await update.message.reply_text(
            f"✅ <b>To'liq to'landi!</b>\n\n👤 {debt['person_name']}\n💰 {format_money(debt['amount'], debt['currency'])}",
            parse_mode='HTML',
            reply_markup=main_menu_keyboard()
        )
        return ConversationHandler.END
    
    paid_amount, currency = parse_amount(text)
    if paid_amount is None or paid_amount <= 0:
        await update.message.reply_text("❌ Summani to'g'ri kiriting!")
        return DEBT_PARTIAL_PAYMENT
    
    # Check if currencies match or convert
    if currency != debt['currency']:
        await update.message.reply_text(f"❌ Valyuta mos emas! Qarz {debt['currency']} da.")
        return DEBT_PARTIAL_PAYMENT
    
    remaining = debt['amount'] - paid_amount
    
    if remaining <= 0:
        # Full payment
        await mark_debt_paid(debt_id)
        context.user_data.clear()
        await update.message.reply_text(
            f"✅ <b>To'liq to'landi!</b>\n\n👤 {debt['person_name']}\n💰 {format_money(debt['amount'], debt['currency'])}",
            parse_mode='HTML',
            reply_markup=main_menu_keyboard()
        )
    else:
        # Partial payment
        await update_debt_amount(debt_id, remaining)
        context.user_data.clear()
        await update.message.reply_text(
            f"✅ <b>To'lov qabul qilindi!</b>\n\n"
            f"👤 {debt['person_name']}\n"
            f"💵 To'langan: {format_money(paid_amount, currency)}\n"
            f"💰 Qolgan qarz: {format_money(remaining, currency)}",
            parse_mode='HTML',
            reply_markup=main_menu_keyboard()
        )
    return ConversationHandler.END

# EDIT HANDLERS
async def edit_debt_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    debt_id = int(query.data.replace("edit_debt_", ""))
    debt = await get_debt_by_id(debt_id)
    
    if not debt:
        await query.edit_message_text("❌ Qarz topilmadi.")
        return
    
    await query.edit_message_text(
        f"✏️ <b>Tahrirlash</b>\n\n"
        f"👤 {debt['person_name']}\n"
        f"📱 {debt.get('phone_number') or 'Kiritilmagan'}\n"
        f"💰 {format_money(debt['amount'], debt['currency'])}\n"
        f"⏰ {format_date(debt['due_date'])}\n\n"
        f"Nimani o'zgartirmoqchisiz?",
        parse_mode='HTML',
        reply_markup=debt_edit_keyboard(debt_id)
    )

async def edit_field_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data.replace("editfield_", "")
    field, debt_id = data.rsplit("_", 1)
    debt_id = int(debt_id)
    
    context.user_data['edit_debt_id'] = debt_id
    context.user_data['edit_field'] = field
    
    field_names = {
        'name': ('👤 Yangi ismni kiriting:', 'person_name'),
        'phone': ('📱 Yangi telefon raqamini kiriting:', 'phone_number'),
        'amount': ('💵 Yangi summani kiriting:', 'amount'),
        'due': ('⏰ Yangi muddatni kiriting (kun.oy.yil):', 'due_date')
    }
    
    prompt, db_field = field_names.get(field, ('Yangi qiymatni kiriting:', field))
    context.user_data['edit_db_field'] = db_field
    
    await query.edit_message_text(prompt, parse_mode='HTML')
    return DEBT_EDIT_VALUE

async def edit_value_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    debt_id = context.user_data.get('edit_debt_id')
    field = context.user_data.get('edit_field')
    db_field = context.user_data.get('edit_db_field')
    
    if not debt_id or not field:
        await update.message.reply_text("❌ Xatolik yuz berdi.", reply_markup=main_menu_keyboard())
        return ConversationHandler.END
    
    # Validate and process value based on field type
    if field == 'amount':
        amount, currency = parse_amount(text)
        if amount is None or amount <= 0:
            await update.message.reply_text("❌ Summani to'g'ri kiriting!")
            return DEBT_EDIT_VALUE
        value = amount
    elif field == 'due':
        parsed = parse_date(text)
        if not parsed:
            await update.message.reply_text("❌ Sanani to'g'ri kiriting! (kun.oy.yil)")
            return DEBT_EDIT_VALUE
        value = parsed
    elif field == 'phone':
        value = re.sub(r'[^\d+]', '', text) if text.lower() not in ["yo'q", "yoq", "-"] else None
    else:
        value = text
    
    await update_debt_field(debt_id, db_field, value)
    context.user_data.clear()
    
    await update.message.reply_text("✅ <b>O'zgartirildi!</b>", parse_mode='HTML', reply_markup=main_menu_keyboard())
    return ConversationHandler.END

async def statistics_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db_user = await get_or_create_user(user.id, user.full_name, user.username)
    stats = await get_statistics(db_user['id'])
    
    text = "📊 <b>STATISTIKA</b>\n\n"
    text += "💰 <b>Bergan qarzlar:</b>\n"
    if stats['given_active']:
        for c, a in stats['given_active'].items(): text += f"   • {format_money(a, c)}\n"
    else:
        text += "   Yo'q\n"
    
    text += "\n💸 <b>Olgan qarzlar:</b>\n"
    if stats['taken_active']:
        for c, a in stats['taken_active'].items(): text += f"   • {format_money(a, c)}\n"
    else:
        text += "   Yo'q\n"
    
    text += "\n📝 <b>Bugungi harajat:</b>\n"
    if stats['today_expenses']:
        for c, a in stats['today_expenses'].items(): text += f"   • {format_money(a, c)}\n"
    else:
        text += "   Yo'q\n"
    
    text += "\n🗓 <b>Oylik harajat:</b>\n"
    if stats['monthly_expenses']:
        for c, a in stats['monthly_expenses'].items(): text += f"   • {format_money(a, c)}\n"
    else:
        text += "   Yo'q\n"
    
    await update.message.reply_html(text)

async def back_main_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("✅")
    await query.message.reply_text("Asosiy menyu:", reply_markup=main_menu_keyboard())

async def back_debts_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("📋 <b>Mening qarzlarim</b>", parse_mode='HTML', reply_markup=my_debts_keyboard())

# EXPENSE HISTORY HANDLERS
async def expense_history_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db_user = await get_or_create_user(user.id, user.full_name, user.username)
    expenses = await get_expenses(db_user['id'])
    
    if not expenses:
        await update.message.reply_text("📋 <b>Harajatlar tarixi</b>\n\n📭 Harajat topilmadi.", parse_mode='HTML')
        return
    
    # Calculate totals
    total_uzs = sum(e['amount'] for e in expenses if e['currency'] == 'UZS')
    total_usd = sum(e['amount'] for e in expenses if e['currency'] == 'USD')
    
    text = "📋 <b>Harajatlar tarixi</b>\n\n"
    if total_uzs: text += f"💵 Jami UZS: {format_money(total_uzs, 'UZS')}\n"
    if total_usd: text += f"💵 Jami USD: {format_money(total_usd, 'USD')}\n"
    text += f"\n📌 {len(expenses)} ta harajat"
    
    await update.message.reply_text(text, parse_mode='HTML', reply_markup=expense_list_keyboard(expenses))

async def view_expense_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    expense_id = int(query.data.replace("expense_", ""))
    expense = await get_expense_by_id(expense_id)
    
    if not expense:
        await query.edit_message_text("❌ Harajat topilmadi.")
        return
    
    category_names = {'food': 'Oziq-ovqat', 'transport': 'Transport', 'home': 'Uy-joy', 
                      'clothes': 'Kiyim', 'health': "Sog'liq", 'other': 'Boshqa'}
    cat_name = category_names.get(expense.get('category', 'other'), 'Boshqa')
    exp_date = expense['expense_date'][:10] if expense.get('expense_date') else "Noma'lum"
    
    text = f"""
📝 <b>Harajat</b>

📦 <b>Kategoriya:</b> {cat_name}
📄 <b>Tavsif:</b> {expense['description']}
💰 <b>Summa:</b> {format_money(expense['amount'], expense['currency'])}
📅 <b>Sana:</b> {exp_date}
"""
    await query.edit_message_text(text, parse_mode='HTML', reply_markup=expense_action_keyboard(expense_id))

async def delete_expense_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    expense_id = int(query.data.replace("delete_expense_", ""))
    expense = await get_expense_by_id(expense_id)
    
    if not expense:
        await query.edit_message_text("❌ Harajat topilmadi.")
        return
    
    await query.edit_message_text(
        f"⚠️ <b>O'chirishni tasdiqlang</b>\n\n📄 {expense['description']}\n💰 {format_money(expense['amount'], expense['currency'])}\n\nRostdan ham o'chirmoqchimisiz?",
        parse_mode='HTML',
        reply_markup=expense_delete_confirm_keyboard(expense_id)
    )

async def confirm_delete_expense_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    expense_id = int(query.data.replace("confirm_del_exp_", ""))
    await delete_expense(expense_id)
    await query.edit_message_text("🗑 <b>O'chirildi!</b>", parse_mode='HTML')
    await query.message.reply_text("Asosiy menyu:", reply_markup=main_menu_keyboard())

async def back_expenses_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user = update.effective_user
    db_user = await get_or_create_user(user.id, user.full_name, user.username)
    expenses = await get_expenses(db_user['id'])
    
    if not expenses:
        await query.edit_message_text("📋 <b>Harajatlar tarixi</b>\n\n📭 Harajat topilmadi.", parse_mode='HTML')
        return
    
    total_uzs = sum(e['amount'] for e in expenses if e['currency'] == 'UZS')
    total_usd = sum(e['amount'] for e in expenses if e['currency'] == 'USD')
    
    text = "📋 <b>Harajatlar tarixi</b>\n\n"
    if total_uzs: text += f"💵 Jami UZS: {format_money(total_uzs, 'UZS')}\n"
    if total_usd: text += f"💵 Jami USD: {format_money(total_usd, 'USD')}\n"
    text += f"\n📌 {len(expenses)} ta harajat"
    
    await query.edit_message_text(text, parse_mode='HTML', reply_markup=expense_list_keyboard(expenses))

# ============== MAIN ==============
def main():
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Debt given handler
    debt_given_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex(r'^💰 Qarz berdim$'), debt_given_start)],
        states={
            DEBT_SELECT_CONTACT: [CallbackQueryHandler(debt_select_contact_callback, pattern=r'^contact_')],
            DEBT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, debt_name_received)],
            DEBT_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, debt_phone_received)],
            DEBT_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, debt_amount_received)],
            DEBT_PAYMENT_TYPE: [CallbackQueryHandler(debt_payment_type_callback, pattern=r'^payment_')],
            DEBT_GIVEN_DATE: [
                CallbackQueryHandler(debt_given_date_callback, pattern=r'^date_'),
                MessageHandler(filters.TEXT & ~filters.COMMAND, debt_given_date_text)
            ],
            DEBT_DUE_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, debt_due_date_received)],
            DEBT_INSTALLMENTS: [CallbackQueryHandler(debt_installments_callback, pattern=r'^inst_')],
            DEBT_CONFIRM: [CallbackQueryHandler(debt_confirm_callback, pattern=r'^confirm_')]
        },
        fallbacks=[CommandHandler('cancel', cancel_command), CommandHandler('start', start_command)],
        allow_reentry=True
    )
    
    # Debt taken handler
    debt_taken_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex(r'^💸 Qarz oldim$'), debt_taken_start)],
        states={
            DEBT_SELECT_CONTACT: [CallbackQueryHandler(debt_select_contact_callback, pattern=r'^contact_')],
            DEBT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, debt_name_received)],
            DEBT_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, debt_phone_received)],
            DEBT_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, debt_amount_received)],
            DEBT_PAYMENT_TYPE: [CallbackQueryHandler(debt_payment_type_callback, pattern=r'^payment_')],
            DEBT_GIVEN_DATE: [
                CallbackQueryHandler(debt_given_date_callback, pattern=r'^date_'),
                MessageHandler(filters.TEXT & ~filters.COMMAND, debt_given_date_text)
            ],
            DEBT_DUE_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, debt_due_date_received)],
            DEBT_INSTALLMENTS: [CallbackQueryHandler(debt_installments_callback, pattern=r'^inst_')],
            DEBT_CONFIRM: [CallbackQueryHandler(debt_confirm_callback, pattern=r'^confirm_')]
        },
        fallbacks=[CommandHandler('cancel', cancel_command), CommandHandler('start', start_command)],
        allow_reentry=True
    )
    
    # Expense handler
    expense_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex(r'^📝 Kunlik harajat$'), expense_start)],
        states={
            EXPENSE_DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, expense_description_received)],
            EXPENSE_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, expense_amount_received)],
            EXPENSE_CATEGORY: [CallbackQueryHandler(expense_category_callback, pattern=r'^cat_')]
        },
        fallbacks=[CommandHandler('cancel', cancel_command), CommandHandler('start', start_command)],
        allow_reentry=True
    )
    
    # Repayment handler
    repay_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(repay_debt_callback, pattern=r'^repay_')],
        states={
            DEBT_PARTIAL_PAYMENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, repay_amount_received)]
        },
        fallbacks=[CommandHandler('cancel', cancel_command), CommandHandler('start', start_command)],
        allow_reentry=True
    )
    
    # Edit handler
    edit_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(edit_field_callback, pattern=r'^editfield_')],
        states={
            DEBT_EDIT_VALUE: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_value_received)]
        },
        fallbacks=[CommandHandler('cancel', cancel_command), CommandHandler('start', start_command)],
        allow_reentry=True
    )
    
    # Add handlers
    application.add_handler(CommandHandler('start', start_command))
    application.add_handler(CommandHandler('cancel', cancel_command))
    application.add_handler(debt_given_handler)
    application.add_handler(debt_taken_handler)
    application.add_handler(expense_handler)
    application.add_handler(repay_handler)
    application.add_handler(edit_handler)
    application.add_handler(MessageHandler(filters.Regex(r'^📊 Statistika$'), statistics_handler))
    application.add_handler(MessageHandler(filters.Regex(r'^📋 Mening qarzlarim$'), my_debts_handler))
    application.add_handler(MessageHandler(filters.Regex(r'^📋 Harajatlar tarixi$'), expense_history_handler))
    application.add_handler(CallbackQueryHandler(view_debts_callback, pattern=r'^view_'))
    application.add_handler(CallbackQueryHandler(view_debt_detail_callback, pattern=r'^debt_\d+$'))
    application.add_handler(CallbackQueryHandler(mark_debt_paid_callback, pattern=r'^mark_paid_'))
    application.add_handler(CallbackQueryHandler(delete_debt_callback, pattern=r'^delete_debt_'))
    application.add_handler(CallbackQueryHandler(confirm_delete_callback, pattern=r'^confirm_delete_'))
    application.add_handler(CallbackQueryHandler(edit_debt_callback, pattern=r'^edit_debt_'))
    application.add_handler(CallbackQueryHandler(view_expense_callback, pattern=r'^expense_\d+$'))
    application.add_handler(CallbackQueryHandler(delete_expense_callback, pattern=r'^delete_expense_'))
    application.add_handler(CallbackQueryHandler(confirm_delete_expense_callback, pattern=r'^confirm_del_exp_'))
    application.add_handler(CallbackQueryHandler(back_expenses_callback, pattern=r'^back_expenses$'))
    application.add_handler(CallbackQueryHandler(back_main_callback, pattern=r'^back_main$'))
    application.add_handler(CallbackQueryHandler(back_debts_callback, pattern=r'^back_debts$'))
    
    # Initialize DB
    async def post_init(app):
        await init_db()
        logger.info("Database ready!")
    
    application.post_init = post_init
    
    logger.info("Hisobchi Bot started!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
