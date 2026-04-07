# Orion MK1 — Local Voice Assistant

Orion MK1 is a Python-based local voice assistant for Windows. It combines speech recognition, text-to-speech, and desktop automation to run spoken commands and respond through a simple GUI.

## Features

- Local voice assistant with microphone input
- Natural voice output using `edge_tts`
- Speech recognition via `SpeechRecognition` (Google Web Speech API by default)
- Built-in commands for search, media control, timers, notes, and system actions
- Modular command handlers for easier extension

## Requirements

- Python 3.13 only — `pygame` and other libraries is not supported on Python 3.14
- Windows 10 / 11
- A working microphone and internet connection for default speech recognition

## Setup

1. Create and activate a virtual environment:

```powershell
python -m venv .venv-1
& .\.venv-1\Scripts\Activate.ps1
```

2. Install the project dependencies:

```powershell
pip install -r requirements.txt
```

3. Start Orion:

```powershell
& .venv-1\Scripts\python.exe .\main.py
```

## How to use

- Speak a command when Orion is listening.
- Orion will announce that it is ready, then process your query.
- Use wake and sleep phrases to control the assistant state.

### Wake / sleep commands

- Sleep: `go to sleep`, `sleep now`
- Wake: `wake up`, `are you there`, `hey orion`, `orion`

## Project layout

- `main.py` — main application entry point, UI, speech engine, and command dispatcher
- `GreetMe.py` — greeting and startup voice helper
- `SearchNow.py` — web search helper utilities
- `requirements.txt` — Python dependencies
- `orion_ui.html` — optional UI markup for the assistant interface

## Troubleshooting

### Microphone issues

- Ensure your microphone is enabled and accessible to Python.
- If `speech_recognition` raises `WaitTimeoutError`, the app is waiting for speech and may need a longer timeout.
- Try running the script from the same shell where the virtual environment is activated.

### Text-to-speech issues on Windows

- `edge_tts` depends on the Microsoft Edge runtime.
- If speech audio does not play, verify Edge is installed and your default audio device is working.

### Wake-word detection

- Orion uses Google speech recognition for wake words by default.
- For offline wake-word support, consider integrating PocketSphinx or another dedicated offline wake-word engine.

## Development notes

- Command modules should accept a shared `speak` callable instead of creating their own TTS engine.
- The dispatcher inspects function signatures to call commands with the correct parameters.
- Add new command modules by following the existing structure in `main.py` and supporting files.

---

Created by TheOscarA

