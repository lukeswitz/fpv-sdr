<div align="center">

<img width="320" alt="fpv-sdr" src="https://github.com/user-attachments/assets/93b07877-7645-4147-af02-5f316be1cab2" />



Receive and decode analog **5.8 GHz FPV video** (the analog NTSC or PAL link in many drones and FPV cameras) with common software-defined radios. **Runs on Linux, macOS, and Windows.**

</div>


- [What you need](#what-you-need)
- [Install](#install)
- [Run](#run)
  - [Tuning the picture](#tuning-the-picture-vertical--horizontal-hold)
  - [Common adjustments](#common-adjustments--type-these-at-the--prompt)
- [Channels](#channels)
- [Supported radios](#supported-radios)
- [Troubleshooting](#troubleshooting)
- [License](#license)
- [Legal & Acceptable Use](#legal--acceptable-use)
  
---

## What you need

- A [supported SDR](#supported-radios): HackRF, BladeRF, B210/200mini, ANT E200, ADALM-Pluto
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


> **Updating:** `git pull`, then restart the scanner— no rebuild needed (re-run `./setup.sh` only if it ever reports a missing component).

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
| `gain <dB>` / `lna <dB>` / `vga <dB>` | RX gain (HackRF default 36; `gain` sets both LNA+VGA) |
| `samp-rate <Msps>` | capture bandwidth — auto per SDR; raise/lower if needed (`samp-rate 14`) |
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

The terminal shows the live `V` / `H` offset and a `lock` meter (0–100%; 0 = noise,
~100% = real synced picture). This is a *hold* (it repositions a split/offset frame) —
not needed once the picture sits right.

### Common adjustments — type these at the `>` prompt

| If you see… | Type this |
|-------------|-----------|
| weak / grainy picture, black flicker at the top | `lna 36` then `gain 40` (more sensitivity) |
| washed-out / too bright | `gain 16` (less gain) |
| choppy video or `OsO` text spamming | `samp-rate 10` (lower bandwidth so the PC keeps up) |
| sharp signal, want more detail | `samp-rate 16` (higher bandwidth) |
| a known channel isn't being found | `margin 8` (detect weaker signals) |
| picture too dark / too washed | `contrast 0.9` (brighter) or `contrast 0.6` (flatter) |
| PAL camera | `pal` |
| frame split by a black bar | hold **↓** until the bar rolls off the bottom |

Defaults per radio are auto-set (e.g. HackRF: gain 36, `samp-rate 12`); the commands above just override them.

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
| ADALM-Pluto | `pluto` | SoapySDR; needs the 5.8 GHz firmware mod; USB 2.0 caps it to ~8 Msps |
| CaribouLite | `cariboulite` | SoapySDR; reaches 5.8 but only 2.5 MHz BW — too narrow for a usable picture |
| LimeSDR · RTL-SDR · Airspy · SDRplay | — | can't reach 5.8 GHz |

> Capture bandwidth is set automatically per radio (HackRF 12, bladeRF 18, ANTSDR/USRP 20, Pluto 8 Msps); override with `samp-rate <Msps>`.

> [!IMPORTANT]
> Ensure the gain settings are correct for your device before running. Keep that hackRF amp off ;)

## Troubleshooting
- **Nothing happens during a search** — normal; it stays in the terminal until a signal is found.
- **A known transmitter is ignored** — lower `margin 10`; or if the level sits near −10…−20 dBFS the
  gain is too high (`gain 16`).
- **Signal found but no window** — `export DISPLAY=:0`.
- **Black flicker at the top of the frame** — weak signal; `lna 36`, a better 5.8 antenna, or move closer.
- **Choppy video or `OsO` text spamming the terminal** — the PC can't keep up at that rate; `samp-rate 10`.
- **Picture split or rolling** — hold it with the arrow keys (see [Tuning the picture](#tuning-the-picture-vertical--horizontal-hold)); `lock` near 100% confirms a real signal.
- **Radio not found** — SoapySDR: `SoapySDRUtil --find`; ANTSDR: `ping 192.168.1.10 && uhd_find_devices`.
- **BladeRF finds nothing** — its FPGA image must be loaded each power-on; `./setup.sh --check` reports it. Use a USB 3.0 port.

## License
For lawful reception of 5.8 GHz FPV video only — you are responsible for the rules in your
jurisdiction. Provided **as is**, no warranty. The bundled NTSC decoder
([gr-ntsc-rc](https://github.com/lscardoso/gr-ntsc-rc), in `vendor/`) is GPLv3; the rest is MIT. Author assumes no liability for anything this code does.

## Legal & Acceptable Use

`fpv-sdr` is provided for lawful, educational, and authorized-testing purposes
only — e.g. receiving signals you own, operate, or have explicit permission to
receive.

You are solely responsible for ensuring your use complies with all applicable
laws, which may include radio-interception, wiretap, privacy, and aviation
statutes. In the United States these may include the Electronic Communications
Privacy Act (18 U.S.C. § 2511) and the Communications Act (47 U.S.C. § 605);
other jurisdictions impose their own rules. Intercepting, decoding, recording,
or divulging communications you are not authorized to receive may be a criminal
offense.

This project does not endorse or support using the software to intercept,
monitor, or interfere with systems operated by third parties — including
government, law enforcement, commercial, or private operators — without their
authorization. Requests for help doing so will be declined.

The software is provided "as is," without warranty of any kind. The authors
accept no liability for misuse. This notice is not legal advice; consult a
qualified attorney in your jurisdiction.
