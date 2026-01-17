from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton

def main_menu_keyboard():
    """Asosiy menyu tugmalari"""
    keyboard = [
        [KeyboardButton("💰 Qarz berdim"), KeyboardButton("💸 Qarz oldim")],
        [KeyboardButton("📝 Kunlik harajat")],
        [KeyboardButton("📊 Statistika"), KeyboardButton("📋 Mening qarzlarim")],
        [KeyboardButton("⚙️ Sozlamalar")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def currency_keyboard():
    """Valyuta tanlash tugmalari"""
    keyboard = [
        [InlineKeyboardButton("🇺🇸 USD", callback_data="currency_USD"),
         InlineKeyboardButton("🇺🇿 UZS", callback_data="currency_UZS")]
    ]
    return InlineKeyboardMarkup(keyboard)


def payment_type_keyboard():
    """To'lov turi tanlash"""
    keyboard = [
        [InlineKeyboardButton("💵 Bir marta to'lash", callback_data="payment_one_time")],
        [InlineKeyboardButton("📅 Bo'lib to'lash", callback_data="payment_installment")]
    ]
    return InlineKeyboardMarkup(keyboard)


def date_keyboard():
    """Sana tanlash tugmalari"""
    keyboard = [
        [InlineKeyboardButton("📅 Bugun", callback_data="date_today")],
        [InlineKeyboardButton("✏️ Boshqa sana", callback_data="date_custom")]
    ]
    return InlineKeyboardMarkup(keyboard)


def confirm_keyboard():
    """Tasdiqlash tugmalari"""
    keyboard = [
        [InlineKeyboardButton("✅ Tasdiqlash", callback_data="confirm_yes"),
         InlineKeyboardButton("❌ Bekor qilish", callback_data="confirm_no")]
    ]
    return InlineKeyboardMarkup(keyboard)


def back_keyboard():
    """Orqaga tugmasi"""
    keyboard = [
        [InlineKeyboardButton("🔙 Orqaga", callback_data="back_main")]
    ]
    return InlineKeyboardMarkup(keyboard)


def debt_list_keyboard(debts, page=0, items_per_page=5):
    """Qarzlar ro'yxati tugmalari"""
    keyboard = []
    start = page * items_per_page
    end = start + items_per_page
    page_debts = debts[start:end]
    
    for debt in page_debts:
        status = "✅" if debt['is_paid'] else "⏳"
        text = f"{status} {debt['person_name']} - {debt['amount']:,.0f} {debt['currency']}"
        keyboard.append([InlineKeyboardButton(text, callback_data=f"debt_{debt['id']}")])
    
    # Pagination
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️ Oldingi", callback_data=f"page_{page-1}"))
    if end < len(debts):
        nav_buttons.append(InlineKeyboardButton("Keyingi ➡️", callback_data=f"page_{page+1}"))
    
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    keyboard.append([InlineKeyboardButton("🔙 Orqaga", callback_data="back_main")])
    
    return InlineKeyboardMarkup(keyboard)


def debt_action_keyboard(debt_id, is_paid=False):
    """Qarz ustida amallar"""
    keyboard = []
    
    if not is_paid:
        keyboard.append([InlineKeyboardButton("✅ To'landi deb belgilash", callback_data=f"mark_paid_{debt_id}")])
    
    keyboard.append([InlineKeyboardButton("🗑 O'chirish", callback_data=f"delete_debt_{debt_id}")])
    keyboard.append([InlineKeyboardButton("🔙 Orqaga", callback_data="back_debts")])
    
    return InlineKeyboardMarkup(keyboard)


def expense_category_keyboard():
    """Harajat kategoriyalari"""
    keyboard = [
        [InlineKeyboardButton("🍔 Oziq-ovqat", callback_data="cat_food"),
         InlineKeyboardButton("🚗 Transport", callback_data="cat_transport")],
        [InlineKeyboardButton("🏠 Uy-joy", callback_data="cat_home"),
         InlineKeyboardButton("👕 Kiyim", callback_data="cat_clothes")],
        [InlineKeyboardButton("💊 Sog'liq", callback_data="cat_health"),
         InlineKeyboardButton("📚 Ta'lim", callback_data="cat_education")],
        [InlineKeyboardButton("🎮 Ko'ngilochar", callback_data="cat_entertainment"),
         InlineKeyboardButton("📦 Boshqa", callback_data="cat_other")]
    ]
    return InlineKeyboardMarkup(keyboard)


def stats_period_keyboard():
    """Statistika davri tanlash"""
    keyboard = [
        [InlineKeyboardButton("📅 Bugun", callback_data="stats_today"),
         InlineKeyboardButton("📆 Shu hafta", callback_data="stats_week")],
        [InlineKeyboardButton("🗓 Shu oy", callback_data="stats_month"),
         InlineKeyboardButton("📊 Hammasi", callback_data="stats_all")]
    ]
    return InlineKeyboardMarkup(keyboard)


def my_debts_keyboard():
    """Mening qarzlarim menyusi"""
    keyboard = [
        [InlineKeyboardButton("💰 Bergan qarzlarim", callback_data="view_given")],
        [InlineKeyboardButton("💸 Olgan qarzlarim", callback_data="view_taken")],
        [InlineKeyboardButton("🔙 Orqaga", callback_data="back_main")]
    ]
    return InlineKeyboardMarkup(keyboard)


def settings_keyboard():
    """Sozlamalar menyusi"""
    keyboard = [
        [InlineKeyboardButton("🔔 Eslatmalar", callback_data="settings_reminders")],
        [InlineKeyboardButton("💱 Valyuta kursi", callback_data="settings_currency")],
        [InlineKeyboardButton("📤 Eksport qilish", callback_data="settings_export")],
        [InlineKeyboardButton("🔙 Orqaga", callback_data="back_main")]
    ]
    return InlineKeyboardMarkup(keyboard)


def installment_count_keyboard():
    """Bo'lib to'lash soni tanlash"""
    keyboard = [
        [InlineKeyboardButton("2 oy", callback_data="inst_2"),
         InlineKeyboardButton("3 oy", callback_data="inst_3"),
         InlineKeyboardButton("4 oy", callback_data="inst_4")],
        [InlineKeyboardButton("6 oy", callback_data="inst_6"),
         InlineKeyboardButton("12 oy", callback_data="inst_12")],
        [InlineKeyboardButton("✏️ Boshqa", callback_data="inst_custom")]
    ]
    return InlineKeyboardMarkup(keyboard)
