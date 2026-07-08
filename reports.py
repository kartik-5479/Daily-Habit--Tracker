from datetime import date, timedelta

import pandas as pd
import plotly.express as px
import streamlit as st

from database import create_backup, execute, export_habits_csv, fetch_all, fetch_one, restore_backup
from utils import dataframe_to_download, rerun


def _period_count(user_id, start):
    return fetch_one(
        "SELECT COUNT(*) AS count FROM habit_logs WHERE user_id=? AND completed=1 AND DATE(completed_date)>=DATE(?)",
        (user_id, start.isoformat()),
    )["count"]


def render_goals(user):
    st.subheader("Goal Management")
    goals = fetch_all("SELECT * FROM goals WHERE user_id=? ORDER BY period", (user["id"],))
    with st.form("goals_form"):
        values = {}
        cols = st.columns(3)
        for index, period in enumerate(["Daily", "Weekly", "Monthly"]):
            existing = next((goal for goal in goals if goal["period"] == period), {"target": 3})
            values[period] = cols[index].number_input(f"{period} target", min_value=1, max_value=500, value=int(existing["target"]))
        submitted = st.form_submit_button("Save goals")
    if submitted:
        for period, target in values.items():
            existing = fetch_one("SELECT id FROM goals WHERE user_id=? AND period=?", (user["id"], period))
            if existing:
                execute("UPDATE goals SET target=? WHERE id=?", (target, existing["id"]))
            else:
                execute(
                    "INSERT INTO goals (id, user_id, period, target) VALUES (lower(hex(randomblob(16))), ?, ?, ?)",
                    (user["id"], period, target),
                )
        st.toast("Goals updated.", icon="🎯")
        rerun()


def render_reports_page(user):
    st.subheader("Reports & Data")
    st.caption("Weekly and monthly reporting, exports, CSV downloads, and database backup/restore.")
    render_goals(user)
    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    month_start = today.replace(day=1)
    c1, c2, c3 = st.columns(3)
    c1.metric("Today", _period_count(user["id"], today))
    c2.metric("This Week", _period_count(user["id"], week_start))
    c3.metric("This Month", _period_count(user["id"], month_start))

    rows = fetch_all(
        """
        SELECT h.title, h.category, h.priority, l.completed_date
        FROM habit_logs l
        JOIN habits h ON h.id = l.habit_id
        WHERE l.user_id=? AND l.completed=1
        ORDER BY l.completed_date DESC
        """,
        (user["id"],),
    )
    df = pd.DataFrame(rows)
    if not df.empty:
        df["completed_date"] = pd.to_datetime(df["completed_date"])
        df["period"] = df["completed_date"].dt.to_period("W").astype(str)
        weekly = df.groupby(["period", "category"]).size().reset_index(name="Completions")
        fig = px.bar(weekly.tail(24), x="period", y="Completions", color="category", title="Weekly Report by Category")
        fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, width="stretch")
        st.download_button("Download log report CSV", dataframe_to_download(df), "habit_log_report.csv", "text/csv")
        st.dataframe(df, width="stretch", hide_index=True)
    else:
        st.info("Reports populate after your first completion.")

    left, right = st.columns(2)
    with left:
        st.subheader("CSV Export")
        if st.button("Prepare habit CSV"):
            path = export_habits_csv(user["id"])
            st.session_state["latest_export"] = str(path)
        path = st.session_state.get("latest_export")
        if path:
            with open(path, "rb") as handle:
                st.download_button("Download habit CSV", handle, file_name=path.split("\\")[-1])
    with right:
        st.subheader("Database Backup")
        if st.button("Create SQLite backup"):
            path = create_backup()
            st.session_state["latest_backup"] = str(path)
        backup = st.session_state.get("latest_backup")
        if backup:
            with open(backup, "rb") as handle:
                st.download_button("Download backup", handle, file_name=backup.split("\\")[-1])
        uploaded = st.file_uploader("Restore database backup", type=["sqlite", "db"])
        if uploaded and st.button("Restore backup"):
            restore_backup(uploaded)
            st.success("Backup restored. Please sign in again.")
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            rerun()

