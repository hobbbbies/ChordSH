"""Integration tests for complete game workflows."""
import pytest
from core.engine import GameEngine
from tests.test_engine import MockUIAdapter, MockAudioAdapter


class TestGameRunIntegration:
    def test_run_complete_game_flow(self):
        """Test a complete game from start to finish."""
        ui = MockUIAdapter()
        ui.queue_commands('r', 'q')  # Start, then quit
        audio = MockAudioAdapter()
        
        engine = GameEngine(ui, audio)
        engine.run()
        
        assert engine.is_running is False
        assert audio.start_count >= 1