"""
Master engine - manages the game selection menu and runs individual games.

The MasterEngine owns the UI lifecycle (init/cleanup) and presents a
top-level menu for selecting which game to play. Individual game engines
run as blocking calls and return control here when the player quits.
"""
from .events import GameEvent, EventType
from .protocols import UIAdapter, AudioAdapter
from .interval_game import IntervalGame


class MasterEngine:
    """
    Top-level engine that presents a game selection menu and
    delegates to individual game engines.
    
    Usage:
        engine = MasterEngine(ui, audio)
        engine.run()  # blocking loop
    """
    
    def __init__(self, ui: UIAdapter, audio: AudioAdapter):
        self._ui = ui
        self._audio = audio
        self._running = False
        self._games: list[type] = [IntervalGame]
    
    def run(self) -> None:
        """
        Main loop: show menu -> run selected game -> repeat.
        Exits when user presses 'q' from the master menu.
        """
        self._ui.init()
        self._running = True
        try:
            while self._running:
                # Show master menu
                game_names = [g.NAME for g in self._games]
                self._ui.on_event(GameEvent.master_menu(game_names))
                
                selection = self._ui.wait_for_selection()
                
                if selection == "q":
                    break
                
                idx = int(selection)
                if 0 <= idx < len(self._games):
                    game_cls = self._games[idx]
                    game = game_cls(self._ui, self._audio)
                    game.run()
        finally:
            self._running = False
            self._ui.cleanup()
