"""
ORION MK2 — presence.py
────────────────────────────────────────────────────────────
Small touches that make Orion feel like he's always there.

  • play_chime()   — soft two-note chime, plays instantly when
                     the wake word is heard.
  • schedule_ack() — if Orion is still thinking after a short
                     delay, he says a quick "One moment, sir."
                     in the same Edge TTS voice. Quick commands
                     finish before the delay, so they never
                     get an unnecessary acknowledgement.
  • cancel_ack()   — called by speak(): the moment Orion has
                     something real to say, the ack is skipped.

The chime is generated as a WAV on first run and the
acknowledgements are generated once with Edge TTS. Both are
cached in ./sounds/ so later startups are instant.
────────────────────────────────────────────────────────────
"""

import asyncio
import math
import os
import random
import struct
import wave
from threading import Lock, Thread, Timer

import edge_tts
import pygame


SOUNDS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sounds")
CHIME_FILE = os.path.join(SOUNDS_DIR, "chime.wav")

# Edit freely — new phrases are generated automatically on next start.
ACK_PHRASES = [
    "One moment, sir.",
    "On it, sir.",
    "Right away.",
    "Give me a second.",
    "Let me check, sir.",
]

# How long Orion can stay silent before he acknowledges you (seconds).
ACK_DELAY = 0.7

_tts_loop    = None
_voice       = "en-GB-RyanNeural"
_chime_sound = None
_last_ack    = None
_ack_timer   = None
_ack_lock    = Lock()


# ──────────────────────────────────────────────────────────
# SETUP
# ──────────────────────────────────────────────────────────
def init(tts_loop, voice: str = "en-GB-RyanNeural"):
    """
    Call once after pygame.mixer.init().
    tts_loop: the persistent asyncio loop that speak() uses, so
    acks and speech play in order and never talk over each other.
    """
    global _tts_loop, _voice, _chime_sound
    _tts_loop = tts_loop
    _voice    = voice

    os.makedirs(SOUNDS_DIR, exist_ok=True)

    try:
        if not os.path.exists(CHIME_FILE):
            _make_chime(CHIME_FILE)
        _chime_sound = pygame.mixer.Sound(CHIME_FILE)
        _chime_sound.set_volume(0.6)
    except Exception as e:
        print(f"[Presence] Chime unavailable: {e}")

    # Generate any missing acks in the background so startup isn't delayed.
    Thread(target=lambda: asyncio.run(_prepare_acks()), daemon=True).start()


def _make_chime(path: str):
    """Write a soft two-note chime (A5 → E6) as a 16-bit mono WAV."""
    rate  = 44100
    notes = [(880.0, 0.09), (1318.5, 0.18)]
    frames = bytearray()
    for freq, dur in notes:
        n = int(rate * dur)
        for i in range(n):
            t      = i / rate
            attack = min(1.0, i / (rate * 0.005))     # 5 ms fade-in, no click
            env    = attack * math.exp(-t * 16)        # gentle decay
            s      = 0.25 * env * (math.sin(2 * math.pi * freq * t)
                                   + 0.3 * math.sin(4 * math.pi * freq * t))
            frames += struct.pack("<h", int(max(-1.0, min(1.0, s)) * 32767))
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(bytes(frames))


def _ack_path(phrase: str) -> str:
    slug = "".join(c for c in phrase.lower() if c.isalnum() or c == " ").strip().replace(" ", "_")
    return os.path.join(SOUNDS_DIR, f"ack_{_voice}_{slug}.mp3")


MIN_ACK_BYTES = 2000   # a real clip is ~10 KB+; anything smaller is broken


def _ack_ready(path: str) -> bool:
    return os.path.exists(path) and os.path.getsize(path) >= MIN_ACK_BYTES


async def _prepare_acks():
    for phrase in ACK_PHRASES:
        path = _ack_path(phrase)
        if _ack_ready(path):
            continue
        tmp = path + ".part"
        try:
            # Write to a temp file and only rename once it's complete, so a
            # failed or half-finished download never becomes a "real" clip.
            await edge_tts.Communicate(phrase, _voice).save(tmp)
            if os.path.getsize(tmp) < MIN_ACK_BYTES:
                raise ValueError("audio came back empty")
            os.replace(tmp, path)
            print(f"[Presence] Generated ack: {phrase!r}")
        except Exception as e:
            print(f"[Presence] Couldn't generate ack {phrase!r}: {e}")
            _remove_quietly(tmp)
            if not _ack_ready(path):
                _remove_quietly(path)     # clear out a broken clip from an older run


def _remove_quietly(path: str):
    try:
        if os.path.exists(path):
            os.remove(path)
    except OSError:
        pass


# ──────────────────────────────────────────────────────────
# CHIME
# ──────────────────────────────────────────────────────────
def play_chime():
    """Play the wake chime. Non-blocking; overlaps nothing important."""
    if _chime_sound:
        _chime_sound.play()


# ──────────────────────────────────────────────────────────
# ACKNOWLEDGEMENTS
# ──────────────────────────────────────────────────────────
def schedule_ack(delay: float = ACK_DELAY):
    """Say a short ack if Orion hasn't spoken within `delay` seconds."""
    global _ack_timer
    with _ack_lock:
        if _ack_timer:
            _ack_timer.cancel()
        _ack_timer = Timer(delay, _fire_ack)
        _ack_timer.daemon = True
        _ack_timer.start()


def cancel_ack():
    """Skip the pending ack — Orion is about to speak (or is done)."""
    global _ack_timer
    with _ack_lock:
        if _ack_timer:
            _ack_timer.cancel()
            _ack_timer = None


def _fire_ack():
    global _ack_timer
    with _ack_lock:
        if _ack_timer is None:      # cancelled at the last moment
            return
        _ack_timer = None
    if _tts_loop:
        asyncio.run_coroutine_threadsafe(_play_ack(), _tts_loop)


async def _play_ack():
    """Start an ack and return straight away; speak() waits for it to end."""
    global _last_ack
    ready = [p for p in ACK_PHRASES if _ack_ready(_ack_path(p))]
    if not ready or pygame.mixer.music.get_busy():
        return
    choices   = [p for p in ready if p != _last_ack] or ready
    phrase    = random.choice(choices)
    _last_ack = phrase
    path      = _ack_path(phrase)
    try:
        pygame.mixer.music.load(path)
        pygame.mixer.music.play()
    except Exception as e:
        print(f"[Presence] Ack {phrase!r} is broken, removing it ({e})")
        try:
            pygame.mixer.music.unload()
        except Exception:
            pass
        _remove_quietly(path)          # regenerated cleanly on next start