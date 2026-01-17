import asyncio
import logging
from datetime import time
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ConversationHandler, filters
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import BOT_TOKEN
from database import init_db

# Handlers
from handlers.start import start_command, help_command, stats_command, cancel_command
from handlers.debt import (
    debt_given_start, debt_taken_start, debt_name_received, 
    debt_amount_received, debt_payment_type_callback,
    debt_given_date_callback, debt_given_date_text, debt_due_date_received,
    debt_installments_callback, debt_installments_text, debt_confirm_callback,
    debt_cancel,
    DEBT_NAME, DEBT_AMOUNT, DEBT_PAYMENT_TYPE, DEBT_GIVEN_DATE, 
    DEBT_DUE_DATE, DEBT_INSTALLMENTS, DEBT_CONFIRM
)
from handlers.expense import (
    expense_start, expense_description_received, expense_amount_received,
    expense_category_callback, expense_cancel,
    EXPENSE_DESCRIPTION, EXPENSE_AMOUNT, EXPENSE_CATEGORY
)
from handlers.views import (
    my_debts_handler, view_debts_callback, view_debt_detail_callback,
    mark_debt_paid_callback, delete_debt_callback, statistics_handler,
    settings_handler, back_main_callback, back_debts_callback, page_callback,
    export_callback
)
from services.reminders import check_and_send_reminders, check_overdue_debts

# Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


def main():
    """Botni ishga tushirish"""
    
    # Application yaratish
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Qarz berdim conversation handler
    debt_given_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex(r'^💰 Qarz berdim$'), debt_given_start)
        ],
        states={
            DEBT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, debt_name_received)],
            DEBT_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, debt_amount_received)],
            DEBT_PAYMENT_TYPE: [CallbackQueryHandler(debt_payment_type_callback, pattern=r'^payment_')],
            DEBT_GIVEN_DATE: [
                CallbackQueryHandler(debt_given_date_callback, pattern=r'^date_'),
                MessageHandler(filters.TEXT & ~filters.COMMAND, debt_given_date_text)
            ],
            DEBT_DUE_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, debt_due_date_received)],
            DEBT_INSTALLMENTS: [
                CallbackQueryHandler(debt_installments_callback, pattern=r'^inst_'),
                MessageHandler(filters.TEXT & ~filters.COMMAND, debt_installments_text)
            ],
            DEBT_CONFIRM: [CallbackQueryHandler(debt_confirm_callback, pattern=r'^confirm_')]
        },
        fallbacks=[
            CommandHandler('cancel', cancel_command),
            MessageHandler(filters.Regex(r'^/start$'), start_command)
        ],
        allow_reentry=True
    )
    
    # Qarz oldim conversation handler
    debt_taken_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex(r'^💸 Qarz oldim$'), debt_taken_start)
        ],
        states={
            DEBT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, debt_name_received)],
            DEBT_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, debt_amount_received)],
            DEBT_PAYMENT_TYPE: [CallbackQueryHandler(debt_payment_type_callback, pattern=r'^payment_')],
            DEBT_GIVEN_DATE: [
                CallbackQueryHandler(debt_given_date_callback, pattern=r'^date_'),
                MessageHandler(filters.TEXT & ~filters.COMMAND, debt_given_date_text)
            ],
            DEBT_DUE_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, debt_due_date_received)],
            DEBT_INSTALLMENTS: [
                CallbackQueryHandler(debt_installments_callback, pattern=r'^inst_'),
                MessageHandler(filters.TEXT & ~filters.COMMAND, debt_installments_text)
            ],
            DEBT_CONFIRM: [CallbackQueryHandler(debt_confirm_callback, pattern=r'^confirm_')]
        },
        fallbacks=[
            CommandHandler('cancel', cancel_command),
            MessageHandler(filters.Regex(r'^/start$'), start_command)
        ],
        allow_reentry=True
    )
    
    # Kunlik harajat conversation handler
    expense_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex(r'^📝 Kunlik harajat$'), expense_start)
        ],
        states={
            EXPENSE_DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, expense_description_received)],
            EXPENSE_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, expense_amount_received)],
            EXPENSE_CATEGORY: [CallbackQueryHandler(expense_category_callback, pattern=r'^cat_')]
        },
        fallbacks=[
            CommandHandler('cancel', cancel_command),
            MessageHandler(filters.Regex(r'^/start$'), start_command)
        ],
        allow_reentry=True
    )
    
    # Command handlers
    application.add_handler(CommandHandler('start', start_command))
    application.add_handler(CommandHandler('help', help_command))
    application.add_handler(CommandHandler('stats', stats_command))
    application.add_handler(CommandHandler('cancel', cancel_command))
    
    # Conversation handlers
    application.add_handler(debt_given_handler)
    application.add_handler(debt_taken_handler)
    application.add_handler(expense_handler)
    
    # Message handlers
    application.add_handler(MessageHandler(filters.Regex(r'^📊 Statistika$'), statistics_handler))
    application.add_handler(MessageHandler(filters.Regex(r'^📋 Mening qarzlarim$'), my_debts_handler))
    application.add_handler(MessageHandler(filters.Regex(r'^⚙️ Sozlamalar$'), settings_handler))
    
    # Callback query handlers
    application.add_handler(CallbackQueryHandler(view_debts_callback, pattern=r'^view_'))
    application.add_handler(CallbackQueryHandler(view_debt_detail_callback, pattern=r'^debt_\d+$'))
    application.add_handler(CallbackQueryHandler(mark_debt_paid_callback, pattern=r'^mark_paid_'))
    application.add_handler(CallbackQueryHandler(delete_debt_callback, pattern=r'^delete_debt_'))
    application.add_handler(CallbackQueryHandler(back_main_callback, pattern=r'^back_main$'))
    application.add_handler(CallbackQueryHandler(back_debts_callback, pattern=r'^back_debts$'))
    application.add_handler(CallbackQueryHandler(page_callback, pattern=r'^page_'))
    application.add_handler(CallbackQueryHandler(export_callback, pattern=r'^settings_export$'))
    
    # Ma'lumotlar bazasini yaratish
    async def post_init(application):
        await init_db()
        logger.info("Ma'lumotlar bazasi tayyor")
    
    application.post_init = post_init
    
    # Scheduler - eslatmalar uchun
    scheduler = AsyncIOScheduler()
    
    async def run_reminders():
        """Eslatmalarni yuborish"""
        try:
            await check_and_send_reminders(application.bot)
        except Exception as e:
            logger.error(f"Eslatma xatosi: {e}")
    
    async def run_overdue_check():
        """Muddati o'tgan qarzlarni tekshirish"""
        try:
            await check_overdue_debts(application.bot)
        except Exception as e:
            logger.error(f"Overdue tekshiruv xatosi: {e}")
    
    # Har kuni soat 9:00 da eslatmalar
    scheduler.add_job(run_reminders, 'cron', hour=9, minute=0)
    
    # Har 3 kunda muddati o'tgan qarzlar haqida
    scheduler.add_job(run_overdue_check, 'cron', day='*/3', hour=10, minute=0)
    
    scheduler.start()
    
    # Botni ishga tushirish
    logger.info("Hisobchi Bot ishga tushdi!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
