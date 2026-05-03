"""
Arduino trigger adapter.

Reads serial button presses from an Arduino and injects them as
commands into the UI adapter. The game engine never knows about
the trigger — it just receives normal input through the UI.
"""
import threading
import serial
from core.protocols import UIAdapter


class SerialTrigger:
    """
    Background serial reader that injects a command into the UI
    when an Arduino button is pressed.

    Usage:
        trigger = SerialTrigger(ui, port="/dev/cu.usbmodem1101")
        trigger.start()
        # ... run game loop ...
        trigger.stop()
    """

    def __init__(
        self,
        ui: UIAdapter,
        port: str,
        baudrate: int = 9600,
        command: str = '\n',
    ):
        self._ui = ui
        self._port = port
        self._baudrate = baudrate
        self._command = command
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._ser: serial.Serial | None = None

    def start(self) -> None:
        """Open serial port and start reading in background."""
        self._ser = serial.Serial(self._port, self._baudrate, timeout=0.1)
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._read_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop background reader and close serial port."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None
        if self._ser and self._ser.is_open:
            self._ser.close()
            self._ser = None

    def _read_loop(self) -> None:
        """Poll serial and inject command on PRESSED."""
        while not self._stop_event.is_set():
            try:
                if self._ser and self._ser.in_waiting:
                    line = self._ser.readline().decode().strip()
                    if line == "PRESSED":
                        self._ui.inject_command(self._command)
            except (serial.SerialException, OSError):
                break