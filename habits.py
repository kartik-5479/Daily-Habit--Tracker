import re
import uuid
from datetime import date

import streamlit as st

from config import CATEGORIES, COLOR_PALETTE, FREQUENCIES, HABIT_EMOJIS, PRIORITIES
from database import (
    add_xp,
    calculate_streaks,
    execute,
    fetch_all,
    fetch_one,
    get_connection,
    import_habits_csv,
    maybe_award_achievements,
)
from utils import compact_date, confetti, progress_bar, rerun

TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def list_habits(user_id, include_archived=False):
    archived_sql = "" if include_archived else "AND archived=0"
    return fetch_all(
        f"SELECT * FROM habits WHERE user_id=? {archived_sql} ORDER BY archived ASC, created_date DESC, title ASC",
        (user_id,),
    )


def _validate_habit_data(data):
    title = (data.get("title") or "").strip()
    if not title:
        raise ValueError("Habit name is required.")
    reminder_time = (data.get("reminder_time") or "").strip()
    if reminder_time and not TIME_RE.match(reminder_time):
        raise ValueError("Reminder time must use HH:MM in 24-hour format.")
    target_count = int(data.get("target_count") or 1)
    if target_count < 1 or target_count > 12:
        raise ValueError("Target count must be between 1 and 12.")
    return {
        "title": title[:120],
        "description": (data.get("description") or "").strip()[:500],
        "notes": (data.get("notes") or "").strip()[:2000],
        "category": data.get("category") if data.get("category") in CATEGORIES else "Personal",
        "priority": data.get("priority") if data.get("priority") in PRIORITIES else "Medium",
        "color": data.get("color") or COLOR_PALETTE[0],
        "emoji": data.get("emoji") if data.get("emoji") in HABIT_EMOJIS else HABIT_EMOJIS[0],
        "frequency": data.get("frequency") if data.get("frequency") in FREQUENCIES else "Daily",
        "reminder_time": reminder_time,
        "target_count": target_count,
    }


def add_habit(user_id, data):
    data = _validate_habit_data(data)
    habit_id = str(uuid.uuid4())
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO habits
            (id, user_id, title, description, notes, category, priority, color, emoji, frequency, reminder_time, target_count, created_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                habit_id,
                user_id,
                data["title"],
                data["description"],
                data["notes"],
                data["category"],
                data["priority"],
                data["color"],
                data["emoji"],
                data["frequency"],
                data["reminder_time"],
                data["target_count"],
                date.today().isoformat(),
            ),
        )
        if data["reminder_time"]:
            conn.execute(
                "INSERT INTO reminders (id, habit_id, user_id, reminder_time, enabled) VALUES (?, ?, ?, ?, 1)",
                (str(uuid.uuid4()), habit_id, user_id, data["reminder_time"]),
            )
    return habit_id


