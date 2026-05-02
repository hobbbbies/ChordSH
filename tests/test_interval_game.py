"""Tests for core/interval_game.py — IntervalGame engine."""
import time
import pytest
from unittest.mock import Mock, MagicMock, call
from core.interval_game import IntervalGame, C_MAJOR_SCALE, G_MAJOR_SCALE, ScreenState
from core.events import GameEvent, EventType
from conftest import MockUIAdapter, MockAudioAdapter


class TestIntervalGameInit:
    def test_creates_with_adapters(self):
        ui = MockUIAdapter()
        audio = MockAudioAdapter()
        
        game = IntervalGame(ui, audio)
        
        assert game._ui is ui
        assert game._audio is audio

    def test_default_scale_is_c_major(self):
        game = IntervalGame(MockUIAdapter(), MockAudioAdapter())
        
        assert game._scale == C_MAJOR_SCALE

    def test_custom_scale(self):
        custom_scale = ["C", "D", "E"]
        game = IntervalGame(MockUIAdapter(), MockAudioAdapter(), scale=custom_scale)
        
        assert game._scale == custom_scale

    def test_initial_state(self):
        game = IntervalGame(MockUIAdapter(), MockAudioAdapter())
        
        assert game.is_running is False
        assert game.current_note is None
        assert game.score == 0


class TestIntervalGameStart:
    def test_start_does_not_initialize_ui(self):
        ui = MockUIAdapter()
        game = IntervalGame(ui, MockAudioAdapter())
        
        game.start()
        
        # UI lifecycle is managed by MasterEngine, not individual games
        assert ui.initialized is False

    def test_start_sets_running(self):
        game = IntervalGame(MockUIAdapter(), MockAudioAdapter())
        
        game.start()
        
        assert game.is_running is True

    def test_start_emits_game_started_event(self):
        ui = MockUIAdapter()
        game = IntervalGame(ui, MockAudioAdapter())
        
        game.start_game()
        
        started_events = ui.get_events_of_type(EventType.GAME_STARTED)
        assert len(started_events) == 1

    def test_start_does_not_choose_target_note(self):
        ui = MockUIAdapter()
        game = IntervalGame(ui, MockAudioAdapter())
        
        game.start()
        
        # Target note is only chosen when a round starts (on 'r' command)
        assert game.current_note is None
        target_events = ui.get_events_of_type(EventType.NEW_TARGET_NOTE)
        assert len(target_events) == 0
    
    def test_starting_round_chooses_target_note(self):
        ui = MockUIAdapter()
        audio = MockAudioAdapter()
        game = IntervalGame(ui, audio)
        
        game.start()
        game.handle_command('r')
        
        # After starting recording, a round begins and target note is chosen
        assert game.current_note in C_MAJOR_SCALE
        target_events = ui.get_events_of_type(EventType.NEW_TARGET_NOTE)
        assert len(target_events) == 1
        assert target_events[0].data["note"] == game.current_note


class TestIntervalGameStop:
    def test_stop_sets_not_running(self):
        game = IntervalGame(MockUIAdapter(), MockAudioAdapter())
        game.start()
        
        game.stop()
        
        assert game.is_running is False

    def test_stop_does_not_cleanup_ui(self):
        ui = MockUIAdapter()
        game = IntervalGame(ui, MockAudioAdapter())
        game.start()
        
        game.stop()
        
        # UI lifecycle is managed by MasterEngine, not individual games
        assert ui.cleaned_up is False

    def test_stop_stops_audio_stream(self):
        audio = MockAudioAdapter()
        game = IntervalGame(MockUIAdapter(), audio)
        game.start()
        
        game.stop()
        
        assert audio.stop_count >= 1

    def test_stop_emits_game_ended_event(self):
        ui = MockUIAdapter()
        game = IntervalGame(ui, MockAudioAdapter())
        game.start()
        
        game.stop()
        
        ended_events = ui.get_events_of_type(EventType.GAME_ENDED)
        assert len(ended_events) == 1
        assert ended_events[0].data["score"] == 0


