import webbrowser
import edge_tts
import speech_recognition
import pywhatkit
import wikipedia
import datetime
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
    
def takeCommand():
    r = speech_recognition.Recognizer()
    with speech_recognition.Microphone() as source:
        print("Listening...")
        r.pause_threshold = 1
        r.energy_threshold = 300
        audio = r.listen(source, 0, 4)
    try:
        print("Understanding")
        query = r.recognize_google(audio, language='en-GB')
        print(f"You said: {query}\n")
    except speech_recognition.UnknownValueError:
        speak("Say that again please...")
        return takeCommand()
    return query

def searchGoogle(query, ui):
    if "google" in query.lower():
        query = query.replace("orion", "")
        query = query.replace("search", "")
        query = query.replace("google", "")
        speak("Sir, this is what I found on Google")
        try:
            print(f"Searching for: {query}")
            pywhatkit.search(query)
            result = wikipedia.summary(query, sentences=2)
            print(f"Wikipedia result: {result}")
            ui.update_text(result)  # Update UI with search result
            speak(result)
        except wikipedia.exceptions.DisambiguationError as e:
            ui.update_text("There are multiple results for this query. Please be more specific, sir.")
            speak("There are multiple results for this query. Please be more specific, sir.")
        except wikipedia.exceptions.PageError:
            ui.update_text("Sorry, I couldn't find any results for that query.")
            speak("Sorry, I couldn't find any results for that query.")
        except Exception as e:
            ui.update_text("Sir, there are no results that I can directly tell you")
            speak("Sir, there are no results that I can directly tell you")
            print(f"Error: {e}")

def searchYoutube(query, ui):
    if "youtube" in query:
        speak("Sir, this is what I found for your search!")
        query = query.replace("youtube search", "")
        query = query.replace("youtube", "")
        query = query.replace("orion", "")
        try:
            print(f"Searching YouTube for: {query}")
            web = "https://www.youtube.com/results?search_query=" + query
            webbrowser.open(web)
            pywhatkit.playonyt(query)
            ui.update_text(f"Opened YouTube search for: {query}")  # Update UI with action
            speak("Sir, I'm done!")
        except Exception as e:
            ui.update_text("Sorry, I couldn't complete the YouTube search.")
            speak("Sorry, I couldn't complete the YouTube search.")
            print(f"Error: {e}")

def searchWikipedia(query, ui):
    if "wikipedia" in query:
        speak("Searching in Wikipedia.")
        query = query.replace("wikipedia", "")
        query = query.replace("search wikipedia", "")
        query = query.replace("orion", "")
        try:
            print(f"Searching Wikipedia for: {query}")
            results = wikipedia.summary(query, sentences=2)
            print(f"Wikipedia result: {results}")
            ui.update_text(f"According to Wikipedia: {results}")  # Update UI with results
            speak("According to Wikipedia...")
            speak(results)
            return results
        except wikipedia.exceptions.DisambiguationError as e:
            ui.update_text("There are multiple results for this query. Please be more specific, sir.")
            speak("There are multiple results for this query. Please be more specific, sir.")
        except wikipedia.exceptions.PageError:
            ui.update_text("Sorry, I couldn't find any results for that query.")
            speak("Sorry, I couldn't find any results for that query.")
        except Exception as e:
            ui.update_text("Sir, there are no results that I can directly tell you")
            speak("Sir, there are no results that I can directly tell you")
            print(f"Error: {e}")
