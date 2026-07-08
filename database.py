import csv
import shutil
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd

from config import ACHIEVEMENTS, DB_PATH, EXPORTS_DIR, LEGACY_DB_PATH


def _db_target() -> Path:
    if LEGACY_DB_PATH.exists() and LEGACY_DB_PATH != DB_PATH and not DB_PATH.exists() and _is_usable_sqlite(LEGACY_DB_PATH):
        shutil.copy2(LEGACY_DB_PATH, DB_PATH)
    DB_PATH.parent.mkdir(exist_ok=True)
    if DB_PATH.exists() and not _is_usable_sqlite(DB_PATH):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        quarantined = EXPORTS_DIR / f"corrupt_database_{timestamp}.sqlite"
        try:
            shutil.move(str(DB_PATH), quarantined)
        except OSError:
            DB_PATH.unlink(missing_ok=True)
    return DB_PATH


def _is_usable_sqlite(path: Path) -> bool:
    try:
        with sqlite3.connect(path) as conn:
            result = conn.execute("PRAGMA integrity_check").fetchone()
        return bool(result and result[0] == "ok")
    except sqlite3.DatabaseError:
        return False


@contextmanager
def get_connection():
    conn = sqlite3.connect(_db_target(), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = MEMORY")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA temp_store = MEMORY")
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _columns(conn, table):
    return {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def _add_column(conn, table, column, definition):
    if column not in _columns(conn, table):
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def init_db():
    with get_connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                profile_image TEXT,
                theme TEXT DEFAULT 'dark',
                xp INTEGER DEFAULT 0,
                level INTEGER DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS habits (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT DEFAULT '',
                notes TEXT DEFAULT '',
                category TEXT DEFAULT 'Personal',
                priority TEXT DEFAULT 'Medium',
                color TEXT DEFAULT '#6C5CE7',
                emoji TEXT DEFAULT '✅',
                frequency TEXT DEFAULT 'Daily',
                reminder_time TEXT DEFAULT '',
                target_count INTEGER DEFAULT 1,
                archived INTEGER DEFAULT 0,
                created_date TEXT DEFAULT CURRENT_DATE,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS habit_logs (
                id TEXT PRIMARY KEY,
                habit_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                completed INTEGER DEFAULT 1,
                completed_date TEXT NOT NULL,
                note TEXT DEFAULT '',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(habit_id, completed_date),
                FOREIGN KEY(habit_id) REFERENCES habits(id) ON DELETE CASCADE,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS goals (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                period TEXT NOT NULL,
                target INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, period),
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS reminders (
                id TEXT PRIMARY KEY,
                habit_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                reminder_time TEXT NOT NULL,
                enabled INTEGER DEFAULT 1,
                UNIQUE(habit_id),
                FOREIGN KEY(habit_id) REFERENCES habits(id) ON DELETE CASCADE,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS achievements (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                code TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT DEFAULT '',
                icon TEXT DEFAULT '🏅',
                earned_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, code),
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            );
            """
        )
        for column, definition in {
            "profile_image": "TEXT",
            "theme": "TEXT DEFAULT 'dark'",
            "xp": "INTEGER DEFAULT 0",
            "level": "INTEGER DEFAULT 1",
            "created_at": "TEXT DEFAULT CURRENT_TIMESTAMP",
        }.items():
            _add_column(conn, "users", column, definition)
        for column, definition in {
            "description": "TEXT DEFAULT ''",
            "notes": "TEXT DEFAULT ''",
            "category": "TEXT DEFAULT 'Personal'",
            "priority": "TEXT DEFAULT 'Medium'",
            "color": "TEXT DEFAULT '#6C5CE7'",
            "emoji": "TEXT DEFAULT '✅'",
            "frequency": "TEXT DEFAULT 'Daily'",
            "reminder_time": "TEXT DEFAULT ''",
            "target_count": "INTEGER DEFAULT 1",
            "archived": "INTEGER DEFAULT 0",
            "updated_at": "TEXT DEFAULT CURRENT_TIMESTAMP",
        }.items():
            _add_column(conn, "habits", column, definition)
        for column, definition in {
            "user_id": "TEXT DEFAULT ''",
            "note": "TEXT DEFAULT ''",
            "created_at": "TEXT DEFAULT CURRENT_TIMESTAMP",
        }.items():
            _add_column(conn, "habit_logs", column, definition)
        for column, definition in {
            "period": "TEXT DEFAULT 'Daily'",
            "target": "INTEGER DEFAULT 3",
            "created_at": "TEXT DEFAULT CURRENT_TIMESTAMP",
        }.items():
            _add_column(conn, "goals", column, definition)
        _repair_legacy_logs(conn)
        _seed_missing_goals(conn)


def _seed_missing_goals(conn):
    for period, target in (("Daily", 3), ("Weekly", 18), ("Monthly", 72)):
        conn.execute(
            """
            INSERT INTO goals (id, user_id, period, target)
            SELECT lower(hex(randomblob(16))), users.id, ?, ?
            FROM users
            WHERE NOT EXISTS (
                SELECT 1 FROM goals WHERE goals.user_id = users.id AND goals.period = ?
            )
            """,
            (period, target, period),
        )


def _repair_legacy_logs(conn):
    logs = conn.execute(
        """
        SELECT habit_logs.id, habits.user_id
        FROM habit_logs
        JOIN habits ON habits.id = habit_logs.habit_id
        WHERE habit_logs.user_id = '' OR habit_logs.user_id IS NULL
        """
    ).fetchall()
    for row in logs:
        conn.execute("UPDATE habit_logs SET user_id=? WHERE id=?", (row["user_id"], row["id"]))


def fetch_one(query, params=()):
    with get_connection() as conn:
        row = conn.execute(query, params).fetchone()
        return dict(row) if row else None


def fetch_all(query, params=()):
    with get_connection() as conn:
        return [dict(row) for row in conn.execute(query, params).fetchall()]


def execute(query, params=()):
    with get_connection() as conn:
        conn.execute(query, params)


def add_xp(user_id, points):
    user = fetch_one("SELECT xp FROM users WHERE id=?", (user_id,))
    xp = max(0, int((user or {}).get("xp") or 0) + int(points))
    level = max(1, xp // 120 + 1)
    execute("UPDATE users SET xp=?, level=? WHERE id=?", (xp, level, user_id))
    return xp, level


def get_user_stats(user_id):
    habits = fetch_all("SELECT * FROM habits WHERE user_id=? AND archived=0", (user_id,))
    logs = fetch_all("SELECT * FROM habit_logs WHERE user_id=? AND completed=1", (user_id,))
    today = date.today().isoformat()
    done_today = {log["habit_id"] for log in logs if str(log.get("completed_date", ""))[:10] == today}
    total = len(habits)
    completed = sum(1 for habit in habits if habit["id"] in done_today)
    percent = int((completed / total) * 100) if total else 0
    return {"total": total, "completed": completed, "pending": max(total - completed, 0), "percent": percent, "logs": len(logs)}


def get_habit_dataframe(user_id, days=180):
    start = date.today() - timedelta(days=days)
    rows = fetch_all(
        """
        SELECT h.id, h.title, h.category, h.priority, h.color, h.emoji, h.created_date,
               l.completed_date, l.completed
        FROM habits h
        LEFT JOIN habit_logs l ON h.id = l.habit_id AND l.completed=1
        WHERE h.user_id=? AND DATE(COALESCE(l.completed_date, h.created_date)) >= DATE(?)
        ORDER BY COALESCE(l.completed_date, h.created_date)
        """,
        (user_id, start.isoformat()),
    )
    df = pd.DataFrame(rows)
    if not df.empty and "completed_date" in df:
        df["completed_day"] = pd.to_datetime(df["completed_date"], errors="coerce").dt.date
    return df


def habit_completion_dates(habit_id):
    rows = fetch_all(
        "SELECT completed_date FROM habit_logs WHERE habit_id=? AND completed=1 ORDER BY completed_date",
        (habit_id,),
    )
    dates = []
    for row in rows:
        try:
            dates.append(datetime.fromisoformat(str(row["completed_date"])[:10]).date())
        except (TypeError, ValueError):
            continue
    return sorted(set(dates))


def calculate_streaks(habit_id):
    dates = habit_completion_dates(habit_id)
    if not dates:
        return 0, 0
    longest = current = 1
    for index in range(1, len(dates)):
        if (dates[index] - dates[index - 1]).days == 1:
            current += 1
            longest = max(longest, current)
        elif dates[index] != dates[index - 1]:
            current = 1
    active = 0
    cursor = date.today()
    completed = set(dates)
    while cursor in completed:
        active += 1
        cursor -= timedelta(days=1)
    return active, longest


def maybe_award_achievements(user_id):
    stats = get_user_stats(user_id)
    earned = []
    habits = fetch_all("SELECT id FROM habits WHERE user_id=?", (user_id,))
    longest = 0
    for habit in habits:
        _, habit_longest = calculate_streaks(habit["id"])
        longest = max(longest, habit_longest)

    checks = {
        "first_win": stats["logs"] >= 1,
        "three_day_streak": longest >= 3,
        "seven_day_streak": longest >= 7,
        "thirty_completions": stats["logs"] >= 30,
        "perfect_day": stats["total"] > 0 and stats["percent"] == 100,
    }
    with get_connection() as conn:
        for code, title, description, icon, _ in ACHIEVEMENTS:
            if not checks.get(code):
                continue
            before = conn.total_changes
            conn.execute(
                """
                INSERT OR IGNORE INTO achievements (id, user_id, code, title, description, icon)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (str(uuid.uuid4()), user_id, code, title, description, icon),
            )
            if conn.total_changes > before:
                earned.append({"code": code, "title": title, "description": description, "icon": icon})
    return earned


def export_habits_csv(user_id):
    path = EXPORTS_DIR / f"habits_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    rows = fetch_all("SELECT * FROM habits WHERE user_id=? ORDER BY created_date DESC", (user_id,))
    fieldnames = ["title", "description", "notes", "category", "priority", "color", "emoji", "frequency", "reminder_time", "target_count", "archived"]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})
    return path


