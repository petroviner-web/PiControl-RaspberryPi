from __future__ import annotations

import math
import platform
import time
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QFile, QIODevice, QTimer, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtUiTools import QUiLoader
from PySide6.QtWidgets import (
    QComboBox, QDoubleSpinBox, QLabel, QLineEdit, QPlainTextEdit, QProgressBar,
    QPushButton, QSpinBox, QVBoxLayout, QWidget,
)

BASE_DIR = Path(__file__).resolve().parent
UI_DIR = BASE_DIR / "ui"


def load_ui(filename: str, parent: QWidget | None = None) -> QWidget:
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


def parse_bytes(text: str) -> list[int]:
    clean = text.replace(",", " ").replace(";", " ")
    result: list[int] = []
    for token in clean.split():
        base = 16 if token.lower().startswith("0x") or any(c in token.lower() for c in "abcdef") else 10
        value = int(token, base)
        if not 0 <= value <= 255:
            raise ValueError("Svaki bajt mora biti između 0 i 255.")
        result.append(value)
    return result


def log_add(log: QPlainTextEdit, message: str) -> None:
    stamp = datetime.now().strftime("%H:%M:%S")
    log.appendPlainText(f"[{stamp}] {message}")


class DesignerControl(QWidget):
    UI_FILE = ""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.ui = load_ui(self.UI_FILE, self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.ui)


class I2CControl(DesignerControl):
    UI_FILE = "i2c_panel.ui"
    SIM_DEVICES = {0x48: "TMP102 temperaturni senzor", 0x3C: "OLED displej"}

    def __init__(self, backend) -> None:
        super().__init__()
        self.backend = backend
        self.bus = None
        self.sim_registers: dict[tuple[int, int], list[int]] = {}
        self.bus_number = child(self.ui, QSpinBox, "busNumberSpin")
        self.address = child(self.ui, QLineEdit, "addressEdit")
        self.register = child(self.ui, QLineEdit, "registerEdit")
        self.data = child(self.ui, QLineEdit, "dataEdit")
        self.length = child(self.ui, QSpinBox, "lengthSpin")
        self.log = child(self.ui, QPlainTextEdit, "logEdit")
        child(self.ui, QPushButton, "scanButton").clicked.connect(self.scan)
        child(self.ui, QPushButton, "readButton").clicked.connect(self.read)
        child(self.ui, QPushButton, "writeButton").clicked.connect(self.write)

    def get_bus(self):
        from smbus2 import SMBus
        if self.bus is not None:
            self.bus.close()
        self.bus = SMBus(self.bus_number.value())
        return self.bus

    def _sim_temperature(self) -> float:
        return 24.5 + 1.7 * math.sin(time.monotonic() / 5.0)

    def _sim_read(self, address: int, register: int, length: int) -> list[int]:
        if address not in self.SIM_DEVICES:
            raise OSError(f"Nema simuliranog I²C uređaja na adresi 0x{address:02X}.")
        stored = self.sim_registers.get((address, register))
        if stored is not None:
            values = stored[:length]
            return values + [0] * max(0, length - len(values))
        if address == 0x48 and register == 0x00:
            temperature = self._sim_temperature()
            raw = int(round(temperature * 16)) & 0x0FFF
            values = [(raw >> 4) & 0xFF, (raw & 0x0F) << 4]
            return (values + [0] * length)[:length]
        return [0x00] * length

    def scan(self) -> None:
        try:
            if not self.backend.hardware:
                found = [f"0x{address:02X}" for address in self.SIM_DEVICES]
                log_add(self.log, "SIM scan → pronađene adrese: " + ", ".join(found))
                for address, name in self.SIM_DEVICES.items():
                    log_add(self.log, f"  0x{address:02X}: {name}")
                return
            if getattr(self.backend, "remote", False):
                addresses = self.backend.i2c_scan(self.bus_number.value())
                found = [f"0x{address:02X}" for address in addresses]
            else:
                bus = self.get_bus(); found: list[str] = []
                for address in range(0x03, 0x78):
                    try:
                        bus.read_byte(address); found.append(f"0x{address:02X}")
                    except OSError:
                        pass
            log_add(self.log, "Pronađene adrese: " + (", ".join(found) if found else "nijedna adresa"))
        except Exception as error:
            log_add(self.log, f"I²C greška: {error}")

    def read(self) -> None:
        try:
            address = int(self.address.text(), 0); register = int(self.register.text(), 0); length = self.length.value()
            if not self.backend.hardware:
                values = self._sim_read(address, register, length)
            elif getattr(self.backend, "remote", False):
                values = self.backend.i2c_read(self.bus_number.value(), address, register, length)
            else:
                values = self.get_bus().read_i2c_block_data(address, register, length)
            log_add(self.log, "RX: " + " ".join(f"{value:02X}" for value in values))
            if not self.backend.hardware and address == 0x48 and register == 0x00:
                log_add(self.log, f"SIM dekodirano → temperatura ≈ {self._sim_temperature():.1f} °C")
        except Exception as error:
            log_add(self.log, f"I²C greška: {error}")

    def write(self) -> None:
        try:
            address = int(self.address.text(), 0); register = int(self.register.text(), 0); values = parse_bytes(self.data.text())
            if not self.backend.hardware:
                if address not in self.SIM_DEVICES:
                    raise OSError(f"Nema simuliranog I²C uređaja na adresi 0x{address:02X}.")
                self.sim_registers[(address, register)] = values.copy()
            elif getattr(self.backend, "remote", False):
                self.backend.i2c_write(self.bus_number.value(), address, register, values)
            else:
                self.get_bus().write_i2c_block_data(address, register, values)
            log_add(self.log, "TX: " + " ".join(f"{value:02X}" for value in values))
            if not self.backend.hardware:
                log_add(self.log, f"SIM → upisano u registar 0x{register:02X} uređaja 0x{address:02X}")
        except Exception as error:
            log_add(self.log, f"I²C greška: {error}")