class TestIntervalGameHandleCommand:
    def test_quit_command_stops_game(self):
        game = IntervalGame(MockUIAdapter(), MockAudioAdapter())
        game.start()
        
        game.handle_command('q')
        
        assert game.is_running is False

    def test_quit_command_case_insensitive(self):
        game = IntervalGame(MockUIAdapter(), MockAudioAdapter())
        game.start()
        
        game.handle_command('Q')
        
        assert game.is_running is False

    def test_record_command_starts_streaming(self):
        audio = MockAudioAdapter()
        game = IntervalGame(MockUIAdapter(), audio)
        game.start()
        
        game.handle_command('r')
        
        assert audio.is_streaming() is True
        assert audio.start_count == 1

    def test_record_command_toggles_streaming(self):
        audio = MockAudioAdapter()
        game = IntervalGame(MockUIAdapter(), audio)
        game.start()
        
        game.handle_command('r')  # Start
        game.handle_command('r')  # Stop
        
        assert audio.is_streaming() is False
        assert audio.stop_count == 1


class TestIntervalGameNoteChecking:
    def test_correct_note_increments_score(self):
        ui = MockUIAdapter()
        audio = MockAudioAdapter()
        game = IntervalGame(ui, audio)
        game.start()

        game.handle_command('r')  # Start streaming
        target = game.current_note
        audio.simulate_detection(target, 4, 440.0)  # Simulate callback during streaming
        
        assert game.score == 1

    def test_correct_note_emits_correct_event(self):
        ui = MockUIAdapter()
        audio = MockAudioAdapter()
        game = IntervalGame(ui, audio)
        game.start()

        game.handle_command('r')  # Start streaming
        target = game.current_note
        audio.simulate_detection(target, 4, 440.0)  # Simulate callback
        
        correct_events = ui.get_events_of_type(EventType.NOTE_CORRECT)
        assert len(correct_events) == 1
        assert correct_events[0].data["played"] == target
        assert correct_events[0].data["expected"] == game._note_to_interval(target)

    def test_correct_note_chooses_new_target(self):
        audio = MockAudioAdapter()
        game = IntervalGame(MockUIAdapter(), audio)
        game.start()
        
        first_target = game.current_note
        
        game.handle_command('r')  # Start streaming
        audio.simulate_detection(first_target, 4, 440.0)  # Simulate correct note
        
        # New target should be chosen (might be same by chance, but event should fire)
        assert game.current_note in C_MAJOR_SCALE

    def test_incorrect_note_does_not_increment_score(self):
        audio = MockAudioAdapter()
        game = IntervalGame(MockUIAdapter(), audio)
        game.start()
        
        # Pick a note that's definitely not the target
        wrong_note = "X"  # Not in scale
        
        game.handle_command('r')  # Start streaming
        audio.simulate_detection(wrong_note, 4, 440.0)  # Simulate wrong note
        
        assert game.score == 0

    def test_incorrect_note_emits_incorrect_event(self):
        ui = MockUIAdapter()
        audio = MockAudioAdapter()
        game = IntervalGame(ui, audio)
        game.start()

        wrong_note = "X"

        game.handle_command('r')  # Start streaming
        target = game.current_note
        audio.simulate_detection(wrong_note, 4, 440.0)  # Simulate wrong note
        
        incorrect_events = ui.get_events_of_type(EventType.NOTE_INCORRECT)
        assert len(incorrect_events) == 1
        assert incorrect_events[0].data["played"] == wrong_note
        assert incorrect_events[0].data["expected"] == game._note_to_interval(target)


class TestIntervalGameStreaming:
    def test_streaming_emits_started_event(self):
        ui = MockUIAdapter()
        game = IntervalGame(ui, MockAudioAdapter())
        game.start()
        
        game.handle_command('r')
        
        started_events = ui.get_events_of_type(EventType.STREAMING_STARTED)
        assert len(started_events) == 1

    def test_streaming_emits_stopped_event(self):
        ui = MockUIAdapter()
        audio = MockAudioAdapter()
        game = IntervalGame(ui, audio)
        game.start()
        
        game.handle_command('r')
        game.handle_command('r')
        
        stopped_events = ui.get_events_of_type(EventType.STREAMING_STOPPED)
        assert len(stopped_events) == 1

    def test_realtime_detection_emits_event(self):
        ui = MockUIAdapter()
        audio = MockAudioAdapter()
        game = IntervalGame(ui, audio)
        game.start()
        
        game.handle_command('r')
        audio.simulate_detection("C", 261.63)
        
        detected_events = ui.get_events_of_type(EventType.NOTE_DETECTED)
        assert len(detected_events) >= 1
        assert detected_events[-1].data["note"] == "C"
        assert detected_events[-1].data["freq"] == 261.63


