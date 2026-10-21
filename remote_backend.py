from __future__ import annotations

import json
import os
import urllib.error
import urllib.request


class RemoteBackend:
    """Backend koji GUI na laptopu povezuje sa Raspberry Pi serverom preko HTTP-a."""

    remote = True

    def __init__(self, host: str | None = None, port: int | None = None, timeout: float = 1.0) -> None:
        host = host or os.environ.get("PICONTROL_HOST", "127.0.0.1")
        port = port if port is not None else int(os.environ.get("PICONTROL_PORT", "8765"))
        self.host = host
        self.port = port
        self.base_url = f"http://{host}:{port}"
        self.token = os.environ.get("PICONTROL_TOKEN", "")
        self.timeout = timeout
        self.simulation = True
        self.hardware_available = False

    @property
    def hardware(self) -> bool:
        return self.hardware_available and not self.simulation

    def _auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"} if self.token else {}

    def _post(self, action: str, **payload):
        body = json.dumps({"action": action, **payload}).encode("utf-8")
        request = urllib.request.Request(
            self.base_url + "/api",
            data=body,
            headers={"Content-Type": "application/json", **self._auth_headers()},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                result = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            self.hardware_available = False
            raise RuntimeError(f"Raspberry Pi nije dostupan na {self.host}:{self.port}: {error}") from error
        if not result.get("ok", False):
            raise RuntimeError(result.get("error", "Nepoznata greška Raspberry Pi servera."))
        self.hardware_available = True
        return result

    def status(self) -> dict:
        try:
            with urllib.request.urlopen(urllib.request.Request(self.base_url + "/status", headers=self._auth_headers()), timeout=self.timeout) as response:
                result = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            self.hardware_available = False
            raise RuntimeError(f"Raspberry Pi nije dostupan na {self.host}:{self.port}: {error}") from error
        self.hardware_available = bool(result.get("ok"))
        return result

    def set_simulation(self, enabled: bool) -> None:
        if enabled:
            if self.hardware:
                try:
                    self._post("gpio_cleanup")
                except RuntimeError:
                    pass
            self.simulation = True
            return
        info = self.status()
        if not info.get("ok"):
            raise RuntimeError("Raspberry Pi server nije spreman.")
        self.simulation = False

    def configure(self, pin) -> None:
        if not self.hardware or pin.gpio is None:
            return
        self._post("gpio_configure", pin=int(pin.gpio), direction=pin.direction, value=int(pin.value))

    def read(self, pin) -> int:
        if not self.hardware or pin.gpio is None:
            return int(pin.value)
        result = self._post("gpio_read", pin=int(pin.gpio), direction=pin.direction)
        return int(result["value"])

    def write(self, pin, value: int) -> None:
        pin.value = int(bool(value))
        if not self.hardware or pin.gpio is None:
            return
        if pin.direction != "OUTPUT":
            raise RuntimeError("U HARDVER režimu vrednost se upisuje samo na OUTPUT pin.")
        self._post("gpio_write", pin=int(pin.gpio), value=pin.value)

    def cleanup(self) -> None:
        if self.hardware:
            try:
                self._post("gpio_cleanup")
            except RuntimeError:
                pass

    # I2C
    def i2c_scan(self, bus: int) -> list[int]:
        return [int(v) for v in self._post("i2c_scan", bus=int(bus))["addresses"]]

    def i2c_read(self, bus: int, address: int, register: int, length: int) -> list[int]:
        return [int(v) for v in self._post(
            "i2c_read", bus=int(bus), address=int(address), register=int(register), length=int(length)
        )["values"]]

    def i2c_write(self, bus: int, address: int, register: int, values: list[int]) -> None:
        self._post(
            "i2c_write", bus=int(bus), address=int(address), register=int(register),
            values=[int(v) for v in values],
        )

    # SPI
    def spi_transfer(self, bus: int, device: int, speed: int, mode: int, tx: list[int]) -> list[int]:
        return [int(v) for v in self._post(
            "spi_transfer", bus=int(bus), device=int(device), speed=int(speed), mode=int(mode),
            tx=[int(v) for v in tx],
        )["rx"]]

    # UART
    def uart_open(self, port: str, baud: int) -> None:
        self._post("uart_open", port=port, baud=int(baud))

    def uart_close(self) -> None:
        self._post("uart_close")

    def uart_send(self, data: bytes) -> None:
        self._post("uart_send", data=list(data))

    def uart_receive(self) -> bytes:
        values = self._post("uart_receive").get("data", [])
        return bytes(int(v) for v in values)

    # PWM
    def pwm_start(self, pin: int, frequency: int, duty: float) -> None:
        self._post("pwm_start", pin=int(pin), frequency=int(frequency), duty=float(duty))

    def pwm_stop(self, pin: int | None = None) -> None:
        self._post("pwm_stop", pin=None if pin is None else int(pin))
