"""
ORION MK2 — fast_path.py
────────────────────────────────────────────────────────────
Instant routing for common, unambiguous commands.

Asking Qwen which function to call takes a moment on every
command. For simple phrases like "what's the time" or "pause"
there's only one sensible answer, so we match them here with
plain Python and skip the model entirely.

Each pattern must match the WHOLE phrase, so longer requests
still go to Qwen:
    "pause"              → fast path (cmd_pause_music)
    "pause and tell me…" → Qwen

To add a phrase: add a row to FAST_PATHS below.
    (regex, "cmd_name", function_that_builds_args_from_match)
────────────────────────────────────────────────────────────
"""

import re


def _no_args(_m):
    return {}

def _level(m):
    return {"level": int(m.group("n"))}


# Words people add around a command that don't change its meaning.
_PREFIX = re.compile(
    r"^(?:(?:hey |ok |okay )?orion[,]? |(?:can|could|would) you (?:please )?|please )+"
)
_SUFFIX = re.compile(r"(?: (?:please|sir|for me|thanks|thank you|orion))+$")

_TODO = r"(?:to-?do|to do)"

FAST_PATHS = [
    # ── Time & date ───────────────────────────────────────
    (r"what(?:'s| is) the time(?: now| right now)?|what time is it(?: now| right now)?|time",
     "cmd_time", _no_args),
    (r"what(?:'s| is) (?:the date|today's date)(?: today)?|what day is it(?: today)?|what(?:'s| is) today",
     "cmd_date", _no_args),

    # ── Weather (default city) ────────────────────────────
    (r"(?:what(?:'s| is)|how(?:'s| is)) the weather(?: like)?(?: today| outside| now| right now)?|weather",
     "cmd_weather_spoken", _no_args),

    # ── Music ─────────────────────────────────────────────
    (r"(?:play|resume|unpause)(?: the| some)?(?: music| song)?|continue (?:playing|the music)",
     "cmd_play_music", _no_args),
    (r"pause(?: it| the| this)?(?: music| song)?|stop the (?:music|song)",
     "cmd_pause_music", _no_args),
    (r"skip(?: it| this| the)?(?: song| track)?|(?:play )?(?:the )?next (?:song|track)",
     "cmd_skip_song", _no_args),
    (r"(?:play )?(?:the )?(?:previous|last) (?:song|track)|go back(?: a| one)?(?: song| track)?",
     "cmd_previous_song", _no_args),
    (r"restart (?:the|this) (?:song|track)|(?:play )?(?:this|the) song (?:again|from the (?:start|beginning))"
     r"|start (?:the|this) song (?:again|over)",
     "cmd_restart_song", _no_args),

    (r"what(?:'s| is) (?:this |the )?(?:song|track|playing)(?: called| right now| now)?"
     r"|what song is (?:this|playing)|who (?:sings|is singing) (?:this|it)|what am i listening to",
     "cmd_now_playing", _no_args),

    # ── Volume & brightness (need a number) ───────────────
    (r"(?:(?:set|turn|change|put) )?(?:the )?volume(?: up| down)?(?: to| at)? (?P<n>\d{1,3})(?: percent)?",
     "cmd_volume", _level),
    (r"(?:(?:set|turn|change|put) )?(?:the )?(?:screen )?brightness(?: up| down)?(?: to| at)? (?P<n>\d{1,3})(?: percent)?",
     "cmd_brightness", _level),

    # ── System ────────────────────────────────────────────
    (r"(?:take |grab )?(?:a )?screenshot",
     "cmd_screenshot", _no_args),
    (r"(?:run )?(?:system )?diagnostics|system (?:stats|status)|check (?:the )?system",
     "cmd_system_stats", _no_args),
    (r"show (?:me )?(?:all )?(?:my )?(?:the )?(?:open )?windows",
     "cmd_show_windows", _no_args),

    # ── Info ──────────────────────────────────────────────
    (r"(?:what(?:'s| is) )?(?:the )?(?:latest )?news|(?:read|tell) me the news|what(?:'s| is) in the news",
     "cmd_news", _no_args),
    (r"(?:open |show me |read )?(?:the |my )?daily text",
     "cmd_daily_text", _no_args),
    (rf"what(?:'s| is) on my {_TODO} list|(?:read|show)(?: me)? my {_TODO} list|what do i need to do(?: today)?",
     "cmd_todo_read", _no_args),
    (r"what(?:'s| is) on my calendar(?: today)?|(?:read|show)(?: me)? my calendar"
     r"|what(?:'s| is) my schedule(?: today| like)?|do i have anything (?:on )?today",
     "cmd_calendar_read", _no_args),
    (r"(?:list|what are|read)(?: me)? (?:my |the )?timers|how (?:long|much time) is left(?: on (?:my|the) timers?)?",
     "cmd_list_timers", _no_args),

    # ── Misc ──────────────────────────────────────────────
    (r"flip a coin|(?:do a )?coin (?:flip|toss)|heads or tails",
     "cmd_flip_coin", _no_args),
]

_COMPILED = [(re.compile(rf"(?:{p})"), fn, build) for p, fn, build in FAST_PATHS]


def normalise(text: str) -> str:
    """Lowercase, tidy punctuation and strip filler like 'can you' / 'please'."""
    t = text.lower().strip()
    t = t.replace("’", "'").replace("%", " percent")
    t = re.sub(r"[?!.,]+$", "", t)        # trailing punctuation from Google
    t = re.sub(r"\s+", " ", t).strip()
    t = _PREFIX.sub("", t)
    t = _SUFFIX.sub("", t)
    return t.strip()


def match_fast_path(text: str) -> dict | None:
    """
    Return {"function": ..., "args": {...}} if the phrase is a known
    simple command, otherwise None (and the caller asks Qwen).
    """
    t = normalise(text)
    if not t:
        return None
    for pattern, fn_name, build_args in _COMPILED:
        m = pattern.fullmatch(t)
        if m:
            return {"function": fn_name, "args": build_args(m)}
    return None