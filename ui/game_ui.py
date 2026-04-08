import curses

class GameUI:
    """
    Handles all curses-based rendering and player-facing messages.

    Responsibilities:
      • Initialize curses environment and color scheme
      • Render the game board and player state
      • Display transient messages and status information
    """

    def __init__(self, stdscr) -> None:
        self._stdscr = stdscr


    # ---------- Initialization ----------

    def init_screen(self) -> None:
        """Initialize curses screen and visual style."""
        curses.cbreak()
        curses.noecho()
        self._stdscr.keypad(True)
        self._clear_screen()

    def _clear_screen(self) -> None:
        """Clear and refresh the screen."""
        self._stdscr.clear()
        self._stdscr.refresh()

    # ---------- Rendering ----------

    def render(self) -> None:
        """Redraw the full board and player."""
        self._draw_status()
        self._stdscr.refresh()

    def _draw_status(self) -> None:
        """Show position and control hints at the bottom line."""
        max_y, max_x = self._stdscr.getmaxyx()
        self._stdscr.move(max_y - 2, 0)
        self._stdscr.clrtoeol()
        text = f"AutoScroll: t | Quit: q"
        self._stdscr.addstr(max_y - 2, 0, text[:max_x - 1], curses.A_REVERSE)
        self._stdscr.refresh()

    # ---------- Messaging ----------

    def message(self, msg: str) -> None:
        """Display a transient message at the top of the screen."""
        self._stdscr.move(0,0)
        self._stdscr.clrtoeol()
        self._stdscr.addstr(0, 0, msg)
        self._stdscr.refresh()

    def room_status(self, status: str) -> None:
        """Display room number and name at top of screen"""
        self._stdscr.move(1,0)
        self._stdscr.clrtoeol()
        self._stdscr.addstr(1,0, status)
        self._stdscr.refresh()

    def debug(self, msg: str) -> None:
        _, max_x = self._stdscr.getmaxyx()
        debug_row = 2
        self._stdscr.move(debug_row, 0)
        self._stdscr.clrtoeol()
        self._stdscr.addstr(debug_row, 0, f"DEBUG: {msg}"[:max_x - 1])
        self._stdscr.refresh()

    # --------------------
    # Not being used 
    # --------------------
    def _draw_profile_stats(self, start_row: int, profile: "Profile") -> None:
        player_name = profile.player_name if profile.player_name else "Player"
        stats_lines = [
            f"      Player: {player_name}",
            f"      Games played: {profile.games_played}",
            f"      Best treasures: {profile.max_treasures_collected}",
            f"      Most rooms completed: {profile.most_rooms_world_completed}",
            f"      Last played: {profile.timestamp_last_played or 'N/A'}",
        ]

        max_y, max_x = self._stdscr.getmaxyx()
        self._stdscr.addstr(start_row, 0, "Stats:")
        start_row += 1
        for i, line in enumerate(stats_lines):
            row = start_row + i
            if row < max_y:
                self._stdscr.addstr(row, 0, line[:max_x - 1])

    def render_start(self):
        max_y, max_x = self._stdscr.getmaxyx()
        self._stdscr.move(max_y // 2, 0)
        self._stdscr.clrtoeol()
        self._stdscr.addstr(max_y // 2, 0, "Chord SH."[:max_x - 1])
        self._stdscr.addstr(max_y // 2 + 1, 0, "Press 'r' to start recording."[:max_x - 1])
        self._stdscr.addstr(max_y // 2 + 2, 0, "Press Q to quit."[:max_x - 1])
        self._stdscr.refresh()

    def render_exit(self, profile):
        max_y, max_x = self._stdscr.getmaxyx()
        self._stdscr.move(max_y // 2, 0)
        self._stdscr.clrtoeol()
        self._stdscr.addstr(max_y // 2, 0, "Game Exited. Progress Saved."[:max_x - 1])
        self._stdscr.addstr(max_y // 2 + 1, 0, "Press any key to exit."[:max_x - 1])
        self._draw_profile_stats(max_y // 2 + 3, profile)
        self._stdscr.refresh()

    def print_middle(self, message: str) -> None:
        self._stdscr.clear()
        max_y, max_x = self._stdscr.getmaxyx()
        self._stdscr.move(max_y // 2, 0)
        self._stdscr.clrtoeol()
        self._stdscr.addstr(max_y // 2, 0, message[:max_x - 1])
        self._stdscr.refresh()

    # def prompt_name(self) -> str:
    #     max_y, max_x = self._stdscr.getmaxyx()
    #     self._clear_screen()
    #     row = max_y // 2
    #     self._stdscr.addstr(row, 0, "No Profile Detected. Please enter a name."[:max_x - 1])
    #     self._stdscr.addstr(row + 1, 0, "Name: "[:max_x - 1])
    #     self._stdscr.refresh()

    #     curses.echo()
    #     try:
    #         curses.curs_set(1)
    #     except curses.error:
    #         pass

    #     name_len = max_x - len("Name: ") - 1
    #     name_bytes = self._stdscr.getstr(row + 1, len("Name: "), name_len)

    #     curses.noecho()
    #     try:
    #         curses.curs_set(0)
    #     except curses.error:
    #         pass

    #     return name_bytes.decode("utf-8", errors="ignore").strip()
