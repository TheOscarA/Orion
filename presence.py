"""
ORION MK2 — presence.py
────────────────────────────────────────────────────────────
Small touches that make Orion feel like he's always there.

  • play_sound()   — short generated sound cues:
                       startup   rising sweep into a chord, on boot
                       wake      two-note chime when woken up
                       got_it    soft tick when a command is heard
                       sleep     the wake chime in reverse
                       timer     rising arpeggio, twice, when a timer ends
                       error     two gentle falling notes when something fails
  • play_chime()   — shortcut for play_sound("wake").
  • schedule_ack() — if Orion is still thinking after a short
                     delay, he says a quick "One moment, sir."
                     in the same Edge TTS voice. Quick commands
                     finish before the delay, so they never
                     get an unnecessary acknowledgement.
  • cancel_ack()   — called by speak(): the moment Orion has
                     something real to say, the ack is skipped.

Sounds are generated as WAVs on first run and the
acknowledgements are generated once with Edge TTS. Both are
cached in ./sounds/ so later startups are instant.

Want your own sound instead? Put a WAV in ./sounds/custom/
with the cue's name (e.g. sounds/custom/wake.wav) and Orion
uses it in place of the generated one.
────────────────────────────────────────────────────────────
"""

import asyncio
import math
import os
import random
import struct
import time
import wave
from threading import Lock, Thread, Timer

import edge_tts
import pygame


SOUNDS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sounds")
CUSTOM_DIR = os.path.join(SOUNDS_DIR, "custom")

# Bump this whenever a sound recipe below changes, so cached copies
# from older versions are regenerated instead of reused.
SOUND_VERSION = 2

# Playback volume for each cue (0.0 – 1.0)
SOUND_VOLUMES = {
    "startup": 0.7,
    "wake":    0.6,
    "got_it":  0.5,
    "sleep":   0.55,
    "timer":   0.8,
    "error":   0.6,
}

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
_sounds      = {}      # name -> pygame.mixer.Sound
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
    global _tts_loop, _voice
    _tts_loop = tts_loop
    _voice    = voice

    os.makedirs(SOUNDS_DIR, exist_ok=True)
    _load_sounds()

    # Generate any missing acks in the background so startup isn't delayed.
    Thread(target=lambda: asyncio.run(_prepare_acks()), daemon=True).start()


# ──────────────────────────────────────────────────────────
# SOUND RECIPES — all generated in code, no audio files needed
# ──────────────────────────────────────────────────────────
_RATE = 44100
A5, CS6, E6, A6 = 880.0, 1108.7, 1318.5, 1760.0

def _tone(freq, dur, vol=0.25, decay=16, glide_to=None):
    """One soft bell-like note, optionally gliding in pitch."""
    n, out, phase = int(_RATE * dur), [], 0.0
    for i in range(n):
        t = i / _RATE
        f = freq if glide_to is None else freq + (glide_to - freq) * (t / dur)
        phase += 2 * math.pi * f / _RATE
        attack = min(1.0, i / (_RATE * 0.005))          # 5 ms fade-in, no click
        env = attack * math.exp(-t * decay)
        out.append(vol * env * (math.sin(phase) + 0.3 * math.sin(2 * phase)))
    return out

def _silence(dur):
    return [0.0] * int(_RATE * dur)

def _mix(*layers):
    n = max(len(l) for l in layers)
    return [sum(l[i] for l in layers if i < len(l)) for i in range(n)]

def _arpeggio():
    return _tone(A5, 0.13, 0.22, 10) + _tone(CS6, 0.13, 0.22, 10) + _tone(E6, 0.3, 0.22, 8)

SOUND_RECIPES = {
    "startup": lambda: _tone(220, 0.45, 0.12, 2, glide_to=880)
                       + _mix(_tone(A5, 0.9, 0.16, 5), _tone(CS6, 0.9, 0.12, 5), _tone(E6, 0.9, 0.12, 5)),
    "wake":    lambda: _tone(A5, 0.14, 0.25, 11) + _tone(E6, 0.42, 0.25, 7),
    "got_it":  lambda: _tone(A6, 0.12, 0.18, 30),
    "sleep":   lambda: _tone(E6, 0.16, 0.2, 12) + _tone(A5, 0.4, 0.18, 7),
    "timer":   lambda: _arpeggio() + _silence(0.25) + _arpeggio(),
    "error":   lambda: _tone(440.0, 0.14, 0.2, 14) + _tone(349.2, 0.32, 0.2, 9),
}

def _write_wav(path: str, samples: list[float]):
    tmp = path + ".part"
    with wave.open(tmp, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(_RATE)
        w.writeframes(b"".join(struct.pack("<h", int(max(-1.0, min(1.0, s)) * 32767))
                               for s in samples))
    os.replace(tmp, path)

def _load_sounds():
    """Use a custom WAV if present, otherwise generate (once) and cache."""
    for name, recipe in SOUND_RECIPES.items():
        custom = os.path.join(CUSTOM_DIR, f"{name}.wav")
        path   = custom if os.path.exists(custom) else os.path.join(SOUNDS_DIR, f"{name}_v{SOUND_VERSION}.wav")
        try:
            if not os.path.exists(path):
                _write_wav(path, recipe())
            snd = pygame.mixer.Sound(path)
            snd.set_volume(SOUND_VOLUMES.get(name, 0.6))
            _sounds[name] = snd
        except Exception as e:
            print(f"[Presence] Sound '{name}' unavailable: {e}")


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
# PLAYBACK
# ──────────────────────────────────────────────────────────
def play_sound(name: str, wait: bool = False):
    """
    Play a sound cue by name (see SOUND_RECIPES). Non-blocking unless
    wait=True, which returns once it has finished — use that when Orion
    is about to speak straight after, so the two don't overlap.
    """
    snd = _sounds.get(name)
    if not snd:
        return
    snd.play()
    if wait:
        time.sleep(snd.get_length())


def play_chime():
    """The wake chime."""
    play_sound("wake")


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