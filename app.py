from datetime import datetime

import streamlit as st

from analytics import render_analytics_page
from auth import (
    authenticate,
    current_user,
    login_user,
    logout_user,
    register_user,
    save_profile_image,
    update_profile,
    update_theme,
)
from config import APP_NAME, APP_TAGLINE
from dashboard import render_dashboard
from database import init_db
from habits import render_habits_page
from reports import render_reports_page
from utils import apply_theme, hero, rerun

PAGES = {
    "Dashboard": ("🏠", render_dashboard),
    "Habit Studio": ("✅", render_habits_page),
    "Analytics": ("📈", render_analytics_page),
    "Reports & Data": ("🗂️", render_reports_page),
}


def render_auth_screen():
    hero(APP_NAME, APP_TAGLINE, "Premium productivity dashboard")
    st.markdown(
        '<div class="auth-shell glass-card"><h2>Welcome</h2>'
        '<p class="muted">Sign in or create your workspace. Your data is stored locally with SQLite.</p></div>',
        unsafe_allow_html=True,
    )

    login_tab, signup_tab = st.tabs(["Login", "Create Account"])
    with login_tab:
        with st.form("login_form", clear_on_submit=False):
            email = st.text_input("Email", placeholder="you@example.com", key="login_email")
            password = st.text_input("Password", type="password", key="login_password")
            submitted = st.form_submit_button("Login")
        if submitted:
            try:
                user = authenticate(email, password)
                if user:
                    login_user(user)
                    st.toast("Welcome back.", icon="✨")
                    rerun()
                st.error("Invalid email or password.")
            except Exception as exc:
                st.error(f"Login failed: {exc}")

    with signup_tab:
        with st.form("register_form", clear_on_submit=False):
            name = st.text_input("Name", key="register_name")
            email = st.text_input("Email address", key="register_email")
            password = st.text_input("Password", type="password", key="register_password")
            submitted = st.form_submit_button("Create account")
        if submitted:
            try:
                register_user(name, email, password)
                user = authenticate(email, password)
                if user:
                    login_user(user)
                    st.toast("Account created. Your first streak starts now.", icon="🚀")
                    rerun()
                st.error("Account was created, but automatic login failed. Please sign in.")
            except Exception as exc:
                st.error(str(exc))


def render_sidebar(user):
    st.sidebar.markdown(f"## {APP_NAME}")
    st.sidebar.caption("Modern habits, real momentum.")
    if user.get("profile_image"):
        st.sidebar.image(user["profile_image"], width=92)
    st.sidebar.markdown(f"**{user.get('name', 'User')}**")
    st.sidebar.caption(f"Level {user.get('level', 1)} | {user.get('xp', 0)} XP")

    page_labels = [f"{icon} {label}" for label, (icon, _) in PAGES.items()]
    selected = st.sidebar.radio("Navigate", page_labels, label_visibility="collapsed")
    page = selected.split(" ", 1)[1]
    st.sidebar.divider()

    current_theme = st.session_state.get("theme", user.get("theme") or "dark")
    selected_theme_label = st.sidebar.segmented_control(
        "Theme",
        ["Dark", "Light"],
        default="Light" if current_theme == "light" else "Dark",
        key="theme_selector",
    )
    selected_theme = "light" if selected_theme_label == "Light" else "dark"
    if selected_theme != current_theme:
        update_theme(user["id"], selected_theme)
        rerun()

    with st.sidebar.expander("Profile"):
        with st.form("profile_form"):
            name = st.text_input("Display name", value=user.get("name", ""))
            email = st.text_input("Email", value=user.get("email", ""))
            image = st.file_uploader("Profile picture", type=["png", "jpg", "jpeg"])
            submitted = st.form_submit_button("Save profile")
        if submitted:
            try:
                if image:
                    save_profile_image(user["id"], image)
                update_profile(user["id"], name, email, selected_theme)
                st.toast("Profile updated.", icon="👤")
                rerun()
            except Exception as exc:
                st.error(f"Could not update profile: {exc}")

    if st.sidebar.button("Logout", width="stretch"):
        logout_user()
        rerun()
    st.sidebar.caption(datetime.now().strftime("%A, %d %b %Y"))
    return page


def main():
    st.set_page_config(
        page_title=APP_NAME,
        page_icon="✅",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    try:
        init_db()
    except Exception as exc:
        st.error(f"Database initialization failed: {exc}")
        st.stop()

    st.session_state.setdefault("theme", "dark")
    apply_theme(st.session_state["theme"])

    user = current_user()
    if not user:
        render_auth_screen()
        return

    page = render_sidebar(user)
    _, renderer = PAGES[page]
    try:
        renderer(current_user())
    except Exception as exc:
        st.error(f"This page could not be rendered: {exc}")


if __name__ == "__main__":
    main()

