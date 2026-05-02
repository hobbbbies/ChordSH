"""Integration tests for complete game workflows."""
import pytest
import threading
import time
from core.interval_game import IntervalGame
from core.events import EventType
from conftest import MockUIAdapter, MockAudioAdapter


class TestGameRunIntegration:
    def test_run_complete_game_flow(self):
        """Test a complete game from start to finish."""
        ui = MockUIAdapter()
        ui.queue_commands('r', 'q', 'q')  # Start, then quit
        audio = MockAudioAdapter()
        
        game = IntervalGame(ui, audio)
        game.run()
        
        assert game.is_running is False
        assert audio.start_count >= 1
    
    def test_run_with_correct_note_played(self):
        """Test that playing the correct note increments score and advances round."""
        ui = MockUIAdapter()
        ui.queue_commands('r')  # Only queue 'r' to start, we'll manually stop later
        audio = MockAudioAdapter()
        
        game = IntervalGame(ui, audio)
        
        # Run game in background thread
        def run_game():
            game.run()
        
        game_thread = threading.Thread(target=run_game, daemon=True)
        game_thread.start()
        
        # Wait for streaming to start and target note to be set
        time.sleep(0.1)
        max_wait = 2.0
        start_time = time.time()
        while game.current_note is None and (time.time() - start_time) < max_wait:
            time.sleep(0.05)
        
        assert game.current_note is not None, "Target note should be set"
        
        # Simulate playing the correct note
        target_note = game.current_note
        audio.simulate_detection(target_note, 4, 440.0)
        
        # Wait for score update
        time.sleep(0.2)
        
        # Verify score increased
        assert game.score == 1, "Score should increment after correct note"
        
        # Verify correct note event was emitted
        correct_events = ui.get_events_of_type(EventType.NOTE_CORRECT)
        assert len(correct_events) >= 1, "Should emit NOTE_CORRECT event"
        
        # Now stop the game manually
        game.stop()
        
        # Clean up
        game_thread.join(timeout=2.0)
    