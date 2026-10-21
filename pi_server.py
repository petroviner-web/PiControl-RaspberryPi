#!/usr/bin/env python3
#koristio sam threadingttpserver umesto httpserver da bi mogao da se koristi u multithreaded okruženju, jer je httpserver blokirajući i ne može da obradi više zahteva istovremeno. ThreadingHTTPServer omogućava da se svaki zahtev obrađuje u posebnoj niti, što omogućava paralelno rukovanje više zahteva.
from __future__ import annotations

import json
import os
import hmac
import platform
import socket
import threading
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# Loopback-only by default. To expose this hardware-control API on LAN,
# provide both PICONTROL_BIND and a strong PICONTROL_TOKEN.
HOST = os.environ.get("PICONTROL_BIND", "127.0.0.1")
PORT = int(os.environ.get("PICONTROL_PORT", "8765"))
TOKEN = os.environ.get("PICONTROL_TOKEN", "")
MAX_BODY_BYTES = 32768


def require_secure_bind(host: str, token: str) -> None:
    if host not in ("127.0.0.1", "::1", "localhost") and len(token) < 24:
        raise RuntimeError("LAN binding requires PICONTROL_TOKEN of at least 24 characters. Use SSH tunneling or a trusted private network; HTTP itself is not encrypted.")


LOCK = threading.RLock()
GPIO = None
CONFIGURED: dict[int, str] = {}
PWMS: dict[int, object] = {}
SERIAL = None
LAST_GPIO_VALUES: dict[int, int] = {}


def event(message: str) -> None:
    """Ispisuje pregledan događaj odmah u Raspberry Pi terminalu."""
    stamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{stamp}] {message}", flush=True)


def init_gpio():
    global GPIO
    if GPIO is None:
        import RPi.GPIO as _GPIO
        _GPIO.setwarnings(False)
        _GPIO.setmode(_GPIO.BCM)
        GPIO = _GPIO
    return GPIO


def gpio_configure(pin: int, direction: str, value: int = 0):
    gpio = init_gpio()
    direction = direction.upper()
    previous_direction = CONFIGURED.get(pin)

    if direction == "INPUT":
        gpio.setup(pin, gpio.IN, pull_up_down=gpio.PUD_DOWN)
        current = int(gpio.input(pin))
        LAST_GPIO_VALUES[pin] = current
        if previous_direction != "INPUT":
            event(f"GPIO{pin} -> INPUT (PUD_DOWN), vrednost={current}")
    elif direction == "OUTPUT":
        current = int(bool(value))
        gpio.setup(pin, gpio.OUT)
        gpio.output(pin, current)
        LAST_GPIO_VALUES[pin] = current
        if previous_direction != "OUTPUT":
            event(f"GPIO{pin} -> OUTPUT, vrednost={current}")
    else:
        raise ValueError("direction mora biti INPUT ili OUTPUT")

    CONFIGURED[pin] = direction


