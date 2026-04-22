"""Integration tests for complete game workflows."""
import pytest
import threading
import time
from core.engine import GameEngine
from core.events import EventType
from tests.test_engine import MockUIAdapter, MockAudioAdapter


class TestGameRunIntegration:
    def test_run_complete_game_flow(self):
        """Test a complete game from start to finish."""
        ui = MockUIAdapter()
        ui.queue_commands('r', 'q', 'q')  # Start, then quit
        audio = MockAudioAdapter()
        
        engine = GameEngine(ui, audio)
        engine.run()
        
        assert engine.is_running is False
        assert audio.start_count >= 1
    
    def test_run_with_correct_note_played(self):
        """Test that playing the correct note increments score and advances round."""
        ui = MockUIAdapter()
        ui.queue_commands('r')  # Only queue 'r' to start, we'll manually stop later
        audio = MockAudioAdapter()
        
        engine = GameEngine(ui, audio)
        
        # Run engine in background thread
        def run_engine():
            engine.run()
        
        engine_thread = threading.Thread(target=run_engine, daemon=True)
        engine_thread.start()
        
        # Wait for streaming to start and target note to be set
        time.sleep(0.1)
        max_wait = 2.0
        start_time = time.time()
        while engine.current_note is None and (time.time() - start_time) < max_wait:
            time.sleep(0.05)
        
        assert engine.current_note is not None, "Target note should be set"
        
        # Simulate playing the correct note
        target_note = engine.current_note
        audio.simulate_detection(target_note, 4, 440.0)
        
        # Wait for score update
        time.sleep(0.2)
        
        # Verify score increased
        assert engine.score == 1, "Score should increment after correct note"
        
        # Verify correct note event was emitted
        correct_events = ui.get_events_of_type(EventType.NOTE_CORRECT)
        assert len(correct_events) >= 1, "Should emit NOTE_CORRECT event"
        
        # Now stop the engine manually
        engine.stop()
        
        # Clean up
        engine_thread.join(timeout=2.0)
    