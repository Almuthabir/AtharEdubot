"""
handlers/commands.py — معالج الأوامر مع دعم أي مجموعة
"""

import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.error import BadRequest, Forbidden

from config import ADMIN_IDS, POINTS, CHANNEL_URL, CHANNEL_ID, DEVELOPER_CHAT
from data import database as db

logger = logging.getLogger(__name__)


def _is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def _name(user) -> str:
    return user.full_name or user.username or str(user.id)


async def check_subscription(user_id: int, bot) -> bool:
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return member.status in ["member", "administrator", "creator"]
    except Exception:
        return True


# ═══════════════════════════════════════════════════════
#                   أوامر الطلاب
# ═══════════════════════════════════════════════════════

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u    = update.effective_user
    chat = update.effective_chat

    # تسجيل المجموعة تلقائياً
    if chat.type in ["group", "supergroup"]:
        db.register_group(chat.id, chat.title)
        await update.message.reply_text(
            f"✅ تم تفعيل بوت أثر في *{chat.title}*!\n\n"
            "سيبدأ البوت إرسال:\n"
            "📚 دقيقة مراجعة — ٨ صباحاً\n"
            "🧠 سؤال يومي — ١٠ صباحاً\n"
            "✅ تحدي اليوم — ٢ ظهراً\n"
            "🧩 لغز التفكير — ٦ مساءً\n\n"
            "اكتب /help لقائمة الأوامر",
            parse_mode="Markdown"
        )
        return

    # في الخاص — تحقق من الاشتراك
    if chat.type == "private":
        is_subscribed = await check_subscription(u.id, ctx.bot)
        if not is_subscribed:
            keyboard = [[InlineKeyboardButton("اشترك في القناة 📢", url=CHANNEL_URL)]]
            await update.message.reply_text(
                "عليك الاشتراك في القناة ثم اضغط /start",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return

    db.upsert_student(u.id, u.username, u.full_name)
    await update.message.reply_text(
        f"أهلاً {u.first_name}! 👋\n\n"
        "🎓 *بوت أثر التعليمي*\n\n"
        "📌 الأوامر المتاحة:\n"
        "/points — رصيدك الحالي\n"
        "/board — لوحة المتصدرين\n"
        "/done — تسجيل إنجاز التحدي\n"
        "/history — تاريخ نشاطك\n"
        "/question — السؤال الحالي\n"
        "/challenge — تحدي اليوم\n"
        "/review — آخر معلومة\n"
        "/help — قائمة الأوامر\n\n"
        "➕ أضف البوت لمجموعتك واكتب /start فيها!",
        parse_mode="Markdown"
    )


async def cmd_settings(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("قناة البوت 📢", url=CHANNEL_URL)],
        [InlineKeyboardButton("مطور البوت 👨‍💻", url=f"https://t.me/{DEVELOPER_CHAT.replace('@', '')}")]
    ]
    await update.message.reply_text("⚙️ إعدادات البوت:", reply_markup=InlineKeyboardMarkup(keyboard))