class SPIControl(DesignerControl):
    UI_FILE = "spi_panel.ui"

    def __init__(self, backend) -> None:
        super().__init__()
        self.backend = backend
        self.bus = child(self.ui, QSpinBox, "busSpin")
        self.device = child(self.ui, QSpinBox, "deviceSpin")
        self.speed = child(self.ui, QSpinBox, "speedSpin")
        self.mode = child(self.ui, QComboBox, "modeCombo")
        self.data = child(self.ui, QLineEdit, "dataEdit")
        self.log = child(self.ui, QPlainTextEdit, "logEdit")
        child(self.ui, QPushButton, "transferButton").clicked.connect(self.transfer)

    def _simulate_transfer(self, tx: list[int]) -> list[int]:
        if tx and tx[0] == 0x9F:
            return ([0x00, 0xEF, 0x40, 0x16] + [0x00] * len(tx))[:len(tx)]
        return [value ^ 0xFF for value in tx]

    def transfer(self) -> None:
        spi = None
        try:
            tx = parse_bytes(self.data.text())
            if not tx:
                raise ValueError("Unesite najmanje jedan bajt.")
            if not self.backend.hardware:
                rx = self._simulate_transfer(tx)
            elif getattr(self.backend, "remote", False):
                rx = self.backend.spi_transfer(
                    self.bus.value(), self.device.value(), self.speed.value(), int(self.mode.currentText()), tx
                )
            else:
                import spidev
                spi = spidev.SpiDev(); spi.open(self.bus.value(), self.device.value())
                spi.max_speed_hz = self.speed.value(); spi.mode = int(self.mode.currentText()); rx = spi.xfer2(tx)
            log_add(self.log, "TX: " + " ".join(f"{v:02X}" for v in tx))
            log_add(self.log, "RX: " + " ".join(f"{v:02X}" for v in rx))
            if not self.backend.hardware and tx[0] == 0x9F:
                log_add(self.log, "SIM dekodirano → JEDEC ID EF 40 16 (virtuelna SPI Flash)")
            elif not self.backend.hardware:
                log_add(self.log, "SIM → generisan full-duplex odgovor (invertovani bajtovi).")
        except Exception as error:
            log_add(self.log, f"SPI greška: {error}")
        finally:
            if spi is not None:
                spi.close()


