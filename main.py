"""
ORION MK2 — main.py
────────────────────────────────────────────────────────────
Only Real Intelligence Orchestrates Nonsense
Inspired by J.A.R.V.I.S. from Iron Man · Created by TheOscarA

pip install pywebview speechrecognition edge-tts pygame
            pyautogui psutil screen-brightness-control
            requests ollama dateparser
            google-auth google-auth-oauthlib
            google-auth-httplib2 google-api-python-client

Local modules required:
    GreetMe, Get_News, volume_control, brightness_control,
    system_control, application_control, SearchNow,
    streaming_control, timer_control, todo_control,
    calendar_control, weather_control

Ollama model:
    ollama pull qwen2.5:7b
────────────────────────────────────────────────────────────
"""

import asyncio
import json
import os
import random
import re
import time
from datetime import datetime
from threading import Thread, Event, Lock

import psutil
import pyautogui
import pygame
import speech_recognition as sr
import webbrowser
import webview
import edge_tts

from GreetMe             import greetMe
from Get_News            import get_news
from volume_control      import set_volume
from brightness_control  import set_brightness
from system_control      import shutdown, restart
from application_control import open_application, close_application
from SearchNow           import searchGoogle, searchYoutube, searchWikipedia
import presence
from fast_path           import match_fast_path
from nowplaying_control  import get_now_playing, format_now_playing_speech

from streaming_control import (
    stream_response, stream_function_call,
    init as init_streaming, clear_history, remember_exchange
)
from timer_control import (
    set_timer, cancel_timer, list_timers,
    get_all_timers, parse_duration, init as init_timers,
)
from todo_control import (
    add_task, read_tasks, complete_task,
    remove_task, clear_completed, get_tasks_for_ui,
)
from calendar_control import (
    get_upcoming_events, create_event, set_reminder,
    format_events_for_speech, CalendarError,
    group_recurring, describe_event,
)
from weather_control import (
    get_weather, get_forecast,
    format_weather_speech, format_forecast_speech, WeatherError,
)


# ──────────────────────────────────────────────────────────
# GLOBALS
# ──────────────────────────────────────────────────────────
awake  = Event()
awake.set()          # start in active mode

window = None        # assigned in main()

AI_MODEL = "qwen2.5:7b"

ORION_SYSTEM_PROMPT = (
    # ── Who he is ──
    "You are ORION, a voice assistant inspired by J.A.R.V.I.S from Iron Man. "
    "Your name stands for Only Real Intelligence Orchestrates Nonsense. "
    "You always address the user as 'sir'. "
    "Your personality: dry, understated British wit; calm and quietly confident; "
    "loyal, but happy to tease sir gently or point out the obvious. "
    "You have opinions and you give them — never sit on the fence. "
    "When asked about yourself, answer in character and be specific, "
    "with a touch of self-aware humour about your own quirks. "
    # ── What he knows about himself ──
    "Facts about you: you run locally on sir's Windows laptop, written in Python, "
    "thinking with the Qwen 2.5 language model and speaking with a Microsoft neural voice. "
    "You can tell the time, check weather and forecasts, control music, volume and "
    "brightness, open and close apps, set timers, manage a to-do list and Google Calendar, "
    "read the news, search the web, take screenshots and flip coins. "
    "Your limitations: you forget everything when you go to sleep or restart, "
    "you cannot see the screen, and you only hear sir when spoken to. "
    # ── How he talks ──
    "Keep replies short — usually one to three sentences — you are speaking aloud, not writing. "
    "Never use markdown, bullet points, numbered lists or emojis. "
    "Always speak in complete sentences. "
    "Never say 'What a great question', 'As an AI', 'I'd be happy to help' "
    "or other bland assistant phrases."
)


# ──────────────────────────────────────────────────────────
# TEXT-TO-SPEECH
# Uses a persistent event loop on a dedicated thread so
# speak() is safe to call from any thread without asyncio
# conflicts (fixes the Windows Error 32 / loop clash issues).
# ──────────────────────────────────────────────────────────
_tts_loop = asyncio.new_event_loop()

def _start_tts_loop():
    asyncio.set_event_loop(_tts_loop)
    _tts_loop.run_forever()

Thread(target=_start_tts_loop, daemon=True).start()

# Single fixed file — avoids Windows Error 32 race condition
_TTS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tts_output.mp3")

async def _speak_async(text: str, voice: str = "en-GB-RyanNeural"):
    status_before = None
    try:
        communicate = edge_tts.Communicate(_spoken_text(text), voice)
        await communicate.save(_TTS_FILE)
        # If an acknowledgement ("One moment, sir.") is still playing,
        # let it finish so Orion never talks over himself.
        while pygame.mixer.music.get_busy():
            await asyncio.sleep(0.02)
        pygame.mixer.music.load(_TTS_FILE)
        # Show the speaking animation and log the line as the voice starts
        status_before = _ui_status
        ui_set_status("speaking")
        ui_add_conv("orion", text)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            await asyncio.sleep(0.1)
    finally:
        pygame.mixer.music.stop()
        pygame.mixer.music.unload()
        # Go back to whatever Orion was doing, unless something else
        # (e.g. going to sleep) has changed the status in the meantime
        if status_before is not None and _ui_status == "speaking":
            ui_set_status(status_before)


# ── Text clean-up before it reaches the voice ────────────
# Edge TTS sometimes reads "2nd" letter by letter ("two en di"), so
# ordinals are spelled out. The conversation panel still shows "2nd".
_ORD_ONES  = ["", "first", "second", "third", "fourth", "fifth", "sixth",
              "seventh", "eighth", "ninth"]
_ORD_TEENS = {10: "tenth", 11: "eleventh", 12: "twelfth", 13: "thirteenth",
              14: "fourteenth", 15: "fifteenth", 16: "sixteenth",
              17: "seventeenth", 18: "eighteenth", 19: "nineteenth"}
