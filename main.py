import pyttsx3
import speech_recognition as sr
import time
import sounddevice as sd
import numpy as np
import pyautogui
import webbrowser
import wolframalpha
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

# Initialize WolframAlpha Client
WOLFRAM_APP_ID = "H496UA-PEAKXWTVP6"
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
        print("Listening...")
        ui.update_status('listening')  # Update status to 'listening'
        r.pause_threshold = 1
        r.energy_threshold = 300
        audio = r.listen(source, 0, 4)

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

class VoiceAssistantUI:
    """UI class for the voice assistant"""
    def __init__(self, root):
        self.root = root
        self.root.title("Voice Assistant")
        self.root.geometry("600x600")
        self.root.configure(bg='black')

        self.canvas = tk.Canvas(root, bg='black', width=600, height=600)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # Define circle position and size
        self.circle_x1, self.circle_y1, self.circle_x2, self.circle_y2 = 100, 100, 500, 500
        self.circle = self.canvas.create_oval(self.circle_x1, self.circle_y1, self.circle_x2, self.circle_y2, outline='blue', width=5)

        # Create a Text widget inside the circle
        self.text_box = tk.Text(root, wrap=tk.WORD, height=11, width=30, bg='black', fg='lightblue', font=('Helvetica', 12), bd=0, relief=tk.FLAT)
        self.text_box.place(x=175, y=200)

        # Create status text widget
        self.status_text = self.canvas.create_text(300, 550, text="Idle", fill='white', font=('Helvetica', 12))

    def update_status(self, status):
        """Update the status text and circle color"""
        self.canvas.itemconfig(self.status_text, text=status.capitalize())
        if status == 'listening':
            self.canvas.itemconfig(self.circle, outline='blue')
        elif status == 'understanding':
            self.canvas.itemconfig(self.circle, outline='red')
        else:
            self.canvas.itemconfig(self.circle, outline='blue')

    def update_text(self, text):
        """Update the text box with command outputs"""
        self.text_box.delete(1.0, tk.END)
        self.text_box.insert(tk.END, text)


def assistant_logic(ui):
    awake = False

    while True:
        if awake:
            ui.update_status('listening')
            query = takeCommand(ui).lower()  # Pass `ui` to `takeCommand`
            if query == "none":
                continue
            if "go to sleep" in query:
                speak("Alright sir, I will be available anytime")
                ui.update_text("Alright sir, I will be available anytime")
                awake = False
            elif "hello" in query:
                speak("Hello sir, how are you?")
                ui.update_text("Hello sir, how are you?")
            elif "i am fine" in query:
                speak("Good to hear, sir")
                ui.update_text("Good to hear, sir")
            elif "how are you" in query:
                speak("No errors and fully functional, sir")
                ui.update_text("No errors and fully functional, sir")
            elif "thank you" in query:
                speak("My pleasure sir")
                ui.update_text("My pleasure sir")
            elif "set volume" in query:
                volume_level = parse_volume_level(query)
                if volume_level is not None:
                    set_volume(volume_level / 100)
                    speak(f"Volume level set to {volume_level} percent")
                    ui.update_text(f"Volume level set to {volume_level} percent")
                else:
                    speak("Sorry, I couldn't understand the volume level.")
                    ui.update_text("Sorry, I couldn't understand the volume level.")
            elif "set brightness" in query:
                brightness_level = parse_brightness_level(query)
                if brightness_level is not None:
                    set_brightness(brightness_level)
                    speak(f"Brightness level set to {brightness_level} percent")
                    ui.update_text(f"Brightness level set to {brightness_level} percent")
                else:
                    speak("Sorry, I couldn't understand the brightness level.")
                    ui.update_text("Sorry, I couldn't understand the brightness level.")
            elif "shutdown" in query:
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
                open_application(query)
                ui.update_text(f"Opening application: {query}")
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
            elif "wolfram" in query or "calculate" in query or "what is" in query:
                wolfram_query = query.replace("wolfram", "").replace("calculate", "").strip()
                wolfram_answer = query_wolfram_alpha(wolfram_query)
                speak(wolfram_answer)
                ui.update_text(wolfram_answer)

            elif "latest news" in query:
                speak("Here is the latest news sir.")
                print(*get_news(),sep="\n")
                speak(get_news())
                
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
    root = tk.Tk()
    ui = VoiceAssistantUI(root)
    
    # Run the assistant logic in a separate thread
    Thread(target=assistant_logic, args=(ui,)).start()
    
    root.mainloop()

if __name__ == "__main__":
    main()
