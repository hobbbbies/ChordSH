"""
Web UI adapter stub - shows how to integrate with a web platform.

This is a skeleton showing the pattern. You would implement this
with your web framework of choice (FastAPI + WebSocket, Flask-SocketIO, etc.)
"""
from typing import Any, Callable
from core.events import GameEvent, EventType


class WebUIAdapter:
    """
    Web-based UI adapter (stub).
    
    In a real implementation:
    - on_event() sends JSON to the browser via WebSocket
    - get_command() / wait_for_command() receive messages from WebSocket
    - The browser renders the UI based on events
    
    Example with FastAPI WebSocket:
    
        @app.websocket("/game")
        async def game_ws(websocket: WebSocket):
            await websocket.accept()
            
            ui = WebUIAdapter(websocket)
            audio = WebAudioAdapter(websocket)  # Audio from browser
            engine = GameEngine(ui, audio)
            
            engine.start()
            async for message in websocket.iter_json():
                engine.handle_command(message["command"])
                if not engine.is_running:
                    break
            engine.stop()
    """
    
    def __init__(self, websocket):  # websocket: WebSocket
        self._ws = websocket
        self._command_queue: list[str] = []
    
    def init(self) -> None:
        """Send initial state to browser."""
        # await self._ws.send_json({"type": "init"})
        pass
    
    def cleanup(self) -> None:
        """Close connection."""
        # await self._ws.close()
        pass
    
    def on_event(self, event: GameEvent) -> None:
        """
        Send event to browser as JSON.
        
        Browser receives:
        {
            "type": "NOTE_DETECTED",
            "data": {"note": "C", "freq": 261.63, "chord_name": None}
        }
        """
        message = {
            "type": event.type.name,
            "data": event.data
        }
        # await self._ws.send_json(message)
        print(f"[WebUI] Would send: {message}")
    
    def get_command(self) -> str | None:
        """Check for pending command (non-blocking)."""
        if self._command_queue:
            return self._command_queue.pop(0)
        return None
    
    def wait_for_command(self) -> str:
        """
        In async context, this would be:
        message = await self._ws.receive_json()
        return message["command"]
        """
        raise NotImplementedError("Use async pattern for web")
    
    def receive_command(self, cmd: str) -> None:
        """Called when browser sends a command."""
        self._command_queue.append(cmd)


class WebAudioAdapter:
    """
    Audio adapter for browser-based audio capture (stub).
    
    In a real implementation:
    - Browser captures audio via Web Audio API
    - Audio chunks sent to server via WebSocket
    - Server analyzes and returns results
    
    Alternatively, audio analysis could happen client-side
    with results sent to server.
    """
    
    def __init__(self, websocket):
        self._ws = websocket
        self._streaming = False
        self._last_result = None
        self._on_result: Callable[[str, float, str | None], None] | None = None
    
    def start_stream(self, on_result: Callable[[str, float, str | None], None]) -> None:
        """Tell browser to start capturing audio."""
        self._streaming = True
        self._on_result = on_result
        # await self._ws.send_json({"type": "start_audio"})
    
    def stop_stream(self) -> tuple[str, float, str | None] | None:
        """Tell browser to stop capturing."""
        self._streaming = False
        # await self._ws.send_json({"type": "stop_audio"})
        return self._last_result
    
    def is_streaming(self) -> bool:
        return self._streaming
    
    def receive_audio_result(self, note: str, freq: float, chord_name: str | None = None) -> None:
        """Called when browser sends analyzed audio result."""
        self._last_result = (note, freq, chord_name)
        if self._on_result:
            self._on_result(note, freq, chord_name)
