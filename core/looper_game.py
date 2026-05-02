"""
Looper Game - record audio and loop it back like a looper pedal.

Press 'r' to start/stop recording, spacebar to toggle loop playback,
'q' to quit back to the master menu.
"""
import time
import numpy as np
from enum import Enum, auto
from typing import Callable
from dataclasses import dataclass, field
from .events import GameEvent, EventType
from .protocols import UIAdapter, AudioAdapter


@dataclass
class LooperTrack:
    """A single recorded audio track."""
    buffer: np.ndarray
    duration: float
    loop_count: int = 0
    playback_id: int | None = None


class LooperState(Enum):
    """Current state of the looper."""
    IDLE = auto()
    RECORDING = auto()
    PLAYING = auto()
    PAUSED = auto()


class LooperGame:
    """
    Looper pedal game engine.

    Records audio from the user's instrument, then plays it back
    in a loop. The user can re-record or toggle playback.

    Designed to be run by a MasterEngine. Does NOT manage UI lifecycle.

    Controls:
        Enter/Return: Start/stop recording
        space: Toggle loop playback
        q: Quit back to master menu

    Usage:
        game = LooperGame(ui, audio)
        game.run()  # blocking loop, returns when player quits
    """

    NAME = "Looper"
    DESCRIPTION = "Record and loop audio like a looper pedal"

    def __init__(self, ui: UIAdapter, audio: AudioAdapter):
        self._ui = ui
        self._audio = audio
        self._running = False
        self._state = LooperState.IDLE
        self._tracks: list[LooperTrack] = []
        self._record_start_time: float = 0.0
        self._event_listeners: list[Callable[[GameEvent], None]] = []

    # ---------- Public API ----------

    def run(self) -> None:
        """Blocking game loop. Returns when the player quits."""
        self._running = True
        self._emit(GameEvent.game_starting())
        try:
            while self._running:
                if self._state == LooperState.RECORDING:
                    self._recording_loop()
                else:
                    self._selection_loop()
        finally:
            self._cleanup()

    def add_event_listener(self, callback: Callable[[GameEvent], None]) -> None:
        """Register a callback to receive all game events."""
        self._event_listeners.append(callback)

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def state(self) -> LooperState:
        return self._state

    @property
    def tracks(self) -> list[LooperTrack]:
        return self._tracks

    # ---------- Track List ----------

    def _format_track_list(self) -> list[str]:
        """Build display strings for each track."""
        if not self._tracks:
            return ["(no tracks yet)"]
        items = []
        for i, track in enumerate(self._tracks):
            playing = " [playing]" if track.playback_id is not None else ""
            items.append(f"Track {i + 1}: {track.duration:.1f}s{playing}")
        return items

    def _selection_loop(self) -> None:
        """Show track list, block until user acts."""
        self._emit(GameEvent(EventType.LOOPER_STATUS, {
            "track_count": len(self._tracks),
        }))
        items = self._format_track_list()
        result = self._ui.wait_for_selection(items, use_enter_key=False)

        if result == 'q':
            self._running = False
        elif result == '\n':
            self._start_recording()
        elif result.startswith('d:'):
            idx = int(result[2:])
            self._delete_track(idx)
        elif result.startswith(' :'):
            idx = int(result[2:])
            self._toggle_playback(idx)

    def _recording_loop(self) -> None:
        """Poll for input during recording."""
        cmd = self._ui.get_command()
        if cmd in ('\n', 'r'):
            self._stop_recording()
        elif cmd == 'q':
            self._stop_recording()
            self._running = False
        else:
            time.sleep(0.05)

    # ---------- Recording ----------

    def _start_recording(self) -> None:
        if self._state == LooperState.PLAYING:
            self._stop_all_playback()

        self._state = LooperState.RECORDING
        self._record_start_time = time.time()
        self._audio.record_buffer()
        self._emit(GameEvent(EventType.LOOPER_RECORDING))

    def _stop_recording(self) -> None:
        buf = self._audio.stop_record_buffer()
        if buf is not None and len(buf) > 0:
            duration = time.time() - self._record_start_time
            self._tracks.append(LooperTrack(buffer=buf, duration=duration))
            self._state = LooperState.PAUSED
            self._emit(GameEvent(EventType.LOOPER_STOPPED))
            self._play_all_tracks()
        else:
            self._state = LooperState.IDLE

    # ---------- Playback ----------

    def _play_all_tracks(self) -> None:
        if not self._tracks:
            return
        for track in self._tracks:
            if track.playback_id is None:
                self._play_track(track)

    def _toggle_playback(self, idx: int) -> None:
        if not self._tracks or idx >= len(self._tracks):
            return
        track = self._tracks[idx]
        if track.playback_id is not None:
            self._stop_track(track)
        else:
            self._play_track(track)

    def _play_track(self, track: LooperTrack) -> None:
        track.loop_count = 0
        track.playback_id = self._audio.play_buffer(track.buffer, loop=True)
        self._state = LooperState.PLAYING
        self._emit(GameEvent(EventType.LOOPER_PLAYING))

    def _stop_track(self, track: LooperTrack) -> None:
        if track.playback_id is not None:
            self._audio.stop_playback(track.playback_id)
            track.playback_id = None
        if not any(t.playback_id is not None for t in self._tracks):
            self._state = LooperState.PAUSED
            self._emit(GameEvent(EventType.LOOPER_STOPPED))

    def _stop_all_playback(self) -> None:
        self._audio.stop_playback()
        for track in self._tracks:
            track.playback_id = None
        self._state = LooperState.PAUSED
        self._emit(GameEvent(EventType.LOOPER_STOPPED))

    # ---------- Track Management ----------

    def _delete_track(self, idx: int) -> None:
        if not self._tracks or idx >= len(self._tracks):
            return
        track = self._tracks[idx]
        if track.playback_id is not None:
            self._stop_track(track)
        del self._tracks[idx]
        if not self._tracks:
            self._state = LooperState.IDLE

    # ---------- Internal ----------

    def _emit(self, event: GameEvent) -> None:
        """Send event to UI and all listeners."""
        self._ui.on_event(event)
        for listener in self._event_listeners:
            listener(event)

    def _cleanup(self) -> None:
        """Stop all audio on exit."""
        if self._state == LooperState.RECORDING:
            self._audio.stop_record_buffer()
        if self._state == LooperState.PLAYING:
            self._stop_all_playback()
        self._state = LooperState.IDLE