class TestIntervalGameEventListeners:
    def test_add_event_listener(self):
        game = IntervalGame(MockUIAdapter(), MockAudioAdapter())
        received_events = []
        
        game.add_event_listener(lambda e: received_events.append(e))
        game.start_game()
        
        assert len(received_events) > 0
        assert any(e.type == EventType.GAME_STARTED for e in received_events)

    def test_multiple_listeners(self):
        game = IntervalGame(MockUIAdapter(), MockAudioAdapter())
        listener1_events = []
        listener2_events = []
        
        game.add_event_listener(lambda e: listener1_events.append(e))
        game.add_event_listener(lambda e: listener2_events.append(e))
        game.start()
        
        assert len(listener1_events) == len(listener2_events)


class TestIntervalGameRun:
    def test_run_processes_commands_until_quit(self):
        ui = MockUIAdapter()
        ui.queue_commands('r', 'r', 'q')
        audio = MockAudioAdapter()
        
        game = IntervalGame(ui, audio)
        game.run()
        
        assert game.is_running is False
        assert audio.start_count == 1
        assert audio.stop_count >= 1

    def test_in_round_boolean_tracking(self):
        ui = MockUIAdapter()
        audio = MockAudioAdapter()
        
        game = IntervalGame(ui, audio)
        
        # Before starting
        assert game._in_round is False
        
        game.start()
        game.handle_command('r')
        # After starting round
        assert game._in_round is True
        
        game.handle_command('r')
        
        # After ending round
        assert game._in_round is False
        
    def test_run_does_not_cleanup_ui_on_exit(self):
        ui = MockUIAdapter()
        ui.queue_commands('q')
        
        game = IntervalGame(ui, MockAudioAdapter())
        game.run()
        
        # UI lifecycle is managed by MasterEngine, not individual games
        assert ui.cleaned_up is False

class TestIntervalGameInterruptibleSleep:
    def test_interruptible_sleep_exits_early_on_quit(self):
        ui = MockUIAdapter()
        ui.queue_commands('q')  # Queue quit command
        audio = MockAudioAdapter()
        
        game = IntervalGame(ui, audio)
        game.start()
        game._screen_state = ScreenState.GAME
        game._in_round = True  # Simulate being in a round
        
        # Sleep should exit early when 'q' is detected
        start_time = time.time()
        game._interruptible_sleep(1.0)
        elapsed = time.time() - start_time
        
        # Should exit much faster than 1 second (allow 0.3s for polling overhead)
        assert elapsed < 0.3, f"Sleep took {elapsed:.2f}s, expected < 0.3s"
        # Round should have been ended by the quit command
        assert game._in_round is False

    def test_interruptible_sleep_exits_early_on_record_input(self):
        ui = MockUIAdapter()
        ui.queue_commands('r')  # Queue record command
        audio = MockAudioAdapter()
        
        game = IntervalGame(ui, audio)
        game.start()
        game._screen_state = ScreenState.GAME
        game._in_round = True  # Simulate being in a round
        
        # Sleep should exit early when 'r' is detected
        start_time = time.time()
        game._interruptible_sleep(1.0)
        elapsed = time.time() - start_time
        
        # Should exit much faster than 1 second (allow 0.3s for polling overhead)
        assert elapsed < 0.3, f"Sleep took {elapsed:.2f}s, expected < 0.3s"
        # Round should have been ended by the quit command
        assert game._in_round is False

    def test_interruptible_sleep_continues_when_no_input(self):
        ui = MockUIAdapter()
        audio = MockAudioAdapter()
        
        game = IntervalGame(ui, audio)
        game.start()
        game._in_round = True  # Simulate being in a round
        
        # Sleep should complete normally when no input is detected
        start_time = time.time()
        game._interruptible_sleep(0.1)
        elapsed = time.time() - start_time
        
        # Should complete close to the requested duration
        assert 0.08 <= elapsed <= 0.12, f"Sleep took {elapsed:.2f}s, expected ~0.1s"
        # Round should still be active
        assert game._in_round is True
        
class TestIntervalGameConfigSetup:
    def test_config_setup_emits_config_setup_event(self):
        ui = MockUIAdapter()
        game = IntervalGame(ui, MockAudioAdapter())
        
        game.config_setup()
        
        config_events = ui.get_events_of_type(EventType.CONFIG_SETUP)
        assert len(config_events) == 1

    def test_config_setup_sets_scale(self):
        ui = MockUIAdapter()
        ui.wait_for_selection = lambda items: "1"  # Select second scale (G Major)
        game = IntervalGame(ui, MockAudioAdapter())
        
        game.config_setup()
        
        assert game._scale == G_MAJOR_SCALE
    