"""
SearchNow.py — Search utilities for ORION MK2
──────────────────────────────────────────────
Google and Wikipedia searches now route through search_control.py
which uses DuckDuckGo + Ollama to give a spoken answer — no browser
tab needed.

This file only keeps what search_control can't do:
    - YouTube: open a browser tab and play a video
    - Google/Wikipedia: thin wrappers that delegate to cmd_web_search
        via the dispatcher (handled in main.py tool definitions)

pywhatkit and wikipedia dependencies removed — no longer needed.
"""

import webbrowser


def searchYoutube(query: str, _ui=None):
    """
    Open a YouTube search in the browser.
    For voice-triggered playback Orion uses keyboard shortcuts
    on Spotify — YouTube is browser-only.
    """
    query = query.strip()
    if not query:
        return
    url = "https://www.youtube.com/results?search_query=" + query.replace(" ", "+")
    webbrowser.open(url)


def searchGoogle(query: str, _ui=None):
    """
    Open a Google search in the browser.
    For spoken answers use cmd_web_search instead — this is
    kept only for cases where the user explicitly wants a
    browser tab opened.
    """
    query = query.strip()
    if not query:
        return
    url = "https://www.google.com/search?q=" + query.replace(" ", "+")
    webbrowser.open(url)


def searchWikipedia(query: str, _ui=None):
    """
    Open a Wikipedia search in the browser.
    For spoken summaries cmd_web_search handles this better.
    """
    query = query.strip()
    if not query:
        return
    url = "https://en.wikipedia.org/w/index.php?search=" + query.replace(" ", "+")
    webbrowser.open(url)
