from core.master_engine import MasterEngine
from core.events import EventType
from conftest import MockUIAdapter, MockAudioAdapter
import pytest

class TestMasterEngineIntegration:
    def test_master_engine_run_and_quit(self):
        ui = MockUIAdapter()
        audio = MockAudioAdapter()
        ui.wait_for_selection = lambda items, use_enter_key=True: "q"
        engine = MasterEngine(ui, audio)
        engine.run()
        assert engine._running is False
        assert ui.cleaned_up is True
    
    def test_master_engine_run_and_select_game(self):
        ui = MockUIAdapter()
        audio = MockAudioAdapter()
        
        call_count = 0
        def fake_selection(items, use_enter_key=True):
            nonlocal call_count
            call_count += 1
            return "0" if call_count == 1 else "q"

        ui.wait_for_selection = fake_selection
        engine = MasterEngine(ui, audio)
        engine.run()

        # IntervalGame emitted CONFIG_SETUP (scale selection screen)
        assert len(ui.get_events_of_type(EventType.CONFIG_SETUP)) >= 1
        # Master menu was shown twice: before game + after game returned
        assert len(ui.get_events_of_type(EventType.MASTER_MENU)) == 2
        
        assert engine._running is False
        assert ui.cleaned_up is True