def _positive_int(value, default=1):
    try:
        return max(1, int(value))
    except (TypeError, ValueError):
        return default


def import_habits_csv(user_id, uploaded_file):
    df = pd.read_csv(uploaded_file)
    if "title" not in df.columns:
        raise ValueError("CSV must include a title column.")
    count = 0
    with get_connection() as conn:
        for _, row in df.fillna("").iterrows():
            title = str(row.get("title", "")).strip()
            if not title:
                continue
            conn.execute(
                """
                INSERT INTO habits
                (id, user_id, title, description, notes, category, priority, color, emoji, frequency, reminder_time, target_count, archived, created_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    user_id,
                    title[:120],
                    str(row.get("description", ""))[:500],
                    str(row.get("notes", ""))[:2000],
                    str(row.get("category", "Personal") or "Personal")[:80],
                    str(row.get("priority", "Medium") or "Medium")[:40],
                    str(row.get("color", "#6C5CE7") or "#6C5CE7")[:20],
                    str(row.get("emoji", "✅") or "✅")[:8],
                    str(row.get("frequency", "Daily") or "Daily")[:40],
                    str(row.get("reminder_time", ""))[:10],
                    _positive_int(row.get("target_count", 1)),
                    int(str(row.get("archived", 0) or 0).lower() in {"1", "true", "yes"}),
                    date.today().isoformat(),
                ),
            )
            count += 1
    return count


def create_backup():
    path = EXPORTS_DIR / f"habit_tracker_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.sqlite"
    shutil.copy2(_db_target(), path)
    return path


def restore_backup(uploaded_file):
    backup_path = EXPORTS_DIR / f"restore_source_{datetime.now().strftime('%Y%m%d_%H%M%S')}.sqlite"
    backup_path.write_bytes(uploaded_file.getvalue())
    try:
        with sqlite3.connect(backup_path) as conn:
            conn.execute("PRAGMA integrity_check").fetchone()
    except sqlite3.DatabaseError as exc:
        backup_path.unlink(missing_ok=True)
        raise ValueError("Uploaded file is not a valid SQLite database.") from exc
    shutil.copy2(backup_path, DB_PATH)
    init_db()