def update_habit(habit_id, data):
    data = _validate_habit_data(data)
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE habits
            SET title=?, description=?, notes=?, category=?, priority=?, color=?, emoji=?,
                frequency=?, reminder_time=?, target_count=?, updated_at=CURRENT_TIMESTAMP
            WHERE id=?
            """,
            (
                data["title"],
                data["description"],
                data["notes"],
                data["category"],
                data["priority"],
                data["color"],
                data["emoji"],
                data["frequency"],
                data["reminder_time"],
                data["target_count"],
                habit_id,
            ),
        )
        habit = conn.execute("SELECT user_id FROM habits WHERE id=?", (habit_id,)).fetchone()
        if not habit:
            raise ValueError("Habit not found.")
        if data["reminder_time"]:
            conn.execute(
                """
                INSERT INTO reminders (id, habit_id, user_id, reminder_time, enabled)
                VALUES (?, ?, ?, ?, 1)
                ON CONFLICT(habit_id) DO UPDATE SET reminder_time=excluded.reminder_time, enabled=1
                """,
                (str(uuid.uuid4()), habit_id, habit["user_id"], data["reminder_time"]),
            )
        else:
            conn.execute("DELETE FROM reminders WHERE habit_id=?", (habit_id,))


def archive_habit(habit_id, archived=True):
    execute("UPDATE habits SET archived=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (int(archived), habit_id))


def delete_habit(habit_id):
    execute("DELETE FROM habits WHERE id=?", (habit_id,))


def is_completed_today(habit_id):
    return bool(
        fetch_one(
            "SELECT id FROM habit_logs WHERE habit_id=? AND completed=1 AND completed_date=?",
            (habit_id, date.today().isoformat()),
        )
    )


def complete_habit(habit, note=""):
    today = date.today().isoformat()
    with get_connection() as conn:
        before = conn.total_changes
        conn.execute(
            """
            INSERT OR IGNORE INTO habit_logs (id, habit_id, user_id, completed, completed_date, note)
            VALUES (?, ?, ?, 1, ?, ?)
            """,
            (str(uuid.uuid4()), habit["id"], habit["user_id"], today, note[:500]),
        )
        inserted = conn.total_changes > before
    if not inserted:
        return None, []
    xp, _ = add_xp(habit["user_id"], 12)
    earned = maybe_award_achievements(habit["user_id"])
    return xp, earned


def undo_completion(habit_id):
    execute("DELETE FROM habit_logs WHERE habit_id=? AND completed_date=?", (habit_id, date.today().isoformat()))


def habit_score(habit_id):
    active, longest = calculate_streaks(habit_id)
    total = fetch_one("SELECT COUNT(*) AS count FROM habit_logs WHERE habit_id=? AND completed=1", (habit_id,))["count"]
    return min(100, total * 3 + longest * 5 + active * 7)


def _habit_form(user_id, habit=None):
    defaults = habit or {}
    with st.form(f"habit_form_{defaults.get('id', 'new')}"):
        c1, c2 = st.columns([1.2, 0.8])
        with c1:
            title = st.text_input("Habit name", value=defaults.get("title", ""), placeholder="Morning run")
            description = st.text_input("Description", value=defaults.get("description", ""))
            notes = st.text_area("Notes", value=defaults.get("notes", ""), height=90)
        with c2:
            emoji = st.selectbox("Emoji", HABIT_EMOJIS, index=HABIT_EMOJIS.index(defaults.get("emoji")) if defaults.get("emoji") in HABIT_EMOJIS else 0)
            category = st.selectbox("Category", CATEGORIES, index=CATEGORIES.index(defaults.get("category")) if defaults.get("category") in CATEGORIES else 0)
            priority = st.selectbox("Priority", PRIORITIES, index=PRIORITIES.index(defaults.get("priority")) if defaults.get("priority") in PRIORITIES else 1)
            frequency = st.selectbox("Frequency", FREQUENCIES, index=FREQUENCIES.index(defaults.get("frequency")) if defaults.get("frequency") in FREQUENCIES else 0)
            color = st.color_picker("Color", defaults.get("color") or COLOR_PALETTE[0])
            reminder_time = st.text_input("Reminder time", value=defaults.get("reminder_time", ""), placeholder="07:30")
            target_count = st.number_input("Target count", min_value=1, max_value=12, value=int(defaults.get("target_count") or 1))
        submitted = st.form_submit_button("Save habit" if habit else "Create habit")
    if submitted:
        data = {
            "title": title,
            "description": description,
            "notes": notes,
            "emoji": emoji,
            "category": category,
            "priority": priority,
            "frequency": frequency,
            "color": color,
            "reminder_time": reminder_time,
            "target_count": target_count,
        }
        try:
            if habit:
                update_habit(habit["id"], data)
                st.toast("Habit updated.", icon="✨")
            else:
                add_habit(user_id, data)
                st.toast("Habit created.", icon="✅")
            rerun()
        except Exception as exc:
            st.error(str(exc))


def render_habit_card(habit):
    completed = is_completed_today(habit["id"])
    active, longest = calculate_streaks(habit["id"])
    score = habit_score(habit["id"])
    opacity = ".56" if habit.get("archived") else "1"
    st.markdown(
        f"""
        <div class="habit-card" style="border-left: 6px solid {habit.get('color')}; opacity:{opacity};">
            <div class="habit-title">{habit.get('emoji')} {habit.get('title')}</div>
            <div class="muted">{habit.get('category')} | {habit.get('priority')} | {habit.get('frequency')} | Created {compact_date(habit.get('created_date'))}</div>
            <div style="margin-top:10px;">
                <span class="chip">🔥 Current {active}</span>
                <span class="chip">🏁 Longest {longest}</span>
                <span class="chip">⚡ Score {score}</span>
                <span class="chip">⏰ {habit.get('reminder_time') or 'No reminder'}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    cols = st.columns([1, 1, 1, 1, 1])
    if not habit.get("archived"):
        if completed:
            if cols[0].button("Undo", key=f"undo_{habit['id']}"):
                undo_completion(habit["id"])
                rerun()
        elif cols[0].button("Complete", key=f"complete_{habit['id']}"):
            _, earned = complete_habit(habit)
            for badge in earned:
                st.toast(f"{badge['icon']} {badge['title']} unlocked", icon=badge["icon"])
            if earned:
                confetti()
            rerun()
        if cols[1].button("Archive", key=f"archive_{habit['id']}"):
            archive_habit(habit["id"], True)
            rerun()
    else:
        if cols[0].button("Restore", key=f"restore_{habit['id']}"):
            archive_habit(habit["id"], False)
            rerun()
    with cols[2].popover("Edit"):
        _habit_form(habit["user_id"], habit)
    if cols[3].button("Delete", key=f"delete_{habit['id']}"):
        delete_habit(habit["id"])
        rerun()


