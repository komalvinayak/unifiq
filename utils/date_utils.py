# ── date_utils.py ────────────────────────────────────────────────────
# One place for all date and time helpers
# All times in IST (Indian Standard Time, Asia/Kolkata, UTC+5:30)
# ─────────────────────────────────────────────────────────────────────

from datetime import datetime
import pytz

# Define IST timezone
IST = pytz.timezone("Asia/Kolkata")


def now_ist():
    """Returns current datetime in IST"""
    return datetime.now(IST)


def now_date_str():
    """Returns today's date as string — example: 18 Nov 2026"""
    return now_ist().strftime("%d %b %Y")


def now_time_str():
    """Returns current time as string — example: 02:35 PM"""
    return now_ist().strftime("%I:%M %p")


def now_datetime_str():
    """Returns full datetime string — example: 18 Nov 2026, 02:35 PM"""
    return now_ist().strftime("%d %b %Y, %I:%M %p")


def today_date_only():
    """Returns today's date as YYYY-MM-DD string — used for comparisons"""
    return now_ist().strftime("%Y-%m-%d")


def greeting():
    """Returns Good Morning / Afternoon / Evening based on current IST hour"""
    hour = now_ist().hour
    if hour < 12:
        return "Good Morning"
    elif hour < 17:
        return "Good Afternoon"
    else:
        return "Good Evening"
