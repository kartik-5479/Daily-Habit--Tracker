# Streamlit Community Cloud Deployment

Use these settings when deploying this app:

- Repository root: this folder, containing `app.py` and `requirements.txt`
- Main file path: `app.py`
- Python version: set by `runtime.txt` as Python 3.12
- Dependencies: installed from `requirements.txt`

Before pushing to GitHub, make sure these files are included:

- `app.py`
- `auth.py`
- `config.py`
- `database.py`
- `dashboard.py`
- `analytics.py`
- `habits.py`
- `reports.py`
- `utils.py`
- `requirements.txt`
- `runtime.txt`

Do not push local runtime files such as SQLite databases, `__pycache__`, or exported CSV/backup files. They are ignored by `.gitignore`; Streamlit Cloud will create runtime folders automatically when the app starts.

