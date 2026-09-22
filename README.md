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

- **DragonOS** — the SDR stack (GNU Radio, SoapySDR, UHD) is already there, built into `/usr/local`,
  and apt is pinned so it cannot be overwritten. `./setup.sh` detects that and skips it. gr-ntsc-rc is
  not part of that stack, so setup builds it from `vendor/`.
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
| `agc <on\|off\|dBFS>` | auto RX gain — tracks LNA/VGA to hold the ADC level (default off, target −20 dBFS) |
| `samp-rate <Msps>` | capture bandwidth — auto per SDR; raise/lower if needed (`samp-rate 14`) |
| `margin <dB>` | how far over the noise floor counts as a signal (default 12) |
| `rotate` / `contrast` / `record <file>` | adjust + capture video |
| `standard <ntsc\|pal>` (or `pal` / `ntsc`) | switch video standard — `pal` = 625/50, 360×288 (EU cameras); default `ntsc` |
| `band <58\|12>` | scan band: 5.x GHz (default) or 1.2/1.3 GHz long-range — fit the matching antenna |
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
| weak / grainy picture, black flicker at the top | `gain 40` (more sensitivity, for a distant transmitter) |
| signal level keeps drifting as you move around | `agc on` — tracks LNA/VGA instead of holding one fixed gain |
| vertical line or smear down the middle of the picture | `export FPV_VIEW_EXTRA="--if-offset 3e6"` — moves the receiver's DC spike off the carrier |
| picture tears into sideways-shifted bands | noise is false-triggering the line sync — try `gain 32` first if the transmitter is close, `gain 40` if it is far |
| choppy video or `OsO` text spamming | `samp-rate 12` (lower bandwidth so the PC keeps up) |
| sharp signal, want more detail | `samp-rate 16` (higher bandwidth) |
| a known channel isn't being found | `margin 8` (detect weaker signals) |
| washed-out, everything mid-gray | `contrast 1.6` (more range) |
| only part of the frame has picture, rest flat gray | `contrast 1.1` — the composite is overshooting the decoder's window |
| PAL camera | `pal` |
| frame split by a black bar | hold **↓** until the bar rolls off the bottom |
| flat / washed-out picture on 1.2 GHz | `contrast 4` (1.2 GHz uses ~¼ the FM deviation of 5.8 GHz, so the demod output is weaker — raise contrast) |

Defaults per radio are auto-set (e.g. HackRF: gain 36, `samp-rate 14`); the commands above just override them.

`contrast` scales the demodulated composite onto the levels the decoder expects
(`BLACK_LEVEL -0.02`, `WHITE_LEVEL 0.06` in `vendor/gr-ntsc-rc/lib/NTSC_configuration.h`). The DC
offset that keeps the back porch above the decoder's `-0.020` sync threshold is derived from
`contrast`, so one knob moves both. The default suits a 5.8 GHz link; for a transmitter with very
different FM deviation, measure the back-porch and sync-tip levels and pass `--sync-mid`.

## Channels
64 channels across 8 bands: Raceband, A, B, E, Fatshark, ImmersionRC, DJI, Low (5362–5945 MHz).
**Type `list` to see them all.**

`scan`/`sweep`/`spectrum` cover the 5.x GHz bands by default. Type **`band 12`** to point them at
1.2/1.3 GHz (and `band 58` to switch back) — these use a different, physically larger antenna, so
they aren't scanned together. 1.2/1.3 GHz has **no standard channel grid** (transmitters sit anywhere
from 1010–1360 MHz), so `band 12` runs a **gapless sweep** of the whole range rather than fixed
channels — nothing slips through the gaps. To watch one frequency, use `freq 1280` (the popular US
channels are 1258 and 1280 MHz).
1.2/1.3 GHz is licence-restricted in most countries (US: ham licence; illegal in much of the EU/UK).

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

> Capture bandwidth is set automatically per radio (HackRF 14, bladeRF 18, ANTSDR/USRP 20, Pluto 8 Msps); override with `samp-rate <Msps>`.

> [!IMPORTANT]
> Ensure the gain settings are correct for your device before running. Keep that hackRF amp off ;)

## Troubleshooting
- **Nothing happens during a search** — normal; it stays in the terminal until a signal is found.
- **A known transmitter is ignored** — lower `margin 10`; or if the level sits near −10…−20 dBFS the
  gain is too high (`gain 16`).
- **Signal found but no window** — `export DISPLAY=:0`.
- **Window opens but stays blank (Linux)** — the gr-video-sdl sink renders black on some Linux
  desktops even with SDL's software YUV overlay forced. The viewer therefore uses `ffplay` whenever
  it is installed; `--display sdl` selects the SDL sink if you want it.
- **Black flicker at the top of the frame** — weak signal; `gain 40`, a better 5.8 antenna, or move closer.
- **Choppy video or `OsO` text spamming the terminal** — the PC can't keep up at that rate; `samp-rate 12`.
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
