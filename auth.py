import base64
import hashlib
import hmac
import re
import uuid
from pathlib import Path

import streamlit as st
from werkzeug.security import check_password_hash, generate_password_hash

from config import ASSETS_DIR
from database import execute, fetch_one, get_connection

PROFILE_DIR = ASSETS_DIR / "profiles"
PROFILE_DIR.mkdir(parents=True, exist_ok=True)
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
ALLOWED_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg"}


def _normalize_email(email):
    return (email or "").strip().lower()


def _validate_identity(name, email):
    clean_name = (name or "").strip()
    clean_email = _normalize_email(email)
    if not clean_name:
        raise ValueError("Name is required.")
    if not EMAIL_RE.match(clean_email):
        raise ValueError("Enter a valid email address.")
    return clean_name, clean_email


def _hash_password(password):
    return generate_password_hash(password, method="pbkdf2:sha256", salt_length=16)


def _verify_password(password, stored):
    if not password or not stored:
        return False
    if stored.startswith(("pbkdf2:", "scrypt:")):
        return check_password_hash(stored, password)
    try:
        raw = base64.b64decode(stored.encode("ascii"))
        salt, digest = raw[:16], raw[16:]
        check = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 140_000)
        return hmac.compare_digest(digest, check)
    except Exception:
        legacy = hashlib.sha256(password.encode()).hexdigest()
        return hmac.compare_digest(stored, legacy)


def register_user(name, email, password):
    clean_name, clean_email = _validate_identity(name, email)
    if len(password or "") < 6:
        raise ValueError("Password must be at least 6 characters.")
    user_id = str(uuid.uuid4())
    with get_connection() as conn:
        try:
            conn.execute(
                "INSERT INTO users (id, name, email, password) VALUES (?, ?, ?, ?)",
                (user_id, clean_name, clean_email, _hash_password(password)),
            )
            for period, target in (("Daily", 3), ("Weekly", 18), ("Monthly", 72)):
                conn.execute(
                    "INSERT INTO goals (id, user_id, period, target) VALUES (?, ?, ?, ?)",
                    (str(uuid.uuid4()), user_id, period, target),
                )
        except Exception as exc:
            if "UNIQUE" in str(exc).upper():
                raise ValueError("An account with this email already exists.") from exc
            raise
    return user_id


def authenticate(email, password):
    clean_email = _normalize_email(email)
    if not clean_email or not password:
        return None
    user = fetch_one("SELECT * FROM users WHERE lower(email)=lower(?)", (clean_email,))
    if not user or not _verify_password(password, user["password"]):
        return None
    if not user["password"].startswith(("pbkdf2:", "scrypt:")):
        execute("UPDATE users SET password=? WHERE id=?", (_hash_password(password), user["id"]))
        user = fetch_one("SELECT * FROM users WHERE id=?", (user["id"],))
    return user


def current_user():
    user = st.session_state.get("user")
    if user and user.get("id"):
        return fetch_one("SELECT * FROM users WHERE id=?", (user["id"],))
    return None


def login_user(user):
    st.session_state["user"] = user
    st.session_state["theme"] = user.get("theme") or "dark"


def logout_user():
    theme = st.session_state.get("theme", "dark")
    st.session_state.clear()
    st.session_state["theme"] = theme


def save_profile_image(user_id, uploaded_file):
    if not uploaded_file:
        return None
    suffix = Path(uploaded_file.name).suffix.lower() or ".png"
    if suffix not in ALLOWED_IMAGE_SUFFIXES:
        raise ValueError("Profile picture must be a PNG or JPG image.")
    if getattr(uploaded_file, "size", 0) and uploaded_file.size > 5 * 1024 * 1024:
        raise ValueError("Profile picture must be 5 MB or smaller.")
    path = PROFILE_DIR / f"{user_id}{suffix}"
    path.write_bytes(uploaded_file.getvalue())
    execute("UPDATE users SET profile_image=? WHERE id=?", (str(path), user_id))
    return str(path)


def update_profile(user_id, name, email, theme):
    clean_name, clean_email = _validate_identity(name, email)
    try:
        execute(
            "UPDATE users SET name=?, email=?, theme=? WHERE id=?",
            (clean_name, clean_email, theme, user_id),
        )
    except Exception as exc:
        if "UNIQUE" in str(exc).upper():
            raise ValueError("Another account already uses this email.") from exc
        raise
    st.session_state["theme"] = theme
    st.session_state["user"] = fetch_one("SELECT * FROM users WHERE id=?", (user_id,))


def update_theme(user_id, theme):
    if theme not in {"dark", "light"}:
        raise ValueError("Invalid theme.")
    execute("UPDATE users SET theme=? WHERE id=?", (theme, user_id))
    st.session_state["theme"] = theme
    st.session_state["user"] = fetch_one("SELECT * FROM users WHERE id=?", (user_id,))