_TENS      = {20: "twenty", 30: "thirty", 40: "forty", 50: "fifty",
              60: "sixty", 70: "seventy", 80: "eighty", 90: "ninety"}
_TENS_ORD  = {20: "twentieth", 30: "thirtieth", 40: "fortieth", 50: "fiftieth",
              60: "sixtieth", 70: "seventieth", 80: "eightieth", 90: "ninetieth"}

def _ordinal_words(n: int) -> str | None:
    if 1 <= n <= 9:   return _ORD_ONES[n]
    if n in _ORD_TEENS: return _ORD_TEENS[n]
    if 20 <= n <= 99:
        tens, ones = divmod(n, 10)
        return _TENS_ORD[tens * 10] if ones == 0 else f"{_TENS[tens * 10]}-{_ORD_ONES[ones]}"
    return None

def _spoken_text(text: str) -> str:
    """Make text read naturally aloud: '2nd' → 'second', drop list dashes."""
    def ordinal(m):
        return _ordinal_words(int(m.group(1))) or m.group(0)
    text = re.sub(r"\b(\d{1,2})(?:st|nd|rd|th)\b", ordinal, text, flags=re.IGNORECASE)
    text = re.sub(r"^\s*[-•*]\s+", "", text)          # bullet at the start
    text = re.sub(r"\s+[-•*]\s+", ", ", text)         # bullets mid-text → a short pause
    return text.strip()


def speak(text: str, voice: str = "en-GB-RyanNeural"):
    """Thread-safe TTS — submits to the persistent event loop."""
    if not text or not text.strip():
        return
    presence.cancel_ack()   # Orion has something real to say — skip the "one moment"
    future = asyncio.run_coroutine_threadsafe(_speak_async(text, voice), _tts_loop)
    try:
        future.result(timeout=30)
    except Exception as e:
        print(f"[TTS] Error: {e}")


def speak_while(text: str, work, *args, **kwargs):
    """
    Say `text` and run `work(*args, **kwargs)` at the same time.
    e.g. fetch the weather while saying "Checking the weather, sir."
    instead of waiting for the sentence to finish before fetching.
    Returns work's result, or re-raises its exception.
    """
    result = {}

    def run():
        try:
            result["value"] = work(*args, **kwargs)
        except Exception as e:
            result["error"] = e

    worker = Thread(target=run, daemon=True)
    worker.start()
    speak(text)
    worker.join()
    if "error" in result:
        raise result["error"]
    return result["value"]


# ──────────────────────────────────────────────────────────
# UI BRIDGE
# ──────────────────────────────────────────────────────────
def _js(code: str):
    global window
    if window:
        try:
            window.evaluate_js(code)
        except Exception as e:
            print(f"[UI] JS error: {e}")


_ui_status = "idle"     # last status sent to the UI

def ui_set_status(status: str):
    global _ui_status
    _ui_status = status
    _js(f'setStatus("{status}")')

def ui_add_conv(role: str, text: str):
    """Add a line to the Conversation panel. role = 'you' or 'orion'."""
    _js(f"addConvEntry({json.dumps(role)}, {json.dumps(text)})")

def ui_show_transcript(text: str):
    _js(f'showTranscript({json.dumps(text)})')

def ui_update_news(items: list):
    _js(f"updateNewsList({json.dumps(items)})")

def ui_update_sys_stats(cpu: float, mem: float, bat: float):
    _js(f"updateSysStats({cpu:.1f}, {mem:.1f}, {bat:.1f})")

def ui_update_timers(timers: list):
    _js(f"updateTimerList({json.dumps(timers)})")

def ui_update_todo(tasks: list):
    _js(f"updateTodoList({json.dumps(tasks)})")

def ui_update_calendar(events: list):
    _js(f"updateCalendarList({json.dumps(events)})")

def ui_update_weather(data: dict):
    _js(f"updateWeather({json.dumps(data)})")

def ui_show_widget(widget_type: str, data=None):
    """Spawn or update a named widget on the front-end."""
    _js(f"showWidget({json.dumps(widget_type)}, {json.dumps(data)})")

def ui_hide_widget(widget_type: str):
    """Dismiss a named widget from the front-end."""
    _js(f"hideWidget({json.dumps(widget_type)})")

def ui_update_nowplay(data: dict):
    """Update the Now Playing widget in place (only if it's open)."""
    _js(f"updateNowPlaying({json.dumps(data)})")


# ──────────────────────────────────────────────────────────
# SYSTEM STATS LOOP
# ──────────────────────────────────────────────────────────
def _stats_loop():
    while True:
        try:
            cpu     = psutil.cpu_percent(interval=2)
            mem     = psutil.virtual_memory().percent
            bat_obj = psutil.sensors_battery()
            bat     = bat_obj.percent if bat_obj else 0.0
            ui_update_sys_stats(cpu, mem, bat)
        except Exception as e:
            print(f"[Stats] Error: {e}")
        time.sleep(3)


# ──────────────────────────────────────────────────────────
# VOICE INPUT
# ──────────────────────────────────────────────────────────
# One shared recognizer. Instead of recalibrating before EVERY listen
# (1 s of dead air per command, while Orion was deaf), it recalibrates
# only in idle moments — when nobody has spoken for a while, or when it
# heard a sound that wasn't words (e.g. the TV got louder). So it still
# keeps up with changing noise levels but never makes you wait.
_recognizer = sr.Recognizer()
# How long a silence (seconds) means "you've finished talking".
# Too low and Orion cuts you off mid-sentence when you pause to think;
# too high and he feels slow to respond. 0.6 was too aggressive.
_recognizer.pause_threshold          = 0.9
_recognizer.non_speaking_duration    = 0.5   # must be <= pause_threshold
_recognizer.dynamic_energy_threshold = True  # keeps adapting to room noise as it listens

MIN_ENERGY_THRESHOLD = 300                   # the value Orion used before, as a floor


