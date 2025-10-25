# Orion AI Assistant - README

Welcome to **Orion** – Inspired by J.A.R.V.I.S.

---

## 🔧 Features

- **Voice-Activated Interface**  
  Reacts to voice commands and responds with voice.

- **Asleep/Wake Mode**  
  Starts in sleep mode and activates via wake up voice command.

- **Natural Language Understanding**  
  Capable of understanding questions and intent (future upgrade to deepseek-r1).

- **System Monitoring**  
  Displays CPU, RAM, and battery status.

- **Google, YouTube, and Wikipedia Search Integration**  
  Results shown directly in the browser.

- **UI Circle Feedback**  
  Color-coded for listening (blue) and uderstanding (red) states.

- **Full-screen UI**  
  Designed for immersive, sleek operation.
  Press "esc" or "del" to toggle full-screen

---

## 🧠 Planned Features

- **Local AI Model (Deepseek-r1)**  
  For natural conversation and improved scalability because I want to add function calling.

- **Enhanced NLP**  
  Improved understanding through intent recognition.

- **Vosk Model**
  For Offline voice recognition.

- **Contextual Memory**  
  Orion will grow and adapt over time.

---

## 🛠️ Tech Stack

- **Language**: Python 3  
- **Voice Engine**: `edge_tts`  
- **UI Framework**: `Tkinter`  
- **Voice Recognition**: Using Google Speech Recognition via `speech_recognition` library
- **Packaging**: PyInstaller (one-file executable)

---

## 💻 Running Orion

1. Clone the repository  
2. Get a api-key from [newsapi.org](https://newsapi.org/)
3. Add api-key in `Get_News.py`
4. Install requirements: `pip install -r requirements.txt`  
5. Run: `python main.py`

---

## 🚀 Future Integrations

- Deepseek-r1 via Ollama
- Function calling
- Code generation support
- Advanced contextual memory module

---

## 🧠 Reminder

- Orion is still under development.
- Made in my spare time, so there are still lots of bugs.
- Only works on Windows

---

Created by **TheOscarA**
