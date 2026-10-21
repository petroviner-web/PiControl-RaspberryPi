# PiControl Qt Designer — HARDVER FIX

Ova verzija ispravlja GPIO HARDVER režim bez menjanja `.ui` fajlova.

## Šta je ispravljeno

- GPIO INPUT se pre prvog čitanja bezbedno konfiguriše preko `RPi.GPIO`.
- INPUT koristi interni `PUD_DOWN`, pa nepovezan pin stabilno čita `0` umesto da "pluta".
- Samo trenutno izabrani pin u **GPIO** kartici periodično se čita sa fizičkog Raspberry Pi pina.
- I2C/SPI/UART/PWM kartice više ne pokušavaju da tretiraju svoje signalne pinove kao obične GPIO pinove u hardverskom režimu.
- Prebacivanje u HARDVER više ne radi `GPIO.setup()` nad svim pinovima odjednom.
- OUTPUT upis je dozvoljen samo kada je pin podešen kao `OUTPUT`.
- `cleanup()` briše i interno stanje konfigurisanih GPIO kanala.
- U HARDVER režimu indikator sada piše `Fizički GPIO ulaz/izlaz`, a ne `Virtuelni`.

## Kako proveriti fizički INPUT

Primer koristi **GPIO17**, fizički pin **11**.

1. Pokreni aplikaciju na Raspberry Pi-ju.
2. Izaberi `HARDVER`.
3. Otvori karticu `GPIO`.
4. Klikni fizički pin 11 / GPIO17.
5. Postavi smer na `INPUT`.
6. Dok ništa nije povezano, interni pull-down treba da drži vrednost na `0`.
7. Dovedi **3,3 V** na GPIO17 (preporučeno preko ~1 kΩ serijskog otpornika za bench demo).
8. U roku od približno 750 ms tabela/status treba da pređu na `1 / HIGH`.
9. Ukloni 3,3 V: vrednost treba da se vrati na `0 / LOW`.

**Nikada ne dovoditi 5 V direktno na Raspberry Pi GPIO.**

## Kako proveriti OUTPUT

1. Izaberi GPIO17 u GPIO kartici.
2. Postavi `OUTPUT`.
3. Klikom na `Vrednost` menjaj `0 ↔ 1`.
4. Na fizičkom pinu GPIO17 treba da se dobije LOW/HIGH nivo (0 V / približno 3,3 V).

Za LED koristi odgovarajući serijski otpornik (npr. 220–1kΩ) i vodi računa o polaritetu.

## Važna napomena za protokolske pinove

Ako planiraš da koristiš I2C/SPI/UART, nemoj prethodno ručno preuzimati njihove pinove kao običan GPIO u GPIO kartici. Linux pin-mux i odgovarajući interfejs treba da ostanu aktivni za protokol.

Za jednostavan GPIO test koristi npr. GPIO17 (fizički 11), GPIO27 (13), GPIO22 (15), GPIO23 (16) ili GPIO24 (18).