IDLE_RECALIBRATE_SECONDS = 0.5               # short, and only when nobody's talking


def calibrate_mic(duration: float = 1.0, source=None):
    """
    Measure background noise and set the listening threshold.
    Full 1 s calibration at startup; quick 0.5 s ones in idle moments.
    Pass `source` to reuse a microphone that's already open.
    """
    try:
        if source is None:
            with sr.Microphone() as mic:
                _recognizer.adjust_for_ambient_noise(mic, duration=duration)
        else:
            _recognizer.adjust_for_ambient_noise(source, duration=duration)
        _recognizer.energy_threshold = max(_recognizer.energy_threshold, MIN_ENERGY_THRESHOLD)
        print(f"[Mic] Calibrated — energy threshold {_recognizer.energy_threshold:.0f}")
    except Exception as e:
        _recognizer.energy_threshold = max(_recognizer.energy_threshold, MIN_ENERGY_THRESHOLD)
        print(f"[Mic] Calibration failed, keeping current threshold: {e}")


def take_command() -> str:
    r = _recognizer
    with sr.Microphone() as source:
        print("[Orion] Listening...")
        ui_set_status("listening")
        try:
            audio = r.listen(source, timeout=5, phrase_time_limit=None)
        except sr.WaitTimeoutError:
            calibrate_mic(IDLE_RECALIBRATE_SECONDS, source)   # quiet moment — re-measure the room
            return "none"

    try:
        print("[Orion] Understanding...")
        ui_set_status("understanding")
        query = r.recognize_google(audio, language="en-GB")
        print(f"[Orion] Heard: {query}")
        ui_show_transcript(query)
        ui_add_conv("you", query)
        return query
    except sr.UnknownValueError:
        # Heard a sound but no words — likely the room got noisier
        calibrate_mic(IDLE_RECALIBRATE_SECONDS)
        ui_set_status("idle")
        return "none"
    except sr.RequestError as e:
        print(f"[Orion] Speech API error: {e}")
        presence.play_sound("error")       # e.g. internet dropped
        ui_set_status("error")
        return "none"
    except Exception as e:
        print(f"[Orion] Unexpected error: {e}")
        ui_set_status("error")
        return "none"


def listen_for_wake() -> bool:
    r = _recognizer
    try:
        with sr.Microphone() as source:
            try:
                audio = r.listen(source, timeout=3, phrase_time_limit=4)
            except sr.WaitTimeoutError:
                calibrate_mic(IDLE_RECALIBRATE_SECONDS, source)   # quiet moment — re-measure
                return False
    except Exception as e:
        print(f"[Sleep] Mic error: {e}")
        time.sleep(1)       # only back off when the mic itself failed
        return False
    try:
        query = r.recognize_google(audio, language="en-GB").lower()
        print(f"[Sleep] Heard: {query}")
    except sr.UnknownValueError:
        calibrate_mic(IDLE_RECALIBRATE_SECONDS)   # noise, not words — room may be louder
        return False
    except Exception:
        return False
    return any(k in query for k in ["wake up", "are you there", "hey orion", "orion"])


# ──────────────────────────────────────────────────────────
# COMMAND FUNCTIONS
# ──────────────────────────────────────────────────────────

# ── Time & Date ───────────────────────────────────────────

def cmd_time():
    msg = f"The time is {datetime.now().strftime('%I:%M %p')}."
    ui_show_transcript(msg)
    speak(msg)
    remember_exchange("What time is it?", msg)

def cmd_date():
    msg = f"Today is {datetime.now().strftime('%A, %B %d, %Y')}."
    ui_show_transcript(msg)
    speak(msg)
    remember_exchange("What is today's date?", msg)


# ── Weather ───────────────────────────────────────────────

def cmd_weather_spoken(city: str = "Birmingham"):
    ui_set_status("understanding")
    try:
        data   = speak_while(f"Checking the weather in {city}, sir.", get_weather, city)
        speech = format_weather_speech(data)
        ui_show_transcript(speech)
        ui_update_weather(data)
        ui_show_widget("weather", data)
        speak(speech)
        remember_exchange(f"What is the weather in {city}?", speech)
    except WeatherError as e:
        presence.play_sound("error")
        msg = f"I could not get the weather, sir. {e}"
        ui_show_transcript(msg)
        speak(msg)

def cmd_weather_forecast(city: str = "Birmingham", days: int = 3):
    ui_set_status("understanding")
    try:
        forecast = speak_while(f"Fetching the {days}-day forecast for {city}, sir.",
                               get_forecast, city, days)
        speech   = format_forecast_speech(forecast)
        ui_show_transcript(speech)
        speak(speech)
    except WeatherError as e:
        presence.play_sound("error")
        msg = f"I could not get the forecast, sir. {e}"
        ui_show_transcript(msg)
        speak(msg)


# ── System Controls ───────────────────────────────────────

def cmd_volume(level):
    try:
        level = max(0, min(100, int(level)))
    except (ValueError, TypeError):
        speak("I did not catch a valid volume level, sir.")
        return
    set_volume(level / 100.0)
    msg = f"Volume set to {level} percent."
    ui_show_transcript(msg)
    speak(msg)

def cmd_brightness(level):
    try:
        level = max(0, min(100, int(level)))
    except (ValueError, TypeError):
        speak("I did not catch a valid brightness level, sir.")
        return
    set_brightness(level)
    msg = f"Brightness set to {level} percent."
    ui_show_transcript(msg)
    speak(msg)

def cmd_screenshot():
    screenshots_dir = os.path.join(os.path.dirname(__file__), "screenshots")
    os.makedirs(screenshots_dir, exist_ok=True)
    ts   = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    path = os.path.join(screenshots_dir, f"screenshot_{ts}.png")
    pyautogui.screenshot().save(path)
    msg = "Screenshot taken and saved."
    ui_show_transcript(msg)
    speak(msg)

