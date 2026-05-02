"""Tests for core/master_engine.py — MasterEngine menu and game delegation."""
import pytest
from unittest.mock import patch, MagicMock
from core.master_engine import MasterEngine
from core.interval_game import IntervalGame
from core.events import GameEvent, EventType
from conftest import MockUIAdapter, MockAudioAdapter


# ---------- Helpers ----------

class FakeGame:
    """Minimal fake game for testing MasterEngine delegation."""
    NAME = "Fake Game"
    DESCRIPTION = "A fake game for testing"
    
    def __init__(self, ui, audio):
        self.ui = ui
        self.audio = audio
        self.run_called = False
    
    def run(self):
        self.run_called = True


class FakeGameSecond:
    """Second fake game to test multi-game menu."""
    NAME = "Second Game"
    DESCRIPTION = "Another fake game"
    
    def __init__(self, ui, audio):
        self.ui = ui
        self.audio = audio
        self.run_called = False
    
    def run(self):
        self.run_called = True


# ---------- Init ----------

class TestMasterEngineInit:
    def test_creates_with_adapters(self):
        ui = MockUIAdapter()
        audio = MockAudioAdapter()
        
        engine = MasterEngine(ui, audio)
        
        assert engine._ui is ui
        assert engine._audio is audio

    def test_initial_state(self):
        engine = MasterEngine(MockUIAdapter(), MockAudioAdapter())
        
        assert engine._running is False

    def test_default_games_list_contains_interval_game(self):
        engine = MasterEngine(MockUIAdapter(), MockAudioAdapter())
        
        assert IntervalGame in engine._games


# ---------- UI Lifecycle ----------

class TestMasterEngineUILifecycle:
    def test_run_initializes_ui(self):
        ui = MockUIAdapter()
        ui.queue_commands()  # No commands — wait_for_selection returns 'q' via wait_for_command fallback
        engine = MasterEngine(ui, MockAudioAdapter())
        # Patch wait_for_selection to return 'q' immediately
        ui.wait_for_selection = lambda items: "q"
        
        engine.run()
        
        assert ui.initialized is True

    def test_run_cleans_up_ui_on_exit(self):
        ui = MockUIAdapter()
        ui.wait_for_selection = lambda items: "q"
        engine = MasterEngine(ui, MockAudioAdapter())
        
        engine.run()
        
        assert ui.cleaned_up is True

    def test_run_cleans_up_ui_on_exception(self):
        ui = MockUIAdapter()
        ui.wait_for_selection = lambda items: (_ for _ in ()).throw(RuntimeError("boom"))
        engine = MasterEngine(ui, MockAudioAdapter())
        
        with pytest.raises(RuntimeError):
            engine.run()
        
        assert ui.cleaned_up is True


# ---------- Menu Display ----------

class TestMasterEngineMenu:
    def test_run_emits_master_menu_event(self):
        ui = MockUIAdapter()
        ui.wait_for_selection = lambda items: "q"
        engine = MasterEngine(ui, MockAudioAdapter())
        
        engine.run()
        
        menu_events = ui.get_events_of_type(EventType.MASTER_MENU)
        assert len(menu_events) == 1

    def test_menu_event_contains_game_names(self):
        ui = MockUIAdapter()
        ui.wait_for_selection = lambda items: "q"
        engine = MasterEngine(ui, MockAudioAdapter())
        
        engine.run()
        
        menu_events = ui.get_events_of_type(EventType.MASTER_MENU)
        assert menu_events[0].data["games"] == ["Interval Game", "Looper"]

    def test_menu_event_contains_multiple_game_names(self):
        ui = MockUIAdapter()
        ui.wait_for_selection = lambda items: "q"
        engine = MasterEngine(ui, MockAudioAdapter())
        engine._games = [FakeGame, FakeGameSecond]
        
        engine.run()
        
        menu_events = ui.get_events_of_type(EventType.MASTER_MENU)
        assert menu_events[0].data["games"] == ["Fake Game", "Second Game"]


# ---------- Quit ----------

class TestMasterEngineQuit:
    def test_quit_from_menu_exits(self):
        ui = MockUIAdapter()
        ui.wait_for_selection = lambda items: "q"
        engine = MasterEngine(ui, MockAudioAdapter())
        
        engine.run()
        
        assert engine._running is False

    def test_quit_sets_running_false(self):
        ui = MockUIAdapter()
        ui.wait_for_selection = lambda items: "q"
        engine = MasterEngine(ui, MockAudioAdapter())
        
        engine.run()
        
        assert engine._running is False


# ---------- Game Selection & Delegation ----------

class TestMasterEngineGameDelegation:
    def test_selecting_game_runs_it(self):
        ui = MockUIAdapter()
        call_count = 0
        def fake_selection(items):
            nonlocal call_count
            call_count += 1
            return "0" if call_count == 1 else "q"
        ui.wait_for_selection = fake_selection
        
        engine = MasterEngine(ui, MockAudioAdapter())
        engine._games = [FakeGame]
        
        engine.run()
        
        # Menu should have been shown twice (before game + after game returns)
        menu_events = ui.get_events_of_type(EventType.MASTER_MENU)
        assert len(menu_events) == 2

    def test_game_receives_ui_and_audio(self):
        ui = MockUIAdapter()
        audio = MockAudioAdapter()
        captured_game = {}
        
        class CapturingGame:
            NAME = "Capturing"
            DESCRIPTION = "Captures constructor args"
            def __init__(self, ui, audio):
                captured_game["ui"] = ui
                captured_game["audio"] = audio
            def run(self):
                pass
        
        call_count = 0
        def fake_selection(items):
            nonlocal call_count
            call_count += 1
            return "0" if call_count == 1 else "q"
        ui.wait_for_selection = fake_selection
        
        engine = MasterEngine(ui, audio)
        engine._games = [CapturingGame]
        
        engine.run()
        
        assert captured_game["ui"] is ui
        assert captured_game["audio"] is audio

    def test_returns_to_menu_after_game_ends(self):
        ui = MockUIAdapter()
        games_run = 0
        
        class CountingGame:
            NAME = "Counter"
            DESCRIPTION = "Counts runs"
            def __init__(self, ui, audio):
                pass
            def run(self):
                nonlocal games_run
                games_run += 1
        
        call_count = 0
        def fake_selection(items):
            nonlocal call_count
            call_count += 1
            # Run game twice, then quit
            if call_count <= 2:
                return "0"
            return "q"
        ui.wait_for_selection = fake_selection
        
        engine = MasterEngine(ui, MockAudioAdapter())
        engine._games = [CountingGame]
        
        engine.run()
        
        assert games_run == 2
        # Menu shown 3 times: before game 1, before game 2, before quit
        menu_events = ui.get_events_of_type(EventType.MASTER_MENU)
        assert len(menu_events) == 3

    def test_invalid_selection_loops_back_to_menu(self):
        ui = MockUIAdapter()
        call_count = 0
        def fake_selection(items):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return "99"  # Out of range
            return "q"
        ui.wait_for_selection = fake_selection
        
        engine = MasterEngine(ui, MockAudioAdapter())
        engine._games = [FakeGame]
        
        engine.run()
        
        # Menu shown twice, no game run
        menu_events = ui.get_events_of_type(EventType.MASTER_MENU)
        assert len(menu_events) == 2
