import os

# Hisobchi Bot Configuration
# Railway'da BOT_TOKEN environment variable sifatida o'rnatiladi
BOT_TOKEN = os.getenv("BOT_TOKEN", "8450831935:AAGhmhvWFmQH-4AOrOUFyDfiv_ufJYvXztw")

# Eslatma kunlari (muddatdan necha kun oldin)
REMINDER_DAYS = [3, 1, 0]

# Valyuta kurslari (UZS uchun)
USD_TO_UZS_RATE = 12700
