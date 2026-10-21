from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QFile, QIODevice, QTimer, Qt
from PySide6.QtGui import QColor
from PySide6.QtUiTools import QUiLoader
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFrame, QHeaderView, QLabel, QMainWindow,
    QMessageBox, QPushButton, QTableWidget, QTableWidgetItem, QTabWidget,
    QVBoxLayout, QWidget,
)

from protocol_controls import ProtocolControl
from remote_backend import RemoteBackend

BASE_DIR = Path(__file__).resolve().parent
UI_DIR = BASE_DIR / "ui"


def load_ui(filename: str, parent: QWidget | None = None) -> QWidget:
    """Učitava Qt Designer .ui fajl direktno, bez pyside6-uic konverzije."""
    file = QFile(str(UI_DIR / filename))
    if not file.open(QIODevice.OpenModeFlag.ReadOnly):
        raise RuntimeError(f"Ne mogu da otvorim UI fajl: {filename}")
    try:
        widget = QUiLoader().load(file, parent)
    finally:
        file.close()
    if widget is None:
        raise RuntimeError(f"Ne mogu da učitam UI fajl: {filename}")
    return widget


def child(root: QWidget, cls, name: str):
    obj = root.findChild(cls, name)
    if obj is None:
        raise RuntimeError(f"U .ui fajlu nedostaje objekat '{name}'.")
    return obj


@dataclass
class Pin:
    physical: int
    name: str
    gpio: int | None = None
    functions: tuple[str, ...] = ()
    direction: str = "INPUT"
    value: int = 0

    @property
    def controllable(self) -> bool:
        return self.gpio is not None


PIN_DATA = {
    1: ("3.3V", None, ()), 2: ("5V", None, ()),
    3: ("GPIO2 / SDA1", 2, ("GPIO", "I2C")), 4: ("5V", None, ()),
    5: ("GPIO3 / SCL1", 3, ("GPIO", "I2C")), 6: ("GND", None, ()),
    7: ("GPIO4", 4, ("GPIO",)), 8: ("GPIO14 / TXD", 14, ("GPIO", "UART")),
    9: ("GND", None, ()), 10: ("GPIO15 / RXD", 15, ("GPIO", "UART")),
    11: ("GPIO17", 17, ("GPIO",)), 12: ("GPIO18 / PWM0", 18, ("GPIO", "PWM")),
    13: ("GPIO27", 27, ("GPIO",)), 14: ("GND", None, ()),
    15: ("GPIO22", 22, ("GPIO",)), 16: ("GPIO23", 23, ("GPIO",)),
    17: ("3.3V", None, ()), 18: ("GPIO24", 24, ("GPIO",)),
    19: ("GPIO10 / MOSI", 10, ("GPIO", "SPI")), 20: ("GND", None, ()),
    21: ("GPIO9 / MISO", 9, ("GPIO", "SPI")), 22: ("GPIO25", 25, ("GPIO",)),
    23: ("GPIO11 / SCLK", 11, ("GPIO", "SPI")), 24: ("GPIO8 / CE0", 8, ("GPIO", "SPI")),
    25: ("GND", None, ()), 26: ("GPIO7 / CE1", 7, ("GPIO", "SPI")),
    27: ("GPIO0 / ID_SD", 0, ("GPIO", "I2C")), 28: ("GPIO1 / ID_SC", 1, ("GPIO", "I2C")),
    29: ("GPIO5", 5, ("GPIO",)), 30: ("GND", None, ()),
    31: ("GPIO6", 6, ("GPIO",)), 32: ("GPIO12 / PWM0", 12, ("GPIO", "PWM")),
    33: ("GPIO13 / PWM1", 13, ("GPIO", "PWM")), 34: ("GND", None, ()),
    35: ("GPIO19 / PWM1", 19, ("GPIO", "PWM")), 36: ("GPIO16", 16, ("GPIO",)),
    37: ("GPIO26", 26, ("GPIO",)), 38: ("GPIO20", 20, ("GPIO",)),
    39: ("GND", None, ()), 40: ("GPIO21", 21, ("GPIO",)),
}


