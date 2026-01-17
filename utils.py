from datetime import datetime, date, timedelta
import re


def format_money(amount: float, currency: str) -> str:
    """Pulni formatlash"""
    if currency == "UZS":
        return f"{amount:,.0f} so'm"
    return f"${amount:,.2f}"


def parse_amount(text: str) -> tuple:
    """Summa va valyutani ajratib olish
    Masalan: '100 USD', '500000 UZS', '100$', '500000'
    """
    text = text.strip().upper()
    
    # $ belgisi bilan
    if '$' in text:
        amount = re.sub(r'[^\d.]', '', text)
        return float(amount), 'USD'
    
    # USD yoki UZS yozilgan
    if 'USD' in text:
        amount = re.sub(r'[^\d.]', '', text.replace('USD', ''))
        return float(amount), 'USD'
    
    if 'UZS' in text or "SO'M" in text or "SOM" in text or "SUM" in text:
        amount = re.sub(r'[^\d.]', '', text.replace('UZS', '').replace("SO'M", '').replace('SOM', '').replace('SUM', ''))
        return float(amount), 'UZS'
    
    # Faqat raqam - UZS deb hisoblaymiz
    amount = re.sub(r'[^\d.]', '', text)
    if amount:
        return float(amount), 'UZS'
    
    return None, None


def parse_date(text: str) -> date:
    """Sanani parse qilish
    Formatlar: DD.MM.YYYY, DD/MM/YYYY, DD-MM-YYYY, YYYY-MM-DD
    """
    text = text.strip()
    
    formats = [
        '%d.%m.%Y',
        '%d/%m/%Y',
        '%d-%m-%Y',
        '%Y-%m-%d',
        '%d.%m.%y',
        '%d/%m/%y',
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    
    return None


def format_date(d: date) -> str:
    """Sanani formatlash"""
    if d is None:
        return "Belgilanmagan"
    if isinstance(d, str):
        d = datetime.fromisoformat(d).date()
    return d.strftime('%d.%m.%Y')


def days_until(target_date) -> int:
    """Sanagacha qolgan kunlar"""
    if isinstance(target_date, str):
        target_date = datetime.fromisoformat(target_date).date()
    today = date.today()
    return (target_date - today).days


def get_debt_status_emoji(due_date, is_paid: bool) -> str:
    """Qarz holatiga emoji"""
    if is_paid:
        return "✅"
    
    days = days_until(due_date)
    
    if days < 0:
        return "🔴"  # Muddati o'tgan
    elif days <= 3:
        return "🟡"  # Yaqin
    else:
        return "🟢"  # Hali bor


def calculate_installments(total_amount: float, num_installments: int, 
                          start_date: date) -> list:
    """Bo'lib to'lash jadvalini hisoblash"""
    amount_per_month = total_amount / num_installments
    installments = []
    
    current_date = start_date
    for i in range(num_installments):
        # Keyingi oyga o'tish
        if i > 0:
            month = current_date.month + 1
            year = current_date.year
            if month > 12:
                month = 1
                year += 1
            # Oyning oxirgi kunini hisobga olish
            day = min(current_date.day, 28)  # Xavfsiz kun
            current_date = date(year, month, day)
        
        installments.append({
            'amount': round(amount_per_month, 2),
            'due_date': current_date
        })
    
    return installments


def get_reminder_dates(due_date, days_before: list = [3, 1, 0]) -> list:
    """Eslatma sanalarini olish"""
    if isinstance(due_date, str):
        due_date = datetime.fromisoformat(due_date).date()
    
    reminder_dates = []
    for days in days_before:
        remind_date = due_date - timedelta(days=days)
        if remind_date >= date.today():
            reminder_dates.append(remind_date)
    
    return reminder_dates


def format_debt_info(debt: dict) -> str:
    """Qarz ma'lumotlarini formatlash"""
    debt_type = "Bergan qarz" if debt['debt_type'] == 'given' else "Olgan qarz"
    status_emoji = get_debt_status_emoji(debt['due_date'], debt['is_paid'])
    
    text = f"""
{status_emoji} <b>{debt_type}</b>

👤 <b>Shaxs:</b> {debt['person_name']}
💰 <b>Summa:</b> {format_money(debt['amount'], debt['currency'])}
📅 <b>Berilgan sana:</b> {format_date(debt['given_date'])}
⏰ <b>Qaytarish muddati:</b> {format_date(debt['due_date'])}
"""
    
    days = days_until(debt['due_date'])
    if not debt['is_paid']:
        if days < 0:
            text += f"⚠️ <b>Muddati {abs(days)} kun o'tgan!</b>\n"
        elif days == 0:
            text += "⚠️ <b>Bugun oxirgi kun!</b>\n"
        else:
            text += f"📆 <b>{days} kun qoldi</b>\n"
    else:
        text += "✅ <b>To'langan</b>\n"
    
    if debt.get('notes'):
        text += f"\n📝 <b>Izoh:</b> {debt['notes']}"
    
    return text


def format_statistics(stats: dict) -> str:
    """Statistikani formatlash"""
    text = "📊 <b>UMUMIY STATISTIKA</b>\n\n"
    
    # Bergan qarzlar
    text += "💰 <b>Bergan qarzlarim:</b>\n"
    if stats['given_active']:
        for currency, amount in stats['given_active'].items():
            text += f"   • {format_money(amount, currency)}\n"
        text += f"   📌 Jami: {stats['given_count']} ta qarz\n"
    else:
        text += "   Hozircha yo'q\n"
    
    text += "\n"
    
    # Olgan qarzlar
    text += "💸 <b>Olgan qarzlarim:</b>\n"
    if stats['taken_active']:
        for currency, amount in stats['taken_active'].items():
            text += f"   • {format_money(amount, currency)}\n"
        text += f"   📌 Jami: {stats['taken_count']} ta qarz\n"
    else:
        text += "   Hozircha yo'q\n"
    
    text += "\n"
    
    # Bugungi harajatlar
    text += "📝 <b>Bugungi harajatlar:</b>\n"
    if stats['today_expenses']:
        for currency, amount in stats['today_expenses'].items():
            text += f"   • {format_money(amount, currency)}\n"
    else:
        text += "   Hozircha yo'q\n"
    
    text += "\n"
    
    # Oylik harajatlar
    text += "🗓 <b>Shu oylik harajatlar:</b>\n"
    if stats['monthly_expenses']:
        for currency, amount in stats['monthly_expenses'].items():
            text += f"   • {format_money(amount, currency)}\n"
    else:
        text += "   Hozircha yo'q\n"
    
    return text


CATEGORY_NAMES = {
    'food': '🍔 Oziq-ovqat',
    'transport': '🚗 Transport',
    'home': '🏠 Uy-joy',
    'clothes': '👕 Kiyim',
    'health': '💊 Sog\'liq',
    'education': '📚 Ta\'lim',
    'entertainment': '🎮 Ko\'ngilochar',
    'other': '📦 Boshqa'
}


def get_category_name(category: str) -> str:
    """Kategoriya nomini olish"""
    return CATEGORY_NAMES.get(category, '📦 Boshqa')
