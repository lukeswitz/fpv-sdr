<div align="center">

<img width="300" alt="edited-photo-4" src="https://github.com/user-attachments/assets/4ed632ec-ba41-429c-a893-c17e84f74164" />


Receive and decode analog **5.8 GHz FPV video** (the analog NTSC or PAL link in many drones and FPV cameras) with common software-defined radios. **Runs on Linux, macOS, and Windows.**

</div>

---

## What you need

- A [supported SDR](#supported-radios) that reaches 5.8 GHz
- Linux/Widows/macOS machine


## Install
```bash
git clone https://github.com/lukeswitz/fpv-sdr.git
cd fpv-sdr
./setup.sh 
```

> [!TIP]
> Run `./setup.sh --check` to report what's already installed

- **DragonOS** — everything is prebuilt; `./setup.sh` just confirms it.
- **Debian / Ubuntu Linux** — `./setup.sh` installs via apt. Fedora / Arch: prints the packages to install
- **macOS** — needs [Homebrew](https://brew.sh); `./setup.sh` does the rest.

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
./fpv_scanner.sh --standard pal  # PAL camera (625/50); default is NTSC
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
| `standard <ntsc\|pal>` (or `pal` / `ntsc`) | switch video standard — `pal` = 625/50, 360×288 (EU cameras); default `ntsc` |
| `list` / `log` / `stop` / `quit` | channels / history / stop / exit |


> Default is NTSC; use `--standard pal` (or type `pal` at the prompt) for 625/50 PAL cameras. 


- Dial in your settings for your radio (defaults should be ok)
- Run `scan` to search every channel; if it finds a real FPV signal it opens the video on that
channel, use `scan loop` for constant monitoring.

The `spectrum` command takes args for channel, use `spectrum live` to keep it updating:

<img width="934" height="392" alt="FPV-SDR scan output" src="https://github.com/user-attachments/assets/45fb7a73-4ede-482d-9ffd-cde08f0434ab" />

### Tuning the picture (vertical / horizontal hold)

A weak vertical or horizontal sync makes the picture roll or tear (common on PAL).
When the scanner opens the video (after `scan`, `set <CH>`, or `freq <MHz>`), tune it
live from the same terminal with the arrow keys:

- **↑ / ↓** — vertical hold (stop the picture rolling up/down)
- **← / →** — horizontal hold (centre the picture)
- **r** reset · **q** back to the scanner menu

The terminal shows the live `V` / `H` offset and a `lock` meter (≈0 on noise, rises
on a real video signal — so you can tell you're synced to an actual picture, not snow).
PAL often locks better at `--samp-rate 18e6`.

## Channels
64 channels across 8 bands: Raceband, A, B, E, Fatshark, ImmersionRC, DJI, Low (5362–5945 MHz).
**Type `list` to see them all.**

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
> Ensure the gain settings are correct for your device before running. Keep that hackRF amp off ;)

## Troubleshooting
- **Nothing happens during a search** — normal; it stays in the terminal until a signal is found.
- **A known transmitter is ignored** — lower `margin 10`; or if the level sits near −10…−20 dBFS the
  gain is too high (`gain 16`).
- **Signal found but no window** — `export DISPLAY=:0`.
- **Window opens but picture rolls / looks like snow** — sync isn't locked. Run the viewer in the foreground and use the arrow keys (see [Tuning the picture](#tuning-the-picture-vertical--horizontal-hold)); watch the `lock` meter to confirm a real signal. PAL often needs `--samp-rate 18e6`.
- **Radio not found** — SoapySDR: `SoapySDRUtil --find`; ANTSDR: `ping 192.168.1.10 && uhd_find_devices`.
- **BladeRF finds nothing** — its FPGA image must be loaded each power-on; `./setup.sh --check` reports it. Use a USB 3.0 port.

## License
For lawful reception of 5.8 GHz FPV video only — you are responsible for the rules in your
jurisdiction. Provided **as is**, no warranty. The bundled NTSC decoder
([gr-ntsc-rc](https://github.com/lscardoso/gr-ntsc-rc), in `vendor/`) is GPLv3; the rest is MIT. Author assumes no liability for anything this code does.
