from pathlib import Path

APP_NAME = "Daily Habit Tracker"
APP_TAGLINE = "Build momentum one beautiful day at a time."

BASE_DIR = Path(__file__).resolve().parent
ASSETS_DIR = BASE_DIR / "assets"
DATABASE_DIR = BASE_DIR / "database"
EXPORTS_DIR = BASE_DIR / "exports"
LEGACY_DB_PATH = BASE_DIR / "database.sqlite"
DB_PATH = DATABASE_DIR / "habit_tracker.sqlite"

for directory in (ASSETS_DIR, DATABASE_DIR, EXPORTS_DIR):
    directory.mkdir(exist_ok=True)

CATEGORIES = [
    "Health",
    "Fitness",
    "Study",
    "Work",
    "Personal",
    "Finance",
    "Reading",
    "Mindfulness",
    "Creativity",
    "Home",
]

PRIORITIES = ["Low", "Medium", "High", "Critical"]
FREQUENCIES = ["Daily", "Weekly", "Monthly"]

HABIT_EMOJIS = ["✅", "💧", "🏃", "📚", "🧘", "💪", "🎨", "🛏️", "🥗", "📝", "💰", "🌱"]
COLOR_PALETTE = ["#6C5CE7", "#00B894", "#0984E3", "#E84393", "#FDCB6E", "#FF7675", "#00CEC9", "#A29BFE"]

QUOTES = [
    "Small wins compound into an identity.",
    "Consistency beats intensity when the calendar gets honest.",
    "Make today easy to repeat tomorrow.",
    "Your future self notices the reps nobody applauds.",
    "Momentum is built in minutes, not moods.",
    "The streak is proof that you keep showing up.",
]

ACHIEVEMENTS = [
    ("first_win", "First Spark", "Complete your first habit.", "✨", 1),
    ("three_day_streak", "Momentum Maker", "Reach a 3 day streak.", "🔥", 3),
    ("seven_day_streak", "Week Warrior", "Reach a 7 day streak.", "🏆", 7),
    ("thirty_completions", "Thirty Wins", "Log 30 total completions.", "🌟", 30),
    ("perfect_day", "Perfect Day", "Complete every active habit today.", "🎉", 1),
]
