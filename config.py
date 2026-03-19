"""
config.py — إعدادات بوت أثر
"""

# ── الإعدادات الأساسية ─────────────────────────────────────────────────────
BOT_TOKEN      = "8619939092:AAE__fPrVHkEBaqdG961zl-xN8ORBw4zINA"
ADMIN_IDS      = [8173083016]
CHANNEL_URL    = "https://t.me/AtharEdu"
CHANNEL_ID     = "@AtharEdu"
DEVELOPER_CHAT = "@AlmuthabirHQ"
GROUP_ID       = -1002434567890  # يرجى استبداله بـ ID المجموعة الصحيح

# ── إعدادات النقاط ────────────────────────────────────────────────────────
POINTS = {
    "question_first":   10,
    "question_second":   5,
    "riddle_best":       8,
    "challenge_done":    3,
    "streak_bonus":     15,
    "streak_days_required": 5,
}

# ── إعدادات التوقيت (بتوقيت بغداد UTC+3) ────────────────────────────────
SCHEDULE = {
    "review":          "08:00",
    "question":        "10:00",
    "challenge":       "14:00",
    "challenge_close": "18:00",
    "riddle":          "18:00",
    "poll":            "21:00",
    "weekly_winner":   "20:00",
}

TIMEZONE = "Asia/Baghdad"

# ── حدود التحدي ───────────────────────────────────────────────────────────
CHALLENGE_OPEN_HOURS    = 4
STREAK_DAYS_REQUIRED    = 5
