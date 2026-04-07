"""
calendar_control.py — Google Calendar integration for ORION MK2
────────────────────────────────────────────────────────────────
Install dependencies:
    pip install google-auth google-auth-oauthlib google-auth-httplib2
                google-api-python-client dateparser

Setup (one-time):
    1. Go to https://console.cloud.google.com/
    2. Create a project → Enable "Google Calendar API"
    3. Credentials → Create OAuth 2.0 Client ID → Desktop App
    4. Download JSON → save as  credentials.json  next to this file
    5. First run opens a browser for you to authorise — token.json
       is then saved automatically for all future runs.
────────────────────────────────────────────────────────────────
"""

import datetime
import os

import dateparser
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# ── Auth ──────────────────────────────────────────────────
SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/tasks",
]
_BASE            = os.path.dirname(os.path.abspath(__file__))
CREDENTIALS_FILE = os.path.join(_BASE, "credentials.json")
TOKEN_FILE       = os.path.join(_BASE, "token.json")

# London timezone — change if needed
TIMEZONE = "Europe/London"


def _get_service():
    """Authenticate and return a Google Calendar API service object."""
    creds = None

    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(CREDENTIALS_FILE):
                raise FileNotFoundError(
                    "credentials.json not found. "
                    "Download it from Google Cloud Console and place it next to this file."
                )
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)

        with open(TOKEN_FILE, "w") as token:
            token.write(creds.to_json())

    return build("calendar", "v3", credentials=creds)


# ── Helpers ───────────────────────────────────────────────

def _parse_dt(date_str: str, time_str: str | None = None) -> datetime.datetime | None:
    """Turn natural-language date/time strings into a datetime object."""
    combined = f"{date_str} {time_str}" if time_str else date_str
    return dateparser.parse(
        combined,
        settings={
            "PREFER_DATES_FROM": "future",
            "TIMEZONE": TIMEZONE,
            "RETURN_AS_TIMEZONE_AWARE": True,
        },
    )


def _ordinal(n: int) -> str:
    """Return the ordinal string for a number e.g. 1 -> 1st, 3 -> 3rd."""
    if 11 <= n % 100 <= 13:
        return f"{n}th"
    return f"{n}{['th','st','nd','rd','th','th','th','th','th','th'][n % 10]}"


def _fmt_dt(iso_str: str) -> str:
    """
    Convert an ISO datetime string to a natural spoken format.
    Works on Windows and Linux (avoids %-I which is Linux-only).

    Examples:
        '2026-04-06'           -> 'Monday the 6th of April'
        '2026-04-06T14:00:00'  -> 'Monday the 6th of April at 2 in the afternoon'
        '2026-04-06T09:30:00'  -> 'Monday the 6th of April at half past 9 in the morning'
    """
    try:
        if "T" in iso_str:
            dt        = datetime.datetime.fromisoformat(iso_str)
            date_part = _fmt_date(dt.date())
            time_part = _fmt_time(dt.hour, dt.minute)
            return f"{date_part} at {time_part}"
        else:
            dt = datetime.date.fromisoformat(iso_str)
            return _fmt_date(dt)
    except Exception:
        return iso_str


def _fmt_date(d: datetime.date) -> str:
    """e.g. 'Monday the 6th of April'"""
    return f"{d.strftime('%A')} the {_ordinal(d.day)} of {d.strftime('%B')}"


def _fmt_time(hour: int, minute: int) -> str:
    """
    Convert hour/minute to a natural spoken time string.
    e.g. 14:00 -> '2 in the afternoon'
         09:30 -> 'half past 9 in the morning'
         13:15 -> 'quarter past 1 in the afternoon'
         07:45 -> 'quarter to 8 in the morning'
    """
    period  = "in the morning" if hour < 12 else ("at noon" if hour == 12 and minute == 0 else "in the afternoon" if hour < 17 else "in the evening")
    h12     = hour % 12 or 12

    if minute == 0:
        time_str = f"{h12}"
    elif minute == 15:
        time_str = f"quarter past {h12}"
    elif minute == 30:
        time_str = f"half past {h12}"
    elif minute == 45:
        next_h = (h12 % 12) + 1
        time_str = f"quarter to {next_h}"
    else:
        time_str = f"{h12}:{str(minute).zfill(2)}"

    if hour == 12 and minute == 0:
        return "noon"
    if hour == 0 and minute == 0:
        return "midnight"
    return f"{time_str} {period}"


