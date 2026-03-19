"""
scheduler/jobs.py — الجدولة التلقائية لكل المجموعات
"""

import logging
from datetime import datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron      import CronTrigger
from telegram.ext                   import Application
from telegram.error                 import Forbidden, BadRequest

from config import SCHEDULE, TIMEZONE, CHALLENGE_OPEN_HOURS, POINTS
from data   import database as db

logger = logging.getLogger(__name__)


async def _broadcast(app: Application, text: str, **kwargs):
    """يرسل رسالة لكل المجموعات المسجّلة"""
    groups = db.get_all_groups()
    for g in groups:
        try:
            await app.bot.send_message(chat_id=g["group_id"], text=text, **kwargs)
        except (Forbidden, BadRequest):
            db.deactivate_group(g["group_id"])
        except Exception as e:
            logger.error(f"Error broadcasting to {g['group_id']}: {e}")


async def post_review(app: Application):
    r = db.get_next_review()
    if not r:
        await _broadcast(app, "📚 دقيقة مراجعة\n\n⚠️ تم استنفاد المراجعات، سيُضاف محتوى جديد قريباً.")
        return
    subject = f"[{r['subject']}] " if r["subject"] else ""
    await _broadcast(app,
        f"📚 دقيقة مراجعة {subject}\n\n"
        f"{r['content']}\n\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"📖 راجع هاي المعلومة وتذكرها!"
    )
    db.mark_review_used(r["id"])
    logger.info(f"✅ نُشرت المراجعة #{r['id']}")


async def post_daily_question(app: Application):
    q = db.get_next_question()
    if not q:
        await _broadcast(app, "🧠 السؤال اليومي\n\n⚠️ تم استنفاد الأسئلة، سيُضاف المزيد قريباً.")
        return
    subject = f"[{q['subject']}] " if q["subject"] else ""
    groups  = db.get_all_groups()
    for g in groups:
        try:
            msg = await app.bot.send_message(
                chat_id=g["group_id"],
                text=(
                    f"🧠 السؤال اليومي {subject}\n\n"
                    f"❓ {q['question']}\n\n"
                    f"━━━━━━━━━━━━━━━━\n"
                    f"🥇 أول إجابة صحيحة = +{POINTS['question_first']} نقطة\n"
                    f"🥈 ثاني إجابة صحيحة = +{POINTS['question_second']} نقاط\n\n"
                    f"اكتب إجابتك الآن! ⬇️"
                )
            )
            db.mark_question_used(q["id"], msg.message_id)
        except (Forbidden, BadRequest):
            db.deactivate_group(g["group_id"])
        except Exception as e:
            logger.error(f"Error: {e}")
    logger.info(f"✅ نُشر السؤال #{q['id']}")


async def post_daily_challenge(app: Application):
    c = db.get_next_challenge()
    if not c:
        await _broadcast(app, "✅ تحدي اليوم\n\n⚠️ ما في تحدٍّ اليوم، نكمل بكرة!")
        return
    closes_at  = datetime.now() + timedelta(hours=CHALLENGE_OPEN_HOURS)
    closes_str = closes_at.strftime("%H:%M")
    groups = db.get_all_groups()
    for g in groups:
        try:
            msg = await app.bot.send_message(
                chat_id=g["group_id"],
                text=(
                    f"✅ تحدي اليوم\n\n"
                    f"📌 {c['challenge']}\n\n"
                    f"━━━━━━━━━━━━━━━━\n"
                    f"⏰ يغلق الساعة {closes_str}\n"
                    f"💫 +{POINTS['challenge_done']} نقاط لكل من ينجزه\n"
                    f"🔥 أنجز 5 أيام متتالية = +{POINTS['streak_bonus']} بونص!\n\n"
                    f"اكتب /done بعد ما تخلص ✔️"
                )
            )
            db.mark_challenge_used(c["id"], msg.message_id, closes_at.isoformat())
        except (Forbidden, BadRequest):
            db.deactivate_group(g["group_id"])
        except Exception as e:
            logger.error(f"Error: {e}")
    logger.info(f"✅ نُشر التحدي #{c['id']}")


async def close_daily_challenge(app: Application):
    c = db.get_active_challenge()
    if not c:
        return
    count = db.get_challenge_completions_count(c["id"])
    db.close_challenge(c["id"])
    await _broadcast(app,
        f"⏰ انتهى وقت التحدي!\n\n"
        f"✅ أنجزه {count} طالب اليوم\n\nبالتوفيق للجميع 💪"
    )