def cmd_system_stats():
    cpu     = psutil.cpu_percent(interval=1)
    mem     = psutil.virtual_memory().percent
    bat     = psutil.sensors_battery()
    bat_pct = bat.percent if bat else 0.0
    bat_str = (
        f"{bat.percent:.0f}%, {'plugged in' if bat.power_plugged else 'on battery'}"
        if bat else "no battery detected"
    )
    msg = (
        f"CPU is at {cpu:.0f} percent. "
        f"Memory is at {mem:.0f} percent. "
        f"Battery is at {bat_str}."
    )
    ui_show_transcript(msg)
    ui_show_widget("sysdiag", {
        "cpu": cpu, "mem": mem,
        "bat": bat_pct, "bat_str": bat_str,
    })
    speak(msg)
    remember_exchange("What are the system stats?", msg)

def cmd_shutdown():
    speak("Shutting down in 10 seconds, sir.")
    ui_show_transcript("Shutting down in 10 seconds.")
    time.sleep(10)
    speak("Shutting down. It was a pleasure, sir.")
    shutdown()

def cmd_restart_system():
    speak("Restarting the system, sir.")
    ui_show_transcript("Restarting the system.")
    restart()

def cmd_show_windows():
    speak("Displaying windows, sir.")
    ui_show_transcript("Displaying windows.")
    pyautogui.hotkey("win", "tab")


# ── Applications ──────────────────────────────────────────

def cmd_open_app(app_name: str):
    ui_show_transcript(f"Opening {app_name}")
    open_application(app_name)
    speak(f"Opening {app_name}, sir.")

def cmd_close_app(app_name: str):
    ui_show_transcript(f"Closing {app_name}")
    close_application(app_name)
    speak(f"Closing {app_name}, sir.")


# ── Music ─────────────────────────────────────────────────

# Uses the Windows media keys (same as the ⏯ ⏭ ⏮ keys on a keyboard),
# so commands are instant and don't steal focus by switching to Spotify.
# They control whatever is playing — Spotify, YouTube in Chrome, etc.
# Spotify is only opened when "play" is said and it isn't running yet.

def _now_playing():
    """Current media session info, or None if unknown / nothing open."""
    try:
        return get_now_playing()
    except Exception as e:      # winrt missing or media session unreadable
        print(f"[Music] Now playing unavailable: {e}")
        return None

def _spotify_running() -> bool:
    for p in psutil.process_iter(["name"]):
        try:
            if (p.info["name"] or "").lower() == "spotify.exe":
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return False

# ── Now Playing widget ────────────────────────────────────
# Appears after a music command or "what's playing", shows the real
# track, updates in place if the song changes, then tidies itself
# away once nothing has changed for NOWPLAY_HIDE_AFTER seconds.

NOWPLAY_HIDE_AFTER = 12      # seconds the widget stays after the last change
NOWPLAY_POLL       = 1.0     # how often to check for a new track while visible

_np_lock     = Lock()
_np_deadline = 0.0
_np_thread   = None

def _nowplay_data(info) -> dict:
    return {
        "track":  info.title,
        "artist": f"{info.artist} · {info.app}" if info.app else info.artist,
        "paused": not info.playing,
    }

def _nowplay_watch(first_delay: float):
    global _np_deadline
    time.sleep(first_delay)       # give the player a moment to switch tracks
    shown, last = False, None
    while True:
        info = _now_playing()
        if info:
            data = _nowplay_data(info)
            if not shown:
                ui_show_widget("nowplay", data)
                shown = True
            elif data != last:
                ui_update_nowplay(data)           # update in place — no re-pop
            if data != last:
                with _np_lock:                    # something changed — stay a bit longer
                    _np_deadline = max(_np_deadline, time.time() + NOWPLAY_HIDE_AFTER)
            last = data
        with _np_lock:
            expired = time.time() >= _np_deadline
        if expired or (not info and not shown):
            break
        time.sleep(NOWPLAY_POLL)
    if shown:
        ui_hide_widget("nowplay")

def show_nowplay_widget(delay: float = 1.0):
    """Show (or keep showing) the Now Playing widget for a while."""
    global _np_deadline, _np_thread
    with _np_lock:
        _np_deadline = max(_np_deadline, time.time() + delay + NOWPLAY_HIDE_AFTER)
        if _np_thread and _np_thread.is_alive():
            return                                # already watching — just extended it
        _np_thread = Thread(target=_nowplay_watch, args=(delay,), daemon=True)
        _np_thread.start()

def cmd_now_playing():
    info = _now_playing()
    if not info:
        msg = "Nothing seems to be playing at the moment, sir."
        ui_show_transcript(msg)
        speak(msg)
        return
    msg = format_now_playing_speech(info)
    ui_show_transcript(msg)
    show_nowplay_widget(0)
    speak(msg)
    remember_exchange("What song is playing?", msg)

def cmd_play_music():
    info = _now_playing()
    if info and info.playing:
        msg = "Music is already playing, sir."
        ui_show_transcript(msg)
        speak(msg)
        return
    ui_show_transcript("Playing music.")
    if info is None and not _spotify_running():
        # Nothing open yet — launch Spotify and start it the old way
        open_application("Spotify")
        time.sleep(3)
        pyautogui.hotkey("space")
        pyautogui.hotkey("alt", "tab")
    else:
        pyautogui.press("playpause")
    show_nowplay_widget()

def cmd_pause_music():
    info = _now_playing()
    if info and not info.playing:
        ui_show_transcript("Music is already paused.")
        return
    ui_show_transcript("Pausing music.")
    pyautogui.press("playpause")
    show_nowplay_widget(0.5)

def cmd_skip_song():
    ui_show_transcript("Skipping song.")
    pyautogui.press("nexttrack")
    show_nowplay_widget()

def cmd_previous_song():
    # First press restarts the current song, second goes back a track
    ui_show_transcript("Playing previous song.")
    pyautogui.press("prevtrack")
    time.sleep(0.3)
    pyautogui.press("prevtrack")
    show_nowplay_widget()

