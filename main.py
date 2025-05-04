import pyttsx3
import speech_recognition as sr
import time
import sounddevice as sd
import numpy as np
import pyautogui
import webbrowser
import wolframalpha
import psutil
import os
import sys
import random
import subprocess
import json
import ollama
import threading
import queue
import re
import requests
import pyperclip
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
from win10toast import ToastNotifier
from pushbullet import Pushbullet


# Initialize the text-to-speech engine
engine = pyttsx3.init('sapi5')
voices = engine.getProperty("voices")
engine.setProperty("voice", voices[0].id)
engine.setProperty("rate", 170)
engine.setProperty("volume", 1.0)  # Set volume to maximum

api_key = 'Your API key'
pb = Pushbullet(api_key)

speak_queue = queue.Queue()

def speak_worker():
    while True:
        text = speak_queue.get()
        if text is None:
            break
        engine.say(text)
        engine.runAndWait()
        speak_queue.task_done()

# Start the speaking thread when program starts
speaking_thread = Thread(target=speak_worker, daemon=True)
speaking_thread.start()

def speak(audio):
    """Non-blocking text-to-speech function"""
    speak_queue.put(audio)

def takeCommand(ui):
    """Listen to a command and return the text"""
    r = sr.Recognizer()
    with sr.Microphone() as source:
        r.adjust_for_ambient_noise(source)
        print("Listening...")
        ui.update_status('listening')  # Update status to 'listening'
        r.pause_threshold = 1
        r.energy_threshold = 300
        audio = r.listen(source, timeout=None)

    try:
        print("Understanding")
        ui.update_status('understanding')  # Update status to 'understanding'
        query = r.recognize_google(audio, language='en-GB')
        print(f"You said: {query}\n")
    except Exception as e:
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

def detect_clap(threshold=0.5, duration=0.1, clap_count=2):
    """Detect double clap sound to activate Orion"""
    clap_times = []

    def callback(indata, frames, time, status):
        volume_norm = np.linalg.norm(indata) * 10
        if volume_norm > threshold:
            clap_times.append(time.inputBufferAdcTime)
            if len(clap_times) > clap_count:
                clap_times.pop(0)
            if len(clap_times) == clap_count and (clap_times[-1] - clap_times[0]) < 1:
                print("Double clap detected!")
                return True
        return False

    with sd.InputStream(callback=callback):
        sd.sleep(int(duration * 1000))


def ask_phi3(user_input, ui):
    """Stream response from O.R.I.O.N and speak in chunks"""
    try:
        response = ollama.chat(
            model='Orion:latest',
            messages=[{'role': 'user', 'content': user_input}],
            stream=True
        )
        
        full_text = ""
        buffer = ""
        
        for chunk in response:
            if not chunk or 'message' not in chunk:
                continue
                
            text = chunk['message'].get('content', '')
            buffer += text
            full_text += text
            
            # Update UI with accumulated text
            ui.update_text(full_text)
            ui.root.update_idletasks()
            
            # Speak complete sentences
            if any(p in buffer for p in ['.', '!', '?']):
                sentences = re.split(r'([.!?])', buffer)
                buffer = ""
                
                for i in range(0, len(sentences)-1, 2):
                    sentence = sentences[i] + (sentences[i+1] if i+1 < len(sentences) else '')
                    if sentence.strip():
                        speak(sentence.strip())
        
        # Speak any remaining text
        if buffer.strip():
            speak(buffer.strip())
            
        return full_text
        
    except Exception as e:
        error_msg = f"Sorry, I encountered an error: {str(e)}"
        speak(error_msg)
        return error_msg

def get_active_url():
    """Copies the URL from the current active browser window."""
    pyautogui.hotkey('ctrl', 'l')  # Focus address bar
    time.sleep(0.1)
    pyautogui.hotkey('ctrl', 'c')  # Copy
    time.sleep(0.1)
    url = pyperclip.paste()
    return url