async def cmd_points(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    db.upsert_student(u.id, u.username, u.full_name)
    student = db.get_student(u.id)
    if not student:
        await update.message.reply_text("ما وجدت بياناتك، جرّب /start أول.")
        return
    streak_text = f"🔥 سلسلة: {student['streak']} يوم" if student['streak'] > 1 else ""
    await update.message.reply_text(
        f"📊 نقاطك يا {u.first_name}\n\n"
        f"⭐ المجموع: {student['points']} نقطة\n"
        f"{streak_text}"
    )


async def cmd_leaderboard(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    board = db.get_leaderboard(10)
    if not board:
        await update.message.reply_text("ما في نقاط بعد!")
        return
    medals = ["🥇", "🥈", "🥉"]
    lines  = ["🏆 لوحة المتصدرين\n"]
    for i, row in enumerate(board):
        medal = medals[i] if i < 3 else f"{i+1}."
        name  = row["full_name"] or row["username"] or "—"
        lines.append(f"{medal} {name} — {row['points']} نقطة")
    await update.message.reply_text("\n".join(lines))


async def cmd_done(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    db.upsert_student(u.id, u.username, u.full_name)
    challenge = db.get_active_challenge()
    if not challenge:
        await update.message.reply_text("❌ ما في تحدٍّ مفتوح الآن.")
        return
    closes_at = datetime.fromisoformat(challenge["closes_at"])
    if datetime.now() > closes_at:
        await update.message.reply_text("⏰ انتهى وقت التحدي.")
        return
    registered = db.register_challenge_completion(challenge["id"], u.id)
    if not registered:
        await update.message.reply_text("✅ أنت مسجّل مسبقاً في هذا التحدي!")
        return
    db.add_points(u.id, POINTS["challenge_done"], "إنجاز تحدي اليوم")
    streak = db.update_streak(u.id)
    streak_msg = ""
    if streak >= POINTS.get("streak_days_required", 5):
        db.add_points(u.id, POINTS["streak_bonus"], f"بونص {streak} أيام متتالية")
        streak_msg = f"\n🎉 حصلت على بونص {POINTS['streak_bonus']} نقطة!"
    count = db.get_challenge_completions_count(challenge["id"])
    await update.message.reply_text(
        f"✅ تم تسجيل إنجازك يا {u.first_name}!\n"
        f"💫 +{POINTS['challenge_done']} نقاط\n"
        f"🔥 سلسلتك: {streak} يوم\n"
        f"👥 أنجز التحدي: {count} طالب"
        + streak_msg
    )


async def cmd_history(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    history = db.get_points_history(u.id, 10)
    if not history:
        await update.message.reply_text("ما في سجل نشاط بعد.")
        return
    lines = [f"📋 آخر نشاطاتك يا {u.first_name}\n"]
    for row in history:
        sign = "+" if row["amount"] > 0 else ""
        dt   = row["created_at"][:10]
        lines.append(f"• {row['reason']} — {sign}{row['amount']} نقطة ({dt})")
    await update.message.reply_text("\n".join(lines))


async def cmd_question(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = db.get_active_question()
    if not q:
        await update.message.reply_text("❌ ما في سؤال نشط الآن، انتظر سؤال الساعة ١٠ صباحاً.")
        return
    subject = f"[{q['subject']}] " if q["subject"] else ""
    await update.message.reply_text(
        f"🧠 السؤال اليومي {subject}\n\n{q['question']}\n\nاكتب إجابتك!"
    )


async def cmd_challenge(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    c = db.get_active_challenge()
    if not c:
        await update.message.reply_text("❌ ما في تحدٍّ نشط الآن، انتظر الساعة ٢ ظهراً.")
        return
    closes = datetime.fromisoformat(c["closes_at"]).strftime("%H:%M")
    count  = db.get_challenge_completions_count(c["id"])
    await update.message.reply_text(
        f"✅ تحدي اليوم\n\n📌 {c['challenge']}\n\n"
        f"⏰ يغلق الساعة {closes}\n"
        f"👥 أنجزه {count} طالب حتى الآن\n\n"
        "اكتب /done بعد ما تخلص!"
    )


async def cmd_review(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    r = db.get_last_review()
    if not r:
        await update.message.reply_text("❌ ما في مراجعة بعد.")
        return
    subject = f"[{r['subject']}] " if r["subject"] else ""
    await update.message.reply_text(f"📚 دقيقة مراجعة {subject}\n\n{r['content']}")


async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 قائمة الأوامر\n\n"
        "👤 للطلاب:\n"
        "/points — رصيدك الحالي\n"
        "/board — لوحة المتصدرين\n"
        "/done — تسجيل إنجاز التحدي\n"
        "/history — تاريخ نشاطك\n"
        "/question — السؤال اليومي\n"
        "/challenge — تحدي اليوم\n"
        "/review — آخر معلومة\n\n"
        "🏆 النقاط:\n"
        "• أول إجابة صحيحة = 10 نقاط\n"
        "• ثاني إجابة صحيحة = 5 نقاط\n"
        "• إنجاز تحدي اليوم = 3 نقاط\n"
        "• بونص 5 أيام متتالية = 15 نقطة\n\n"
        "➕ أضف البوت لأي مجموعة واكتب /start فيها!"
    )


# ═══════════════════════════════════════════════════════
#                   أوامر الأدمن
# ═══════════════════════════════════════════════════════

async def cmd_admin_add_question(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update.effective_user.id):
        return
    try:
        text    = " ".join(ctx.args)
        parts   = [p.strip() for p in text.split("|")]
        q, a    = parts[0], parts[1]
        subject = parts[2] if len(parts) > 2 else ""
        q_id    = db.add_question(q, a, subject)
        await update.message.reply_text(f"✅ تم إضافة السؤال #{q_id}")
    except Exception:
        await update.message.reply_text("❌ الصيغة:\n/add_q السؤال | الإجابة | المادة")


async def cmd_admin_add_challenge(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update.effective_user.id):
        return
    try:
        c_id = db.add_challenge(" ".join(ctx.args))
        await update.message.reply_text(f"✅ تم إضافة التحدي #{c_id}")
    except Exception:
        await update.message.reply_text("❌ اكتب النص بعد الأمر.")


async def cmd_admin_add_review(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update.effective_user.id):
        return
    try:
        text    = " ".join(ctx.args)
        parts   = [p.strip() for p in text.split("|")]
        content = parts[0]
        subject = parts[1] if len(parts) > 1 else ""
        r_id    = db.add_review_note(content, subject)
        await update.message.reply_text(f"✅ تم إضافة المراجعة #{r_id}")
    except Exception:
        await update.message.reply_text("❌ الصيغة: /add_r النص | المادة")


async def cmd_admin_add_riddle(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update.effective_user.id):
        return
    try:
        text  = " ".join(ctx.args)
        parts = [p.strip() for p in text.split("|")]
        r_id  = db.add_riddle(parts[0], parts[1])
        await update.message.reply_text(f"✅ تم إضافة اللغز #{r_id}")
    except Exception:
        await update.message.reply_text("❌ الصيغة: /add_l اللغز | الإجابة")


async def cmd_admin_reset_week(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update.effective_user.id):
        return
    db.reset_weekly_points()
    await update.message.reply_text("🔄 تم ريست النقاط الأسبوعية.")


async def cmd_admin_announce(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update.effective_user.id):
        return
    text = " ".join(ctx.args)
    if not text:
        await update.message.reply_text("❌ اكتب الإعلان بعد الأمر.")
        return
    groups = db.get_all_groups()
    count  = 0
    for g in groups:
        try:
            await ctx.bot.send_message(chat_id=g["group_id"], text=f"📢 إعلان\n\n{text}")
            count += 1
        except (Forbidden, BadRequest):
            db.deactivate_group(g["group_id"])
        except Exception as e:
            logger.error(f"Error sending to group {g['group_id']}: {e}")
    await update.message.reply_text(f"✅ تم إرسال الإعلان لـ {count} مجموعة.")
