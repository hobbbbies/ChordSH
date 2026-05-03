import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.events import GameEvent, EventType


class MockUIAdapter:
    """Mock UI adapter for testing."""
    
    def __init__(self):
        self.events: list[GameEvent] = []
        self.commands: list[str] = []
        self._command_index = 0
        self.initialized = False
        self.cleaned_up = False
    
    def on_event(self, event: GameEvent) -> None:
        self.events.append(event)
    
    def get_command(self) -> str | None:
        if self._command_index < len(self.commands):
            cmd = self.commands[self._command_index]
            self._command_index += 1
            return cmd
        return None
    
    def wait_for_command(self) -> str:
        if self._command_index < len(self.commands):
            cmd = self.commands[self._command_index]
            self._command_index += 1
            return cmd
        return 'q'  # Default to quit to prevent infinite loop

    def wait_for_selection(self, items: list[str], use_enter_key: bool = True) -> str:
        if self._command_index < len(self.commands):
            cmd = self.commands[self._command_index]
            self._command_index += 1
            return cmd
        return 'q'  # Default to quit to prevent infinite loop
    
    def init(self) -> None:
        self.initialized = True
    
    def cleanup(self) -> None:
        self.cleaned_up = True
    
    def inject_command(self, cmd: str) -> None:
        self.commands.insert(self._command_index, cmd)

    def queue_commands(self, *cmds: str) -> None:
        self.commands.extend(cmds)
    
    def get_events_of_type(self, event_type: EventType) -> list[GameEvent]:
        return [e for e in self.events if e.type == event_type]


class MockAudioAdapter:
    """Mock audio adapter for testing."""
    
    def __init__(self):
        self._streaming = False
        self._result: tuple[str, int, float] | None = None
        self._on_result = None
        self.start_count = 0
        self.stop_count = 0
    
    def start_stream(self, on_result) -> None:
        self._streaming = True
        self._on_result = on_result
        self.start_count += 1
    
    def stop_stream(self) -> tuple[str, int, float] | None:
        self._streaming = False
        self.stop_count += 1
        return self._result
    
    def is_streaming(self) -> bool:
        return self._streaming
    
    def set_result(self, note: str, freq: float, chord_name: str | None = None) -> None:
        self._result = (note, freq, chord_name)
    
    def simulate_detection(self, note: str, freq: float, chord_name: str | None = None) -> None:
        if self._on_result:
            self._on_result(note, freq, chord_name)

    # Looper support
    def record_buffer(self) -> None:
        self._recording_raw = True
        self.record_buffer_count = getattr(self, 'record_buffer_count', 0) + 1

    def stop_record_buffer(self):
        self._recording_raw = False
        self.stop_record_buffer_count = getattr(self, 'stop_record_buffer_count', 0) + 1
        return getattr(self, '_fake_buffer', None)

    def play_buffer(self, buffer, loop=False, on_loop=None) -> int:
        self._play_loop = loop
        self._play_on_loop = on_loop
        self.play_buffer_count = getattr(self, 'play_buffer_count', 0) + 1
        playback_id = getattr(self, '_next_playback_id', 0)
        self._next_playback_id = playback_id + 1
        if not hasattr(self, '_active_playbacks'):
            self._active_playbacks = set()
        self._active_playbacks.add(playback_id)
        return playback_id

    def stop_playback(self, playback_id: int | None = None) -> None:
        self.stop_playback_count = getattr(self, 'stop_playback_count', 0) + 1
        if not hasattr(self, '_active_playbacks'):
            self._active_playbacks = set()
        if playback_id is not None:
            self._active_playbacks.discard(playback_id)
        else:
            self._active_playbacks.clear()

    def is_playing(self) -> bool:
        if not hasattr(self, '_active_playbacks'):
            return False
        return len(self._active_playbacks) > 0

    def set_fake_buffer(self, buf) -> None:
        """Set a fake buffer to be returned by stop_record_buffer."""
        self._fake_buffer = buf