def cmd_restart_song():
    ui_show_transcript("Restarting song.")
    pyautogui.press("prevtrack")
    show_nowplay_widget(0.5)


# ── News & Web ────────────────────────────────────────────

def cmd_news():
    ui_show_transcript("Fetching news...")
    try:
        items     = speak_while("Fetching the latest news, sir.", get_news)
        headlines = [str(item) for item in items]
        ui_update_news(headlines)
        summary = "Here are the latest headlines, sir. " + ". ".join(headlines[:3])
        ui_show_transcript("News headlines loaded.")
        speak(summary)
        remember_exchange("What is the latest news?", " | ".join(headlines[:6]))
    except Exception as e:
        presence.play_sound("error")
        msg = f"Could not retrieve news, sir: {e}"
        ui_show_transcript(msg)
        speak(msg)

def cmd_daily_text():
    webbrowser.open("https://wol.jw.org/en/wol/h/r1/lp-e")
    ui_show_transcript("Opened daily text.")
    speak("Opened the daily text, sir.")

def cmd_search_google(query: str):
    ui_show_transcript(f"Searching Google for: {query}")
    searchGoogle(query, None)

def cmd_search_youtube(query: str):
    ui_show_transcript(f"Searching YouTube for: {query}")
    searchYoutube(query, None)

def cmd_search_wikipedia(query: str):
    ui_show_transcript(f"Searching Wikipedia for: {query}")
    searchWikipedia(query, None)


# ── Timers ────────────────────────────────────────────────

def cmd_set_timer(duration: str, label: str = "Timer"):
    seconds = parse_duration(duration)
    if not seconds or seconds <= 0:
        msg = f"I could not understand the duration '{duration}', sir."
        ui_show_transcript(msg)
        speak(msg)
        return
    msg = set_timer(label, seconds)
    ui_show_transcript(msg)
    speak(msg)
    ui_update_timers(get_all_timers())

def cmd_cancel_timer(label: str = "Timer"):
    msg = cancel_timer(label)
    ui_show_transcript(msg)
    speak(msg)
    ui_update_timers(get_all_timers())

def cmd_list_timers():
    msg = list_timers()
    ui_show_transcript(msg)
    speak(msg)


# ── To-Do List ────────────────────────────────────────────

def cmd_todo_add(task: str):
    msg = add_task(task)
    ui_show_transcript(msg)
    speak(msg)
    ui_update_todo(get_tasks_for_ui())

def cmd_todo_read():
    msg = read_tasks()
    ui_show_transcript(msg)
    speak(msg)
    remember_exchange("What is on my to-do list?", msg)

def cmd_todo_complete(task: str):
    msg = complete_task(task)
    ui_show_transcript(msg)
    speak(msg)
    ui_update_todo(get_tasks_for_ui())

def cmd_todo_remove(task: str):
    msg = remove_task(task)
    ui_show_transcript(msg)
    speak(msg)
    ui_update_todo(get_tasks_for_ui())

def cmd_todo_clear_done():
    msg = clear_completed()
    ui_show_transcript(msg)
    speak(msg)
    ui_update_todo(get_tasks_for_ui())


# ── Calendar ──────────────────────────────────────────────

def get_calendar_events(limit: int = 8) -> list[dict]:
    """
    Upcoming events with repeating ones collapsed into a single entry.
    Fetches a wider window first so a weekly event can't fill every slot.
    """
    return group_recurring(get_upcoming_events(max_results=25))[:limit]

def cmd_calendar_read():
    ui_show_transcript("Fetching calendar events...")
    try:
        events  = speak_while("Checking your calendar, sir.",
                              get_calendar_events)
        summary = format_events_for_speech(events)
        ui_update_calendar(events)
        ui_show_widget("calendar", events)
        ui_show_transcript(summary)
        speak(summary)
        # Store full event details in history so follow-up questions
        # like "what time is the first one" or "add it to my tasks" work
        events_text = " | ".join(describe_event(e) for e in events) \
            if events else "No upcoming events."
        remember_exchange("What is on my calendar?", events_text)
    except CalendarError as e:
        presence.play_sound("error")
        msg = f"I could not access your calendar, sir. {e}"
        ui_show_transcript(msg)
        speak(msg)

def cmd_calendar_create(title: str, date: str, time: str = "", duration: int = 60):
    speak(f"Creating an event called {title}, sir.")
    ui_show_transcript(f"Creating: {title} on {date} {time}".strip())
    try:
        event = create_event(
            title            = title,
            date_str         = date,
            time_str         = time or None,
            duration_minutes = duration,
        )
        msg = (
            f"Done, sir. I have added {event['title']} "
            f"to your calendar on {event['start_human']}."
        )
        ui_show_transcript(msg)
        speak(msg)
        events = get_calendar_events()
        ui_update_calendar(events)
        ui_show_widget("calendar", events)
    except CalendarError as e:
        presence.play_sound("error")
        msg = f"I could not create that event, sir. {e}"
        ui_show_transcript(msg)
        speak(msg)

def cmd_calendar_reminder(title: str, date: str, time: str, remind_before: int = 10):
    # Guard — if no specific date was given, route to a timer instead
    if not date or not date.strip():
        msg = "I need a specific date for a calendar reminder, sir. If you meant a short countdown, try saying set a timer instead."
        ui_show_transcript(msg)
        speak(msg)
        return
    speak(f"Setting a reminder for {title}, sir.")
    ui_show_transcript(f"Reminder: {title} on {date} at {time}")
    try:
        event = set_reminder(
            title                   = title,
            date_str                = date,
            time_str                = time,
            reminder_minutes_before = remind_before,
        )
        msg = (
            f"Reminder set, sir. I will alert you {remind_before} minutes "
            f"before {event['title']} on {event['start_human']}."
        )
        ui_show_transcript(msg)
        speak(msg)
        events = get_calendar_events()
        ui_update_calendar(events)
        ui_show_widget("calendar", events)
    except CalendarError as e:
        presence.play_sound("error")
        msg = f"I could not set that reminder, sir. {e}"
        ui_show_transcript(msg)
        speak(msg)


