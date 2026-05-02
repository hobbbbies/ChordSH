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

    def play_buffer(self, buffer, loop=False, on_loop=None) -> None:
        self._playing = True
        self._play_loop = loop
        self._play_on_loop = on_loop
        self.play_buffer_count = getattr(self, 'play_buffer_count', 0) + 1

    def stop_playback(self) -> None:
        self._playing = False
        self.stop_playback_count = getattr(self, 'stop_playback_count', 0) + 1

    def is_playing(self) -> bool:
        return getattr(self, '_playing', False)

    def set_fake_buffer(self, buf) -> None:
        """Set a fake buffer to be returned by stop_record_buffer."""
        self._fake_buffer = buf