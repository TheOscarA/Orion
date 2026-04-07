"""
todo_control.py — Google Tasks integration for ORION MK2
──────────────────────────────────────────────────────────
Replaces the local todo_list.txt with Google Tasks so tasks
sync across all your devices (phone, web, Orion).

Uses the same credentials.json / token.json as calendar_control.
The Tasks scope must be included in SCOPES — see calendar_control.py.

Tasks are stored in your default Google Tasks list (@default).
──────────────────────────────────────────────────────────
"""

import os

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# ── Auth — shared with calendar_control ───────────────────
SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/tasks",
]

_BASE            = os.path.dirname(os.path.abspath(__file__))
CREDENTIALS_FILE = os.path.join(_BASE, "credentials.json")
TOKEN_FILE       = os.path.join(_BASE, "token.json")

# Default tasklist ID — "@default" is always the primary list
TASKLIST_ID = "@default"


def _get_service():
    """Authenticate and return a Google Tasks API service object."""
    creds = None

    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(CREDENTIALS_FILE):
                raise TaskError(
                    "credentials.json not found. "
                    "Download it from Google Cloud Console."
                )
            flow  = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())

    return build("tasks", "v1", credentials=creds)


# ── Helpers ───────────────────────────────────────────────

def _fetch_tasks(include_completed: bool = False) -> list[dict]:
    """
    Fetch all tasks from the default list.
    Returns a list of raw Google Tasks API task dicts.
    """
    try:
        service = _get_service()
        result  = service.tasks().list(
            tasklist        = TASKLIST_ID,
            showCompleted   = include_completed,
            showHidden      = include_completed,
            maxResults      = 100,
        ).execute()
        return result.get("items", [])
    except HttpError as e:
        raise TaskError(f"Google Tasks API error: {e}") from e


def _task_is_done(task: dict) -> bool:
    return task.get("status") == "completed"


# ── Public API ────────────────────────────────────────────
# All function signatures are identical to the old txt-file
# version so main.py requires no changes.

def add_task(task: str) -> str:
    """
    Add a new task to Google Tasks.
    Returns a spoken confirmation.
    """
    task = task.strip()
    if not task:
        return "I did not catch a task name, sir."

    try:
        # Check for duplicates among pending tasks
        existing = _fetch_tasks(include_completed=False)
        titles   = [t.get("title", "").lower() for t in existing]
        if task.lower() in titles:
            return f"'{task}' is already on your list, sir."

        service = _get_service()
        service.tasks().insert(
            tasklist = TASKLIST_ID,
            body     = {"title": task, "status": "needsAction"},
        ).execute()

        return f"Added '{task}' to your to-do list, sir."

    except HttpError as e:
        raise TaskError(f"Could not add task: {e}") from e


def read_tasks(include_done: bool = False) -> str:
    """
    Read out all pending (and optionally completed) tasks.
    Returns a spoken summary string.
    """
    try:
        all_tasks = _fetch_tasks(include_completed=include_done)
        pending   = [t for t in all_tasks if not _task_is_done(t)]
        done      = [t for t in all_tasks if _task_is_done(t)]

        if not all_tasks:
            return "Your to-do list is empty, sir."

        parts = []
        if pending:
            names = [t.get("title", "Untitled") for t in pending]
            if len(names) == 1:
                parts.append(f"You have one pending task: {names[0]}.")
            else:
                listed = ", ".join(names[:-1]) + f", and {names[-1]}"
                parts.append(f"You have {len(names)} pending tasks: {listed}.")
        else:
            parts.append("You have no pending tasks, sir.")

        if include_done and done:
            parts.append(
                f"You have also completed "
                f"{len(done)} task{'s' if len(done) != 1 else ''}."
            )

        return " ".join(parts)

    except HttpError as e:
        raise TaskError(f"Could not read tasks: {e}") from e


def complete_task(task: str) -> str:
    """
    Mark a task as complete by partial name match (case-insensitive).
    Returns a spoken confirmation.
    """
    task_low = task.strip().lower()

    try:
        service   = _get_service()
        all_tasks = _fetch_tasks(include_completed=False)

        match = next(
            (t for t in all_tasks
            if task_low in t.get("title", "").lower()
            and not _task_is_done(t)),
            None,
        )

        if not match:
            return f"I could not find a task matching '{task}', sir."

        match["status"] = "completed"
        service.tasks().update(
            tasklist = TASKLIST_ID,
            task     = match["id"],
            body     = match,
        ).execute()

        return f"Marked '{match['title']}' as complete, sir. Well done."

    except HttpError as e:
        raise TaskError(f"Could not complete task: {e}") from e


def remove_task(task: str) -> str:
    """
    Permanently delete a task by partial name match.
    Returns a spoken confirmation.
    """
    task_low = task.strip().lower()

    try:
        service   = _get_service()
        all_tasks = _fetch_tasks(include_completed=True)

        matches = [
            t for t in all_tasks
            if task_low in t.get("title", "").lower()
        ]

        if not matches:
            return f"I could not find a task matching '{task}', sir."

        for t in matches:
            service.tasks().delete(
                tasklist = TASKLIST_ID,
                task     = t["id"],
            ).execute()

        removed = len(matches)
        return f"Removed {removed} task{'s' if removed != 1 else ''} from your list, sir."

    except HttpError as e:
        raise TaskError(f"Could not remove task: {e}") from e


def clear_completed() -> str:
    """
    Delete all completed tasks from the list.
    Returns a spoken confirmation.
    """
    try:
        service = _get_service()
        # clearCompleted is a Google Tasks API endpoint that does this in one call
        service.tasks().clear(tasklist=TASKLIST_ID).execute()
        return "Cleared all completed tasks, sir."

    except HttpError as e:
        raise TaskError(f"Could not clear completed tasks: {e}") from e


def get_tasks_for_ui() -> list[dict]:
    """
    Return a list of task dicts for the UI panel.
    Format: [{"text": str, "done": bool}, ...]
    """
    try:
        all_tasks = _fetch_tasks(include_completed=True)
        return [
            {
                "text": t.get("title", "Untitled"),
                "done": _task_is_done(t),
            }
            for t in all_tasks
        ]
    except (HttpError, TaskError):
        return []


# ── Custom exception ──────────────────────────────────────

class TaskError(Exception):
    """Raised when any Google Tasks operation fails."""