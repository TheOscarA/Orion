from cx_Freeze import setup, Executable
import sys

# Include any additional packages that cx_Freeze might miss
build_exe_options = {
    "packages": [
        "os", "pyttsx3", "speech_recognition", "numpy", "pyautogui", 
        "tkinter", "webbrowser", "screen_brightness_control", "pycaw", 
        "sounddevice", "pywhatkit", "wikipedia", "ctypes", "comtypes", 
        "AppOpener", "screen_brightness_control"  # Include screen_brightness_control (sbc)
    ],
    "include_files": []  # Add paths to any additional files that need to be included
}

# Base for Windows GUI applications
base = None
if sys.platform == "win32":
    base = "Win32GUI"

setup(
    name="Orion",
    version="1.0",
    description="Orion MK1 Assistant",
    options={"build_exe": build_exe_options},
    executables=[Executable("main.py", base=base)]
)