def summarize_url(url):
    """Sends the URL to Phi4-Mini and streams back a spoken summary."""
    # Prompt sent to Phi4-mini
    prompt = f"Summarize the following webpage in a few sentences: {url}"
    
    # Ollama API endpoint
    api_url = "http://localhost:11434/api/chat"
    
    payload = {
        "model": "Orion",  # or whatever your model is named I modified Phi4-Mini
        "messages": [{"role": "user", "content": prompt}],
        "stream": True
    }

    # Start request
    try:
        with requests.post(api_url, json=payload, stream=True, timeout=60) as response:
            response.raise_for_status()

            buffer = ""
            for line in response.iter_lines():
                if line:
                    # Decode the streamed JSON
                    decoded_line = line.decode('utf-8')
                    if decoded_line.startswith("data: "):
                        content_piece = decoded_line[6:]
                        
                        if '"done":true' in content_piece:
                            break

                        try:
                            content_json = eval(content_piece)  # safe because Ollama format
                            chunk = content_json.get("message", {}).get("content", "")
                            buffer += chunk

                            # If buffer contains a complete sentence
                            while any(punct in buffer for punct in [".", "!", "?"]):
                                for punct in [".", "!", "?"]:
                                    if punct in buffer:
                                        sentence, buffer = buffer.split(punct, 1)
                                        full_sentence = (sentence + punct).strip()
                                        if full_sentence:
                                            print(f"[SPEAKING] {full_sentence}")
                                            speak(full_sentence)
                                        break
                        except Exception as e:
                            print(f"Error parsing chunk: {e}")

            # If anything is left over at the end
            if buffer.strip():
                print(f"[SPEAKING] {buffer.strip()}")
                speak(buffer.strip())

    except requests.exceptions.RequestException as e:
        print(f"Request error: {e}")
        speak("Sorry, I couldn't summarize the page.")


    
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

MEMORY_FILE = "memory.json"

def remember(key, value):
    # Load existing memory or create new
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, "r") as f:
            data = json.load(f)
    else:
        data = {}

    # Save new memory
    data[key.lower()] = value
    with open(MEMORY_FILE, "w") as f:
        json.dump(data, f, indent=4)

def recall(key):
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, "r") as f:
            data = json.load(f)
        key = key.lower()
        if key in data:
            return f"{key} is {data[key]}"
        else:
            return f"I don't remember anything about {key}."
    else:
        return "I don't have any memory stored yet."



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

class BatteryMonitor:
    def __init__(self):
        self.notifier = ToastNotifier()  # Initialize the notification system
        self.last_notification_time = 3
        self.notification_cooldown = 300  # 5 minutes in seconds

    def check_battery(self):
        battery = psutil.sensors_battery()
        current_time = time.time()
        
        if battery and battery.power_plugged and battery.percent >= 80:
            if current_time - self.last_notification_time > self.notification_cooldown:
                self.notifier.show_toast(  # Use the notifier to display a notification
                    "Battery Health",
                    "Battery is above 80%. Consider unplugging to extend battery life.",
                    duration=10,
                    threaded=True
                )
                pb.push_note("O.R.I.O.N", "Battery is above 80%. Consider unplugging to extend battery life.")
                speak("Sir, battery is above 80 percent. I recommend unplugging the charger to extend battery life.")
                self.last_notification_time = current_time

        elif battery and not battery.power_plugged and battery.percent <= 30:
            if current_time - self.last_notification_time > self.notification_cooldown:
                self.notifier.show_toast(  # Use the notifier to display a notification
                    "Battery Health",
                    "Battery is below 30%. Consider unplugging to extend battery life.",
                    duration=10,
                    threaded=True
                )
                pb.push_note("O.R.I.O.N", "Battery is below 30%. Consider plugging in the device")
                speak("Sir, battery is below 30 percent. I recommend plugging in the device.")
                self.last_notification_time = current_time


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
        self.battery_monitor = BatteryMonitor()


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
        self.battery_monitor.check_battery()
        self.parent.after(100, self.update_info) # updates system stats every second

