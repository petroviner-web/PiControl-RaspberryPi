# Architecture and interfaces

The desktop UI (`main.py` + `protocol_controls.py`) talks to `RemoteBackend`, which sends HTTP/JSON requests to `pi_server.py` on a Raspberry Pi. The hardware server dispatches actions to GPIO, I²C, SPI, UART and PWM libraries.

The client has simulation support for workflows without hardware. Hardware commands are sent only when the user enters HARDVER mode. Commands are serialized using a reentrant lock around dispatch operations.

## API surface

- `GET /status`: server and GPIO readiness check.
- `POST /api`: JSON body with `action` and operation-specific arguments.

Actions include `gpio_configure`, `gpio_read`, `gpio_write`, `gpio_cleanup`, `i2c_scan`, `i2c_read`, `i2c_write`, `spi_transfer`, `uart_open`, `uart_send`, `uart_receive`, `uart_close`, `pwm_start` and `pwm_stop`.

The server is configured to bind to loopback by default. For LAN listening, it requires a bearer token, but does **not** provide transport-layer encryption. Use an SSH tunnel or a VPN for remote usage.

## Demo and original hardware validation

The original accompanying report describes an actual bench setup with a Raspberry Pi Model B+, BMP280 over I²C, LED and PWM testing, SPI loopback and UART loopback. Documentation was derived from the provided report; hardware test results were not independently repeated during repository preparation.
