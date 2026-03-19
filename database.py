"""
data/database.py — قاعدة البيانات مع دعم أكثر من مجموعة
"""

import sqlite3
import logging
from datetime import date, timedelta
from pathlib import Path

DB_PATH = Path(__file__).parent / "athar.db"
logger  = logging.getLogger(__name__)


def _conn():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


def init_db():
    with _conn() as con:
        con.executescript("""
        -- المجموعات المسجّلة
        CREATE TABLE IF NOT EXISTS groups (
            group_id    INTEGER PRIMARY KEY,
            title       TEXT,
            added_at    TEXT DEFAULT (date('now')),
            is_active   INTEGER DEFAULT 1
        );

        -- الطلاب
        CREATE TABLE IF NOT EXISTS students (
            user_id     INTEGER PRIMARY KEY,
            username    TEXT,
            full_name   TEXT,
            points      INTEGER DEFAULT 0,
            streak      INTEGER DEFAULT 0,
            last_active TEXT,
            joined_at   TEXT DEFAULT (date('now'))
        );

        -- سجل النقاط
        CREATE TABLE IF NOT EXISTS points_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER REFERENCES students(user_id),
            reason      TEXT,
            amount      INTEGER,
            created_at  TEXT DEFAULT (datetime('now'))
        );

        -- الأسئلة اليومية
        CREATE TABLE IF NOT EXISTS daily_questions (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            question      TEXT NOT NULL,
            answer        TEXT NOT NULL,
            subject       TEXT,
            used_on       TEXT,
            message_id    INTEGER,
            first_winner  INTEGER,
            second_winner INTEGER,
            is_open       INTEGER DEFAULT 1
        );

        -- الألغاز
        CREATE TABLE IF NOT EXISTS riddles (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            riddle           TEXT NOT NULL,
            answer           TEXT NOT NULL,
            used_on          TEXT,
            message_id       INTEGER,
            best_reply_user  INTEGER,
            is_open          INTEGER DEFAULT 1
        );

        -- التحديات اليومية
        CREATE TABLE IF NOT EXISTS daily_challenges (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            challenge   TEXT NOT NULL,
            used_on     TEXT,
            message_id  INTEGER,
            closes_at   TEXT,
            is_open     INTEGER DEFAULT 1
        );

        -- سجل إنجاز التحديات
        CREATE TABLE IF NOT EXISTS challenge_completions (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            challenge_id INTEGER REFERENCES daily_challenges(id),
            user_id      INTEGER REFERENCES students(user_id),
            completed_at TEXT DEFAULT (datetime('now')),
            UNIQUE(challenge_id, user_id)
        );

        -- دقائق المراجعة
        CREATE TABLE IF NOT EXISTS review_notes (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            content  TEXT NOT NULL,
            subject  TEXT,
            used_on  TEXT
        );

        -- سجل إجابات الأسئلة
        CREATE TABLE IF NOT EXISTS question_answers (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            question_id INTEGER REFERENCES daily_questions(id),
            user_id     INTEGER REFERENCES students(user_id),
            answered_at TEXT DEFAULT (datetime('now')),
            is_correct  INTEGER,
            UNIQUE(question_id, user_id)
        );
        """)
    logger.info("✅ قاعدة البيانات جاهزة")


# ─────────────────────────── GROUPS ──────────────────────────────────────

def register_group(group_id: int, title: str):
    with _conn() as con:
        con.execute("""
            INSERT INTO groups (group_id, title)
            VALUES (?, ?)
            ON CONFLICT(group_id) DO UPDATE SET title = excluded.title, is_active = 1
        """, (group_id, title or ""))


def get_all_groups() -> list:
    with _conn() as con:
        return con.execute(
            "SELECT group_id FROM groups WHERE is_active = 1"
        ).fetchall()


def deactivate_group(group_id: int):
    with _conn() as con:
        con.execute("UPDATE groups SET is_active = 0 WHERE group_id = ?", (group_id,))


# ─────────────────────────── STUDENTS ────────────────────────────────────

