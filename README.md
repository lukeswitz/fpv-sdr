# Dragon FPV Decoder

Receive and decode analog **5.8 GHz FPV video** (the FM/NTSC link in many drones and FPV cameras)
with a software-defined radio. All decoding runs on your computer in GNU Radio — the SDR just tunes
and streams. Runs on Linux, macOS, and Windows.

A video window opens only when a real FPV signal is found — not for every channel.

## What you need
- An SDR that reaches 5.8 GHz and streams ~20 MHz: ANTSDR / USRP (UHD), or HackRF / BladeRF (SoapySDR).
- A 5.8 GHz antenna on the radio, and a powered FPV transmitter to receive.

## Install
```bash
git clone https://github.com/lukeswitz/dragon-fpv-decoder.git
cd dragon-fpv-decoder
./setup.sh
```
`./setup.sh` installs everything for your OS and builds the decoder. `./setup.sh --check` only
reports what's installed.

- **DragonOS** — everything is prebuilt; `./setup.sh` just confirms it.
- **Linux (Debian / Ubuntu)** — `./setup.sh` installs via apt. Fedora / Arch: it prints the packages to install, then re-run it.
- **macOS** — needs [Homebrew](https://brew.sh); `./setup.sh` does the rest.
- **Windows** — see below.

### Windows
The tool runs inside Ubuntu (WSL). From the project folder in **PowerShell**:
```powershell
.\setup.cmd                 # install (run as Administrator the first time; reboot if asked, then run again)
.\run.cmd --sdr hackrf      # run  (leave off --sdr for ANTSDR / USRP)
```

**Running Windows in a VM on a Mac (Parallels)?** WSL needs nested virtualization, which only
**M3 or newer** Macs have. On an **M1 / M2 Mac you get WSL1**: the tool installs and the terminal
parts (`scan`, `sweep`, `spectrum`) work with a **networked ANTSDR**, but **USB radios and the video
window won't** — those need WSL2, i.e. a physical Windows PC or an M3+ Mac. A physical Windows PC
has WSL2 and runs everything.

## Run
```bash
./fpv_scanner.sh                 # ANTSDR / USRP (default)
./fpv_scanner.sh --sdr hackrf    # or --sdr bladerf
```
Type `scan`. It searches every channel; if it finds a real FPV signal it opens the video on that
channel, otherwise it prints `No FPV signals`.

<img width="934" height="392" alt="Dragon FPV Decoder scan output" src="https://github.com/user-attachments/assets/45fb7a73-4ede-482d-9ffd-cde08f0434ab" />

| Command | Does |
|---------|------|
| `scan` | search once; open the video if a signal is found |
| `scan loop [SEC]` | keep searching until a signal; ENTER / Ctrl-C stops, `SEC` auto-stops |
| `sweep` | signal-strength table for all channels, no video |
| `spectrum [live\|CH\|MHz]` | live spectrum in the terminal |
| `set <CH>` / `freq <MHz>` | tune + view a channel (`set R6`) or frequency (`freq 5843`) |
| `sdr <name>` | switch radio (`uhd`, `hackrf`, `bladerf`) |
| `gain <dB>` / `lna <dB>` / `vga <dB>` | RX gain |
| `margin <dB>` | how far over the noise floor counts as a signal (default 12) |
| `rotate` / `contrast` / `record <file>` | adjust + capture video |
| `list` / `log` / `stop` / `quit` | channels / history / stop / exit |

## Channels
64 channels across 8 bands — Raceband, A, B, E, Fatshark, ImmersionRC, DJI, Low (5362–5945 MHz).
Type `list` to see them all.

## Supported radios
Decoding is all on your computer, so the SDR's FPGA size doesn't matter — any radio that reaches
5.8 GHz and streams ~20 MHz works.

| SDR | `--sdr` | Notes |
|-----|---------|-------|
| ANTSDR E200 | `uhd` | recommended |
| USRP B210 / B200mini | `uhd` | |
| BladeRF 2.0 micro | `bladerf` | needs its FPGA image (setup loads it) |
| HackRF One | `hackrf` | 20 MHz / 8-bit — fine for FM video |
| ADALM-Pluto | `uhd` | only with modified firmware for 5.8 GHz |
| LimeSDR · RTL-SDR · Airspy · SDRplay | — | can't reach 5.8 GHz |

**HackRF safety:** leave the amp **off** (the default). HackRF's max input is −5 dBm — the amp on a
strong nearby transmitter can damage it; use an attenuator instead. `--gain` drives LNA + VGA
(default 24).

## Troubleshooting
- **Nothing happens during a search** — normal; it stays in the terminal until a signal is found.
- **A known transmitter is ignored** — lower `margin 10`; or if the level sits near −10…−20 dBFS the
  gain is too high (`gain 16`).
- **Signal found but no window** — `export DISPLAY=:0`.
- **Radio not found** — SoapySDR: `SoapySDRUtil --find`; ANTSDR: `ping 192.168.1.10 && uhd_find_devices`.
- **BladeRF finds nothing** — its FPGA image must be loaded each power-on; `./setup.sh --check` reports it. Use a USB 3.0 port.

## License
For lawful reception of 5.8 GHz FPV video only — you are responsible for the rules in your
jurisdiction. Provided **as is**, no warranty. The bundled NTSC decoder
([gr-ntsc-rc](https://github.com/lscardoso/gr-ntsc-rc), in `vendor/`) is GPLv3; the rest is MIT.
