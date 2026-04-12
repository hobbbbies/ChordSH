"""Tests for core/engine.py"""
import pytest
from unittest.mock import Mock, MagicMock, call
from core.engine import GameEngine, C_MAJOR_SCALE
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
    
    def set_result(self, note: str, octave: int, freq: float) -> None:
        self._result = (note, octave, freq)
    
    def simulate_detection(self, note: str, octave: int, freq: float) -> None:
        if self._on_result:
            self._on_result(note, octave, freq)


class TestGameEngineInit:
    def test_creates_with_adapters(self):
        ui = MockUIAdapter()
        audio = MockAudioAdapter()
        
        engine = GameEngine(ui, audio)
        
        assert engine._ui is ui
        assert engine._audio is audio

    def test_default_scale_is_c_major(self):
        engine = GameEngine(MockUIAdapter(), MockAudioAdapter())
        
        assert engine._scale == C_MAJOR_SCALE

    def test_custom_scale(self):
        custom_scale = ["C", "D", "E"]
        engine = GameEngine(MockUIAdapter(), MockAudioAdapter(), scale=custom_scale)
        
        assert engine._scale == custom_scale

    def test_initial_state(self):
        engine = GameEngine(MockUIAdapter(), MockAudioAdapter())
        
        assert engine.is_running is False
        assert engine.current_note is None
        assert engine.score == 0


class TestGameEngineStart:
    def test_start_initializes_ui(self):
        ui = MockUIAdapter()
        engine = GameEngine(ui, MockAudioAdapter())
        
        engine.start()
        
        assert ui.initialized is True

    def test_start_sets_running(self):
        engine = GameEngine(MockUIAdapter(), MockAudioAdapter())
        
        engine.start()
        
        assert engine.is_running is True

    def test_start_emits_game_started_event(self):
        ui = MockUIAdapter()
        engine = GameEngine(ui, MockAudioAdapter())
        
        engine.start()
        
        started_events = ui.get_events_of_type(EventType.GAME_STARTED)
        assert len(started_events) == 1

    def test_start_chooses_target_note(self):
        ui = MockUIAdapter()
        engine = GameEngine(ui, MockAudioAdapter())
        
        engine.start()
        
        assert engine.current_note in C_MAJOR_SCALE
        target_events = ui.get_events_of_type(EventType.NEW_TARGET_NOTE)
        assert len(target_events) == 1
        assert target_events[0].data["note"] == engine.current_note


class TestGameEngineStop:
    def test_stop_sets_not_running(self):
        engine = GameEngine(MockUIAdapter(), MockAudioAdapter())
        engine.start()
        
        engine.stop()
        
        assert engine.is_running is False

    def test_stop_cleans_up_ui(self):
        ui = MockUIAdapter()
        engine = GameEngine(ui, MockAudioAdapter())
        engine.start()
        
        engine.stop()
        
        assert ui.cleaned_up is True

    def test_stop_stops_audio_stream(self):
        audio = MockAudioAdapter()
        engine = GameEngine(MockUIAdapter(), audio)
        engine.start()
        
        engine.stop()
        
        assert audio.stop_count >= 1

    def test_stop_emits_game_ended_event(self):
        ui = MockUIAdapter()
        engine = GameEngine(ui, MockAudioAdapter())
        engine.start()
        
        engine.stop()
        
        ended_events = ui.get_events_of_type(EventType.GAME_ENDED)
        assert len(ended_events) == 1
        assert ended_events[0].data["score"] == 0


class TestGameEngineHandleCommand:
    def test_quit_command_stops_game(self):
        engine = GameEngine(MockUIAdapter(), MockAudioAdapter())
        engine.start()
        
        engine.handle_command('q')
        
        assert engine.is_running is False

    def test_quit_command_case_insensitive(self):
        engine = GameEngine(MockUIAdapter(), MockAudioAdapter())
        engine.start()
        
        engine.handle_command('Q')
        
        assert engine.is_running is False

    def test_record_command_starts_streaming(self):
        audio = MockAudioAdapter()
        engine = GameEngine(MockUIAdapter(), audio)
        engine.start()
        
        engine.handle_command('r')
        
        assert audio.is_streaming() is True
        assert audio.start_count == 1

    def test_record_command_toggles_streaming(self):
        audio = MockAudioAdapter()
        engine = GameEngine(MockUIAdapter(), audio)
        engine.start()
        
        engine.handle_command('r')  # Start
        engine.handle_command('r')  # Stop
        
        assert audio.is_streaming() is False
        assert audio.stop_count == 1


