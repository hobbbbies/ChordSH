"""Tests for adapters (curses_ui, sounddevice_audio)"""
import pytest
from unittest.mock import Mock, MagicMock, patch
import queue
import numpy as np

from core.events import GameEvent, EventType


class TestCursesUIAdapter:
    """Tests for CursesUIAdapter using mocked curses."""
    
    @pytest.fixture
    def mock_stdscr(self):
        """Create a mock curses window."""
        stdscr = MagicMock()
        stdscr.getmaxyx.return_value = (24, 80)
        stdscr.getch.return_value = -1
        return stdscr
    
    @pytest.fixture
    def adapter(self, mock_stdscr):
        """Create adapter with mocked stdscr."""
        from adapters.curses_ui import CursesUIAdapter
        return CursesUIAdapter(mock_stdscr)
    
    @patch('adapters.curses_ui.curses')
    def test_init_sets_up_curses(self, mock_curses, adapter, mock_stdscr):
        adapter.init()
        
        mock_curses.cbreak.assert_called()
        mock_curses.noecho.assert_called()
        mock_stdscr.keypad.assert_called_with(True)
        mock_stdscr.clear.assert_called()
        mock_stdscr.refresh.assert_called()
    
    @patch('adapters.curses_ui.curses')
    def test_cleanup_restores_terminal(self, mock_curses, adapter, mock_stdscr):
        adapter.cleanup()
        
        mock_curses.nocbreak.assert_called()
        mock_curses.echo.assert_called()
        mock_stdscr.keypad.assert_called_with(False)
    
    def test_get_command_returns_none_when_no_input(self, adapter, mock_stdscr):
        mock_stdscr.getch.return_value = -1
        
        result = adapter.get_command()
        
        assert result is None
    
    def test_get_command_returns_char_on_input(self, adapter, mock_stdscr):
        mock_stdscr.getch.return_value = ord('r')
        
        result = adapter.get_command()
        
        assert result == 'r'
    
    def test_on_event_handles_message(self, adapter, mock_stdscr):
        event = GameEvent.message("Test message", row=1)
        
        adapter.on_event(event)
        
        mock_stdscr.addstr.assert_called()
        mock_stdscr.refresh.assert_called()
    
    def test_on_event_handles_new_target(self, adapter, mock_stdscr):
        event = GameEvent.new_target("C")
        
        adapter.on_event(event)
        
        # Should display target note
        calls = [str(c) for c in mock_stdscr.addstr.call_args_list]
        assert any("C" in c for c in calls)
    
    def test_on_event_handles_note_detected(self, adapter, mock_stdscr):
        event = GameEvent.note_detected("A", 4, 440.0)
        
        adapter.on_event(event)
        
        calls = [str(c) for c in mock_stdscr.addstr.call_args_list]
        assert any("A4" in c or "A" in c for c in calls)
    
    def test_on_event_handles_note_correct(self, adapter, mock_stdscr):
        event = GameEvent(EventType.NOTE_CORRECT, {"played": "C", "expected": "C"})
        
        adapter.on_event(event)
        
        calls = [str(c) for c in mock_stdscr.addstr.call_args_list]
        assert any("Success" in c for c in calls)
    
    def test_on_event_handles_note_incorrect(self, adapter, mock_stdscr):
        event = GameEvent(EventType.NOTE_INCORRECT, {"played": "D", "expected": "C"})
        
        adapter.on_event(event)
        
        calls = [str(c) for c in mock_stdscr.addstr.call_args_list]
        assert any("Wrong" in c for c in calls)
    
    def test_on_event_handles_streaming_started(self, adapter, mock_stdscr):
        event = GameEvent(EventType.STREAMING_STARTED)
        
        adapter.on_event(event)
        
        calls = [str(c) for c in mock_stdscr.addstr.call_args_list]
        assert any("Streaming" in c for c in calls)
    
    def test_on_event_handles_game_ended(self, adapter, mock_stdscr):
        event = GameEvent(EventType.GAME_ENDED, {"score": 5})
        
        adapter.on_event(event)
        
        calls = [str(c) for c in mock_stdscr.addstr.call_args_list]
        assert any("5" in c for c in calls)


class TestSoundDeviceAudioAdapter:
    """Tests for SoundDeviceAudioAdapter."""
    
    @pytest.fixture
    def adapter(self):
        """Create adapter with default settings."""
        from adapters.sounddevice_audio import SoundDeviceAudioAdapter
        return SoundDeviceAudioAdapter(samplerate=44100)
    
    def test_initial_state_not_streaming(self, adapter):
        assert adapter.is_streaming() is False
    
    def test_stop_stream_when_not_streaming_returns_none(self, adapter):
        result = adapter.stop_stream()
        
        assert result is None
    
    @patch('adapters.sounddevice_audio.sd.InputStream')
    def test_start_stream_sets_streaming(self, mock_input_stream, adapter):
        mock_input_stream.return_value.__enter__ = Mock()
        mock_input_stream.return_value.__exit__ = Mock()
        
        callback = Mock()
        adapter.start_stream(callback)
        
        # Give thread time to start
        import time
        time.sleep(0.1)
        
        assert adapter.is_streaming() is True
        
        adapter.stop_stream()
    
    @patch('adapters.sounddevice_audio.sd.InputStream')
    def test_stop_stream_stops_streaming(self, mock_input_stream, adapter):
        mock_input_stream.return_value.__enter__ = Mock()
        mock_input_stream.return_value.__exit__ = Mock()
        
        adapter.start_stream(Mock())
        import time
        time.sleep(0.1)
        
        adapter.stop_stream()
        
        assert adapter.is_streaming() is False
    
    def test_drain_queue_clears_audio_data(self, adapter):
        # Add some data to queue
        adapter._audio_queue.put(np.zeros(100))
        adapter._audio_queue.put(np.zeros(100))
        
        adapter._drain_queue()
        
        assert adapter._audio_queue.empty()


class TestSoundDeviceAudioAdapterIntegration:
    """Integration tests that require actual audio hardware (skipped in CI)."""
    
    @pytest.fixture
    def adapter(self):
        from adapters.sounddevice_audio import SoundDeviceAudioAdapter
        return SoundDeviceAudioAdapter()
    
    @pytest.mark.skip(reason="Requires audio hardware")
    def test_real_audio_streaming(self, adapter):
        """Manual test - requires microphone."""
        results = []
        
        def on_result(note, freq, chord_name):
            results.append((note, freq, chord_name))
        
        adapter.start_stream(on_result)
        
        import time
        time.sleep(3)  # Record for 3 seconds
        
        last_result = adapter.stop_stream()
        
        assert last_result is not None or len(results) > 0
    
    def test_receives_new_target_note_event(self, adapter):
        """Audio adapter should receive and store NEW_TARGET_NOTE events."""
        event = GameEvent.new_target("C", "I")
        
        adapter.on_event(event)
        
        assert adapter._target_note == "C"
        assert adapter._target_interval == "I"
    
    def test_ignores_other_events(self, adapter):
        """Audio adapter should ignore non-NEW_TARGET_NOTE events."""
        adapter._target_note = "D"
        adapter._target_interval = "II"
        
        # Send a different event type
        event = GameEvent(EventType.GAME_STARTED)
        adapter.on_event(event)
        
        # Target should remain unchanged
        assert adapter._target_note == "D"
        assert adapter._target_interval == "II"
