from datetime import date, datetime, timedelta
from random import choice

import pandas as pd
import streamlit as st

from config import QUOTES


def rerun():
    st.rerun()


def daily_quote():
    key = f"quote_{date.today().isoformat()}"
    if key not in st.session_state:
        st.session_state[key] = choice(QUOTES)
    return st.session_state[key]


def apply_theme(theme="dark"):
    dark = theme == "dark"
    bg = "#0b1020" if dark else "#f4f7fb"
    panel = "rgba(255,255,255,0.10)" if dark else "rgba(255,255,255,0.78)"
    text = "#f8fbff" if dark else "#172033"
    muted = "#aeb9d4" if dark else "#5d6a83"
    border = "rgba(255,255,255,0.18)" if dark else "rgba(32,45,73,0.12)"
    sidebar_bg = "rgba(10,14,28,.86)" if dark else "rgba(23,32,51,.92)"
    st.markdown(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
        :root {{
            --app-bg: {bg};
            --panel: {panel};
            --text: {text};
            --muted: {muted};
            --border: {border};
            --accent: #7c5cff;
            --accent-2: #00d4ff;
            --success: #12c99b;
            --warning: #ffca64;
            --danger: #ff5c7a;
            --radius: 18px;
        }}
        html, body, [class*="css"] {{ font-family: 'Inter', sans-serif; }}
        .stApp {{
            background:
              radial-gradient(circle at 12% 16%, rgba(124,92,255,.30), transparent 30%),
              radial-gradient(circle at 86% 12%, rgba(0,212,255,.22), transparent 26%),
              linear-gradient(135deg, var(--app-bg), {'#101733' if dark else '#eef4ff'} 58%, {'#15142b' if dark else '#f7fbff'});
            color: var(--text);
        }}
        section[data-testid="stSidebar"] {{
            background: linear-gradient(180deg, {sidebar_bg}, rgba(11,16,32,.78));
            border-right: 1px solid rgba(255,255,255,.12);
        }}
        section[data-testid="stSidebar"] * {{ color: #f7faff !important; }}
        .block-container {{ padding-top: 1.7rem; max-width: 1400px; }}
        h1, h2, h3 {{ color: var(--text); letter-spacing: 0; }}
        div[data-testid="stMetric"] {{
            padding: 18px;
            background: var(--panel);
            border: 1px solid var(--border);
            border-radius: var(--radius);
            box-shadow: 0 18px 50px rgba(0,0,0,.16);
            backdrop-filter: blur(18px);
            transition: transform .18s ease, border-color .18s ease, box-shadow .18s ease;
        }}
        div[data-testid="stMetric"]:hover {{
            transform: translateY(-3px);
            border-color: rgba(124,92,255,.55);
            box-shadow: 0 24px 60px rgba(20,26,54,.26);
        }}
        .glass-card {{
            padding: 22px;
            border: 1px solid var(--border);
            border-radius: var(--radius);
            background: var(--panel);
            box-shadow: 0 20px 60px rgba(0,0,0,.18);
            backdrop-filter: blur(18px);
            margin-bottom: 18px;
        }}
        .hero {{
            position: relative;
            overflow: hidden;
            padding: clamp(24px, 4vw, 42px);
            border-radius: 24px;
            background:
              linear-gradient(135deg, rgba(124,92,255,.92), rgba(0,212,255,.62)),
              linear-gradient(45deg, rgba(255,255,255,.18), transparent);
            color: white;
            box-shadow: 0 30px 90px rgba(36,54,112,.35);
            margin-bottom: 22px;
        }}
        .hero h1 {{ color: white; font-size: clamp(2.2rem, 5vw, 4.5rem); margin: 0; font-weight: 800; }}
        .hero p {{ max-width: 760px; color: rgba(255,255,255,.88); font-size: 1.06rem; }}
        .chip {{
            display: inline-flex;
            align-items: center;
            gap: 7px;
            padding: 7px 11px;
            margin: 3px 5px 3px 0;
            border-radius: 999px;
            background: rgba(255,255,255,.12);
            border: 1px solid rgba(255,255,255,.18);
            color: var(--text);
            font-weight: 700;
            font-size: .82rem;
        }}
        .habit-card {{
            border-radius: 18px;
            padding: 18px;
            margin-bottom: 14px;
            border: 1px solid var(--border);
            background: linear-gradient(135deg, rgba(255,255,255,.13), rgba(255,255,255,.06));
            box-shadow: 0 18px 50px rgba(0,0,0,.12);
            transition: transform .18s ease, border-color .18s ease;
        }}
        .habit-card:hover {{ transform: translateY(-2px); border-color: rgba(0,212,255,.50); }}
        .habit-title {{ font-size: 1.05rem; font-weight: 800; margin-bottom: 4px; }}
        .muted {{ color: var(--muted); }}
        .progress-shell {{
            height: 16px;
            overflow: hidden;
            border-radius: 999px;
            background: rgba(255,255,255,.16);
            border: 1px solid rgba(255,255,255,.18);
        }}
        .progress-fill {{
            height: 100%;
            border-radius: 999px;
            background: linear-gradient(90deg, #12c99b, #00d4ff, #7c5cff);
            box-shadow: 0 0 26px rgba(0,212,255,.45);
            transition: width .5s ease;
        }}
        div.stButton > button, div.stDownloadButton > button {{
            border-radius: 12px;
            border: 1px solid rgba(255,255,255,.18);
            background: linear-gradient(135deg, #7c5cff, #00d4ff);
            color: white;
            font-weight: 800;
            transition: transform .16s ease, filter .16s ease;
        }}
        div.stButton > button:hover, div.stDownloadButton > button:hover {{
            transform: translateY(-1px);
            filter: brightness(1.08);
            color: white;
        }}
        div[data-testid="stExpander"] {{
            border-radius: 16px;
            border: 1px solid var(--border);
            background: var(--panel);
        }}
        .stTabs [data-baseweb="tab-list"] {{ gap: 8px; }}
        .stTabs [data-baseweb="tab"] {{
            border-radius: 999px;
            background: rgba(255,255,255,.09);
            padding: 8px 16px;
        }}
        @media (max-width: 760px) {{
            .block-container {{ padding-left: 1rem; padding-right: 1rem; }}
            .hero {{ padding: 24px; }}
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def hero(title, subtitle, eyebrow="Today"):
    st.markdown(
        f"""
        <div class="hero">
            <span class="chip">{eyebrow}</span>
            <h1>{title}</h1>
            <p>{subtitle}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def glass_card(body):
    st.markdown(f'<div class="glass-card">{body}</div>', unsafe_allow_html=True)


def progress_bar(percent, label="Progress"):
    percent = max(0, min(100, int(percent)))
    st.markdown(
        f"""
        <div class="glass-card">
          <div style="display:flex;justify-content:space-between;font-weight:800;margin-bottom:10px;">
            <span>{label}</span><span>{percent}%</span>
          </div>
          <div class="progress-shell"><div class="progress-fill" style="width:{percent}%"></div></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def badge(icon, title, subtitle=""):
    st.markdown(
        f"""
        <div class="chip" title="{subtitle}">
            <span>{icon}</span><span>{title}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def confetti():
    st.balloons()
    st.toast("Perfect day unlocked. Beautiful work.", icon="🎉")


def date_range(period):
    today = date.today()
    if period == "Weekly":
        start = today - timedelta(days=today.weekday())
    elif period == "Monthly":
        start = today.replace(day=1)
    else:
        start = today
    return start, today


def dataframe_to_download(df):
    return df.to_csv(index=False).encode("utf-8")


def safe_datetime(value):
    try:
        return pd.to_datetime(value)
    except Exception:
        return pd.NaT


def compact_date(value):
    if not value:
        return ""
    try:
        return datetime.fromisoformat(str(value)[:10]).strftime("%d %b")
    except Exception:
        return str(value)