class VoiceAssistantUI:
    """UI class for the voice assistant"""
    def __init__(self, root):
        self.root = root
        self.root.title("ORION MK1")
        self.root.configure(bg='black')
        self.running = True

        self.canvas = tk.Canvas(root, bg='black')
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # Frame to simulate a colored border around the input box
        self.input_frame = tk.Frame(root, bg='blue', bd=2)
        self.input_box = tk.Entry(self.input_frame, bg='black', fg='lightblue', 
                                insertbackground='lightblue', font=('Helvetica', 12),
                                bd=0, relief=tk.FLAT)
        self.input_box.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.input_box.pack(fill=tk.BOTH, expand=True)
        self.input_box.bind('<Return>', self.handle_input)

        # Create a Text widget inside the circle
        self.text_box = tk.Text(root, wrap=tk.WORD, bg='black', fg='lightblue', font=('Helvetica', 12), bd=0, relief=tk.FLAT)

        # Define circle position and size relative to window size
        self.circle = self.canvas.create_oval(0, 0, 100, 100, outline='blue', width=5)
        
        # Create status text widget
        self.status_text = self.canvas.create_text(0, 0, text="Idle", fill='lightblue', font=('Helvetica', 12))

        # Initialize To-Do List widget
        self.todo_list = ToDoList(root)

        #initialise system info widget
        self.system_info = SystemInfo(root)

        # Initialize system monitoring widget
        self.system_monitor = tk.Label(root, bg='black', fg='lightblue', font=('Helvetica', 10), anchor='sw', justify='left')

        self.keyboard_input = None  # Add this to __init__

        # Initial layout update
        self.update_layout()

    def cleanup(self):
        """Clean up resources before closing the UI"""
        self.running = False
        self.root.quit()

    def update_status(self, status):
        """Update the status text and circle color"""
        self.canvas.itemconfig(self.status_text, text=status.capitalize())
        if status == 'listening':
            color = 'blue'
        elif status == 'understanding':
            color = 'red'  
        else:
            color = 'lightblue'
            
        self.canvas.itemconfig(self.circle, outline=color)
        self.input_frame.configure(bg=color)  # Update input frame border color

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

        # Update its position and size based on current window size
        frame_height = 40  # Increased height for better text visibility
        self.input_frame.place(relx=0.5, rely=0.85, anchor='center', 
                             width=int(self.root.winfo_width() * 0.5), 
                             height=frame_height)

    def handle_input(self, event):
        """Handle keyboard input when user presses Enter"""
        query = self.input_box.get().strip().lower()
        self.input_box.delete(0, tk.END)
        if query:
            self.keyboard_input = query  # Store the keyboard input
            self.update_status("understanding")
            print(f"Keyboard input received: {query}")

def toggle_fullscreen(event=None):
    """Toggle between full screen and windowed mode."""
    current_state = root.attributes("-fullscreen")
    root.attributes("-fullscreen", not current_state)