def upsert_student(user_id: int, username: str, full_name: str):
    with _conn() as con:
        con.execute("""
            INSERT INTO students (user_id, username, full_name)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                username  = excluded.username,
                full_name = excluded.full_name
        """, (user_id, username or "", full_name or ""))


def get_student(user_id: int):
    with _conn() as con:
        return con.execute(
            "SELECT * FROM students WHERE user_id = ?", (user_id,)
        ).fetchone()


def add_points(user_id: int, amount: int, reason: str):
    with _conn() as con:
        con.execute(
            "UPDATE students SET points = points + ? WHERE user_id = ?",
            (amount, user_id)
        )
        con.execute(
            "INSERT INTO points_log (user_id, reason, amount) VALUES (?, ?, ?)",
            (user_id, reason, amount)
        )


def get_leaderboard(limit: int = 10) -> list:
    with _conn() as con:
        return con.execute("""
            SELECT user_id, full_name, username, points
            FROM students ORDER BY points DESC LIMIT ?
        """, (limit,)).fetchall()


def get_points_history(user_id: int, limit: int = 10) -> list:
    with _conn() as con:
        return con.execute("""
            SELECT reason, amount, created_at FROM points_log
            WHERE user_id = ? ORDER BY created_at DESC LIMIT ?
        """, (user_id, limit)).fetchall()


def reset_weekly_points():
    with _conn() as con:
        con.execute("UPDATE students SET points = 0")
        con.execute("DELETE FROM points_log")
    logger.info("🔄 تم ريست النقاط الأسبوعية")


def get_weekly_winner():
    with _conn() as con:
        return con.execute("""
            SELECT user_id, full_name, username, points
            FROM students ORDER BY points DESC LIMIT 1
        """).fetchone()


def update_streak(user_id: int) -> int:
    today     = date.today().isoformat()
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    with _conn() as con:
        row = con.execute(
            "SELECT streak, last_active FROM students WHERE user_id = ?", (user_id,)
        ).fetchone()
        if not row:
            return 0
        last_active = row["last_active"]
        streak      = row["streak"]
        if last_active == today:
            return streak
        if last_active == yesterday:
            streak += 1
        else:
            streak = 1
        con.execute(
            "UPDATE students SET streak = ?, last_active = ? WHERE user_id = ?",
            (streak, today, user_id)
        )
        return streak


# ─────────────────────────── QUESTIONS ───────────────────────────────────

def add_question(question: str, answer: str, subject: str = "") -> int:
    with _conn() as con:
        cur = con.execute(
            "INSERT INTO daily_questions (question, answer, subject) VALUES (?, ?, ?)",
            (question, answer, subject)
        )
        return cur.lastrowid


def get_next_question():
    with _conn() as con:
        return con.execute(
            "SELECT * FROM daily_questions WHERE used_on IS NULL ORDER BY id LIMIT 1"
        ).fetchone()


def mark_question_used(q_id: int, msg_id: int):
    with _conn() as con:
        con.execute(
            "UPDATE daily_questions SET used_on = date('now'), message_id = ? WHERE id = ?",
            (msg_id, q_id)
        )


def get_active_question():
    today = date.today().isoformat()
    with _conn() as con:
        return con.execute(
            "SELECT * FROM daily_questions WHERE used_on = ? AND is_open = 1", (today,)
        ).fetchone()


def record_question_answer(q_id: int, user_id: int, is_correct: bool) -> bool:
    try:
        with _conn() as con:
            con.execute(
                "INSERT INTO question_answers (question_id, user_id, is_correct) VALUES (?, ?, ?)",
                (q_id, user_id, int(is_correct))
            )
        return True
    except sqlite3.IntegrityError:
        return False


def close_question(q_id: int):
    with _conn() as con:
        con.execute("UPDATE daily_questions SET is_open = 0 WHERE id = ?", (q_id,))


def set_question_winner(q_id: int, user_id: int, place: int):
    col = "first_winner" if place == 1 else "second_winner"
    with _conn() as con:
        con.execute(f"UPDATE daily_questions SET {col} = ? WHERE id = ?", (user_id, q_id))