class GPIOBackend:
    """Razdvaja simulaciju od stvarnog RPi.GPIO hardvera.

    U HARDVER režimu GPIO kanal se konfiguriše tek kada ga korisnik stvarno
    izabere u GPIO kartici. INPUT koristi interni pull-down, pa nepovezan pin
    stabilno daje LOW umesto slučajnih (floating) promena.
    """

    def __init__(self) -> None:
        self.gpio = None
        self.hardware_available = False
        self.simulation = True
        # Pamti koje BCM kanale je OVA aplikacija preuzela kao običan GPIO.
        # Time izbegavamo da pri pokretanju prekonfigurišemo I2C/SPI/UART pinove.
        self._configured: dict[int, str] = {}
        try:
            import RPi.GPIO as gpio  # type: ignore
            gpio.setwarnings(False)
            gpio.setmode(gpio.BCM)
            self.gpio = gpio
            self.hardware_available = True
            self.simulation = False
        except (ImportError, RuntimeError):
            pass

    @property
    def hardware(self) -> bool:
        return self.hardware_available and not self.simulation

    def set_simulation(self, enabled: bool) -> None:
        if not enabled and not self.hardware_available:
            raise RuntimeError("RPi.GPIO nije dostupan. HARDVER režim radi samo na Raspberry Pi-ju.")
        if enabled and self.hardware:
            self.cleanup()
        self.simulation = enabled
        if not enabled and self.gpio is not None:
            # Posle cleanup-a ponovo eksplicitno postavi BCM numeraciju.
            self.gpio.setwarnings(False)
            self.gpio.setmode(self.gpio.BCM)

    def configure(self, pin: Pin) -> None:
        """Podešava jedan izabrani pin kao običan digitalni GPIO."""
        if not self.hardware or self.gpio is None or pin.gpio is None:
            return

        if pin.direction == "INPUT":
            # PUD_DOWN sprečava floating ulaz: bez spoljnog signala čita se LOW.
            self.gpio.setup(pin.gpio, self.gpio.IN, pull_up_down=self.gpio.PUD_DOWN)
        else:
            self.gpio.setup(pin.gpio, self.gpio.OUT)
            self.gpio.output(pin.gpio, pin.value)

        self._configured[pin.gpio] = pin.direction

    def _ensure_configured(self, pin: Pin) -> None:
        if not self.hardware or pin.gpio is None:
            return
        if self._configured.get(pin.gpio) != pin.direction:
            self.configure(pin)

    def read(self, pin: Pin) -> int:
        """Čita fizički nivo iz RPi.GPIO ili simuliranu vrednost iz modela."""
        if self.hardware and self.gpio is not None and pin.gpio is not None:
            # Lazy setup: prvi read je bezbedan čak i ako kanal ranije nije bio setup-ovan.
            self._ensure_configured(pin)
            return int(self.gpio.input(pin.gpio))
        return pin.value

    def write(self, pin: Pin, value: int) -> None:
        pin.value = int(bool(value))
        if self.hardware and self.gpio is not None and pin.gpio is not None:
            if pin.direction != "OUTPUT":
                raise RuntimeError("U HARDVER režimu vrednost se upisuje samo na OUTPUT pin.")
            self._ensure_configured(pin)
            self.gpio.output(pin.gpio, pin.value)

    def cleanup(self) -> None:
        if self.hardware_available and self.gpio is not None:
            try:
                self.gpio.cleanup()
            except RuntimeError:
                pass
        self._configured.clear()


