"""
streaming_control.py — Streaming responses + session memory for ORION MK2
──────────────────────────────────────────────────────────────────────────
Streams Ollama output word by word.
When a complete sentence is detected (via punctuation),
that sentence is immediately passed to speak() — so Orion
starts talking before the full response is finished.

SESSION MEMORY
──────────────
_history holds the running conversation as a list of
{"role": "user"|"assistant", "content": str} dicts.

Two ways context gets into history:

1. cmd_chat — automatically via stream_response()
    Every time Orion has a conversation the exchange is appended.

2. All other commands — via remember_exchange()
    Commands like cmd_weather_spoken, cmd_calendar_read etc. call
    remember_exchange(user_msg, assistant_response) after executing
    so follow-up questions have context:
    "What's the weather in Tokyo?" → remember_exchange called
    "Book a trip there" → Orion knows "there" = Tokyo

History is capped at MAX_HISTORY_TURNS pairs to avoid overflowing
the model's context window. Cleared on sleep via clear_history().

pip install ollama
──────────────────────────────────────────────────────────────────────────
"""

import re
import threading
from queue import Queue

import ollama

# ── Injected from main.py ─────────────────────────────────
_speak_fn         = None
_ui_transcript_fn = None

# ── Session history ───────────────────────────────────────
_history: list[dict] = []

# Max user/assistant pairs to keep in context
# 10 pairs = 20 messages — enough for rich context
MAX_HISTORY_TURNS = 10

# Sentence-ending punctuation
_SENTENCE_END = re.compile(r'[.!?]+')

# How long the model stays in VRAM after the last request. Ollama's
# default is 5 minutes; after that the next command waits several
# seconds to reload. -1 = never unload, "0" = unload immediately.
KEEP_ALIVE = "10m"


# ── Init ──────────────────────────────────────────────────

def init(speak_fn, ui_transcript_fn):
    """Call once from main.py after defining speak and ui_show_transcript."""
    global _speak_fn, _ui_transcript_fn
    _speak_fn         = speak_fn
    _ui_transcript_fn = ui_transcript_fn


# ── History management ────────────────────────────────────

def clear_history():
    """
    Wipe the session history.
    Called when Orion goes to sleep so each active session starts fresh.
    """
    global _history
    _history = []
    print("[Memory] Session history cleared.")


def remember_exchange(user_msg: str, assistant_msg: str):
    """
    Manually add a user/assistant exchange to history.

    Called by non-chat commands (weather, calendar, timers etc.)
    after they execute, so follow-up questions have context.

    Example:
        cmd_weather_spoken fetches Tokyo weather and speaks it,
        then calls:
            remember_exchange(
                "What's the weather in Tokyo?",
                "Currently in Tokyo: partly cloudy, 18 degrees..."
            )
        Now if the user says "book a trip there", Orion knows
        "there" = Tokyo.
    """
    _append_history("user",      user_msg)
    _append_history("assistant", assistant_msg)


def _append_history(role: str, content: str):
    """Add a message and trim to MAX_HISTORY_TURNS pairs."""
    global _history
    _history.append({"role": role, "content": content})
    max_messages = MAX_HISTORY_TURNS * 2
    if len(_history) > max_messages:
        _history = _history[-max_messages:]


def _build_messages(system: str, user_prompt: str) -> list[dict]:
    """
    Assemble the full message list for ollama.chat():
      [system] + [history so far] + [current user message]
    """
    return (
        [{"role": "system", "content": system}]
        + list(_history)
        + [{"role": "user", "content": user_prompt}]
    )


# ── Sentence splitter ─────────────────────────────────────

def _split_sentences(buffer: str) -> tuple[list[str], str]:
    """
    Given a text buffer return (complete_sentences, leftover).
    Splits on . ! ? keeping punctuation with each sentence.
    """
    sentences = []
    last_end  = 0
    for match in _SENTENCE_END.finditer(buffer):
        end      = match.end()
        sentence = buffer[last_end:end].strip()
        if sentence:
            sentences.append(sentence)
        last_end = end
    leftover = buffer[last_end:].strip()
    return sentences, leftover


# ── TTS worker ────────────────────────────────────────────

def _speak_worker(queue: Queue):
    """
    Dedicated thread — pulls sentences from the queue and speaks
    them one at a time so TTS never overlaps with streaming.
    """
    while True:
        sentence = queue.get()
        if sentence is None:    # poison pill
            queue.task_done()
            break
        try:
            if _speak_fn:
                _speak_fn(sentence)
        except Exception as e:
            print(f"[Stream] TTS error: {e}")
        finally:
            queue.task_done()


# ── Core: streaming chat with memory ─────────────────────

def stream_response(
    prompt:  str,
    system:  str,
    model:   str  = "qwen2.5:7b",
    show_ui: bool = True,
) -> str:
    """
    Stream an Ollama response, speaking each sentence as it arrives.
    Automatically appends the exchange to session history.

    Parameters
    ----------
    prompt   : the user message
    system   : the system prompt / persona
    model    : Ollama model name
    show_ui  : whether to update the transcript panel live

    Returns
    -------
    The full assembled response as a string.
    """
    speech_queue  = Queue()
    full_response = []
    buffer        = ""

    worker = threading.Thread(
        target=_speak_worker,
        args=(speech_queue,),
        daemon=True,
    )
    worker.start()

    try:
        messages = _build_messages(system, prompt)

        stream = ollama.chat(
            model    = model,
            messages = messages,
            stream   = True,
            keep_alive = KEEP_ALIVE,
        )

        for chunk in stream:
            token = chunk["message"]["content"]
            if not token:
                continue

            buffer        += token
            full_response.append(token)

            if show_ui and _ui_transcript_fn:
                _ui_transcript_fn("".join(full_response))

            sentences, buffer = _split_sentences(buffer)
            for sentence in sentences:
                if sentence.strip():
                    speech_queue.put(sentence)

        if buffer.strip():
            speech_queue.put(buffer.strip())

    except Exception as e:
        error_msg = f"I encountered a streaming error, sir: {e}"
        speech_queue.put(error_msg)
        if _ui_transcript_fn:
            _ui_transcript_fn(error_msg)
        print(f"[Stream] Error: {e}")

    finally:
        speech_queue.put(None)
        worker.join()

    response_text = "".join(full_response)

    # Save exchange to history so the next call has context
    if response_text.strip():
        _append_history("user",      prompt)
        _append_history("assistant", response_text)

    return response_text


# ── Function routing call (no memory) ────────────────────

def stream_function_call(
    user_input:  str,
    tool_schema: str,
    model:       str = "qwen2.5:7b",
) -> str:
    """
    Non-streaming Ollama call for command routing.
    Does NOT use or update history — the router only needs to
    classify the current command, not understand conversation context.
    Returns the raw JSON string.
    """
    try:
        response = ollama.chat(
            model    = model,
            messages = [
                {
                    "role":    "user",
                    "content": (
                        tool_schema
                        + f'\n\nUser said: "{user_input}"\n\n'
                        + "Respond with only the JSON object."
                    ),
                }
            ],
            stream = False,
            keep_alive = KEEP_ALIVE,
        )
        return response["message"]["content"].strip()
    except Exception as e:
        print(f"[Stream] Function call error: {e}")
        return ""