from datetime import date, timedelta

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from database import fetch_all


def _logs_frame(user_id):
    rows = fetch_all(
        """
        SELECT h.title, h.category, h.priority, h.color, h.emoji, l.completed_date
        FROM habit_logs l
        JOIN habits h ON h.id = l.habit_id
        WHERE l.user_id=? AND l.completed=1
        ORDER BY l.completed_date
        """,
        (user_id,),
    )
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["date"] = pd.to_datetime(df["completed_date"])
    df["day"] = df["date"].dt.date
    df["week"] = df["date"].dt.to_period("W").astype(str)
    df["month"] = df["date"].dt.to_period("M").astype(str)
    df["weekday"] = df["date"].dt.day_name()
    return df


def _transparent_layout(fig, height=360):
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=height,
        margin=dict(l=20, r=20, t=55, b=25),
        font=dict(family="Inter"),
    )
    return fig


def _success_rate(user_id, df):
    habits = fetch_all("SELECT id, title, created_date FROM habits WHERE user_id=? AND archived=0", (user_id,))
    if not habits:
        return pd.DataFrame()
    rows = []
    today = date.today()
    for habit in habits:
        created = pd.to_datetime(habit.get("created_date") or today).date()
        days = max((today - created).days + 1, 1)
        completed = 0 if df.empty else int((df["title"] == habit["title"]).sum())
        rows.append({"Habit": habit["title"], "Success Rate": min(100, completed / days * 100), "Completions": completed})
    return pd.DataFrame(rows)


def render_analytics_page(user):
    st.subheader("Analytics")
    st.caption("Daily, weekly, monthly, habit-wise, and trend views powered by Plotly.")
    df = _logs_frame(user["id"])
    if df.empty:
        st.info("Complete a few habits to unlock analytics.")
        return

    daily = df.groupby("day").size().reset_index(name="Completions")
    weekly = df.groupby("week").size().reset_index(name="Completions")
    monthly = df.groupby("month").size().reset_index(name="Completions")
    habit_stats = df.groupby(["title", "category"]).size().reset_index(name="Completions").sort_values("Completions", ascending=False)
    success = _success_rate(user["id"], df).sort_values("Success Rate", ascending=False)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Logs", len(df))
    c2.metric("Success Rate", f"{success['Success Rate'].mean():.0f}%" if not success.empty else "0%")
    c3.metric("Most Consistent", success.iloc[0]["Habit"] if not success.empty else "N/A")
    c4.metric("Needs Attention", success.iloc[-1]["Habit"] if not success.empty else "N/A")

    tabs = st.tabs(["Progress", "Habit Mix", "Heatmap", "Radar", "Trends"])
    with tabs[0]:
        left, right = st.columns(2)
        with left:
            fig = px.line(daily, x="day", y="Completions", markers=True, title="Daily Progress", color_discrete_sequence=["#00d4ff"])
            fig.update_traces(line={"width": 4})
            st.plotly_chart(_transparent_layout(fig), width="stretch")
        with right:
            fig = px.bar(weekly.tail(12), x="week", y="Completions", title="Weekly Progress", color="Completions", color_continuous_scale="Viridis")
            st.plotly_chart(_transparent_layout(fig), width="stretch")
        fig = px.bar(monthly, x="month", y="Completions", title="Monthly Progress", color="Completions", color_continuous_scale="Plasma")
        st.plotly_chart(_transparent_layout(fig, 330), width="stretch")
    with tabs[1]:
        left, right = st.columns(2)
        with left:
            fig = px.pie(habit_stats, values="Completions", names="category", title="Category Split", hole=.45, color_discrete_sequence=px.colors.qualitative.Set3)
            st.plotly_chart(_transparent_layout(fig), width="stretch")
        with right:
            fig = px.bar(habit_stats.head(12), x="Completions", y="title", orientation="h", color="category", title="Habit-wise Completion Statistics")
            st.plotly_chart(_transparent_layout(fig), width="stretch")
        st.dataframe(success, width="stretch", hide_index=True)
    with tabs[2]:
        start = date.today() - timedelta(days=120)
        calendar = pd.DataFrame({"day": pd.date_range(start, date.today(), freq="D")})
        heat = daily.copy()
        heat["day"] = pd.to_datetime(heat["day"])
        calendar = calendar.merge(heat, on="day", how="left").fillna({"Completions": 0})
        calendar["Week"] = calendar["day"].dt.isocalendar().week
        calendar["Weekday"] = calendar["day"].dt.day_name()
        order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        pivot = calendar.pivot_table(index="Weekday", columns="Week", values="Completions", aggfunc="sum").reindex(order)
        fig = go.Figure(data=go.Heatmap(z=pivot.values, x=pivot.columns, y=pivot.index, colorscale="Turbo", hoverongaps=False))
        fig.update_layout(title="Calendar Heatmap")
        st.plotly_chart(_transparent_layout(fig, 420), width="stretch")
    with tabs[3]:
        category = df.groupby("category").size().reset_index(name="score")
        fig = go.Figure()
        fig.add_trace(
            go.Scatterpolar(
                r=category["score"],
                theta=category["category"],
                fill="toself",
                name="Category strength",
                line_color="#00d4ff",
            )
        )
        fig.update_layout(title="Radar Chart", polar=dict(radialaxis=dict(visible=True)), showlegend=False)
        st.plotly_chart(_transparent_layout(fig, 460), width="stretch")
    with tabs[4]:
        trend = daily.copy()
        trend["Rolling 7 Day"] = trend["Completions"].rolling(7, min_periods=1).mean()
        fig = go.Figure()
        fig.add_trace(go.Bar(x=trend["day"], y=trend["Completions"], name="Daily", marker_color="#7c5cff"))
        fig.add_trace(go.Scatter(x=trend["day"], y=trend["Rolling 7 Day"], name="7 day trend", line=dict(color="#12c99b", width=4)))
        fig.update_layout(title="Trend Analysis")
        st.plotly_chart(_transparent_layout(fig, 420), width="stretch")