class UARTControl(DesignerControl):
    UI_FILE = "uart_panel.ui"

    def __init__(self, backend) -> None:
        super().__init__()
        self.backend = backend; self.serial = None; self.sim_connected = False; self.remote_connected = False; self.pending_response: bytes | None = None
        self.port = child(self.ui, QLineEdit, "portEdit")
        self.port.setText("/dev/serial0" if getattr(self.backend, "remote", False) or platform.system() != "Windows" else "COM3")
        self.baud = child(self.ui, QComboBox, "baudCombo")
        self.encoding = child(self.ui, QComboBox, "encodingCombo")
        self.data = child(self.ui, QLineEdit, "dataEdit")
        self.connect_button = child(self.ui, QPushButton, "connectButton")
        self.log = child(self.ui, QPlainTextEdit, "logEdit")
        self.connect_button.clicked.connect(self.toggle_connection)
        child(self.ui, QPushButton, "sendButton").clicked.connect(self.send)
        self.timer = QTimer(self); self.timer.timeout.connect(self.receive); self.timer.start(150)

    def toggle_connection(self) -> None:
        try:
            if not self.backend.hardware:
                self.sim_connected = not self.sim_connected
                self.connect_button.setText("Prekini" if self.sim_connected else "Poveži")
                log_add(self.log, "SIM UART povezan." if self.sim_connected else "SIM UART prekinut.")
                return
            if getattr(self.backend, "remote", False):
                if self.remote_connected:
                    self.backend.uart_close(); self.remote_connected = False
                    self.connect_button.setText("Poveži"); log_add(self.log, "Remote UART zatvoren.")
                else:
                    self.backend.uart_open(self.port.text().strip(), int(self.baud.currentText()))
                    self.remote_connected = True
                    self.connect_button.setText("Prekini"); log_add(self.log, "Remote UART otvoren na Raspberry Pi-ju.")
                return
            if self.serial and self.serial.is_open:
                self.serial.close(); self.connect_button.setText("Poveži"); log_add(self.log, "Port zatvoren.")
            else:
                import serial
                self.serial = serial.Serial(self.port.text().strip(), int(self.baud.currentText()), timeout=0)
                self.connect_button.setText("Prekini"); log_add(self.log, "Port otvoren.")
        except Exception as error:
            log_add(self.log, f"UART greška: {error}")

    def send(self) -> None:
        try:
            if not self.backend.hardware:
                if not self.sim_connected:
                    raise RuntimeError("Prvo kliknite Poveži da otvorite virtuelni UART.")
                if self.encoding.currentIndex():
                    data = bytes(parse_bytes(self.data.text())); self.pending_response = bytes([0xAA]) + data
                else:
                    data = self.data.text().encode("utf-8"); text = self.data.text().strip()
                    response = "OK; TEMP=24.8C; GPIO=READY" if text.upper() == "STATUS" else "PONG" if text.upper() == "PING" else f"ACK: {text}"
                    self.pending_response = response.encode("utf-8")
                log_add(self.log, "TX: " + data.hex(" ").upper()); return
            data = bytes(parse_bytes(self.data.text())) if self.encoding.currentIndex() else self.data.text().encode("utf-8")
            if getattr(self.backend, "remote", False):
                if not self.remote_connected:
                    raise RuntimeError("Prvo otvorite UART port na Raspberry Pi-ju.")
                self.backend.uart_send(data); log_add(self.log, "TX: " + data.hex(" ").upper()); return
            if not self.serial or not self.serial.is_open:
                raise RuntimeError("Prvo otvorite UART port.")
            self.serial.write(data); log_add(self.log, "TX: " + data.hex(" ").upper())
        except Exception as error:
            log_add(self.log, f"UART greška: {error}")

    def receive(self) -> None:
        try:
            if not self.backend.hardware:
                if self.sim_connected and self.pending_response is not None:
                    data = self.pending_response; self.pending_response = None
                    log_add(self.log, "RX: " + (data.decode("utf-8", errors="replace") if self.encoding.currentIndex() == 0 else data.hex(" ").upper()))
                return
            if getattr(self.backend, "remote", False):
                if self.remote_connected:
                    data = self.backend.uart_receive()
                    if data:
                        log_add(self.log, "RX: " + (data.decode("utf-8", errors="replace") if self.encoding.currentIndex() == 0 else data.hex(" ").upper()))
                return
            if self.serial and self.serial.is_open and self.serial.in_waiting:
                data = self.serial.read(self.serial.in_waiting)
                log_add(self.log, "RX: " + (data.decode("utf-8", errors="replace") if self.encoding.currentIndex() == 0 else data.hex(" ").upper()))
        except Exception as error:
            log_add(self.log, f"UART RX greška: {error}")


