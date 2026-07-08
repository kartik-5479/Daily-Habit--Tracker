from datetime import date, timedelta

import pandas as pd
import plotly.express as px
import streamlit as st

from database import fetch_all, fetch_one, get_user_stats
from habits import is_completed_today, list_habits, render_habit_card
from utils import badge, daily_quote, hero, progress_bar


def _daily_series(user_id, days=14):
    start = date.today() - timedelta(days=days - 1)
    rows = fetch_all(
        """
        SELECT completed_date, COUNT(*) AS completed
        FROM habit_logs
        WHERE user_id=? AND completed=1 AND DATE(completed_date) >= DATE(?)
        GROUP BY completed_date
        ORDER BY completed_date
        """,
        (user_id, start.isoformat()),
    )
    frame = pd.DataFrame({"date": pd.date_range(start, date.today(), freq="D")})
    if rows:
        logs = pd.DataFrame(rows)
        logs["date"] = pd.to_datetime(logs["completed_date"])
        frame = frame.merge(logs[["date", "completed"]], on="date", how="left")
    else:
        frame["completed"] = 0
    frame["completed"] = frame["completed"].fillna(0)
    return frame


def _period_completion(user_id, period, today, stats):
    if period == "Daily":
        return stats["completed"]
    start = today - timedelta(days=today.weekday()) if period == "Weekly" else today.replace(day=1)
    return fetch_one(
        "SELECT COUNT(*) AS count FROM habit_logs WHERE user_id=? AND completed=1 AND DATE(completed_date)>=DATE(?)",
        (user_id, start.isoformat()),
    )["count"]


def render_dashboard(user):
    stats = get_user_stats(user["id"])
    first_name = user.get("name", "there").split()[0]
    hero(
        f"Welcome back, {first_name}",
        "Track today's momentum, protect your streaks, and steer your week from one calm command center.",
        "Daily Habit Tracker",
    )
    st.markdown(f'<div class="glass-card"><b>Daily quote:</b> {daily_quote()}</div>', unsafe_allow_html=True)
    cols = st.columns(4)
    cols[0].metric("Completed Today", stats["completed"], f"{stats['percent']}% done")
    cols[1].metric("Open Habits", stats["total"], f"{stats['pending']} pending")
    cols[2].metric("Lifetime Wins", stats["logs"], "all completions")
    cols[3].metric("Level", user.get("level", 1), f"{user.get('xp', 0)} XP")
    progress_bar(stats["percent"], "Today's completion")

    left, right = st.columns([1.15, 0.85])
    with left:
        st.subheader("Momentum")
        series = _daily_series(user["id"])
        fig = px.area(
            series,
            x="date",
            y="completed",
            markers=True,
            color_discrete_sequence=["#00d4ff"],
            title="Completions over the last 14 days",
        )
        fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", height=340)
        fig.update_traces(line={"width": 4}, fill="tozeroy")
        st.plotly_chart(fig, use_container_width=True)
    with right:
        st.subheader("Achievements")
        achievements = fetch_all("SELECT * FROM achievements WHERE user_id=? ORDER BY earned_at DESC", (user["id"],))
        if achievements:
            for item in achievements[:6]:
                badge(item.get("icon", "🏅"), item["title"], item.get("description", ""))
        else:
            st.info("Complete a habit to unlock your first badge.")
        goals = fetch_all("SELECT * FROM goals WHERE user_id=? ORDER BY period", (user["id"],))
        st.subheader("Goals")
        today = date.today()
        for goal in goals:
            period = goal["period"]
            completed = _period_completion(user["id"], period, today, stats)
            target = max(goal.get("target") or 1, 1)
            progress_bar(min(100, int(completed / target * 100)), f"{period}: {completed}/{target}")

    st.subheader("Today")
    habits = list_habits(user["id"])
    if not habits:
        st.info("Create your first habit from the Habit Studio.")
        return
    todo = [habit for habit in habits if not is_completed_today(habit["id"])]
    done = [habit for habit in habits if is_completed_today(habit["id"])]
    st.caption(f"{len(todo)} pending | {len(done)} completed")
    for habit in (todo + done)[:5]:
        render_habit_card(habit)
