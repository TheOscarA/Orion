# Orion MK1 — Local Voice Assistant

This repository contains Orion MK1, a local voice assistant built with Python.

It uses:
- edge_tts for very natural sounding voices
- SpeechRecognition for microphone input (Google Web Speech API by default)
- pywhatkit, wikipedia, pyautogui, psutil and other helper libraries

This README covers quick setup, running, and common troubleshooting steps (especially TTS issues on Windows).

## Quick start

1. Create and activate a Python virtual environment (recommended):

```powershell
python -m venv .venv-1
& .\.venv-1\Scripts\Activate.ps1
```

2. Install dependencies:

```powershell
pip install -r requirements.txt
```

3. Run Orion:

```powershell
& .venv-1\Scripts\python.exe .\main.py
```

On first run the GUI will open. Orion will announce startup greetings and then listen for commands.

## Basic usage
- Speak a command when Orion is in the listening state.
- Wake/sleep commands:
  - "go to sleep" or "sleep now" — Orion sleeps but listens for wake words.
  - "wake up", "are you there", "hey orion", or simply "orion" — wake words supported while asleep.

## File overview
- `main.py` — main program, UI, command dispatcher, and TTS engine initialization.
- `GreetMe.py` — greeting helper (now reuses main speak function when called with `greetMe(speak)`).
- `SearchNow.py` — web search helpers (now accept a `speak` callable from `main.py`).
- `requirements.txt` — Python package dependencies.

## Common issues & troubleshooting


1. Microphone or recognizer errors

	- Make sure your default microphone is enabled and accessible to Python.
	- If `speech_recognition` raises `WaitTimeoutError`, the app waits for a speech start for up to 5 seconds (configurable in `takeCommand`). Increase `timeout` if needed.

2. Offline wake-word detection

	- The current implementation uses Google speech recognition for wake detection. For offline, lower-latency wake-word detection, consider PocketSphinx or a dedicated wakeword engine.

## Development notes

- Command dispatcher: The app inspects function signatures to call command functions with the correct `(ui)` or `(ui, query)` arguments.
- If you add new modules that speak, make them accept a `speak` callable rather than creating their own pyttsx3 engine.


Created by TheOscarA

