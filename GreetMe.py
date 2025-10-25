import datetime
import edge_tts
import pygame
import asyncio
import os

# Internal async function
async def _speak_async(text, voice="en-GB-RyanNeural"):
    # Generate a unique filename using timestamp
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
    filename = f"temp_{timestamp}.mp3"

    # Generate TTS audio
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(filename)

    # Initialize pygame mixer and play
    pygame.mixer.init()
    pygame.mixer.music.load(filename)
    pygame.mixer.music.play()

    # Wait until audio finishes
    while pygame.mixer.music.get_busy():
        await asyncio.sleep(0.1)

    # Stop the mixer before removing file
    pygame.mixer.music.stop()
    pygame.mixer.quit()

    # Now it’s safe to remove
    os.remove(filename)

# Synchronous wrapper
def speak(text, voice="en-GB-RyanNeural"):
    asyncio.run(_speak_async(text, voice))
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