class TestGameEngineNoteChecking:
    def test_correct_note_increments_score(self):
        ui = MockUIAdapter()
        audio = MockAudioAdapter()
        engine = GameEngine(ui, audio)
        engine.start()

        engine.handle_command('r')  # Start streaming
        target = engine.current_note
        audio.simulate_detection(target, 4, 440.0)  # Simulate callback during streaming
        
        assert engine.score == 1

    def test_correct_note_emits_correct_event(self):
        ui = MockUIAdapter()
        audio = MockAudioAdapter()
        engine = GameEngine(ui, audio)
        engine.start()

        engine.handle_command('r')  # Start streaming
        target = engine.current_note
        audio.simulate_detection(target, 4, 440.0)  # Simulate callback
        
        correct_events = ui.get_events_of_type(EventType.NOTE_CORRECT)
        assert len(correct_events) == 1
        assert correct_events[0].data["played"] == target
        assert correct_events[0].data["expected"] == target

    def test_correct_note_chooses_new_target(self):
        audio = MockAudioAdapter()
        engine = GameEngine(MockUIAdapter(), audio)
        engine.start()
        
        first_target = engine.current_note
        
        engine.handle_command('r')  # Start streaming
        audio.simulate_detection(first_target, 4, 440.0)  # Simulate correct note
        
        # New target should be chosen (might be same by chance, but event should fire)
        assert engine.current_note in C_MAJOR_SCALE

    def test_incorrect_note_does_not_increment_score(self):
        audio = MockAudioAdapter()
        engine = GameEngine(MockUIAdapter(), audio)
        engine.start()
        
        # Pick a note that's definitely not the target
        wrong_note = "X"  # Not in scale
        
        engine.handle_command('r')  # Start streaming
        audio.simulate_detection(wrong_note, 4, 440.0)  # Simulate wrong note
        
        assert engine.score == 0

    def test_incorrect_note_emits_incorrect_event(self):
        ui = MockUIAdapter()
        audio = MockAudioAdapter()
        engine = GameEngine(ui, audio)
        engine.start()

        wrong_note = "X"

        engine.handle_command('r')  # Start streaming
        target = engine.current_note
        audio.simulate_detection(wrong_note, 4, 440.0)  # Simulate wrong note
        
        incorrect_events = ui.get_events_of_type(EventType.NOTE_INCORRECT)
        assert len(incorrect_events) == 1
        assert incorrect_events[0].data["played"] == wrong_note
        assert incorrect_events[0].data["expected"] == target


class TestGameEngineStreaming:
    def test_streaming_emits_started_event(self):
        ui = MockUIAdapter()
        engine = GameEngine(ui, MockAudioAdapter())
        engine.start()
        
        engine.handle_command('r')
        
        started_events = ui.get_events_of_type(EventType.STREAMING_STARTED)
        assert len(started_events) == 1

    def test_streaming_emits_stopped_event(self):
        ui = MockUIAdapter()
        audio = MockAudioAdapter()
        engine = GameEngine(ui, audio)
        engine.start()
        
        engine.handle_command('r')
        engine.handle_command('r')
        
        stopped_events = ui.get_events_of_type(EventType.STREAMING_STOPPED)
        assert len(stopped_events) == 1

    def test_realtime_detection_emits_event(self):
        ui = MockUIAdapter()
        audio = MockAudioAdapter()
        engine = GameEngine(ui, audio)
        engine.start()
        
        engine.handle_command('r')
        audio.simulate_detection("C", 4, 261.63)
        
        detected_events = ui.get_events_of_type(EventType.NOTE_DETECTED)
        assert len(detected_events) >= 1
        assert detected_events[-1].data["note"] == "C"
        assert detected_events[-1].data["octave"] == 4
        assert detected_events[-1].data["freq"] == 261.63


class TestGameEngineEventListeners:
    def test_add_event_listener(self):
        engine = GameEngine(MockUIAdapter(), MockAudioAdapter())
        received_events = []
        
        engine.add_event_listener(lambda e: received_events.append(e))
        engine.start()
        
        assert len(received_events) > 0
        assert any(e.type == EventType.GAME_STARTED for e in received_events)

    def test_multiple_listeners(self):
        engine = GameEngine(MockUIAdapter(), MockAudioAdapter())
        listener1_events = []
        listener2_events = []
        
        engine.add_event_listener(lambda e: listener1_events.append(e))
        engine.add_event_listener(lambda e: listener2_events.append(e))
        engine.start()
        
        assert len(listener1_events) == len(listener2_events)


class TestGameEngineRun:
    def test_run_processes_commands_until_quit(self):
        ui = MockUIAdapter()
        ui.queue_commands('r', 'r', 'q')
        audio = MockAudioAdapter()
        
        engine = GameEngine(ui, audio)
        engine.run()
        
        assert engine.is_running is False
        assert audio.start_count == 1
        assert audio.stop_count >= 1

    def test_run_cleans_up_on_exit(self):
        ui = MockUIAdapter()
        ui.queue_commands('q')
        
        engine = GameEngine(ui, MockAudioAdapter())
        engine.run()
        
        assert ui.cleaned_up is True