async def post_riddle(app: Application):
    r = db.get_next_riddle()
    if not r:
        await _broadcast(app, "🧩 لغز التفكير\n\n⚠️ ما في لغز اليوم، نكمل بكرة!")
        return
    groups = db.get_all_groups()
    for g in groups:
        try:
            msg = await app.bot.send_message(
                chat_id=g["group_id"],
                text=(
                    f"🧩 لغز التفكير\n\n"
                    f"🤔 {r['riddle']}\n\n"
                    f"━━━━━━━━━━━━━━━━\n"
                    f"أفضل تفسير يحصل على +{POINTS['riddle_best']} نقاط!\n"
                    f"الجواب غداً ⬇️"
                )
            )
            db.mark_riddle_used(r["id"], msg.message_id)
        except (Forbidden, BadRequest):
            db.deactivate_group(g["group_id"])
        except Exception as e:
            logger.error(f"Error: {e}")


async def post_weekly_poll(app: Application):
    polls = [
        ("أصعب مادة بالسادس؟",      ["الرياضيات", "الفيزياء", "الكيمياء", "الأحياء"]),
        ("كم ساعة تذاكر يومياً؟",   ["أقل من ساعة", "١-٢ ساعة", "٢-٤ ساعات", "أكثر من ٤"]),
        ("أفضل وقت للمذاكرة؟",      ["الصباح الباكر", "بعد الظهر", "المساء", "الليل"]),
        ("أكثر شي يصعّب المذاكرة؟", ["الجوال", "الضجيج", "قلة النوم", "صعوبة المادة"]),
        ("أفضل طريقة مراجعة؟",      ["الملخصات", "حل الأسئلة", "الشرح لأحد", "القراءة"]),
    ]
    from datetime import date
    poll_data         = polls[date.today().isocalendar()[1] % len(polls)]
    question, options = poll_data
    groups = db.get_all_groups()
    for g in groups:
        try:
            await app.bot.send_poll(
                chat_id=g["group_id"],
                question=f"🗳️ تصويت الأسبوع\n\n{question}",
                options=options,
                is_anonymous=False,
                allows_multiple_answers=False,
            )
        except (Forbidden, BadRequest):
            db.deactivate_group(g["group_id"])
        except Exception as e:
            logger.error(f"Error: {e}")


async def announce_weekly_winner(app: Application):
    winner = db.get_weekly_winner()
    board  = db.get_leaderboard(5)
    if not winner or winner["points"] == 0:
        await _broadcast(app, "🏆 طالب الأسبوع\n\nما في نقاط هذا الأسبوع بعد!\nنشاطكم يحدد الفائز 💪")
        return
    name  = winner["full_name"] or winner["username"] or "—"
    lines = ["🏆 طالب الأسبوع 🏆\n", f"🥇 المتصدر: {name}", f"⭐ النقاط: {winner['points']} نقطة\n",
             "━━━━━━━━━━━━━━━━", "📊 أفضل ٥ طلاب:\n"]
    medals = ["🥇", "🥈", "🥉", "4.", "5."]
    for i, row in enumerate(board):
        n = row["full_name"] or row["username"] or "—"
        lines.append(f"{medals[i]} {n} — {row['points']} نقطة")
    lines += ["\n━━━━━━━━━━━━━━━━", f"مبروك {name}! 🎉", "استمروا بالتفوق الأسبوع القادم 💪"]
    await _broadcast(app, "\n".join(lines))


def setup_scheduler(app: Application):
    scheduler = AsyncIOScheduler(timezone=TIMEZONE)

    def _time(t):
        h, m = t.split(":")
        return int(h), int(m)

    rh, rm = _time(SCHEDULE["review"])
    qh, qm = _time(SCHEDULE["question"])
    ch, cm = _time(SCHEDULE["challenge"])
    xh, xm = _time(SCHEDULE["challenge_close"])
    dh, dm = _time(SCHEDULE["riddle"])
    ph, pm = _time(SCHEDULE["poll"])
    wh, wm = _time(SCHEDULE["weekly_winner"])

    scheduler.add_job(post_review,            CronTrigger(hour=rh, minute=rm), args=[app])
    scheduler.add_job(post_daily_question,    CronTrigger(hour=qh, minute=qm), args=[app])
    scheduler.add_job(post_daily_challenge,   CronTrigger(hour=ch, minute=cm), args=[app])
    scheduler.add_job(close_daily_challenge,  CronTrigger(hour=xh, minute=xm), args=[app])
    scheduler.add_job(post_riddle,            CronTrigger(hour=dh, minute=dm), args=[app])
    scheduler.add_job(post_weekly_poll,       CronTrigger(day_of_week=0, hour=ph, minute=pm), args=[app])
    scheduler.add_job(announce_weekly_winner, CronTrigger(day_of_week=4, hour=wh, minute=wm), args=[app])

    scheduler.start()
    logger.info("⏰ الجدولة التلقائية شغالة")