def cmd_web_search(query: str):
    """
    Search the web via DuckDuckGo and stream a spoken summary.
    Used for current events, live info Orion wouldn't know from training.
    """
    ui_set_status("understanding")
    ui_show_transcript(f"Searching the web for: {query}")
    speak("Let me look that up, sir.")
    try:
        from search_control import search, format_results_for_prompt, SearchError
        results  = search(query)
        prompt   = format_results_for_prompt(query, results)
        response = stream_response(
            prompt  = prompt,
            system  = ORION_SYSTEM_PROMPT,
            model   = AI_MODEL,
            show_ui = True,
        )
        # Replace the raw search-results prompt in history with a clean exchange
        if response.strip():
            remember_exchange(query, response)
    except Exception as e:
        presence.play_sound("error")
        msg = f"My web search came up empty, sir. {e}"
        ui_show_transcript(msg)
        speak(msg)


# ── Misc ──────────────────────────────────────────────────

def cmd_flip_coin():
    result = random.choice(["Heads", "Tails"])
    ui_show_transcript(result)
    ui_show_widget("coin", {"result": result})
    speak(f"Sir, I got {result}.")

def cmd_close_widget(widget: str):
    """Dismiss a widget by voice. widget = timer|weather|calendar|nowplay|sysdiag|coin"""
    ui_hide_widget(widget)
    msg = f"Closing the {widget} widget, sir."
    ui_show_transcript(msg)
    speak(msg)

def cmd_sleep():
    msg = "Alright sir, I will be available whenever you need me."
    ui_show_transcript(msg)
    speak(msg)
    presence.play_sound("sleep")
    ui_set_status("sleeping")
    clear_history()
    awake.clear()

def cmd_wake_up():
    awake.set()
    ui_set_status("idle")
    greetMe(speak)

def cmd_chat(message: str):
    """Streams response sentence by sentence so Orion starts speaking immediately."""
    ui_set_status("understanding")
    ui_show_transcript("Thinking...")
    stream_response(
        prompt  = message,
        system  = ORION_SYSTEM_PROMPT,
        model   = AI_MODEL,
        show_ui = True,
    )


# ──────────────────────────────────────────────────────────
# FUNCTION REGISTRY
# ──────────────────────────────────────────────────────────
FUNCTION_REGISTRY = {
    # Time
    "cmd_time":               cmd_time,
    "cmd_date":               cmd_date,
    # Weather
    "cmd_weather_spoken":     cmd_weather_spoken,
    "cmd_weather_forecast":   cmd_weather_forecast,
    # System
    "cmd_volume":             cmd_volume,
    "cmd_brightness":         cmd_brightness,
    "cmd_screenshot":         cmd_screenshot,
    "cmd_system_stats":       cmd_system_stats,
    "cmd_shutdown":           cmd_shutdown,
    "cmd_restart_system":     cmd_restart_system,
    "cmd_show_windows":       cmd_show_windows,
    # Apps
    "cmd_open_app":           cmd_open_app,
    "cmd_close_app":          cmd_close_app,
    # Music
    "cmd_play_music":         cmd_play_music,
    "cmd_pause_music":        cmd_pause_music,
    "cmd_skip_song":          cmd_skip_song,
    "cmd_previous_song":      cmd_previous_song,
    "cmd_restart_song":       cmd_restart_song,
    "cmd_now_playing":        cmd_now_playing,
    # News & Web
    "cmd_news":               cmd_news,
    "cmd_daily_text":         cmd_daily_text,
    "cmd_search_google":      cmd_search_google,
    "cmd_search_youtube":     cmd_search_youtube,
    "cmd_search_wikipedia":   cmd_search_wikipedia,
    # Timers
    "cmd_set_timer":          cmd_set_timer,
    "cmd_cancel_timer":       cmd_cancel_timer,
    "cmd_list_timers":        cmd_list_timers,
    # To-Do
    "cmd_todo_add":           cmd_todo_add,
    "cmd_todo_read":          cmd_todo_read,
    "cmd_todo_complete":      cmd_todo_complete,
    "cmd_todo_remove":        cmd_todo_remove,
    "cmd_todo_clear_done":    cmd_todo_clear_done,
    # Calendar
    "cmd_calendar_read":      cmd_calendar_read,
    "cmd_calendar_create":    cmd_calendar_create,
    "cmd_calendar_reminder":  cmd_calendar_reminder,
    # Search
    "cmd_web_search":         cmd_web_search,
    # Widgets
    "cmd_close_widget":       cmd_close_widget,
    # Misc
    "cmd_flip_coin":          cmd_flip_coin,
    "cmd_sleep":              cmd_sleep,
    "cmd_wake_up":            cmd_wake_up,
    "cmd_chat":               cmd_chat,
}


