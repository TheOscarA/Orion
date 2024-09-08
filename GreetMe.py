import pyttsx3
import datetime

# Initialize the text-to-speech engine
engine = pyttsx3.init('sapi5')
voices = engine.getProperty("voices")
engine.setProperty("voice", voices[0].id)
engine.setProperty("rate", 170)

def speak(audio):
    engine.say(audio)
    engine.runAndWait()

def greetMe():
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