def assistant_logic(ui):
    awake = False
    while ui.running:
        if awake:
            ui.update_status('listening')
            
            if ui.keyboard_input:  # Check for keyboard input first
                query = ui.keyboard_input
                ui.keyboard_input = None  # Clear the keyboard input after using it
            else:
                query = takeCommand(ui).lower()  # Fallback to voice input
                if query == "none":
                    continue
            
            # Process the query (rest of the command handling)
            if "go to sleep" in query:
                ui.update_text("Alright sir, I will be available anytime")
                speak("Alright sir, I will be available anytime")
                awake = False

            elif "hello" in query:
                ui.update_text("Hello sir, how are you?")
                speak("Hello sir, how are you?")
                
            elif "i am fine" in query:
                ui.update_text("Good to hear, sir")
                speak("Good to hear, sir")
                
            elif "how are you" in query:
                ui.update_text("No errors and fully functional, sir")
                speak("No errors and fully functional, sir")
                
            elif "thank you" in query:
                ui.update_text("My pleasure sir")
                speak("My pleasure sir")

            elif "what is your name" in query:
                ui.update_text("My name is Orion, sir")
                speak("My name is Orion, sir")

            elif "what can you do" in query:
                ui.update_text("I can do a lot of things sir. Just ask me")
                speak("I can do a lot of things sir. Just ask me")

            elif "what time is it" in query or "what's the time" in query or "tell me the time" in query or "what is the time" in query:
                current_time = datetime.now().strftime("%I:%M %p")
                ui.update_text(f"The time is {current_time}")
                speak(f"The time is {current_time}")

            elif "what day is it" in query:
                current_day = datetime.now().strftime("%A")
                ui.update_text(f"Today is {current_day}")
                speak(f"Today is {current_day}")

            elif "what is the date" in query:
                current_date = datetime.now().strftime("%B %d, %Y")
                ui.update_text(f"Today is {current_date}")
                speak(f"Today is {current_date}")

            elif "what is the weather" in query:
                webbrowser.open("https://www.bbc.co.uk/weather")
                ui.update_text("Opening weather forecast")
                speak("Opening weather forecast")
                
            elif "set volume" in query:
                volume_level = parse_volume_level(query)
                if volume_level is not None:
                    set_volume(volume_level / 100)
                    ui.update_text(f"Volume level set to {volume_level} percent")
                    speak(f"Volume level set to {volume_level} percent")
                    
                else:
                    ui.update_text("Sorry, I couldn't understand the volume level.")
                    speak("Sorry, I couldn't understand the volume level.")
                    
            elif "set brightness" in query:
                brightness_level = parse_brightness_level(query)
                if brightness_level is not None:
                    set_brightness(brightness_level)
                    ui.update_text(f"Brightness level set to {brightness_level} percent")
                    speak(f"Brightness level set to {brightness_level} percent")
                    
                else:
                    ui.update_text("Sorry, I couldn't understand the brightness level.")
                    speak("Sorry, I couldn't understand the brightness level.")

            elif "open" in query:
                app_name = query.replace("open", "")
                ui.update_text(f"Opening application: {app_name}")
                open_application(app_name)
                
            elif "close" in query:
                app_name = query.replace("close", "").strip()
                close_application(app_name)
                ui.update_text(f"Closing application: {app_name}")

            elif "google" in query:
                searchGoogle(query, ui)


            elif "youtube" in query:
                searchYoutube(query, ui)


            elif "wikipedia" in query:
                searchWikipedia(query, ui)

            elif "take a screenshot" in query:
                current_time = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                screenshot = pyautogui.screenshot()
                screenshot.save(f"screenshot_{current_time}.png")
                speak("Screenshot taken.")
                ui.update_text("Screenshot taken.")

            elif "daily text" in query:
                text = "https://wol.jw.org/en/wol/h/r1/lp-e"
                webbrowser.open(text)
                ui.update_text("Opened daily text.")

            elif "latest news" in query:
                speak("Here is the latest news sir.")
                print(*get_news(),sep="\n")
                ui.update_text(get_news())
                speak(get_news())

            elif "system status" in query:
                system_stats = get_system_stats()
                ui.update_text(system_stats)
                speak(system_stats)

            elif "play music" in query:
                ui.update_text("Playing music on Spotify")
                open_application("Spotify")
                time.sleep(3)
                pyautogui.hotkey('space')
                pyautogui.hotkey('alt', 'tab')

            elif "pause music" in query:
                ui.update_text("Pausing music on Spotify")
                open_application("Spotify")
                time.sleep(2)
                pyautogui.hotkey('space')
                pyautogui.hotkey('alt', 'tab')

            elif "skip song" in query or "next song" in query or "skip track" in query:
                ui.update_text("Skipping song on Spotify")
                open_application("Spotify")
                time.sleep(2)
                pyautogui.hotkey('ctrl', 'right')
                pyautogui.hotkey('alt', 'tab')

            elif "previous song" in query or "last song" in query:
                ui.update_text("Playing previous song on Spotify")
                open_application("Spotify")
                time.sleep(2)
                pyautogui.hotkey('ctrl', 'left')
                time.sleep(0.5)
                pyautogui.hotkey('ctrl', 'left')
                pyautogui.hotkey('alt', 'tab')

            elif "restart song" in query or "replay song" in query:
                ui.update_text("Restarting song on Spotify")
                open_application("Spotify")
                time.sleep(2)
                pyautogui.hotkey('ctrl', 'left')
                pyautogui.hotkey('alt', 'tab')

            elif "flip a coin" in query:
                coinop = ["Heads", "Tails"]
                coin = random.choice(coinop)
                ui.update_text(coin)
                speak("Sir, I got heads.")

            elif "roll a dice" in query:
                dice = random.randint(1, 6)
                ui.update_text(dice)
                speak(f"Sir, I got {dice}.")

            elif "shutdown" in query or "shut down" in query:
                speak("Shutting down in 10 seconds")
                ui.update_text("Shutting down in 10 seconds")
                time.sleep(10)
                speak("Shutting down. It was a pleasure to work with you, sir.")
                ui.update_text("Shutting down. It was a pleasure to work with you, sir.")
                shutdown()
                
            elif "restart" in query:
                speak("Restarting the system.")
                ui.update_text("Restarting the system.")
                restart()

            elif "my windows" in query:
                speak("Displaying the windows now, sir.")
                ui.update_text("Displaying the windows now, sir.")
                pyautogui.hotkey('win', 'tab')

            elif "show taskbar" in query:
                speak("Hiding the taskbar.")
                ui.update_text("Hiding the taskbar.")
                pyautogui.hotkey('win', 'b')

            elif "show start menu" in query:
                speak("Opening the start menu.")
                ui.update_text("Opening the start menu.")
                pyautogui.hotkey('win')

            elif "show action center" in query or "show notifications" in query:
                speak("Opening the action center.")
                ui.update_text("Opening the action center.")
                pyautogui.hotkey('win', 'a')

            elif "show desktop" in query:
                speak("Minimizing all windows to show desktop.")
                ui.update_text("Minimizing all windows to show desktop.")
                pyautogui.hotkey('win', 'd')

            elif "add desktop" in query:
                ui.update_text("Adding a new desktop.")
                speak("Adding a new desktop.")
                pyautogui.hotkey('win', 'ctrl', 'd')

            elif "orion" in query or "tell me" in query:
                say = ["One moment while I analyze that.","Sir, I'm processing your request now.","Let me think about that...","Compiling a response, Sir...", "Just a moment sir...", "Gimme a second sir..."]
                say = random.choice(say)
                ui.update_text(say)
                speak(say)
                response = ask_phi3(query, ui)
                # print(response)
                # ui.update_text(response)
                # speak(response)


            elif "remember that" in query:
                key = query.lower().split("remember that")[-1].strip()
                if "is" in key:
                    k, v = key.split("is", 1)
                    remember(k.strip(), v.strip())
                    ui.update_text(f"Got it, sir. I'll remember that {k.strip()} is {v.strip()}.")
                    speak(f"Got it, sir. I'll remember that {k.strip()} is {v.strip()}.")
                else:
                    ui.update_text("Sorry, I didn't understand that. Please use the format 'remember that [key] is [value]'.")
                    speak("Sorry, I didn't understand that. Please use the format 'remember that [key] is [value]'.")

            elif "what is" in query.lower():
                key = query.lower().split("what is")[-1].strip()
                response = recall(key)
                speak(response)
                
            else:
                speak("Sorry, I didn't understand that command. Could you please repeat it, sir?")
                ui.update_text("Sorry, I didn't understand that command. Could you please repeat it?")
                if not ui.running:
                    break
        else:
            ui.update_status('idle')
            query = takeCommand(ui).lower()
            if "wake up" in query or "arise" in query:
                greetMe()
                awake = True
                ui.update_status('listening')
            elif detect_clap():
                greetMe()
                awake = True
                ui.update_status('listening')

def main():
    global root
    root = tk.Tk()
    root.iconbitmap('logo.ico')
    ui = VoiceAssistantUI(root)

    def on_closing():
        ui.cleanup()
        root.destroy()
        sys.exit()

    root.protocol("WM_DELETE_WINDOW", on_closing)

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