class FunctionPanel(QWidget):
    """Jedan tab aplikacije; izgled dolazi iz ui/function_panel.ui."""

    def __init__(self, name: str, pins: dict[int, Pin], backend: GPIOBackend) -> None:
        super().__init__()
        self.name = name
        self.pins = pins
        self.backend = backend
        self.selected: int | None = None

        self.ui = load_ui("function_panel.ui", self)
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.addWidget(self.ui)

        self.heading = child(self.ui, QLabel, "panelHeadingLabel")
        self.info = child(self.ui, QLabel, "infoLabel")
        self.direction = child(self.ui, QComboBox, "directionCombo")
        self.value_button = child(self.ui, QPushButton, "valueButton")
        self.signal_card = child(self.ui, QLabel, "signalCardLabel")
        self.sim_low = child(self.ui, QPushButton, "simLowButton")
        self.sim_high = child(self.ui, QPushButton, "simHighButton")
        self.protocol_container = child(self.ui, QWidget, "protocolContainer")
        self.table = child(self.ui, QTableWidget, "pinTable")

        self.heading.setText(f"{name} PINOVI")
        self.buttons: dict[int, QPushButton] = {}
        for physical, pin in self.pins.items():
            button = child(self.ui, QPushButton, f"pinButton_{physical}")
            label = child(self.ui, QLabel, f"pinLabel_{physical}")
            button.setText(str(physical))
            label.setText(pin.name)
            button.clicked.connect(lambda checked=False, p=physical: self.select_pin(p))
            button.setEnabled(not pin.controllable or name == "GPIO" or name in pin.functions)
            self.buttons[physical] = button

        self.direction.currentTextChanged.connect(self.change_direction)
        self.value_button.clicked.connect(self.toggle_value)
        self.sim_low.clicked.connect(lambda: self.set_simulated_input(0))
        self.sim_high.clicked.connect(lambda: self.set_simulated_input(1))

        protocol = ProtocolControl(name, self.selected_gpio, backend)
        protocol_layout = self.protocol_container.layout()
        if protocol_layout is None:
            protocol_layout = QVBoxLayout(self.protocol_container)
            protocol_layout.setContentsMargins(0, 0, 0, 0)
        protocol_layout.addWidget(protocol)

        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.cellClicked.connect(self.select_table_row)

        self.refresh_table()
        self.update_controls()
        self.refresh_board()

    def selected_gpio(self) -> int | None:
        return None if self.selected is None else self.pins[self.selected].gpio

    def relevant(self, pin: Pin) -> bool:
        return pin.controllable and (self.name == "GPIO" or self.name in pin.functions)

    def select_pin(self, physical: int) -> None:
        pin = self.pins[physical]
        if not self.relevant(pin):
            self.info.setText(f"Pin {physical} je {pin.name} i nije upravljiv u {self.name} panelu.")
            return
        self.selected = physical
        # U HARDVER režimu običan GPIO se preuzima tek kada ga korisnik
        # izabere u GPIO kartici. Protokolske kartice ne diraju pin-mux.
        if self.backend.hardware and self.name == "GPIO":
            try:
                self.backend.configure(pin)
            except RuntimeError as error:
                QMessageBox.warning(self, "GPIO greška", str(error))
        self.update_controls()
        self.refresh_board()
        self.select_matching_row()

    def select_table_row(self, row: int, _column: int) -> None:
        item = self.table.item(row, 0)
        if item is not None:
            self.select_pin(int(item.text()))

    def select_matching_row(self) -> None:
        if self.selected is None:
            return
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item is not None and int(item.text()) == self.selected:
                self.table.selectRow(row)
                break

    def change_direction(self, direction: str) -> None:
        if self.selected is None:
            return
        if self.backend.hardware and self.name != "GPIO":
            # I2C/SPI/UART/PWM pinove u hardverskom režimu kontrolišu njihove
            # odgovarajuće Linux/Raspberry Pi periferije, ne običan GPIO setup.
            self.update_controls()
            return
        pin = self.pins[self.selected]
        pin.direction = direction
        self.backend.configure(pin)
        self.update_controls()
        self.refresh_table()
        self.refresh_board()

    def toggle_value(self) -> None:
        if self.selected is None:
            return
        pin = self.pins[self.selected]
        if self.backend.hardware and self.name != "GPIO":
            QMessageBox.information(
                self,
                "Protokolski pin",
                "U HARDVER režimu vrednost ovog pina određuje izabrani I2C/SPI/UART/PWM interfejs.",
            )
            return
        if pin.direction == "INPUT" and self.backend.hardware:
            QMessageBox.information(self, "Ulazni pin", "Vrednost ulaznog pina dolazi sa hardvera.")
            return
        try:
            self.backend.write(pin, 1 - pin.value)
        except RuntimeError as error:
            QMessageBox.warning(self, "GPIO greška", str(error))
            return
        self.update_controls(); self.refresh_table(); self.refresh_board()

    def set_simulated_input(self, value: int) -> None:
        if self.selected is None:
            return
        pin = self.pins[self.selected]
        if self.backend.hardware:
            QMessageBox.information(self, "Hardverski režim", "Simulacija ulaza je dostupna samo u SIMULACIJA režimu.")
            return
        if pin.direction != "INPUT":
            QMessageBox.information(self, "Izlazni pin", "Za simuliranje spoljašnjeg signala postavite pin na INPUT.")
            return
        self.backend.write(pin, value)
        self.update_controls(); self.refresh_table(); self.refresh_board()

    def _tooltip(self, pin: Pin) -> str:
        if not pin.controllable:
            return f"Fizički pin {pin.physical}: {pin.name}"
        return f"Fizički pin {pin.physical}\n{pin.name}\nSmer: {pin.direction}, vrednost: {pin.value}"

    def refresh_board(self) -> None:
        for physical, button in self.buttons.items():
            pin = self.pins[physical]
            if not pin.controllable:
                color = "#f5c451" if "V" in pin.name else "#343a46"
                text_color = "#17191f" if "V" in pin.name else "white"
            else:
                color = "#2dcc70" if pin.direction == "INPUT" else "#ef5350"
                text_color = "#10151b" if pin.direction == "INPUT" else "white"
            border = "3px solid #ffffff" if physical == self.selected else "1px solid rgba(255,255,255,0.25)"
            button.setStyleSheet(
                f"QPushButton {{background:{color}; color:{text_color}; border:{border}; border-radius:8px; font-weight:700;}}"
                "QPushButton:hover {border:3px solid #71b7ff;}"
            )
            button.setToolTip(self._tooltip(pin))

    def update_controls(self) -> None:
        enabled = self.selected is not None
        direct_gpio_control = enabled and (not self.backend.hardware or self.name == "GPIO")
        self.direction.setEnabled(direct_gpio_control)
        self.value_button.setEnabled(direct_gpio_control)
        self.sim_low.setEnabled(enabled and not self.backend.hardware)
        self.sim_high.setEnabled(enabled and not self.backend.hardware)

        if not enabled:
            self.value_button.setText("Vrednost: –")
            self.signal_card.setText("Nema izabranog pina")
            self.signal_card.setStyleSheet("background:#2a313e; color:#9da9b8; border-radius:8px; font-weight:700;")
            return

        pin = self.pins[self.selected]
        self.direction.blockSignals(True)
        self.direction.setCurrentText(pin.direction)
        self.direction.blockSignals(False)
        self.value_button.setText(f"Vrednost: {pin.value}")
        self.info.setText(f"Fizički pin {pin.physical}  •  GPIO {pin.gpio}\n{pin.name}  •  {pin.direction}  •  vrednost {pin.value}")

        state = "HIGH / 1" if pin.value else "LOW / 0"
        if self.backend.hardware:
            if self.name != "GPIO":
                text = f"Hardverski protokolski pin: {pin.name}"
                color = "#404a58"
            elif pin.direction == "OUTPUT":
                text = f"Fizički GPIO izlaz: {state}"
                color = "#2dcc70" if pin.value else "#404a58"
            else:
                text = f"Fizički GPIO ulaz: {state}"
                color = "#2d70c9" if pin.value else "#404a58"
        elif pin.direction == "OUTPUT":
            text = f"Virtuelna LED: {'UKLJUČENA' if pin.value else 'ISKLJUČENA'}   ({state})"
            color = "#2dcc70" if pin.value else "#404a58"
        else:
            text = f"Virtuelni ulazni signal: {state}"
            color = "#2d70c9" if pin.value else "#404a58"
        self.signal_card.setText(text)
        self.signal_card.setStyleSheet(f"background:{color}; color:white; border-radius:8px; padding:8px; font-weight:800;")

    def refresh_table(self) -> None:
        rows = [pin for pin in self.pins.values() if self.relevant(pin)]
        self.table.setRowCount(len(rows))
        for row, pin in enumerate(rows):
            if not self.backend.hardware:
                pin.value = self.backend.read(pin)
            elif self.name == "GPIO" and self.selected == pin.physical:
                # Samo trenutno izabrani običan GPIO se periodično čita sa
                # fizičkog pina. Time ne preuzimamo I2C/SPI/UART pinove.
                try:
                    pin.value = self.backend.read(pin)
                except RuntimeError as error:
                    self.info.setText(f"GPIO greška: {error}")
            values = [pin.physical, pin.gpio, pin.name, pin.direction, pin.value]
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if column == 3:
                    item.setBackground(QColor("#2dcc70" if pin.direction == "INPUT" else "#ef5350"))
                    item.setForeground(QColor("#111820" if pin.direction == "INPUT" else "white"))
                if column == 4:
                    item.setForeground(QColor("#55d98b" if pin.value else "#aab4c1"))
                self.table.setItem(row, column, item)
        self.update_controls()


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Sistem za nadzor i upravljanje GPIO pinovima i komunikacionim interfejsima Raspberry Pi Model B+")
        self.resize(1320, 860)

        self.backend = RemoteBackend()
        self.pins = {number: Pin(number, name, gpio, functions) for number, (name, gpio, functions) in PIN_DATA.items()}

        self.ui = load_ui("main_window.ui")
        self.setCentralWidget(self.ui)
        self.mode_combo = child(self.ui, QComboBox, "modeCombo")
        self.mode_label = child(self.ui, QLabel, "modeStatusLabel")
        self.tabs = child(self.ui, QTabWidget, "tabs")

        self.mode_combo.setCurrentText("SIMULACIJA")
        self.mode_combo.currentTextChanged.connect(self.change_mode)
        self.update_mode_label()

        self.panels: list[FunctionPanel] = []
        for function in ("GPIO", "I2C", "SPI", "UART", "PWM"):
            panel = FunctionPanel(function, self.pins, self.backend)
            self.panels.append(panel)
            self.tabs.addTab(panel, function)

        qss_path = BASE_DIR / "styles.qss"
        if qss_path.exists():
            self.setStyleSheet(qss_path.read_text(encoding="utf-8"))

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_all)
        self.timer.start(750)

    def update_mode_label(self) -> None:
        if self.backend.hardware:
            self.mode_label.setText(f"● RASPBERRY {self.backend.host}:{self.backend.port}")
            self.mode_label.setStyleSheet("color:#2dcc70; font-weight:800;")
        else:
            self.mode_label.setText("● demonstracija")
            self.mode_label.setStyleSheet("color:#f5c451; font-weight:800;")

    def change_mode(self, mode: str) -> None:
        try:
            self.backend.set_simulation(mode == "SIMULACIJA")
            # Ne konfigurišemo svih 26 GPIO kanala odjednom: to bi moglo da
            # preuzme pinove koje Linux koristi za I2C/SPI/UART. Izabrani GPIO
            # se konfiguriše tek kada ga korisnik odabere u GPIO kartici.
            self.update_mode_label(); self.refresh_all()
        except RuntimeError as error:
            QMessageBox.warning(self, "Raspberry nije dostupan", str(error))
            self.mode_combo.blockSignals(True)
            self.mode_combo.setCurrentText("SIMULACIJA")
            self.mode_combo.blockSignals(False)
            self.backend.set_simulation(True)
            self.update_mode_label()

    def refresh_all(self) -> None:
        for panel in self.panels:
            panel.refresh_table(); panel.refresh_board()

    def closeEvent(self, event) -> None:  
        self.backend.cleanup()
        super().closeEvent(event)


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Raspberry Pi GPIO kontrolni sistem")
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