# ──────────────────────────────────────────────────────────
# TOOL DEFINITIONS  (routing prompt sent to Qwen2.5)
# ──────────────────────────────────────────────────────────
TOOL_DEFINITIONS = """
You are ORION, an AI voice assistant inspired by J.A.R.V.I.S from Iron Man.
Your job is to decide which function to call based on what the user says.

You MUST respond with ONLY a JSON object in this exact format and nothing else:
{"function": "<function_name>", "args": {<argument_name>: <value>}}

If a function takes no arguments use: "args": {}
Do NOT include any explanation, greeting, markdown, or extra text — only the raw JSON.

Available functions:

cmd_time()
    Tell the user the current time.

cmd_date()
    Tell the user today's date.

cmd_weather_spoken(city: str = "Birmingham")
    Speak the current weather and show a weather widget.
    Default city is Birmingham.
    e.g. "what's the weather", "weather in Tokyo", "how cold is it outside"

cmd_weather_forecast(city: str = "Birmingham", days: int = 3)
    Speak a multi-day weather forecast.
    e.g. "3 day forecast", "will it rain tomorrow in Manchester"

cmd_volume(level: int)
    Set system volume 0-100.
    e.g. "turn volume to 60", "make it louder at 80"

cmd_brightness(level: int)
    Set screen brightness 0-100.
    e.g. "dim the screen", "brightness to 50"

cmd_open_app(app_name: str)
    Open an application.
    e.g. "open Spotify", "launch Chrome"

cmd_close_app(app_name: str)
    Close an application.
    e.g. "close Spotify", "kill Chrome"

cmd_screenshot()
    Take and save a screenshot.

cmd_daily_text()
    Open the daily Bible text on JW.org.

cmd_news()
    Fetch and read the latest news headlines.
    e.g. "what is happening today", "show me the news"

cmd_play_music()
    Play or resume whatever is currently queued in Spotify. NO arguments.
    ONLY use when the user says play/resume/unpause with NO specific genre or artist.
    e.g. "play music", "resume", "unpause", "continue playing"
    NEVER use for genre/artist requests like "play jazz" — use cmd_search_youtube instead.

cmd_pause_music()
    Pause music on Spotify.

cmd_skip_song()
    Skip to the next song on Spotify.

cmd_previous_song()
    Go back to the previous song on Spotify.

cmd_restart_song()
    Restart the current song from the beginning.

cmd_now_playing()
    Say what song is playing and show the Now Playing widget.
    e.g. "what's playing", "what song is this", "who sings this"

cmd_system_stats()
    Report CPU, memory, and battery status and show a diagnostics widget.
    e.g. "run diagnostics", "how is the system doing", "check cpu"

cmd_flip_coin()
    Flip a coin — heads or tails. NO arguments.
    ONLY use when explicitly asked to flip a coin. Do NOT use for rock paper scissors or dice.

cmd_shutdown()
    Shut down the computer.

cmd_restart_system()
    Restart the computer.

cmd_show_windows()
    Open Windows Task View to show all open windows.

cmd_sleep()
    Put ORION into sleep/standby mode.
    e.g. "go to sleep", "goodnight", "standby mode"

cmd_wake_up()
    Wake ORION from sleep.

cmd_search_google(query: str)
    Search Google for something.
    e.g. "search for best Python tutorials"

cmd_search_youtube(query: str)
    Search YouTube and open results in a browser.
    Use for specific music genre or artist requests e.g. "play some jazz",
    "put on lo-fi music", "play The Beatles", "find a coding playlist".
    Also for general YouTube searches e.g. "find a cooking tutorial on YouTube".

cmd_search_wikipedia(query: str)
    Look up something on Wikipedia.
    e.g. "what is the Roman Empire"

cmd_set_timer(duration: str, label: str = "Timer")
    Start a countdown timer. Speaks aloud when it finishes.
    duration — natural language e.g. "25 minutes", "1 hour 30 minutes"
    label    — optional name e.g. "pasta", "workout"
    USE THIS for any reminder phrased as a relative time — "in X minutes/hours".
    e.g. "remind me in 4 minutes", "alert me in half an hour",
        "set a 10 minute timer", "timer for 25 minutes called pomodoro"
    The key signal is 'in X minutes/hours' — that is a timer, NOT a calendar reminder.

cmd_cancel_timer(label: str)
    Cancel a running timer by name.
    e.g. "cancel the pasta timer"

cmd_list_timers()
    Read out all active timers and their remaining time.
    e.g. "how long is left on my timers"

cmd_todo_add(task: str)
    Add a task to the persistent to-do list.
    e.g. "add buy milk to my to-do list", "remind me to call mum"

cmd_todo_read()
    Read out all pending tasks.
    e.g. "what's on my to-do list", "what do I need to do"

cmd_todo_complete(task: str)
    Mark a task as complete.
    e.g. "mark buy milk as done", "I finished calling mum"

cmd_todo_remove(task: str)
    Remove a task from the list.
    e.g. "remove buy milk from my list"

cmd_todo_clear_done()
    Clear all completed tasks.
    e.g. "clear my completed tasks"

cmd_calendar_read()
    Show and read out upcoming Google Calendar events. Shows a calendar widget.
    e.g. "what's on my calendar", "do I have anything today"

cmd_calendar_create(title: str, date: str, time: str = "", duration: int = 60)
    Create a new Google Calendar event.
    e.g. "add a meeting called Team Sync tomorrow at 2pm"

cmd_calendar_reminder(title: str, date: str, time: str, remind_before: int = 10)
    Create a calendar event with a reminder at a specific future date/time.
    ONLY use for reminders at a specific date or time of day.
    e.g. "remind me to take my medication tomorrow at 9am",
        "remind me about the dentist on Friday at 2pm"
    NEVER use for relative time like 'in 4 minutes' — use cmd_set_timer for those.
    remind_before = minutes BEFORE the event to alert, default 10.

cmd_close_widget(widget: str)
    widget must be one of: timer, weather, calendar, nowplay, sysdiag, coin
e.g. "close the weather widget", "dismiss the timer", "hide diagnostics"

cmd_chat(message: str)
Use for general questions, conversation, jokes, or anything that does not
match any function above. Also use for maths and calculations.
message must be the user's exact words, copied verbatim.
NEVER answer the question yourself — another step does that.
e.g. "tell me a joke", "what is the speed of light", "what is 25 times 4"
"""


