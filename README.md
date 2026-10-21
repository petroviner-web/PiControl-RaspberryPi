# PiControl B+ — Raspberry Pi Hardware Control Dashboard

**Desktop control and monitoring of Raspberry Pi GPIO, I²C, SPI, UART and PWM — with simulation and hardware modes.**

Built as a measurement and control engineering project. A Python/PySide6 interface represents a Raspberry Pi 40-pin header and provides dedicated controls for digital I/O, I²C peripherals, SPI transfers, UART messages and PWM signals. A small HTTP/JSON service running on Raspberry Pi executes the hardware operations; the same UI can demonstrate these workflows without hardware in simulation mode.

**Tech stack:** Python · PySide6 / Qt Designer · Raspberry Pi · GPIO · I²C · SPI · UART · PWM · HTTP/JSON · Linux

## Features

- **Digital I/O:** select pins, change INPUT/OUTPUT direction, read signal levels, toggle outputs.
- **I²C:** scan buses, read and write registers; simulated TMP102 and OLED devices.
- **SPI:** configure bus, mode, clock speed, and full-duplex transfers; virtual flash ID response.
- **UART:** configure serial port and baud rate, exchange messages; simulation support.
- **PWM:** select pin, frequency and duty cycle; control PWM channel remotely.
- **Simulation / hardware:** usable on a normal computer without Raspberry Pi, or connected to a Pi over a local private network.
- **GUI:** Qt Designer `.ui` forms loaded dynamically by PySide6; includes editable stylesheet.

## Architecture

```text
Desktop workstation
└── PySide6 desktop GUI (main.py + protocol_controls.py)
      └── RemoteBackend (remote_backend.py)
            │ HTTP + JSON; bearer token when LAN-bound
            ▼
      Pi hardware server (pi_server.py)
            ├── RPi.GPIO (GPIO / PWM)
            ├── smbus2 (I²C)
            ├── spidev (SPI)
            └── pyserial (UART)
```

The server uses `ThreadingHTTPServer` with a lock around hardware operations. **Simulation mode does not need a running server.**

## Quick start (simulation mode)

**Requirements:** Python 3.10+ and a desktop capable of running PySide6.

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
py main.py
```

Or Linux/macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

The application starts in `SIMULACIJA` mode; **do not switch to hardware mode unless a Raspberry Pi server is available and correctly configured.**

## Raspberry Pi hardware mode

> **Security warning:** This API can directly alter physical pins and buses. Never expose port 8765 to the public Internet. Communications use **plain HTTP**; for remote connections use an SSH tunnel or an isolated, trusted network. A bearer token protects against unauthenticated requests, but does not encrypt traffic.

### Recommended: local SSH tunnel

On the Raspberry Pi, enable the required hardware interfaces, install the Pi-side Python dependencies (`python3 -m pip install -r requirements-pi.txt` in a compatible environment), and ensure the OS-supported `RPi.GPIO` module is available. **Do not install the desktop-only PySide6 dependency on the Pi.** Keep the server bound to loopback (default):

```bash
python3 pi_server.py
```

From the workstation, establish a tunnel:

```bash
ssh -L 8765:127.0.0.1:8765 pi@your-raspberry-pi-host
```

In a separate terminal launch `python main.py`. Default `PICONTROL_HOST=127.0.0.1` and `PICONTROL_PORT=8765` work with this tunnel. Select `HARDVER` after the server is ready.

### LAN deployment (only on a trusted network)

Generate a strong shared secret using `python -c "import secrets; print(secrets.token_urlsafe(32))"`, then set identical `PICONTROL_TOKEN` in the server and client environments, then set `PICONTROL_BIND=0.0.0.0` on the Pi and `PICONTROL_HOST=<Pi's private IP>` on the desktop. Network binding requires a token of at least 24 characters. Avoid copying tokens into source files or committing your personal `.env`.

**Environment variables:**

| Variable | Purpose | Default |
| --- | --- | --- |
| `PICONTROL_HOST` | GUI target IP / host | `127.0.0.1` |
| `PICONTROL_PORT` | HTTP port | `8765` |
| `PICONTROL_BIND` | Server listening address | `127.0.0.1` |
| `PICONTROL_TOKEN` | Shared bearer token | unset for loopback |

Sample configuration lives in `.env.example` (edit **locally**, not in the repository). The app reads environment variables; it does not automatically load a `.env` file.

## Tests and development

```bash
python -m unittest discover -s tests -v
python -m compileall -q .
```

The repository CI runs headless tests. Hardware integration tests require a Raspberry Pi and actual wiring.

## GPIO safety

- Raspberry Pi GPIO is **3.3 V logic**; never connect 5 V directly to a GPIO signal.
- Use appropriate current-limiting resistors and verify wiring before enabling outputs or PWM.
- Reserve I²C/SPI/UART pins for their system peripherals; do not reconfigure them as general GPIO at the same time.
- Simulated devices and hardware measurements are distinct. Do not use this project for critical industrial control.

## Repository layout

```text
main.py              Qt window and Raspberry Pi pin model
protocol_controls.py Dedicated bus / PWM controls
remote_backend.py    HTTP/JSON client
pi_server.py         Raspberry Pi hardware command server
ui/                  Qt Designer layouts
styles.qss           Appearance
docs/                Setup and implementation notes
tests/               Pure-Python tests
```

## Project status and limitations

- These sources are adapted from the original archive to make network configuration safer; see `docs/CHANGES.md`.
- Original project report documents bench experiments using a BMP280 sensor, LEDs and SPI/UART loopback. **The report is not published** because it contains a personal student identifier.
- Automated tests cover the networking guardrails and Python modules, not physical hardware.
- UI screenshot is not included because the GUI could not be launched in the preparation environment. Run the application locally and capture a genuine screenshot for this README.

## Credits

Project by **Stefan Petrović**. Intended as an educational embedded/automation portfolio project.
