import speech_recognition as sr
import time
import sounddevice as sd
import numpy as np
import pyautogui
import webbrowser
import psutil
import os
from datetime import datetime
from GreetMe import greetMe
from Get_News import get_news
from volume_control import set_volume
from brightness_control import set_brightness
from system_control import shutdown, restart
from application_control import open_application, close_application
from SearchNow import searchGoogle, searchYoutube, searchWikipedia
import tkinter as tk
from threading import Thread
import inspect
import asyncio
import edge_tts
import pygame
import os
from datetime import datetime
import subprocess
import json

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


def takeCommand(ui):
    """Listen to a command and return the text"""
    r = sr.Recognizer()
    with sr.Microphone() as source:
        r.adjust_for_ambient_noise(source)
        print("Listening...")
        ui.update_status('listening')  # Update status to 'listening'
        r.pause_threshold = 1
        r.energy_threshold = 300
        # Wait up to 5 seconds for the user to start speaking (timeout)
        # Once speech starts, do not limit the phrase duration so the recognizer
        # listens until it detects the user has finished speaking (end-of-speech)
        try:
            audio = r.listen(source, timeout=5, phrase_time_limit=None)
        except sr.WaitTimeoutError:
            # No speech was detected within the timeout window
            return "None"

    try:
        print("Understanding")
        ui.update_status('understanding')  # Update status to 'understanding'
        query = r.recognize_google(audio, language='en-GB')
    except sr.UnknownValueError:
        # Speech was unintelligible
        print("Could not understand audio")
        ui.update_status('error')
        return "None"
    except sr.RequestError as e:
        # API was unreachable or unresponsive
        print(f"Could not request results; {e}")
        ui.update_status(f"error: {e}")
        return "None"
    except Exception as e:
        # Generic fallback
        print(e)
        ui.update_status(f"error: {e}")  # Update status to 'error'
        return "None"
    return query



number_words = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4,
    "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
    "ten": 10, "twenty": 20, "thirty": 30, "forty": 40,
    "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80,
    "ninety": 90, "hundred": 100
}

def parse_volume_level(query):
    """Extract volume level from a command string"""
    words = query.split()
    for word in words:
        if word.isdigit():
            return int(word)
        elif word in number_words:
            return number_words[word]
    return None

def parse_brightness_level(query):
    """Extract brightness level from a command string"""
    words = query.split()
    for word in words:
        if word.isdigit():
            return int(word)
        elif word in number_words:
            return number_words[word]
    return None
    
def get_system_stats():
    cpu_usage = psutil.cpu_percent(interval=1)
    memory_info = psutil.virtual_memory()
    battery = psutil.sensors_battery()

    # Check if the battery information is available
    if battery is not None:
        battery_status = f"{battery.percent}% remaining, {'Plugged in' if battery.power_plugged else 'Not plugged in'}"
    else:
        battery_status = "No battery info available (desktop or non-battery system)"

    return (
        f"CPU: {cpu_usage}%              |\n "
        f"Memory: {memory_info.percent}% |\n "
        f"Battery: {battery_status}      |"
    )

