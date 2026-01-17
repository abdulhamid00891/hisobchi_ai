# 🤖 Hisobchi Bot

O'zbekcha shaxsiy moliyaviy hisobchi Telegram bot.

## ✨ Funksiyalar

- **💰 Qarz berdim** - Boshqalarga bergan qarzlarni kuzatish
- **💸 Qarz oldim** - O'zingiz olgan qarzlarni kuzatish
- **📝 Kunlik harajat** - Har kunlik xarajatlarni yozib borish
- **🔔 Avtomatik eslatmalar** - Muddat yaqinlashganda xabar
- **📊 Statistika** - Umumiy moliyaviy holat
- **💱 Valyuta** - USD va UZS qo'llab-quvvatlash
- **📤 Excel eksport** - Ma'lumotlarni yuklab olish

## 🚀 O'rnatish

### 1. Kerakli kutubxonalarni o'rnatish

```bash
pip install -r requirements.txt
```

### 2. Bot tokenini sozlash

`config.py` faylida bot tokenini o'zgartiring:

```python
BOT_TOKEN = "sizning_bot_tokeningiz"
```

### 3. Botni ishga tushirish

```bash
python main.py
```

## 📱 Foydalanish

1. Telegram'da botni toping va `/start` buyrug'ini yuboring
2. Asosiy menyudan kerakli funksiyani tanlang
3. Bot ko'rsatmalariga amal qiling

## 📁 Loyiha tuzilmasi

```
hisobchi-bot/
├── main.py              # Asosiy fayl
├── config.py            # Sozlamalar
├── database.py          # Ma'lumotlar bazasi
├── keyboards.py         # Tugmalar
├── utils.py             # Yordamchi funksiyalar
├── handlers/            # Xabar qayta ishlovchilar
│   ├── start.py
│   ├── debt.py
│   ├── expense.py
│   └── views.py
├── services/            # Xizmatlar
│   ├── reminders.py
│   └── export.py
└── requirements.txt
```

## 🔔 Eslatmalar

Bot quyidagi vaqtlarda eslatma yuboradi:
- Muddatdan 3 kun oldin
- Muddatdan 1 kun oldin
- Muddat kuni

## 📝 Litsenziya

MIT
