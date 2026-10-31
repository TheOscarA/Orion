"""
nowplaying_control.py — Windows SMTC Now Playing for ORION MK2
────────────────────────────────────────────────────────────────
Reads current media info from the Windows System Media Transport
Controls — the same interface the taskbar media widget uses.
Works with Spotify, Chrome, YouTube Music, any app that registers
a media session with Windows.

pip install winrt-runtime winrt-Windows.Media.Control
            winrt-Windows.Foundation winrt-Windows.Foundation.Collections
            winrt-Windows.Storage winrt-Windows.Storage.Streams
────────────────────────────────────────────────────────────────
"""

import asyncio
from dataclasses import dataclass


@dataclass
class NowPlayingInfo:
    title:   str
    artist:  str
    album:   str
    app:     str       # source app e.g. "Spotify", "Chrome"
    playing: bool


class NowPlayingError(Exception):
    pass


async def _get_info_async() -> NowPlayingInfo | None:
    try:
        from winrt.windows.media.control import (
            GlobalSystemMediaTransportControlsSessionManager as Manager,
        )
    except ImportError:
        raise NowPlayingError(
            "winrt packages not installed. Run: "
            "pip install winrt-runtime winrt-Windows.Media.Control "
            "winrt-Windows.Foundation winrt-Windows.Foundation.Collections "
            "winrt-Windows.Storage winrt-Windows.Storage.Streams"
        )

    manager  = await Manager.request_async()
    session  = manager.get_current_session()

    if not session:
        return None

    # Get playback status
    info    = session.get_playback_info()
    playing = (
        info.playback_status.value == 4   # 4 = Playing in WinRT enum
        if info else False
    )

    # Get media properties
    try:
        props = await session.try_get_media_properties_async()
    except Exception:
        return None

    if not props:
        return None

    # Source app ID e.g. "Spotify.exe" or browser
    app_id = session.source_app_user_model_id or ""
    if "spotify" in app_id.lower():
        app = "Spotify"
    elif "chrome" in app_id.lower():
        app = "Chrome"
    elif "firefox" in app_id.lower():
        app = "Firefox"
    elif "msedge" in app_id.lower():
        app = "Edge"
    elif "youtube" in app_id.lower():
        app = "YouTube"
    else:
        # Trim to just the exe name
        app = app_id.split("!")[-1].replace(".exe", "").strip() or "Unknown"

    return NowPlayingInfo(
        title   = props.title   or "Unknown Title",
        artist  = props.artist  or "Unknown Artist",
        album   = props.album_title or "",
        app     = app,
        playing = playing,
    )


def get_now_playing() -> NowPlayingInfo | None:
    """
    Synchronously fetch the current media session info.
    Returns None if nothing is playing.
    Raises NowPlayingError if winrt is not installed.
    """
    try:
        loop = asyncio.new_event_loop()
        return loop.run_until_complete(_get_info_async())
    except NowPlayingError:
        raise
    except Exception as e:
        raise NowPlayingError(f"Could not read media session: {e}") from e
    finally:
        loop.close()


def format_now_playing_speech(info: NowPlayingInfo) -> str:
    """Turn a NowPlayingInfo into a natural spoken sentence."""
    status = "playing" if info.playing else "paused"
    if info.artist and info.artist != "Unknown Artist":
        return f"Currently {status}: {info.title} by {info.artist} on {info.app}."
    return f"Currently {status}: {info.title} on {info.app}."
