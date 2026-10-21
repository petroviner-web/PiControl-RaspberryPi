# PiControl — Qt Designer verzija

Ova verzija ima istu Full Simulation / Hardware logiku, ali je GUI izdvojen u **Qt Designer `.ui` fajlove**.

## Najvažnije

Ne moraš da pokrećeš `pyside6-uic` posle svake izmene. Program koristi `QUiLoader` i učitava `.ui` fajlove direktno pri pokretanju.

## Kako da pokreneš aplikaciju

```powershell
py -m pip install -r requirements.txt
py main.py
```

## Kako da otvoriš GUI u Qt Designer-u

```powershell
pyside6-designer
```

Zatim u Designer-u otvori fajlove iz foldera `ui`:

- `main_window.ui` — naslov, režim SIMULACIJA/HARDVER i tabovi
- `function_panel.ui` — Raspberry Pi ploča, 40 pinova, kontrole i tabela
- `i2c_panel.ui` — I²C deo
- `spi_panel.ui` — SPI deo
- `uart_panel.ui` — UART deo
- `pwm_panel.ui` — PWM deo
- `gpio_panel.ui` — tekst GPIO panela

Posle `Ctrl+S` samo ponovo pokreni `py main.py` i promene će se videti.

## Važno: ne menjaj objectName bez izmene Python koda

Možeš slobodno menjati poziciju, veličinu, tekst, font, minimum/maximum size, layout i većinu vizuelnih svojstava.

Ako promeniš `objectName`, npr. `pinTable`, `modeCombo`, `scanButton`, Python više neće moći da pronađe taj element dok se isto ime ne promeni i u kodu.

## Boje

Globalni izgled je u `styles.qss`. Dinamičke boje GPIO pinova i indikatora se i dalje postavljaju iz Python koda zato što zavise od INPUT/OUTPUT i LOW/HIGH stanja.

> Napomena: Stara programski generisana GUI verzija nije uključena u ovaj javni paket.
