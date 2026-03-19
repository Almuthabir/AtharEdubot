"""
handlers/answers.py — معالج الإجابات في الجروب
"""

import logging
from telegram import Update
from telegram.ext import ContextTypes

from config import POINTS, GROUP_ID
from data import database as db

logger = logging.getLogger(__name__)


def _normalize(text: str) -> str:
    """توحيد النص للمقارنة"""
    text = text.strip().lower()
    # إزالة التشكيل
    import re
    text = re.sub(r'[\u064B-\u065F]', '', text)
    # توحيد الألف
    text = re.sub(r'[أإآا]', 'ا', text)
    # توحيد الياء والواو
    text = text.replace('ى', 'ي').replace('ة', 'ه')
    return text


from handlers.commands import check_subscription, CHANNEL_URL
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg  = update.message
    user = update.effective_user

    if not msg or not msg.text:
        return

    # التحقق من الاشتراك الإجباري في الخاص
    if msg.chat.type == "private":
        is_subscribed = await check_subscription(user.id, ctx.bot)
        if not is_subscribed:
            keyboard = [[InlineKeyboardButton("اشترك في القناة 📢", url=CHANNEL_URL)]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await msg.reply_text(
                "عليك الاشتراك في القناة ثم اضغط /start",
                reply_markup=reply_markup
            )
            return
        # إذا كان مشترك وفي الخاص، ممكن نضيف ردود عامة أو نتجاهل
        return

    # فقط في الجروب (للمسابقات)
    if msg.chat.id != GROUP_ID:
        return

    db.upsert_student(user.id, user.username, user.full_name)

    text = msg.text.strip()

    # ── تحقق من إجابة السؤال اليومي ──────────────────────────
    q = db.get_active_question()
    if q:
        correct_answer = _normalize(q["answer"])
        user_answer    = _normalize(text)

        if user_answer == correct_answer:
            # تحقق لو هذا الشخص جاوب قبل
            already = not db.record_question_answer(q["id"], user.id, True)
            if already:
                return  # جاوب قبل، تجاهل

            correct_count = db.count_correct_answers(q["id"])

            if correct_count == 1:
                # أول إجابة صحيحة
                db.set_question_winner(q["id"], user.id, 1)
                db.add_points(user.id, POINTS["question_first"], "أول إجابة صحيحة")
                await msg.reply_text(
                    f"🎯 إجابة صحيحة يا {user.first_name}!\n"
                    f"🥇 أنت الأول! +{POINTS['question_first']} نقطة 🎉"
                )

            elif correct_count == 2:
                # ثاني إجابة صحيحة
                db.set_question_winner(q["id"], user.id, 2)
                db.add_points(user.id, POINTS["question_second"], "ثاني إجابة صحيحة")
                await msg.reply_text(
                    f"✅ إجابة صحيحة يا {user.first_name}!\n"
                    f"🥈 أنت الثاني! +{POINTS['question_second']} نقاط"
                )
            else:
                # بعد الثاني — صح بدون نقاط
                db.record_question_answer(q["id"], user.id, True)
                await msg.reply_text(f"✅ إجابة صحيحة يا {user.first_name}! (بدون نقاط إضافية)")

        else:
            # إجابة خاطئة — سجّلها بدون نقاط (مرة وحدة)
            db.record_question_answer(q["id"], user.id, False)
