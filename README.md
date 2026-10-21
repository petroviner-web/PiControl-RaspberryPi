# PiControl B+ — Raspberry Pi Hardware Control Dashboard

Python/PySide6 desktop application for Raspberry Pi GPIO, I²C, SPI, UART and PWM control, with simulation and hardware modes.

**Stack:** Python, PySide6 / Qt Designer, Raspberry Pi, GPIO, I²C, SPI, UART, PWM, HTTP/JSON, Linux.

## Features

- GPIO input/output, pin selection and reading signal states
- I²C bus scanning and register operations
- SPI configuration and transfers
- UART communication
- PWM frequency and duty-cycle control
- Simulation without physical hardware
- Raspberry Pi HTTP/JSON server for real hardware

## Repository status

**Source upload pending.** The full, prepared source code is available in the `PiControl-RaspberryPi_GitHub_Ready.zip` archive supplied in the ChatGPT conversation. The repository currently contains documentation only. Do not treat it as a runnable release until source files are committed.

## Architecture

```text
Desktop Python/PySide6 GUI
        |
        +-- simulation mode
        |
        +-- HTTP JSON client (remote_backend.py)
                    |
                    v
             Raspberry Pi server (pi_server.py)
                  GPIO / I2C / SPI / UART / PWM
```

## Run (once source is uploaded)

```bash
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

Default mode is simulation; no Raspberry Pi required.

The Raspberry Pi server listens on loopback by default. To connect over a network, prefer an SSH tunnel; if binding to a LAN interface, configure a shared `PICONTROL_TOKEN` of at least 24 characters. **Never expose the server to the public Internet.**

## Tests

```bash
python -m unittest discover -s tests -v
```

## Safety

This is a portfolio/demo project, not certified industrial control software. Observe 3.3 V GPIO limits. Original private project report containing student identifying information is intentionally excluded from public distribution.

Project by Stefan Petrović.
