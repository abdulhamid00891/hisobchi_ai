import aiosqlite
import os
from datetime import datetime, date

DB_PATH = os.path.join(os.path.dirname(__file__), "hisobchi.db")


async def init_db():
    """Ma'lumotlar bazasini yaratish"""
    async with aiosqlite.connect(DB_PATH) as db:
        # Foydalanuvchilar jadvali
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE NOT NULL,
                full_name TEXT,
                username TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Qarzlar jadvali
        await db.execute("""
            CREATE TABLE IF NOT EXISTS debts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                person_name TEXT NOT NULL,
                amount REAL NOT NULL,
                currency TEXT DEFAULT 'UZS',
                debt_type TEXT NOT NULL,
                payment_type TEXT DEFAULT 'one_time',
                given_date DATE,
                due_date DATE,
                is_paid INTEGER DEFAULT 0,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        """)
        
        # Bo'lib to'lashlar jadvali
        await db.execute("""
            CREATE TABLE IF NOT EXISTS installments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                debt_id INTEGER NOT NULL,
                amount REAL NOT NULL,
                due_date DATE,
                is_paid INTEGER DEFAULT 0,
                paid_date DATE,
                FOREIGN KEY (debt_id) REFERENCES debts (id)
            )
        """)
        
        # Kunlik harajatlar jadvali
        await db.execute("""
            CREATE TABLE IF NOT EXISTS daily_expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                description TEXT,
                amount REAL NOT NULL,
                currency TEXT DEFAULT 'UZS',
                category TEXT,
                expense_date DATE DEFAULT CURRENT_DATE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        """)
        
        # Eslatmalar jadvali
        await db.execute("""
            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                debt_id INTEGER NOT NULL,
                remind_date DATE,
                is_sent INTEGER DEFAULT 0,
                FOREIGN KEY (debt_id) REFERENCES debts (id)
            )
        """)
        
        await db.commit()


