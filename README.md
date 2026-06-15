# Dragon FPV Decoder

Receive and decode analog **5.8 GHz FPV video** (the FM-modulated analog NTSC link in many drones and FPV cameras; PAL is not supported) with a software-defined radio. 

All decoding runs on your computer in GNU Radio, the SDR just tunes and streams. **Runs on Linux, macOS, and Windows.**

## What you need
Any supported [radio](#supported-radios) that reaches 5.8 GHz ~20 MHz: HackRF, BladeRF, ANTSDR, USRP ...


## Install
```bash
git clone https://github.com/lukeswitz/dragon-fpv-decoder.git
cd dragon-fpv-decoder
./setup.sh
```

> [!NOTE]
> `./setup.sh` installs everything for your OS and builds the decoder. `./setup.sh --check` only
reports what's installed.

- **DragonOS** — everything is prebuilt; `./setup.sh` just confirms it.
- **Linux (Debian / Ubuntu)** — `./setup.sh` installs via apt. Fedora / Arch: prints the packages to install
- **macOS** — needs [Homebrew](https://brew.sh); `./setup.sh` does the rest.
- **Windows** — see below.

### Windows
The tool runs inside Ubuntu (WSL). From the project folder in **PowerShell**:
```powershell
.\setup.cmd                 # install (run as Administrator the first time; reboot if asked, then run again)
.\run.cmd --sdr hackrf      # run  (leave off --sdr for ANTSDR / USRP)
```



## Run
```bash
./fpv_scanner.sh                 # ANTSDR / USRP (default)
./fpv_scanner.sh --sdr hackrf    # or --sdr bladerf
```


| Command | Does |
|---------|------|
| `scan` | search once; open the video if a signal is found |
| `scan loop [SEC]` | keep searching until a signal; ENTER / Ctrl-C stops, `SEC` auto-stops |
| `sweep` | signal-strength table for all channels, no video |
| `spectrum [live\|CH\|MHz]` | live spectrum in the terminal |
| `set <CH>` / `freq <MHz>` | tune + view a channel (`set R6`) or frequency (`freq 5843`) |
| `sdr <name>` | switch radio (`uhd`, `hackrf`, `bladerf`, `pluto`) |
| `gain <dB>` / `lna <dB>` / `vga <dB>` | RX gain |
| `margin <dB>` | how far over the noise floor counts as a signal (default 12) |
| `rotate` / `contrast` / `record <file>` | adjust + capture video |
| `list` / `log` / `stop` / `quit` | channels / history / stop / exit |

Type `scan`. It searches every channel; if it finds a real FPV signal it opens the video on that
channel, otherwise it prints `No FPV signals`. Use `spectrum` for a live FFT view:

<img width="934" height="392" alt="Dragon FPV Decoder scan output" src="https://github.com/user-attachments/assets/45fb7a73-4ede-482d-9ffd-cde08f0434ab" />

## Channels
64 channels across 8 bands — Raceband, A, B, E, Fatshark, ImmersionRC, DJI, Low (5362–5945 MHz).
Type `list` to see them all.

## Supported radios

| SDR | `--sdr` | Notes |
|-----|---------|-------|
| ANTSDR E200 | `uhd` | recommended |
| USRP B210 / B200mini | `uhd` | |
| BladeRF 2.0 micro | `bladerf` | needs its FPGA image (setup loads it) |
| HackRF One | `hackrf` | 8-bit — _fine_ for FM video, slower fps than the rest|
| ADALM-Pluto | `pluto` | SoapySDR (SoapyPlutoSDR); needs the 5.8 GHz firmware mod, and USB 2.0 caps sustained bandwidth |
| LimeSDR · RTL-SDR · Airspy · SDRplay | — | can't reach 5.8 GHz |

> [!IMPORTANT]
> Ensure the gain settings are not too high for your device. Do not turn on the HackRF amp.

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
([gr-ntsc-rc](https://github.com/lscardoso/gr-ntsc-rc), in `vendor/`) is GPLv3; the rest is MIT. Author assumes no liability for anything this code does.