class ToDoList:
    def __init__(self, parent):
        self.parent = parent
        self.file_path = 'todo_list.txt'
        self.frame = tk.Frame(parent, bg='black')
        self.frame.place(relx=0.01, rely=0.01, anchor='nw', width=300, height=300)

        self.listbox = tk.Listbox(self.frame, bg='black', fg='lightblue', font=('Helvetica', 10))
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.entry = tk.Entry(self.frame, bg='black', fg='lightblue', font=('Helvetica', 10))
        self.entry.pack(side=tk.BOTTOM, fill=tk.X, padx=5, pady=5)

        self.add_button = tk.Button(self.frame, text='Add Task', command=self.add_task, bg='blue', fg='lightblue', font=('Helvetica', 10), width = 15, height =1)
        self.add_button.pack(side=tk.BOTTOM, padx=5, pady= 5)

        self.remove_button = tk.Button(self.frame, text='Remove Task', command=self.remove_task, bg='coral1', fg='blue', font=('Helvetica', 10), width = 15, height =1)
        self.remove_button.pack(side=tk.BOTTOM, padx=5, pady=5)

        #load existing tasks
        self.load_tasks()

    def add_task(self):
        task = self.entry.get()
        if task:
            self.listbox.insert(tk.END, task)
            self.entry.delete(0, tk.END)
            self.save_tasks()  # Save the updated list to the file


    def remove_task(self):
        try:
            selected_index = self.listbox.curselection()[0]  # Get the index of the selected item
            self.listbox.delete(selected_index)  # Remove the item from the Listbox
            self.save_tasks()  # Save the updated list to the file
        except IndexError:
            speak("Sir, you did not select a task for me to remove. Would you like to try that again sir?")

    def save_tasks(self):
        try:
            with open(self.file_path, 'w') as file:
                for task in self.listbox.get(0, tk.END):
                    file.write(task + '\n')
        except Exception as e:
            print(f"An error occurred while saving tasks: {e}")


    def load_tasks(self):
        """Load the tasks from a file"""
        if os.path.exists(self.file_path):
            with open(self.file_path, 'r') as file:
                tasks = file.readlines()
                for task in tasks:
                    self.listbox.insert(tk.END, task.strip())


class SystemInfo:
    def __init__(self, parent):
        self.parent = parent
        self.frame = tk.Frame(parent, bg='black')
        
        # Remove fixed width and height, let it auto-size
        self.frame.place(relx=0.01, rely=0.9, anchor='sw')

        # Add padding to the label for better appearance
        self.info_label = tk.Label(self.frame, bg='black', fg='lightblue', 
                                 font=('Helvetica', 10), anchor='w', 
                                 justify='left', padx=5, pady=5)
        self.info_label.pack()

        self.update_info()

    def update_info(self):
        """Update system information"""
        battery = psutil.sensors_battery()
        cpu_usage = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        battery_status = f"{battery.percent}% remaining" if battery else "No battery info available"
        memory_usage = f"{memory.percent}% used"

        # Adjust the formatting to be more compact
        info = (f"CPU Usage: {cpu_usage}%\n"
               f"Memory Usage: {memory_usage}\n"
               f"Battery: {battery_status}")
        self.info_label.config(text=info)
        self.parent.after(10000, self.update_info)

class VoiceAssistantUI:
    """UI class for the voice assistant"""
    def __init__(self, root):
        self.root = root
        self.root.title("ORION MK1")
        self.root.configure(bg='black')

        self.canvas = tk.Canvas(root, bg='black')
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # Define circle position and size relative to window size
        self.circle = self.canvas.create_oval(0, 0, 100, 100, outline='blue', width=5)



        # Create a Text widget inside the circle
        self.text_box = tk.Text(root, wrap=tk.WORD, bg='black', fg='lightblue', font=('Helvetica', 12), bd=0, relief=tk.FLAT)
        
        # Create status text widget
        self.status_text = self.canvas.create_text(0, 0, text="Idle", fill='lightblue', font=('Helvetica', 12))

        # Initialize To-Do List widget
        self.todo_list = ToDoList(root)

        #initialise system info widget
        self.system_info = SystemInfo(root)

        # Initialize system monitoring widget
        self.system_monitor = tk.Label(root, bg='black', fg='lightblue', font=('Helvetica', 10), anchor='sw', justify='left')

        # Initial layout update
        self.update_layout()

    def update_status(self, status):
        """Update the status text and circle color"""
        self.canvas.itemconfig(self.status_text, text=status.capitalize())
        if status == 'listening':
            self.canvas.itemconfig(self.circle, outline='blue')
        elif status == 'understanding':
            self.canvas.itemconfig(self.circle, outline='red')
        else:
            self.canvas.itemconfig(self.circle, outline='lightblue')

    def update_text(self, text):
        """Update the text box with command outputs"""
        self.text_box.delete(1.0, tk.END)
        self.text_box.insert(tk.END, text)

    def update_system_monitor(self, stats):
        """Update the system monitoring widget"""
        self.system_monitor.config(text=stats)

    def update_layout(self):
        """Update widget positions and sizes"""
        # Get window size
        width = self.root.winfo_width()
        height = self.root.winfo_height()

        # Update circle size and position
        circle_size = min(width, height) * 0.8
        self.canvas.coords(self.circle, 
                           (width - circle_size) / 2, 
                           (height - circle_size) / 2, 
                           (width + circle_size) / 2, 
                           (height + circle_size) / 2)

        # Update text box position and size
        self.text_box.place(relx=0.5, rely=0.5, anchor='center', height=int(height * 0.39), width=int(width * 0.39))

        # Update status text position
        self.canvas.coords(self.status_text, width / 2, height - 30)

        # Update system monitor position
        self.system_monitor.place(x=10, y=height - 150)