class Database:
    def __init__(self):
        self.db_path = DB_PATH
    
    async def get_or_create_user(self, telegram_id: int, full_name: str, username: str = None):
        """Foydalanuvchini olish yoki yaratish"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)
            )
            user = await cursor.fetchone()
            
            if user:
                return dict(user)
            
            await db.execute(
                "INSERT INTO users (telegram_id, full_name, username) VALUES (?, ?, ?)",
                (telegram_id, full_name, username)
            )
            await db.commit()
            
            cursor = await db.execute(
                "SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)
            )
            return dict(await cursor.fetchone())
    
    async def add_debt(self, user_id: int, person_name: str, amount: float, 
                       currency: str, debt_type: str, payment_type: str,
                       given_date: date, due_date: date, notes: str = None):
        """Yangi qarz qo'shish"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                INSERT INTO debts (user_id, person_name, amount, currency, 
                                   debt_type, payment_type, given_date, due_date, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (user_id, person_name, amount, currency, debt_type, 
                  payment_type, given_date, due_date, notes))
            debt_id = cursor.lastrowid
            await db.commit()
            return debt_id
    
    async def add_installment(self, debt_id: int, amount: float, due_date: date):
        """Bo'lib to'lash qo'shish"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO installments (debt_id, amount, due_date)
                VALUES (?, ?, ?)
            """, (debt_id, amount, due_date))
            await db.commit()
    
    async def add_reminder(self, debt_id: int, remind_date: date):
        """Eslatma qo'shish"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO reminders (debt_id, remind_date)
                VALUES (?, ?)
            """, (debt_id, remind_date))
            await db.commit()
    
    async def get_debts_by_type(self, user_id: int, debt_type: str, include_paid: bool = False):
        """Foydalanuvchining qarzlarini olish"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            if include_paid:
                cursor = await db.execute("""
                    SELECT * FROM debts WHERE user_id = ? AND debt_type = ?
                    ORDER BY due_date ASC
                """, (user_id, debt_type))
            else:
                cursor = await db.execute("""
                    SELECT * FROM debts WHERE user_id = ? AND debt_type = ? AND is_paid = 0
                    ORDER BY due_date ASC
                """, (user_id, debt_type))
            return [dict(row) for row in await cursor.fetchall()]
    
    async def get_all_active_debts(self, user_id: int):
        """Barcha faol qarzlarni olish"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("""
                SELECT * FROM debts WHERE user_id = ? AND is_paid = 0
                ORDER BY due_date ASC
            """, (user_id,))
            return [dict(row) for row in await cursor.fetchall()]
    
    async def mark_debt_paid(self, debt_id: int):
        """Qarzni to'langan deb belgilash"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE debts SET is_paid = 1 WHERE id = ?", (debt_id,)
            )
            await db.commit()
    
    async def delete_debt(self, debt_id: int):
        """Qarzni o'chirish"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM installments WHERE debt_id = ?", (debt_id,))
            await db.execute("DELETE FROM reminders WHERE debt_id = ?", (debt_id,))
            await db.execute("DELETE FROM debts WHERE id = ?", (debt_id,))
            await db.commit()
    
    async def add_expense(self, user_id: int, description: str, amount: float,
                          currency: str, category: str = None, expense_date: date = None):
        """Kunlik harajat qo'shish"""
        if expense_date is None:
            expense_date = date.today()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO daily_expenses (user_id, description, amount, currency, category, expense_date)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (user_id, description, amount, currency, category, expense_date))
            await db.commit()
    
    async def get_expenses_by_date(self, user_id: int, expense_date: date):
        """Sana bo'yicha harajatlarni olish"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("""
                SELECT * FROM daily_expenses WHERE user_id = ? AND expense_date = ?
                ORDER BY created_at DESC
            """, (user_id, expense_date))
            return [dict(row) for row in await cursor.fetchall()]
    
    async def get_expenses_by_month(self, user_id: int, year: int, month: int):
        """Oy bo'yicha harajatlarni olish"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("""
                SELECT * FROM daily_expenses 
                WHERE user_id = ? AND strftime('%Y', expense_date) = ? AND strftime('%m', expense_date) = ?
                ORDER BY expense_date DESC
            """, (user_id, str(year), str(month).zfill(2)))
            return [dict(row) for row in await cursor.fetchall()]
    
    async def get_statistics(self, user_id: int):
        """Umumiy statistika olish"""
        async with aiosqlite.connect(self.db_path) as db:
            stats = {}
            
            # Bergan qarzlar (faol)
            cursor = await db.execute("""
                SELECT currency, SUM(amount) as total FROM debts 
                WHERE user_id = ? AND debt_type = 'given' AND is_paid = 0
                GROUP BY currency
            """, (user_id,))
            stats['given_active'] = {row[0]: row[1] for row in await cursor.fetchall()}
            
            # Olgan qarzlar (faol)
            cursor = await db.execute("""
                SELECT currency, SUM(amount) as total FROM debts 
                WHERE user_id = ? AND debt_type = 'taken' AND is_paid = 0
                GROUP BY currency
            """, (user_id,))
            stats['taken_active'] = {row[0]: row[1] for row in await cursor.fetchall()}
            
            # Bergan qarzlar soni
            cursor = await db.execute("""
                SELECT COUNT(*) FROM debts WHERE user_id = ? AND debt_type = 'given' AND is_paid = 0
            """, (user_id,))
            stats['given_count'] = (await cursor.fetchone())[0]
            
            # Olgan qarzlar soni
            cursor = await db.execute("""
                SELECT COUNT(*) FROM debts WHERE user_id = ? AND debt_type = 'taken' AND is_paid = 0
            """, (user_id,))
            stats['taken_count'] = (await cursor.fetchone())[0]
            
            # Shu oylik harajatlar
            today = date.today()
            cursor = await db.execute("""
                SELECT currency, SUM(amount) as total FROM daily_expenses 
                WHERE user_id = ? AND strftime('%Y-%m', expense_date) = ?
                GROUP BY currency
            """, (user_id, today.strftime('%Y-%m')))
            stats['monthly_expenses'] = {row[0]: row[1] for row in await cursor.fetchall()}
            
            # Bugungi harajatlar
            cursor = await db.execute("""
                SELECT currency, SUM(amount) as total FROM daily_expenses 
                WHERE user_id = ? AND expense_date = ?
                GROUP BY currency
            """, (user_id, today))
            stats['today_expenses'] = {row[0]: row[1] for row in await cursor.fetchall()}
            
            return stats
    
    async def get_pending_reminders(self, target_date: date):
        """Yuborilishi kerak bo'lgan eslatmalarni olish"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("""
                SELECT r.*, d.person_name, d.amount, d.currency, d.debt_type, d.due_date, u.telegram_id
                FROM reminders r
                JOIN debts d ON r.debt_id = d.id
                JOIN users u ON d.user_id = u.id
                WHERE r.remind_date = ? AND r.is_sent = 0 AND d.is_paid = 0
            """, (target_date,))
            return [dict(row) for row in await cursor.fetchall()]
    
    async def mark_reminder_sent(self, reminder_id: int):
        """Eslatmani yuborilgan deb belgilash"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE reminders SET is_sent = 1 WHERE id = ?", (reminder_id,)
            )
            await db.commit()
    
    async def get_overdue_debts(self):
        """Muddati o'tgan qarzlarni olish"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            today = date.today()
            cursor = await db.execute("""
                SELECT d.*, u.telegram_id FROM debts d
                JOIN users u ON d.user_id = u.id
                WHERE d.due_date < ? AND d.is_paid = 0
                ORDER BY d.due_date ASC
            """, (today,))
            return [dict(row) for row in await cursor.fetchall()]
    
    async def get_debt_by_id(self, debt_id: int):
        """ID bo'yicha qarzni olish"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM debts WHERE id = ?", (debt_id,)
            )
            row = await cursor.fetchone()
            return dict(row) if row else None
    
    async def get_installments(self, debt_id: int):
        """Qarz bo'yicha bo'lib to'lashlarni olish"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("""
                SELECT * FROM installments WHERE debt_id = ?
                ORDER BY due_date ASC
            """, (debt_id,))
            return [dict(row) for row in await cursor.fetchall()]
    
    async def mark_installment_paid(self, installment_id: int):
        """Bo'lib to'lashni to'langan deb belgilash"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                UPDATE installments SET is_paid = 1, paid_date = ? WHERE id = ?
            """, (date.today(), installment_id))
            await db.commit()
    
    async def delete_expense(self, expense_id: int):
        """Harajatni o'chirish"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM daily_expenses WHERE id = ?", (expense_id,))
            await db.commit()