def _event_to_dict(event: dict) -> dict:
    """Normalise a raw Google Calendar event into a clean dict."""
    start_raw = event["start"].get("dateTime", event["start"].get("date", ""))
    end_raw   = event["end"].get("dateTime",   event["end"].get("date",   ""))
    return {
        "id":          event["id"],
        "title":       event.get("summary", "Untitled"),
        "start":       start_raw,
        "end":         end_raw,
        "start_human": _fmt_dt(start_raw),
        "description": event.get("description", ""),
        "location":    event.get("location", ""),
    }


# ── Public API ────────────────────────────────────────────

def get_upcoming_events(max_results: int = 8) -> list[dict]:
    """
    Return the next `max_results` calendar events as a list of clean dicts.
    Raises CalendarError on failure.
    """
    try:
        service = _get_service()
        now     = datetime.datetime.utcnow().isoformat() + "Z"

        raw = service.events().list(
            calendarId   = "primary",
            timeMin      = now,
            maxResults   = max_results,
            singleEvents = True,
            orderBy      = "startTime",
        ).execute()

        return [_event_to_dict(e) for e in raw.get("items", [])]

    except HttpError as e:
        raise CalendarError(f"Google API error: {e}") from e


def create_event(
    title:            str,
    date_str:         str,
    time_str:         str | None = None,
    duration_minutes: int        = 60,
    description:      str        = "",
    location:         str        = "",
) -> dict:
    """
    Create a new calendar event.

    Parameters
    ----------
    title            : event name, e.g. "Team standup"
    date_str         : natural language date, e.g. "tomorrow", "next Friday"
    time_str         : natural language time, e.g. "3pm", "half past 2"
                        If omitted an all-day event is created.
    duration_minutes : length of timed events (default 60)
    description      : optional notes
    location         : optional location string
    """
    try:
        service   = _get_service()
        parsed_dt = _parse_dt(date_str, time_str)

        if parsed_dt is None:
            raise CalendarError(
                f"Could not understand the date/time: '{date_str} {time_str}'"
            )

        if time_str:
            end_dt = parsed_dt + datetime.timedelta(minutes=duration_minutes)
            body   = {
                "summary":     title,
                "description": description,
                "location":    location,
                "start": {"dateTime": parsed_dt.isoformat(), "timeZone": TIMEZONE},
                "end":   {"dateTime": end_dt.isoformat(),    "timeZone": TIMEZONE},
            }
        else:
            date_only = parsed_dt.date()
            next_day  = date_only + datetime.timedelta(days=1)
            body      = {
                "summary":     title,
                "description": description,
                "location":    location,
                "start": {"date": date_only.isoformat()},
                "end":   {"date": next_day.isoformat()},
            }

        created = service.events().insert(calendarId="primary", body=body).execute()
        return _event_to_dict(created)

    except HttpError as e:
        raise CalendarError(f"Google API error: {e}") from e


def set_reminder(
    title:                  str,
    date_str:               str,
    time_str:               str,
    reminder_minutes_before: int = 10,
) -> dict:
    """
    Create an event with an email + popup reminder.

    Parameters
    ----------
    title                   : reminder text, e.g. "Take medication"
    date_str                : natural language date, e.g. "tomorrow"
    time_str                : natural language time, e.g. "9am"
    reminder_minutes_before : how many minutes before to alert (default 10)
    """
    try:
        service   = _get_service()
        parsed_dt = _parse_dt(date_str, time_str)

        if parsed_dt is None:
            raise CalendarError(
                f"Could not understand the date/time: '{date_str} {time_str}'"
            )

        end_dt = parsed_dt + datetime.timedelta(minutes=30)

        body = {
            "summary": title,
            "start":   {"dateTime": parsed_dt.isoformat(), "timeZone": TIMEZONE},
            "end":     {"dateTime": end_dt.isoformat(),    "timeZone": TIMEZONE},
            "reminders": {
                "useDefault": False,
                "overrides": [
                    {"method": "popup", "minutes": reminder_minutes_before},
                    {"method": "email", "minutes": reminder_minutes_before},
                ],
            },
        }

        created = service.events().insert(calendarId="primary", body=body).execute()
        return _event_to_dict(created)

    except HttpError as e:
        raise CalendarError(f"Google API error: {e}") from e


def format_events_for_speech(events: list[dict]) -> str:
    """Turn a list of event dicts into a natural spoken sentence."""
    if not events:
        return "You have no upcoming events, sir."

    if len(events) == 1:
        e = events[0]
        return f"You have one event: {e['title']} on {e['start_human']}."

    lines = [f"You have {len(events)} upcoming events, sir."]
    for e in events[:5]:           # speak at most 5 to avoid a wall of text
        lines.append(f"{e['title']} on {e['start_human']}.")
    return " ".join(lines)


# ── Custom exception ──────────────────────────────────────

class CalendarError(Exception):
    """Raised when any calendar operation fails."""