"""Tests for protocol compliance."""
import pytest
from typing import get_type_hints
from core.protocols import UIAdapter, AudioAdapter
from core.events import GameEvent, EventType


class TestUIAdapterProtocol:
    """Verify UIAdapter protocol requirements."""
    
    def test_protocol_has_on_event(self):
        assert hasattr(UIAdapter, 'on_event')
    
    def test_protocol_has_get_command(self):
        assert hasattr(UIAdapter, 'get_command')
    
    def test_protocol_has_wait_for_command(self):
        assert hasattr(UIAdapter, 'wait_for_command')
    
    def test_protocol_has_init(self):
        assert hasattr(UIAdapter, 'init')
    
    def test_protocol_has_cleanup(self):
        assert hasattr(UIAdapter, 'cleanup')
    
    def test_curses_adapter_implements_protocol(self):
        """Verify CursesUIAdapter has all required methods."""
        from adapters.curses_ui import CursesUIAdapter
        
        # Check method existence
        assert hasattr(CursesUIAdapter, 'on_event')
        assert hasattr(CursesUIAdapter, 'get_command')
        assert hasattr(CursesUIAdapter, 'wait_for_command')
        assert hasattr(CursesUIAdapter, 'init')
        assert hasattr(CursesUIAdapter, 'cleanup')


class TestAudioAdapterProtocol:
    """Verify AudioAdapter protocol requirements."""
    
    def test_protocol_has_start_stream(self):
        assert hasattr(AudioAdapter, 'start_stream')
    
    def test_protocol_has_stop_stream(self):
        assert hasattr(AudioAdapter, 'stop_stream')
    
    def test_protocol_has_is_streaming(self):
        assert hasattr(AudioAdapter, 'is_streaming')
    
    def test_sounddevice_adapter_implements_protocol(self):
        """Verify SoundDeviceAudioAdapter has all required methods."""
        from adapters.sounddevice_audio import SoundDeviceAudioAdapter
        
        assert hasattr(SoundDeviceAudioAdapter, 'start_stream')
        assert hasattr(SoundDeviceAudioAdapter, 'stop_stream')
        assert hasattr(SoundDeviceAudioAdapter, 'is_streaming')


class TestMockAdapterCompliance:
    """Test that mock adapters can be used with GameEngine."""
    
    def test_mock_ui_works_with_engine(self):
        from core.engine import GameEngine
        
        class MinimalUI:
            def on_event(self, event): pass
            def get_command(self): return None
            def wait_for_command(self): return 'q'
            def wait_for_selection(self, items): return '0'
            def init(self): pass
            def cleanup(self): pass
        
        class MinimalAudio:
            def start_stream(self, cb): pass
            def stop_stream(self): return None
            def is_streaming(self): return False
        
        # Should not raise
        engine = GameEngine(MinimalUI(), MinimalAudio())
        engine.run()
    
    def test_dict_based_ui_adapter(self):
        """Show that any object with correct methods works."""
        from core.engine import GameEngine
        
        events = []
        
        class DictUI:
            def on_event(self, event):
                events.append({"type": event.type.name, "data": event.data})
            def get_command(self): return None
            def wait_for_command(self): return 'q'
            def wait_for_selection(self, items): return '0'
            def init(self): pass
            def cleanup(self): pass
        
        class StubAudio:
            def start_stream(self, cb): pass
            def stop_stream(self): return None
            def is_streaming(self): return False
        
        engine = GameEngine(DictUI(), StubAudio())
        engine.run()
        
        # Events should have been captured as dicts
        assert len(events) > 0
        # Event order: GAME_STARTING → GAME_STARTED → CONFIG_SETUP
        assert events[0]["type"] == "GAME_STARTING"
        # GAME_STARTED is emitted by start(), CONFIG_SETUP by config_setup()
        # But config_setup is called first in menu_init, so check both exist
        event_types = [e["type"] for e in events]
        assert "GAME_STARTING" in event_types
        assert "CONFIG_SETUP" in event_types