def toggle_fullscreen(event=None):
    """Toggle between full screen and windowed mode."""
    current_state = root.attributes("-fullscreen")
    root.attributes("-fullscreen", not current_state)

def time_function(ui):
    current_time = datetime.now().strftime("%I:%M %p")
    ui.update_text(f"The time is {current_time}")
    speak(f"The time is {current_time}")

def date_function(ui):
    current_date = datetime.now().strftime("%B %d, %Y")
    ui.update_text(f"Today is {current_date}")
    speak(f"Today is {current_date}")

def weather_function(ui):
    webbrowser.open("https://www.bbc.co.uk/weather")
    ui.update_text("Opening weather forecast")
    speak("Opening weather forecast")

def volume_function(ui, query):
    """Set system volume from a spoken query like 'set volume to 50'."""
    volume_level = parse_volume_level(query)
    if volume_level is not None:
        # set_volume expects a 0.0-1.0 float
        set_volume(max(0.0, min(1.0, volume_level / 100)))
        ui.update_text(f"Volume level set to {volume_level} percent")
        speak(f"Volume level set to {volume_level} percent")
    else:
        ui.update_text("Sorry, I couldn't understand the volume level.")
        speak("Sorry, I couldn't understand the volume level.")

def brightness_function(ui, query):
    """Set screen brightness from a spoken query like 'set brightness to 70'."""
    brightness_level = parse_brightness_level(query)
    if brightness_level is not None:
        # clamp to 0-100
        brightness_level = max(0, min(100, brightness_level))
        set_brightness(brightness_level)
        ui.update_text(f"Brightness level set to {brightness_level} percent")
        speak(f"Brightness level set to {brightness_level} percent")
    else:
        ui.update_text("Sorry, I couldn't understand the brightness level.")
        speak("Sorry, I couldn't understand the brightness level.")

def app_opening(ui, query):
    app_name = query.replace("open", "").strip()
    ui.update_text(f"Opening application: {app_name}")
    open_application(app_name)
    speak(f"Opening application: {app_name}")

def app_closing(ui, query):
    app_name = query.replace("close", "").strip()
    close_application(app_name)
    ui.update_text(f"Closing application: {app_name}")
    speak(f"Closing application: {app_name}")
    
def screenshot_function(ui):
    # Create screenshots directory if it doesn't exist
    screenshots_dir = os.path.join(os.path.dirname(__file__), "screenshots")
    if not os.path.exists(screenshots_dir):
        os.makedirs(screenshots_dir)
    
    current_time = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    screenshot = pyautogui.screenshot()
    screenshot_path = os.path.join(screenshots_dir, f"screenshot_{current_time}.png")
    screenshot.save(screenshot_path)
    speak("Screenshot taken and saved in screenshots folder.")
    ui.update_text("Screenshot taken and saved in screenshots folder.")

def daily_text_function(ui):
    text = "https://wol.jw.org/en/wol/h/r1/lp-e"
    webbrowser.open(text)
    ui.update_text("Opened daily text.")
    speak("Opened daily text.")

def news_function(ui):
    speak("Here is the latest news sir.")
    news_items = get_news()
    # Convert news items to a formatted string
    news_text = "\n".join(str(item) for item in news_items)
    print(news_text)
    ui.update_text(news_text)
    speak(news_text)