class PWMWaveform(QWidget):
    def __init__(self) -> None:
        super().__init__(); self.frequency = 1000; self.duty = 50.0; self.active = False; self.setMinimumHeight(105)

    def set_signal(self, frequency: int, duty: float, active: bool) -> None:
        self.frequency = frequency; self.duty = duty; self.active = active; self.update()

    def paintEvent(self, event) -> None:  
        painter = QPainter(self); painter.setRenderHint(QPainter.RenderHint.Antialiasing); painter.fillRect(self.rect(), QColor("#111720"))
        margin = 12; top = 22; bottom = self.height() - 20; width = max(1, self.width() - 2 * margin)
        painter.setPen(QPen(QColor("#344152"), 1)); painter.drawLine(margin, top, margin + width, top); painter.drawLine(margin, bottom, margin + width, bottom)
        if not self.active:
            painter.setPen(QColor("#8f9bab")); painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "PWM zaustavljen"); return
        painter.setPen(QPen(QColor("#4db7ff"), 3)); periods = 5; period_w = width / periods; high_w = period_w * max(0.0, min(100.0, self.duty)) / 100.0; x = float(margin)
        for _ in range(periods):
            painter.drawLine(int(x), bottom, int(x), top); painter.drawLine(int(x), top, int(x + high_w), top)
            painter.drawLine(int(x + high_w), top, int(x + high_w), bottom); painter.drawLine(int(x + high_w), bottom, int(x + period_w), bottom); x += period_w
        painter.setPen(QColor("#d7e2ef")); painter.drawText(margin, 15, f"{self.frequency} Hz   duty {self.duty:g}%")


class PWMControl(DesignerControl):
    UI_FILE = "pwm_panel.ui"

    def __init__(self, selected_gpio, backend) -> None:
        super().__init__()
        self.selected_gpio = selected_gpio; self.backend = backend; self.pwm = None
        self.frequency = child(self.ui, QSpinBox, "frequencySpin")
        self.duty = child(self.ui, QDoubleSpinBox, "dutySpin")
        self.duty_bar = child(self.ui, QProgressBar, "dutyBar")
        self.log = child(self.ui, QPlainTextEdit, "logEdit")
        container = child(self.ui, QWidget, "waveformContainer")
        self.waveform = PWMWaveform(); container.layout().addWidget(self.waveform)
        child(self.ui, QPushButton, "startButton").clicked.connect(self.start)
        child(self.ui, QPushButton, "stopButton").clicked.connect(self.stop)

    def start(self) -> None:
        try:
            gpio_number = self.selected_gpio()
            if gpio_number is None:
                raise RuntimeError("Prvo izaberite PWM pin na nacrtu ili u tabeli.")
            frequency = self.frequency.value(); duty = self.duty.value(); self.duty_bar.setValue(int(round(duty))); self.waveform.set_signal(frequency, duty, True)
            if not self.backend.hardware:
                log_add(self.log, f"SIM PWM → GPIO {gpio_number}: {frequency} Hz, {duty:g}%"); return
            if getattr(self.backend, "remote", False):
                self.backend.pwm_start(gpio_number, frequency, duty)
                log_add(self.log, f"Remote PWM → GPIO {gpio_number}: {frequency} Hz, {duty:g}%")
                return
            import RPi.GPIO as GPIO
            GPIO.setwarnings(False); GPIO.setmode(GPIO.BCM); GPIO.setup(gpio_number, GPIO.OUT)
            if self.pwm is not None:
                self.pwm.stop()
            self.pwm = GPIO.PWM(gpio_number, frequency); self.pwm.start(duty); log_add(self.log, f"GPIO {gpio_number}: {frequency} Hz, {duty:g}%")
        except Exception as error:
            log_add(self.log, f"PWM greška: {error}")

    def stop(self) -> None:
        gpio_number = self.selected_gpio()
        if self.backend.hardware and getattr(self.backend, "remote", False):
            try:
                self.backend.pwm_stop(gpio_number)
            except Exception as error:
                log_add(self.log, f"PWM greška: {error}")
        elif self.pwm is not None:
            self.pwm.stop(); self.pwm = None
        self.waveform.set_signal(self.frequency.value(), self.duty.value(), False); log_add(self.log, "PWM zaustavljen.")


class ProtocolControl(QWidget):
    def __init__(self, function: str, selected_gpio, backend) -> None:
        super().__init__()
        layout = QVBoxLayout(self); layout.setContentsMargins(0, 0, 0, 0)
        if function == "I2C":
            layout.addWidget(I2CControl(backend))
        elif function == "SPI":
            layout.addWidget(SPIControl(backend))
        elif function == "UART":
            layout.addWidget(UARTControl(backend))
        elif function == "PWM":
            layout.addWidget(PWMControl(selected_gpio, backend))
        else:
            layout.addWidget(load_ui("gpio_panel.ui", self))