def count_correct_answers(q_id: int) -> int:
    with _conn() as con:
        row = con.execute(
            "SELECT COUNT(*) as c FROM question_answers WHERE question_id = ? AND is_correct = 1",
            (q_id,)
        ).fetchone()
        return row["c"] if row else 0


# ─────────────────────────── CHALLENGES ──────────────────────────────────

def add_challenge(challenge: str) -> int:
    with _conn() as con:
        cur = con.execute(
            "INSERT INTO daily_challenges (challenge) VALUES (?)", (challenge,)
        )
        return cur.lastrowid


def get_next_challenge():
    with _conn() as con:
        return con.execute(
            "SELECT * FROM daily_challenges WHERE used_on IS NULL ORDER BY id LIMIT 1"
        ).fetchone()


def mark_challenge_used(c_id: int, msg_id: int, closes_at: str):
    with _conn() as con:
        con.execute(
            "UPDATE daily_challenges SET used_on = date('now'), message_id = ?, closes_at = ? WHERE id = ?",
            (msg_id, closes_at, c_id)
        )


def get_active_challenge():
    today = date.today().isoformat()
    with _conn() as con:
        return con.execute(
            "SELECT * FROM daily_challenges WHERE used_on = ? AND is_open = 1", (today,)
        ).fetchone()


def register_challenge_completion(c_id: int, user_id: int) -> bool:
    try:
        with _conn() as con:
            con.execute(
                "INSERT INTO challenge_completions (challenge_id, user_id) VALUES (?, ?)",
                (c_id, user_id)
            )
        return True
    except sqlite3.IntegrityError:
        return False


def close_challenge(c_id: int):
    with _conn() as con:
        con.execute("UPDATE daily_challenges SET is_open = 0 WHERE id = ?", (c_id,))


def get_challenge_completions_count(c_id: int) -> int:
    with _conn() as con:
        row = con.execute(
            "SELECT COUNT(*) as c FROM challenge_completions WHERE challenge_id = ?", (c_id,)
        ).fetchone()
        return row["c"] if row else 0


# ─────────────────────────── REVIEW NOTES ────────────────────────────────

def add_review_note(content: str, subject: str = "") -> int:
    with _conn() as con:
        cur = con.execute(
            "INSERT INTO review_notes (content, subject) VALUES (?, ?)", (content, subject)
        )
        return cur.lastrowid


def get_next_review():
    with _conn() as con:
        return con.execute(
            "SELECT * FROM review_notes WHERE used_on IS NULL ORDER BY id LIMIT 1"
        ).fetchone()


def mark_review_used(r_id: int):
    with _conn() as con:
        con.execute("UPDATE review_notes SET used_on = date('now') WHERE id = ?", (r_id,))


def get_last_review():
    with _conn() as con:
        return con.execute(
            "SELECT * FROM review_notes WHERE used_on IS NOT NULL ORDER BY used_on DESC LIMIT 1"
        ).fetchone()


# ─────────────────────────── RIDDLES ─────────────────────────────────────

def add_riddle(riddle: str, answer: str) -> int:
    with _conn() as con:
        cur = con.execute(
            "INSERT INTO riddles (riddle, answer) VALUES (?, ?)", (riddle, answer)
        )
        return cur.lastrowid


def get_next_riddle():
    with _conn() as con:
        return con.execute(
            "SELECT * FROM riddles WHERE used_on IS NULL ORDER BY id LIMIT 1"
        ).fetchone()


def mark_riddle_used(r_id: int, msg_id: int):
    with _conn() as con:
        con.execute(
            "UPDATE riddles SET used_on = date('now'), message_id = ? WHERE id = ?",
            (msg_id, r_id)
        )


def get_active_riddle():
    today = date.today().isoformat()
    with _conn() as con:
        return con.execute(
            "SELECT * FROM riddles WHERE used_on = ? AND is_open = 1", (today,)
        ).fetchone()