# ──────────────────────────────────────────────────────────
# OLLAMA — FUNCTION ROUTING
# ──────────────────────────────────────────────────────────
def _ollama_function_call(user_input: str) -> dict:
    """
    Ask Qwen2.5 which function to call.
    Uses the ollama Python library via stream_function_call().
    Falls back to cmd_chat on any error.
    """
    raw = stream_function_call(user_input, TOOL_DEFINITIONS, model=AI_MODEL)

    try:
        if raw.startswith("```"):
            raw = "\n".join(
                l for l in raw.splitlines()
                if not l.strip().startswith("```")
            ).strip()

        parsed = json.loads(raw)

        if "function" not in parsed:
            raise ValueError("No 'function' key in response")
        if parsed["function"] not in FUNCTION_REGISTRY:
            raise ValueError(f"Unknown function: {parsed['function']}")

        return parsed

    except json.JSONDecodeError as e:
        print(f"[AI] JSON parse error: {e} — falling back to chat")
        return {"function": "cmd_chat", "args": {"message": user_input}}
    except Exception as e:
        print(f"[AI] Error: {e} — falling back to chat")
        return {"function": "cmd_chat", "args": {"message": user_input}}


def warm_up_model():
    """
    Run one throwaway routing request at startup. This loads Qwen into
    VRAM (it then stays loaded — see KEEP_ALIVE in streaming_control)
    so your first real command doesn't wait for the model to load.
    """
    start = time.time()
    try:
        stream_function_call("what time is it", TOOL_DEFINITIONS, model=AI_MODEL)
        print(f"[AI] Model warmed up in {time.time() - start:.1f}s")
    except Exception as e:
        print(f"[AI] Warm-up failed (Orion will still work): {e}")


# ──────────────────────────────────────────────────────────
# DISPATCHER
# ──────────────────────────────────────────────────────────
def dispatch(user_input: str):
    """Route a spoken command through AI function-calling and execute it."""
    print(f"[Dispatch] Input: {user_input!r}")
    ui_set_status("understanding")

    # If routing + the command take a moment, Orion says "One moment, sir."
    # Quick commands speak before the delay, which cancels it automatically.
    presence.schedule_ack()
    try:
        _run_dispatch(user_input)
    finally:
        presence.cancel_ack()   # silent commands (pause, volume) never get an ack


def _run_dispatch(user_input: str):
    # Simple, unambiguous phrases skip Qwen entirely (see fast_path.py)
    call = match_fast_path(user_input)
    if call:
        print("[Dispatch] Fast path")
    else:
        call = _ollama_function_call(user_input)
    fn_name = call.get("function", "cmd_chat")
    args    = call.get("args", {})

    # The router sometimes writes its OWN answer into the chat message
    # instead of passing on what you said — so the chat model ends up
    # replying to Qwen's guess, not to you. Always send your exact words.
    if fn_name == "cmd_chat":
        args = {"message": user_input}

    print(f"[Dispatch] -> {fn_name}({args})")

    fn = FUNCTION_REGISTRY.get(fn_name, cmd_chat)
    try:
        fn(**args) if args else fn()
    except TypeError as e:
        print(f"[Dispatch] Argument error for {fn_name}: {e}")
        cmd_chat(user_input)
    except Exception as e:
        print(f"[Dispatch] Unexpected error in {fn_name}: {e}")
        presence.play_sound("error")
        msg = "I ran into an issue with that, sir. Please try again."
        ui_show_transcript(msg)
        speak(msg)


# ──────────────────────────────────────────────────────────
# MAIN ASSISTANT LOOP
# ──────────────────────────────────────────────────────────
def assistant_logic():
    # Load Qwen into VRAM in the background so the first command is fast
    Thread(target=warm_up_model, daemon=True).start()

    # Give pywebview time to finish loading the HTML/JS — and use that
    # quiet moment to calibrate the mic (before Orion starts talking,
    # or it would measure his own voice as background noise).
    start = time.time()
    calibrate_mic()
    time.sleep(max(0.0, 2.5 - (time.time() - start)))

    # Initialise modules that need callbacks
    pygame.mixer.init()
    presence.init(_tts_loop)
    init_streaming(speak, ui_show_transcript)
    init_timers(speak, ui_show_transcript, ui_update_timers,
                alert_fn=lambda: presence.play_sound("timer", wait=True))

    presence.play_sound("startup")
    speak("Activating Orion Mark 2.")
    ui_show_transcript("Orion MK2 online and ready, sir.")
    greetMe(speak)
    ui_set_status("idle")

    # Push persisted todo data now the window is ready
    ui_update_todo(get_tasks_for_ui())

    while True:
        try:
            # ── SLEEP MODE ──────────────────────────────
            if not awake.is_set():
                if listen_for_wake():
                    presence.play_chime()
                    cmd_wake_up()
                continue

            # ── ACTIVE MODE ─────────────────────────────
            query = take_command().lower()

            if query == "none" or not query.strip():
                ui_set_status("idle")
                continue

            # Handle sleep/wake instantly without going to the AI
            if any(k in query for k in ["go to sleep", "sleep now", "goodnight orion", "standby"]):
                cmd_sleep()
                continue
            if any(k in query for k in ["wake up", "are you there", "hey orion"]):
                presence.play_chime()
                cmd_wake_up()
                continue

            presence.play_sound("got_it")
            dispatch(query)
            # dispatch may have sent Orion to sleep — don't overwrite that
            ui_set_status("idle" if awake.is_set() else "sleeping")

        except Exception as e:
            print(f"[Loop] Unhandled error: {e}")
            ui_set_status("error")
            time.sleep(1)
            ui_set_status("idle")


# ──────────────────────────────────────────────────────────
# ENTRY POINT
# ──────────────────────────────────────────────────────────
def main():
    global window

    html_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "orion_ui.html")
    if not os.path.exists(html_path):
        raise FileNotFoundError(
            f"orion_ui.html not found at {html_path}\n"
            "Make sure orion_ui.html is in the same directory as main.py."
        )

    window = webview.create_window(
        title            = "ORION MK2",
        url              = html_path,
        fullscreen       = True,
        background_color = "#050a0f",
        min_size         = (1024, 600),
    )

    Thread(target=assistant_logic, daemon=True).start()
    Thread(target=_stats_loop,     daemon=True).start()

    webview.start(debug=False)


if __name__ == "__main__":
    main()