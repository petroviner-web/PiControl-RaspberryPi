# Changes made for public portfolio release

The implementation is preserved from the supplied PiControl archive, with focused changes:

1. Removed machine-specific `192.168.1.50` settings from `main.py`, `remote_backend.py` and `pi_server.py`; use environment variables instead.
2. The hardware-control API defaults to loopback binding (`127.0.0.1`), and a LAN bind requires a 24+ character bearer token. Client requests send an `Authorization` header when configured.
3. The HTTP request body is capped at 32 KiB. The hardware API still uses **unencrypted HTTP**; SSH tunneling or a protected private network is required.
4. Added public README, `.gitignore`, example environment settings, Pi-only dependencies and headless checks.
5. Excluded `desktop.ini`, compiled Python caches and original PDF report, which includes the student's personal identifier.
6. Did not add fabricated screenshots or claim independent hardware verification.

## Compatibility note

This repository is a cleaned **portfolio release**. It has not been retested on the original Raspberry Pi Model B+ or with the original wiring after the configuration changes. Simulation can be checked in a PySide6-capable desktop environment; hardware testing should be done gradually and only on an isolated network.