def play_music_function(ui):
    ui.update_text("Playing music on Spotify")
    open_application("Spotify")
    time.sleep(3)
    pyautogui.hotkey('space')
    pyautogui.hotkey('alt', 'tab')

def pause_music_function(ui):
    ui.update_text("Pausing music on Spotify")
    open_application("Spotify")
    time.sleep(2)
    pyautogui.hotkey('space')
    pyautogui.hotkey('alt', 'tab')

def skip_song_function(ui):
    ui.update_text("Skipping song on Spotify")
    open_application("Spotify")
    time.sleep(2)
    pyautogui.hotkey('ctrl', 'right')
    pyautogui.hotkey('alt', 'tab')

def previous_song_function(ui):
    ui.update_text("Playing previous song on Spotify")
    open_application("Spotify")
    time.sleep(2)
    pyautogui.hotkey('ctrl', 'left')
    time.sleep(0.5)
    pyautogui.hotkey('ctrl', 'left')
    pyautogui.hotkey('alt', 'tab')

def restart_song_function(ui):
    ui.update_text("Restarting song on Spotify")
    open_application("Spotify")
    time.sleep(2)
    pyautogui.hotkey('ctrl', 'left')
    pyautogui.hotkey('alt', 'tab')
    
def system_stats_function(ui):
    system_stats = get_system_stats()
    ui.update_text(system_stats)
    speak(system_stats)

def flip_coin_function(ui):
    import random
    coinop = ["Heads", "Tails"]
    coin = random.choice(coinop)
    ui.update_text(coin)
    speak(f"Sir, I got {coin}.")

def shutdown_function(ui):
    speak("Shutting down in 10 seconds")
    ui.update_text("Shutting down in 10 seconds")
    time.sleep(10)
    speak("Shutting down. It was a pleasure to work with you, sir.")
    ui.update_text("Shutting down. It was a pleasure to work with you, sir.")
    shutdown()

def restart_function(ui):
    speak("Restarting the system.")
    ui.update_text("Restarting the system.")
    restart()

def display_windows(ui):
    speak("Displaying the windows now, sir.")
    ui.update_text("Displaying the windows now, sir.")
    pyautogui.hotkey('win', 'tab')

def go_to_sleep(ui):
    global awake
    ui.update_text("Alright sir, I will be available anytime")
    speak("Alright sir, I will be available anytime")
    awake = False

def wake_up(ui):
    global awake
    greetMe(speak)
    awake = True
    ui.update_status('listening')

def listen_for_wake(ui):
    """Lightweight listener used while Orion is asleep to detect wake words.

    Returns True if a wake word was detected, False otherwise.
    This uses a short timeout so it doesn't block for long when asleep.
    """
    r = sr.Recognizer()
    try:
        with sr.Microphone() as source:
            # Short ambient calibration for sleep mode
            r.adjust_for_ambient_noise(source, duration=0.5)
            print("Sleep-mode: listening for wake word...")
            ui.update_status('sleeping')
            # Wait briefly for speech to start; once started, listen up to a few seconds
            try:
                audio = r.listen(source, timeout=3, phrase_time_limit=4)
            except sr.WaitTimeoutError:
                return False
    except Exception as e:
        # Microphone not available or other I/O error; don't wake
        print(f"Sleep-mode listener error: {e}")
        return False

    try:
        query = r.recognize_google(audio, language='en-GB').lower()
        print(f"[SLEEP] Heard: {query}")
    except Exception:
        return False

    # Define wake keywords (can be extended)
    wake_keywords = ['wake up', 'are you there', 'hey orion', 'orion']
    return any(k in query for k in wake_keywords)

def search_google(ui, query):
    searchGoogle(query, ui, )

def search_youtube(ui, query):
    searchYoutube(query, ui)

def search_wikipedia(ui, query):
    searchWikipedia(query, ui)

