"""
timer_control.py — Timers & Countdowns for ORION MK2
────────────────────────────────────────────────────
Supports multiple simultaneous named timers.
Speaks aloud when each one finishes.
────────────────────────────────────────────────────
"""

import threading
import time
from datetime import datetime


# ── Active timer store ────────────────────────────
# { timer_id: {"name": str, "ends_at": float, "thread": Thread} }
_timers: dict[str, dict] = {}
_lock   = threading.Lock()
_id_counter = 0

# Injected at startup from main.py
_speak_fn       = None
_ui_transcript  = None
_ui_update_timers = None


def init(speak_fn, ui_transcript_fn, ui_update_timers_fn):
    """Call this once from main.py after defining speak / ui functions."""
    global _speak_fn, _ui_transcript, _ui_update_timers
    _speak_fn         = speak_fn
    _ui_transcript    = ui_transcript_fn
    _ui_update_timers = ui_update_timers_fn


def _next_id() -> str:
    global _id_counter
    _id_counter += 1
    return str(_id_counter)


def _timer_thread(timer_id: str, seconds: float, label: str):
    time.sleep(seconds)
    with _lock:
        if timer_id not in _timers:
            return          # was cancelled
        del _timers[timer_id]

    msg = f"Sir, your timer '{label}' is done."
    if _ui_transcript:
        _ui_transcript(msg)
    if _speak_fn:
        _speak_fn(msg)
    if _ui_update_timers:
        _ui_update_timers(get_all_timers())


def set_timer(label: str, seconds: int) -> str:
    """
    Start a named countdown timer.
    Returns a human-readable confirmation string.
    """
    timer_id = _next_id()
    ends_at  = time.time() + seconds

    t = threading.Thread(
        target=_timer_thread,
        args=(timer_id, seconds, label),
        daemon=True,
    )

    with _lock:
        _timers[timer_id] = {"name": label, "ends_at": ends_at, "thread": t}

    t.start()

    if _ui_update_timers:
        _ui_update_timers(get_all_timers())

    mins, secs = divmod(seconds, 60)
    if mins and secs:
        duration_str = f"{mins} minute{'s' if mins != 1 else ''} and {secs} second{'s' if secs != 1 else ''}"
    elif mins:
        duration_str = f"{mins} minute{'s' if mins != 1 else ''}"
    else:
        duration_str = f"{secs} second{'s' if secs != 1 else ''}"

    return f"Timer set for {duration_str}: '{label}'."


def cancel_timer(label: str) -> str:
    """Cancel a timer by name. Returns a confirmation or error string."""
    with _lock:
        match = next(
            (tid for tid, t in _timers.items()
            if t["name"].lower() == label.lower()),
            None
        )
        if not match:
            return f"I could not find a timer called '{label}', sir."
        del _timers[match]

    if _ui_update_timers:
        _ui_update_timers(get_all_timers())

    return f"Timer '{label}' cancelled, sir."


def list_timers() -> str:
    """Return a spoken summary of all active timers."""
    with _lock:
        if not _timers:
            return "You have no active timers, sir."
        now   = time.time()
        lines = []
        for t in _timers.values():
            remaining = max(0, int(t["ends_at"] - now))
            mins, secs = divmod(remaining, 60)
            if mins:
                rem_str = f"{mins}m {secs}s"
            else:
                rem_str = f"{secs}s"
            lines.append(f"{t['name']} — {rem_str} remaining")
        return "Active timers: " + ". ".join(lines) + "."


def get_all_timers() -> list[dict]:
    """Return a list of timer dicts for the UI."""
    now = time.time()
    with _lock:
        return [
            {
                "id":        tid,
                "name":      t["name"],
                "remaining": max(0, int(t["ends_at"] - now)),
            }
            for tid, t in _timers.items()
        ]


def parse_duration(text: str) -> int | None:
    """
    Parse natural-language duration into total seconds.
    Examples: "5 minutes", "90 seconds", "1 hour 30 minutes", "25 mins"
    Returns None if it cannot parse.
    """
    import re
    text    = text.lower()
    total   = 0
    found   = False
    patterns = [
        (r"(\d+)\s*h(?:our|rs?)?",   3600),
        (r"(\d+)\s*m(?:in(?:ute)?s?)?", 60),
        (r"(\d+)\s*s(?:ec(?:ond)?s?)?",  1),
    ]
    for pattern, multiplier in patterns:
        for match in re.finditer(pattern, text):
            total += int(match.group(1)) * multiplier
            found  = True
    return total if found else None
