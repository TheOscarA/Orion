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
import random
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
from tkinter import messagebox
# add system info into ui like battery cpu etc.

# Initialize WolframAlpha Client
WOLFRAM_APP_ID = "Your Wolfram ID"
client = wolframalpha.Client(WOLFRAM_APP_ID)

# Initialize the text-to-speech engine
engine = pyttsx3.init('sapi5')
voices = engine.getProperty("voices")
engine.setProperty("voice", voices[0].id)
engine.setProperty("rate", 170)
engine.setProperty("volume", 1.0)  # Set volume to maximum

def speak(audio):
    """Text-to-speech function"""
    engine.say(audio)
    engine.runAndWait()

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

def query_wolfram_alpha(query):
    """Query Wolfram Alpha and return the result"""
    try:
        res = client.query(query)
        answer = next(res.results).text
        return answer
    except Exception as e:
        print(f"Error querying Wolfram Alpha: {e}")
        return "Sorry, I couldn't retrieve information from Wolfram Alpha."
    
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
        f"CPU: {cpu_usage}% |\n "
        f"Memory: {memory_info.percent}% |\n "
        f"Battery: {battery_status}"
    )

class ToDoList:
    def __init__(self, parent):
        self.parent = parent
        self.file_path = 'todo_list.txt'
        self.frame = tk.Frame(parent, bg='black')
        self.frame.place(relx=0.01, rely=0.01, anchor='nw', width=200, height=300)

        self.listbox = tk.Listbox(self.frame, bg='black', fg='lightblue', font=('Helvetica', 10))
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.entry = tk.Entry(self.frame, bg='black', fg='lightblue', font=('Helvetica', 10))
        self.entry.pack(side=tk.BOTTOM, fill=tk.X, padx=5, pady=5)

        self.add_button = tk.Button(self.frame, text='Add Task', command=self.add_task, bg='blue', fg='lightblue', font=('Helvetica', 10))
        self.add_button.pack(side=tk.BOTTOM, pady=5)

        self.remove_button = tk.Button(self.frame, text='Remove Task', command=self.remove_task, bg='red', fg='lightblue', font=('Helvetica', 10))
        self.remove_button.pack(side=tk.BOTTOM, pady=5)

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
            

    

import psutil
import tkinter as tk

class SystemInfo:
    def __init__(self, parent):
        self.parent = parent
        self.frame = tk.Frame(parent, bg='black')
        self.frame.place(relx=0.01, rely=0.8, anchor='sw', width=300, height=150)

        self.info_label = tk.Label(self.frame, bg='black', fg='lightblue', font=('Helvetica', 10), anchor='nw', justify='left')
        self.info_label.pack(fill=tk.BOTH, expand=False)

        self.update_info()

    def update_info(self):
        """Update system information"""
        battery = psutil.sensors_battery()
        cpu_usage = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        battery_status = f"{battery.percent}% remaining" if battery else "No battery info available"
        memory_usage = f"{memory.percent}% used"

        info = (f"| CPU Usage: {cpu_usage}% |\n"
                f"| Memory Usage: {memory_usage}\n"
                f"|Battery Status: {battery_status}")
        self.info_label.config(text=info)


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

def assistant_logic(ui):
    awake = False

    while True:
        if awake:
            ui.update_status('listening')
            query = takeCommand(ui).lower()  # Pass `ui` to `takeCommand`
            if query == "none":
                continue
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

            elif "wolfram" in query or "calculate" in query or "what is" in query:
                wolfram_query = query.replace("wolfram", "").replace("calculate", "").strip()
                wolfram_answer = query_wolfram_alpha(wolfram_query)
                speak(wolfram_answer)
                ui.update_text(wolfram_answer)

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
                open_application("Spotify")
                time.sleep(3)
                pyautogui.hotkey('space')

            elif "pause music" in query:
                open_application("Spotify")
                time.sleep(3)
                pyautogui.hotkey('space')

            elif "skip song" in query or "next song" in query or "skip track" in query:
                open_application("Spotify")
                time.sleep(3)
                pyautogui.hotkey('ctrl', 'left')


            elif "previous song" in query or "last song" in query:
                open_application("Spotify")
                time.sleep(3)
                pyautogui.hotkey('ctrl', 'left')
            
            elif "flip a coin" in query:
                coinop = ["Heads", "Tails"]
                coin = random.choice(coinop)
                ui.update_text(coin)
                speak("Sir, I got heads.")
                
            else:
                speak("Sorry, I didn't understand that command. Could you please repeat it?")
                ui.update_text("Sorry, I didn't understand that command. Could you please repeat it?")
        else:
            ui.update_status('idle')
            query = takeCommand(ui).lower()
            if "wake up" in query:
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