def get_phi3_response(prompt: str, model: str = "O.R.I.O.N") -> str:
    """
    Sends a prompt to O.R.I.O.N model via Ollama and returns plain text output.
    """
    try:
        result = subprocess.run(
            ["ollama", "run", model, prompt],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60
        )

        if result.returncode != 0:
            return f"[O.R.I.O.N error: {result.stderr.strip()}]"

        return result.stdout.strip() or "[O.R.I.O.N gave no response.]"

    except Exception as e:
        return f"[Error communicating with O.R.I.O.N: {e}]"

def orion_ai_function(ui, query: str):
    # Remove the keyword 'orion' from the query
    # signature changed to accept (ui, query) so dispatcher passes both
    clean_query = query.lower().replace("orion", "").strip()
    if not clean_query:
        clean_query = "Hello, how can I help you?"

    response = get_phi3_response(clean_query)

    # Speak or print it in your UI
    try:
        speak(response)
    except Exception:
        print("[O.R.I.O.N]:", response)



# Each entry: (list of keywords, function)
command_patterns = [
    (["what time is it", "time"], time_function),
    (["what is the date", "date"], date_function),
    (["what is the weather", "weather"], weather_function),
    (["set volume to", "volume"], volume_function),
    (["set brightness to", "brightness"], brightness_function),
    (["open"], app_opening),
    (["close"], app_closing),
    (["take a screenshot", "screenshot this"], screenshot_function),
    (["open daily text", "daily text"], daily_text_function),
    (["latest news", "show me the news"], news_function),
    (["play music", "play song"], play_music_function),
    (["pause music", "pause song"], pause_music_function),
    (["skip song", "next song"], skip_song_function),
    (["previous song", "last song"], previous_song_function),
    (["restart song"], restart_song_function),
    (["system stats", "system information"], system_stats_function),
    (["flip a coin", "toss a coin", "coin toss"], flip_coin_function),
    (["shutdown the system", "shut down"], shutdown_function),
    (["restart the system",], restart_function),
    (["display windows", "show windows"], display_windows),
    (["go to sleep", "sleep now"], go_to_sleep),
    (["wake up", "are you there"], wake_up),
    (["search google for","search"], search_google),
    (["search youtube for"], search_youtube),
    (["search wikipedia for"], search_wikipedia),
    (["orion", "ryan"], orion_ai_function),
]


def assistant_logic(ui):
    global awake 
    awake = True
    speak("Activating Orion Mark 2")
    speak("Orion is online and ready, sir.")
    greetMe()

    while True:
        if not awake:
            # While asleep, listen briefly for wake words without blocking forever
            try:
                if listen_for_wake(ui):
                    wake_up(ui)
                else:
                    # Sleep a short interval before listening again to avoid tight loop
                    time.sleep(0.5)
            except Exception as e:
                print(f"Error in sleep-mode listening: {e}")
                time.sleep(1)
            continue

        query = takeCommand(ui).lower()  # Pass `ui` to `takeCommand`
        print(f"[DEBUG] Heard: {query}")


        matched = False
        for keywords, function in command_patterns:
            if any(keyword in query for keyword in keywords):
                # Call the command with the right arguments depending on its signature
                try:
                    sig = inspect.signature(function)
                    param_count = len(sig.parameters)
                except Exception:
                    param_count = 0

                if param_count == 0:
                    function()
                elif param_count == 1:
                    # Most commands expect (ui,)
                    function(ui)
                else:
                    # Commands that need the query should accept (ui, query)
                    function(ui, query)

                matched = True
                break
        if not matched:
            continue

def main():
    global root
    root = tk.Tk()
    ui = VoiceAssistantUI(root)

    # Set the window to full screen
    root.attributes("-fullscreen", True)
    root.bind("<Escape>", lambda e: root.attributes("-fullscreen", False))  # Exit full screen with Escape key

    #bind del to make full screen
    root.bind("<Delete>", toggle_fullscreen)

    # Bind resize event
    root.bind("<Configure>", lambda event: ui.update_layout())

    # Run the assistant logic in a separate thread
    Thread(target=assistant_logic, args=(ui,)).start()

    root.mainloop()


if __name__ == "__main__":
    main()
