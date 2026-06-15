# Dragon FPV Decoder

Receive and decode analog **5.8 GHz FPV video** — the FM/NTSC video link used by many drones and
FPV cameras — with a software-defined radio. The SDR only tunes and streams raw IQ; all
demodulation and NTSC decoding runs on the host CPU in GNU Radio.

Runs on **Linux, macOS, and Windows (via WSL2)**. The interactive scanner sweeps the FPV channels
headless and opens a video window only after it confirms a real FPV carrier — it does not open a
window for every channel.

## Requirements
- An SDR that tunes ~5.6–5.95 GHz and streams ≥20 MHz of bandwidth (see [Supported SDRs](#supported-sdrs)).
- GNU Radio 3.10/3.11 and the bundled `gr-ntsc-rc` decoder (built by `setup.sh`).
- A 5.8 GHz antenna on the RX port, and a powered FPV VTX to actually receive video.

## Install
`./setup.sh` detects your OS, installs the stack, and builds the bundled decoder.
`./setup.sh --check` audits an existing install and changes nothing.

```bash
git clone https://github.com/lukeswitz/dragon-fpv-decoder.git
cd dragon-fpv-decoder
./setup.sh
```

### DragonOS
GNU Radio and `gr-ntsc-rc` ship prebuilt. `setup.sh` detects the decoder and skips the build;
`./setup.sh --check` confirms it. You can run the scanner straight away.

### Linux (Debian / Ubuntu and derivatives)
`setup.sh` installs via apt and builds the decoder. The apt line it runs:
```bash
sudo apt install gnuradio gnuradio-dev soapysdr-tools \
  soapysdr-module-hackrf soapysdr-module-bladerf uhd-host \
  ffmpeg cmake g++ git pkg-config python3-numpy python3-pil \
  python3-dev python3-pybind11 libboost-all-dev libsndfile1-dev
```
Non-apt distros (Fedora/Arch) aren't automated — `setup.sh` prints the packages to install, then
you re-run it.

### macOS (Homebrew)
`setup.sh` installs the brew formulae, builds the SoapySDR HackRF/BladeRF modules from source, and
builds the decoder into `~/.local`.
> Don't `brew install soapyhackrf` / `soapybladerf` — those formulae pull a second Python that can
> shadow GNU Radio's, and their CMake is too old to build. `setup.sh` builds them from C++ source
> instead.

brew's GNU Radio has no `video_sdl`, so the viewer uses an `ffplay` window (same decode).
`fpv_env.sh` locates the GNU Radio Python automatically; set `FPV_PYTHON` to override.

### Windows (WSL2)
No native Windows build — run it inside WSL2 Ubuntu.
```powershell
wsl --install -d Ubuntu
```
Then follow the Linux steps inside Ubuntu. A networked ANTSDR works over normal networking; a USB
radio (HackRF/BladeRF) must be passed in with [usbipd-win](https://github.com/dorssel/usbipd-win)
from an Administrator PowerShell:
```powershell
winget install dorssel.usbipd-win
usbipd list
usbipd bind   --busid <BUSID>
usbipd attach --wsl --busid <BUSID>
```
The decoded-video window uses WSLg (built into Windows 11). **This path is documented but has not
been tested on real Windows hardware.**

## Run
```bash
./fpv_scanner.sh                 # ANTSDR / UHD (default)
./fpv_scanner.sh --sdr hackrf    # or: --sdr bladerf
```
Type `scan`. The detector sweeps every channel headless; if it confirms an FPV signal it opens the
viewer on that channel, otherwise it prints `No FPV signals`.

<img width="934" height="392" alt="Dragon FPV Decoder scan output" src="https://github.com/user-attachments/assets/45fb7a73-4ede-482d-9ffd-cde08f0434ab" />

Commands at the prompt:

| Command | Does |
|---------|------|
| `scan` | sweep once; open the viewer if a signal is confirmed |
| `scan loop [SEC]` | keep sweeping until a signal; ENTER/Ctrl-C stops, `SEC` auto-stops |
| `sweep` | RSSI/SNR table for all channels, no video |
| `spectrum [live\|CH\|MHz] [SEC]` | terminal FFT (whole band, live, or one channel) |
| `set <CH>` / `freq <MHz>` | tune + view a channel (`set R6`) or frequency (`freq 5843`) |
| `sdr <name>` | switch radio (`uhd`, `hackrf`, `bladerf`) |
| `gain <dB>` / `lna <dB>` / `vga <dB>` | RX gain (HackRF gain drives LNA+VGA) |
| `margin <dB>` | SNR over the noise floor to count as a signal (default 12) |
| `dwell <SEC>` | per-chunk sweep settle time |
| `rotate <deg>` / `contrast <x>` / `record <file>` | display + capture |
| `list` / `log` / `stop` / `quit` | channels / scan history / stop sweep / exit |

Settings also accept flags / `FPV_*` env vars: `--sdr --gain --lna --vga --amp --samp-rate
--margin --dev-args --antenna`, and `FPV_CONFIRM=cv|ntsc|snr`.

## Channels
64 channels across 8 bands — Raceband R1–R8, Band A, Band B, Band E, Fatshark F1–F8,
ImmersionRC IMD1–6, DJI D1–D8, Low Band L1–L8 (5362–5945 MHz). Type `list` to print them.

## Supported SDRs
Decoding is entirely host-side, so the SDR's FPGA size is irrelevant — any radio that reaches
5.8 GHz and streams ~20 MHz of bandwidth works.

| SDR | Driver | `--sdr` | Status |
|-----|--------|---------|--------|
| ANTSDR E200 | UHD | `uhd` | Tested on-air |
| HackRF One | SoapySDR | `hackrf` | Tested on-air (decoded video) |
| BladeRF 2.0 micro | SoapySDR | `bladerf` | Tested on-air |
| USRP B210 / B200mini | UHD | `uhd` | Untested — same UHD path as ANTSDR |
| ADALM-Pluto | UHD/IIO | `uhd` | Untested — needs modified firmware to reach 5.8 GHz |
| LimeSDR · RTL-SDR · Airspy · SDRplay | — | — | Won't work — can't tune 5.8 GHz |

The scanner sweeps at 20 MHz (HackRF) or 40 MHz (others) and decodes at 10 MHz — within every
supported radio's limit. Override with `--samp-rate` / `FPV_DETECT_SAMP_RATE`.

**HackRF gain & safety.** Three gain stages: AMP (0/+14 dB), LNA (0–40), VGA (0–62). `--gain`
drives LNA+VGA; the default is 24 dB with **AMP off**. Leave AMP off — HackRF's max safe input is
−5 dBm and the amp on a strong nearby VTX can damage the front end; use an attenuator instead.
Default gains: HackRF 24, BladeRF 20, ANTSDR/UHD 30 (kept low to avoid clipping a close VTX).

## How detection works
For each channel the detector requires three things before calling it a signal:
1. power ≥ `--margin` dB over the measured noise floor (default 12),
2. a narrow peak above its neighbors (rejects broadband Wi-Fi, which can be louder than a real VTX),
3. a constant-envelope check — analog FM video is near-constant amplitude; Wi-Fi and noise are not.

It finds the carrier's true center by an FFT energy centroid and maps it to the nearest channel,
so an off-frequency VTX is still identified (with the offset reported). Where the NTSC decoder is
built, an NTSC sync-lock runs as an extra pass that can rescue a borderline signal but never reject
one. One process owns the radio at a time — the detector releases it before the viewer opens.

## Troubleshooting
- **Nothing happens during a scan** — expected; it's headless until a signal confirms. Watch the
  per-channel dBFS/SNR lines.
- **A known-live VTX is rejected** — lower `margin 10`, or loosen the envelope check with
  `--env-cv`. A floor near −10…−20 dBFS means gain is too high (clipping) → `gain 16`.
- **Signal found but no window** — `export DISPLAY=:0` (WSLg handles this on WSL2).
- **SoapySDR device not found** — `SoapySDRUtil --find`; install the matching `soapysdr-module-*`.
- **BladeRF streams nothing** — its FPGA loads every power-on and the file must be named
  `~/.config/Nuand/bladeRF/hostedxA4.rbf` (xA4) or `hostedxA9.rbf` (xA9) — the nuand download is
  `…-latest.rbf`, rename it. `setup.sh` does this; `--check` reports it. Use a USB 3.0 port.
- **ANTSDR not found** — `ping 192.168.1.10 && uhd_find_devices`.

## Testing
`./tests/smoke_test.sh` verifies an install and boots the app (no radio needed).
`./tests/docker_test.sh` runs the Linux fresh-install in clean containers. Full guide and the
on-air hardware tests: [`tests/README.md`](tests/README.md).

## Project layout
- `setup.sh` — installer (`--check` audits without changing anything)
- `fpv_scanner.sh` — interactive scanner: channel tables, scan→view handoff, radio management
- `fpv_env.sh` — finds the GNU Radio Python and wires its paths
- `fpv_detect.py` — headless detector (FFT sweep + the three gates above)
- `fpv_viewer.py` — opens one video window for one confirmed channel
- `fpv_display.py` — decoded frames → `ffplay` window / PNG / `ffmpeg` recording
- `fpv_spectrum.py` — terminal FFT renderer
- `fpv_sdr.py` — shared UHD / SoapySDR source factory
- `vendor/gr-ntsc-rc/` — bundled NTSC decoder (pinned; see `VENDORED.md`)
- `patches/` — the converter-bounds diff (already baked into `vendor/`)
- `tools/`, `reference/` — standalone tune helper; original GRC flowgraph (not used at runtime)

## Credits & license
- NTSC decoder: [gr-ntsc-rc](https://github.com/lscardoso/gr-ntsc-rc) (GPLv3), vendored from PR #6.
- ANTSDR: MicroPhase Technology.
- This project is MIT (`LICENSE`); the vendored `vendor/gr-ntsc-rc/` tree is GPLv3 under its own
  `LICENSE`.

## Legal
For receiving analog 5.8 GHz FPV video. You are solely responsible for complying with the laws and
obtaining any authorization required in your jurisdiction. Provided **AS IS**, with no warranty and
no liability. **Use at your own risk.**