def dispatch(data: dict):
    global SERIAL
    action = data.get("action")

    with LOCK:
        if action == "status":
            init_gpio()
            return {
                "hostname": socket.gethostname(),
                "platform": platform.platform(),
                "gpio": True,
                "bind_address": HOST,
            }

        if action == "gpio_configure":
            gpio_configure(int(data["pin"]), str(data["direction"]), int(data.get("value", 0)))
            return {}

        if action == "gpio_read":
            gpio = init_gpio()
            pin = int(data["pin"])
            direction = str(data.get("direction", "INPUT")).upper()

            if pin not in CONFIGURED:
                gpio_configure(pin,direction)

            value = int(gpio.input(pin))
            previous = LAST_GPIO_VALUES.get(pin)
            if previous is None:
                LAST_GPIO_VALUES[pin] = value
                event(f"GPIO{pin} {direction} = {value} (početno stanje)")
            elif value != previous:
                LAST_GPIO_VALUES[pin] = value
                event(f"GPIO{pin} {direction}: {previous} -> {value}  <-- PROMENA")

            return {"value": value}

        if action == "gpio_write":
            gpio = init_gpio()
            pin = int(data["pin"])
            value = int(bool(data["value"]))
            if CONFIGURED.get(pin) != "OUTPUT":
                gpio_configure(pin, "OUTPUT", value)

            previous = LAST_GPIO_VALUES.get(pin)
            gpio.output(pin, value)
            LAST_GPIO_VALUES[pin] = value
            if previous is None:
                event(f"GPIO{pin} OUTPUT = {value} (početno stanje)")
            elif value != previous:
                event(f"GPIO{pin} OUTPUT: {previous} -> {value}  <-- PROMENA")
            return {}

        if action == "gpio_cleanup":
            gpio = init_gpio()
            for pwm in list(PWMS.values()):
                try:
                    pwm.stop()
                except Exception:
                    pass
            PWMS.clear()
            gpio.cleanup()
            CONFIGURED.clear()
            LAST_GPIO_VALUES.clear()
            gpio.setmode(gpio.BCM)
            event("GPIO cleanup završen.")
            return {}

        if action == "i2c_scan":
            from smbus2 import SMBus
            bus_number = int(data.get("bus", 1))
            found = []
            with SMBus(bus_number) as bus:
                for address in range(0x03, 0x78):
                    try:
                        bus.read_byte(address)
                        found.append(address)
                    except OSError:
                        pass
            pretty = ", ".join(f"0x{a:02X}" for a in found) if found else "nema nijednog uređaja"
            event(f"I2C bus {bus_number} SCAN -> {pretty}")
            return {"addresses": found}

        if action == "i2c_read":
            from smbus2 import SMBus
            bus_number = int(data["bus"])
            address = int(data["address"])
            register = int(data["register"])
            length = int(data["length"])
            with SMBus(bus_number) as bus:
                values = bus.read_i2c_block_data(address, register, length)
            event(
                f"I2C READ bus={bus_number} addr=0x{address:02X} reg=0x{register:02X} "
                + "RX=" + " ".join(f"{v:02X}" for v in values)
            )
            return {"values": values}

        if action == "i2c_write":
            from smbus2 import SMBus
            bus_number = int(data["bus"])
            address = int(data["address"])
            register = int(data["register"])
            values = [int(v) for v in data["values"]]
            with SMBus(bus_number) as bus:
                bus.write_i2c_block_data(address, register, values)
            event(
                f"I2C WRITE bus={bus_number} addr=0x{address:02X} reg=0x{register:02X} "
                + "TX=" + " ".join(f"{v:02X}" for v in values)
            )
            return {}

        if action == "spi_transfer":
            import spidev
            bus_number = int(data["bus"])
            device = int(data["device"])
            speed = int(data["speed"])
            mode = int(data["mode"])
            tx = [int(v) for v in data["tx"]]
            spi = spidev.SpiDev()
            try:
                spi.open(bus_number, device)
                spi.max_speed_hz = speed
                spi.mode = mode
                rx = spi.xfer2(tx)
            finally:
                spi.close()
            event(
                f"SPI bus={bus_number} CE={device} mode={mode} speed={speed}Hz "
                + "TX=" + " ".join(f"{v:02X}" for v in tx)
                + " | RX=" + " ".join(f"{v:02X}" for v in rx)
            )
            return {"rx": rx}

        if action == "uart_open":
            import serial
            if SERIAL is not None and SERIAL.is_open:
                SERIAL.close()
            port = str(data["port"])
            baud = int(data["baud"])
            SERIAL = serial.Serial(port, baud, timeout=0)
            event(f"UART OPEN port={port} baud={baud}")
            return {}

        if action == "uart_close":
            if SERIAL is not None and SERIAL.is_open:
                SERIAL.close()
            SERIAL = None
            event("UART CLOSE")
            return {}

        if action == "uart_send":
            if SERIAL is None or not SERIAL.is_open:
                raise RuntimeError("UART port nije otvoren")
            payload = bytes(int(v) for v in data["data"])
            SERIAL.write(payload)
            event("UART TX=" + payload.hex(" ").upper())
            return {}

        if action == "uart_receive":
            if SERIAL is None or not SERIAL.is_open or not SERIAL.in_waiting:
                return {"data": []}
            payload = SERIAL.read(SERIAL.in_waiting)
            event("UART RX=" + payload.hex(" ").upper())
            return {"data": list(payload)}

        if action == "pwm_start":
            gpio = init_gpio()
            pin = int(data["pin"])
            frequency = int(data["frequency"])
            duty = float(data["duty"])
            gpio.setup(pin, gpio.OUT)
            CONFIGURED[pin] = "OUTPUT"
            old = PWMS.pop(pin, None)
            if old is not None:
                old.stop()
            pwm = gpio.PWM(pin, frequency)
            pwm.start(duty)
            PWMS[pin] = pwm
            event(f"PWM START GPIO{pin}: {frequency} Hz, duty={duty:g}%")
            return {}

        if action == "pwm_stop":
            pin = data.get("pin")
            if pin is None:
                for pwm in list(PWMS.values()):
                    pwm.stop()
                count = len(PWMS)
                PWMS.clear()
                event(f"PWM STOP ALL ({count} kanal/a)")
            else:
                pin = int(pin)
                pwm = PWMS.pop(pin, None)
                if pwm is not None:
                    pwm.stop()
                event(f"PWM STOP GPIO{pin}")
            return {}

        raise ValueError(f"Nepoznata akcija: {action}")


class Handler(BaseHTTPRequestHandler):
    server_version = "PiControl/1.0"

    def _send(self, status: int, payload: dict):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _authorized(self) -> bool:
        if not TOKEN:
            return True  # Only permitted when bound to loopback.
        return hmac.compare_digest(self.headers.get("Authorization", ""), "Bearer " + TOKEN)

    def _check_authorization(self) -> bool:
        if not self._authorized():
            self._send(401, {"ok": False, "error": "Unauthorized"})
            return False
        return True

    def do_GET(self):
        if not self._check_authorization():
            return
        if self.path == "/status":
            try:
                self._send(200, {"ok": True, **dispatch({"action": "status"})})
            except Exception as error:
                self._send(500, {"ok": False, "error": str(error)})
        else:
            self._send(404, {"ok": False, "error": "Not found"})

    def do_POST(self):
        if not self._check_authorization():
            return
        if self.path != "/api":
            self._send(404, {"ok": False, "error": "Not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= MAX_BODY_BYTES:
                self._send(413, {"ok": False, "error": "Invalid request size"})
                return
            data = json.loads(self.rfile.read(length).decode("utf-8"))
            if not isinstance(data, dict):
                raise ValueError("JSON request must be an object")
            result = dispatch(data)
            self._send(200, {"ok": True, **result})
        except Exception as error:
            self._send(400, {"ok": False, "error": f"{type(error).__name__}: {error}"})

    def log_message(self, fmt, *args):
        # Ne prikazuj svaki HTTP polling zahtev. Terminal ostaje pregledan i
        # prikazuje samo stvarne GPIO/promene i važne događaje.
        return


if __name__ == "__main__":
    require_secure_bind(HOST, TOKEN)
    init_gpio()
    print("=== PiControl HARDWARE LOG ===", flush=True)
    print(f"PiControl server: http://{HOST}:{PORT}", flush=True)
    print(f"Status: http://{HOST}:{PORT}/status", flush=True)
    print("Logovi za GPIO + I2C + SPI + UART + PWM", flush=True)
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
