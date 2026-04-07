import datetime


def _make_local_speak():
    """Create a temporary pyttsx3 engine and return a speak function that uses it.

    We create a local engine only when no external speak function is provided so
    the main program can reuse its own engine and avoid conflicts.
    """
    try:
        import pyttsx3
    except Exception:
        # If pyttsx3 is unavailable, fall back to a no-op speak to avoid crashes
        def _noop(msg):
            print(f"TTS unavailable: {msg}")

        return _noop

    engine = pyttsx3.init('sapi5')
    voices = engine.getProperty("voices")
    if voices:
        engine.setProperty("voice", voices[0].id)
    engine.setProperty("rate", 170)

    def _local_speak(audio):
        engine.say(audio)
        engine.runAndWait()

    return _local_speak


def greetMe(speak_fn=None):
    """Greet based on the current time.

    If speak_fn is provided, use it for TTS; otherwise create a temporary engine.
    """
    if speak_fn is None:
        speak = _make_local_speak()
    else:
        speak = speak_fn

    hour = int(datetime.datetime.now().hour)
    if hour >= 0 and hour < 12:
        speak("Good morning sir")
    elif hour >= 12 and hour < 18:
        speak("Good afternoon sir")
    elif hour >= 18 and hour < 24:
        speak("Good evening sir")
    else:
        speak("Good night sir")

    current_time = datetime.datetime.now()
    hour = current_time.hour
    minute = current_time.minute
    speak(f"The time is currently {hour}:{minute:02d}")
    speak("Orion at your service. How can I help you?")
