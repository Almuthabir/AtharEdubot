"""
بوت أثر — main.py
"""

import logging
import asyncio
from telegram.ext import Application, CommandHandler, MessageHandler, filters, PollAnswerHandler

from config import BOT_TOKEN, ADMIN_IDS
from handlers.commands import (
    cmd_start, cmd_points, cmd_leaderboard, cmd_done,
    cmd_history, cmd_question, cmd_challenge, cmd_review,
    cmd_help, cmd_settings,
    cmd_admin_add_question, cmd_admin_add_challenge,
    cmd_admin_add_review, cmd_admin_add_riddle,
    cmd_admin_reset_week, cmd_admin_announce,
)
from handlers.answers import handle_message
from handlers.poll    import handle_poll_answer
from scheduler.jobs   import setup_scheduler
from data.database    import init_db

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
    handlers=[
        logging.FileHandler("athar.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


async def post_init(application: Application):
    logger.info("✅ بوت أثر شغال!")
    init_db()
    setup_scheduler(application)


def main():
    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    # أوامر الطلاب
    app.add_handler(CommandHandler("start",    cmd_start))
    app.add_handler(CommandHandler("نقاطي",    cmd_points))
    app.add_handler(CommandHandler("ترتيب",    cmd_leaderboard))
    app.add_handler(CommandHandler("انجزت",    cmd_done))
    app.add_handler(CommandHandler("سجلي",     cmd_history))
    app.add_handler(CommandHandler("سؤال",     cmd_question))
    app.add_handler(CommandHandler("تحدي",     cmd_challenge))
    app.add_handler(CommandHandler("مراجعة",   cmd_review))
    app.add_handler(CommandHandler("مساعدة",   cmd_help))
    app.add_handler(CommandHandler("settings", cmd_settings))

    # أوامر الأدمن
    app.add_handler(CommandHandler("اضف_سؤال",   cmd_admin_add_question))
    app.add_handler(CommandHandler("اضف_تحدي",   cmd_admin_add_challenge))
    app.add_handler(CommandHandler("اضف_مراجعة", cmd_admin_add_review))
    app.add_handler(CommandHandler("اضف_لغز",    cmd_admin_add_riddle))
    app.add_handler(CommandHandler("ريست_اسبوع", cmd_admin_reset_week))
    app.add_handler(CommandHandler("اعلان",      cmd_admin_announce))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(PollAnswerHandler(handle_poll_answer))

    logger.info("🚀 بدء التشغيل...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