def render_habits_page(user):
    st.subheader("Habit Studio")
    st.caption("Create, tune, complete, restore, and review every habit in one fast workspace.")
    tabs = st.tabs(["Active", "Add", "Archive", "Import"])
    with tabs[0]:
        habits = list_habits(user["id"])
        if habits:
            stats_completed = sum(1 for habit in habits if is_completed_today(habit["id"]))
            progress_bar(int(stats_completed / len(habits) * 100), "Today's habit completion")
        q1, q2, q3 = st.columns([1.2, 0.9, 0.9])
        search = q1.text_input("Search", placeholder="Filter by name, notes, category")
        category = q2.selectbox("Category filter", ["All"] + CATEGORIES)
        sort = q3.selectbox("Sort", ["Newest", "Name", "Priority", "Score"])
        filtered = []
        for habit in habits:
            haystack = " ".join(str(habit.get(key, "")) for key in ("title", "notes", "category", "description")).lower()
            if search and search.lower() not in haystack:
                continue
            if category != "All" and habit.get("category") != category:
                continue
            filtered.append(habit)
        if sort == "Name":
            filtered.sort(key=lambda h: h["title"].lower())
        elif sort == "Priority":
            order = {name: index for index, name in enumerate(reversed(PRIORITIES))}
            filtered.sort(key=lambda h: order.get(h.get("priority"), 99))
        elif sort == "Score":
            filtered.sort(key=lambda h: habit_score(h["id"]), reverse=True)
        if not filtered:
            st.info("No active habits match this view.")
        for habit in filtered:
            render_habit_card(habit)
        if habits and all(is_completed_today(h["id"]) for h in habits):
            if st.session_state.get("confetti_day") != date.today().isoformat():
                st.session_state["confetti_day"] = date.today().isoformat()
                confetti()
    with tabs[1]:
        _habit_form(user["id"])
    with tabs[2]:
        archived = [habit for habit in list_habits(user["id"], include_archived=True) if habit.get("archived")]
        if not archived:
            st.info("Archived habits will appear here.")
        for habit in archived:
            render_habit_card(habit)
    with tabs[3]:
        uploaded = st.file_uploader("Import habits from CSV", type=["csv"])
        if uploaded and st.button("Import CSV"):
            try:
                count = import_habits_csv(user["id"], uploaded)
                st.success(f"Imported {count} habits.")
                rerun()
            except Exception as exc:
                st.error(str(exc))
