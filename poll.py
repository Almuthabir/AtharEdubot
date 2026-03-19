"""
handlers/poll.py — معالج إجابات التصويت
"""

import logging
from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


async def handle_poll_answer(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """يُسجَّل كل تصويت — يمكن توسيعه لاحقاً"""
    answer  = update.poll_answer
    user    = answer.user
    options = answer.option_ids
    logger.info(f"تصويت من {user.full_name} — خيار: {options}")
