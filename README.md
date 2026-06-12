# Dragon FPV Decoder

NTSC 5.8 GHz FPV video receiver and scanner for ANTSDR E200 using GNU Radio.

## Prerequisites

- ANTSDR configured with **UHD firmware** 
- GNU Radio and UHD drivers (pre-installed on WarDragon)
- Specified PR of gr-ntsc-rc

## Installation
```bash
# Clone gr-ntsc-rc decoder module
git clone https://github.com/lscardoso/gr-ntsc-rc.git
cd gr-ntsc-rc
git fetch origin pull/6/head:pr6
git checkout pr6

# Clone Dragon FPV Decoder
cd ~/
git clone https://github.com/lukeswitz/dragon-fpv-decoder.git
cd dragon-fpv-decoder
chmod +x fpv_scanner.sh
```

## Verify ANTSDR Connection
```bash
ping 192.168.1.10
uhd_find_devices
```

## macOS (Apple Silicon) + HackRF

The scanner runs on macOS via Homebrew GNU Radio. `fpv_env.sh` auto-detects the
right Python (Homebrew's GNU Radio uses its own `python@3.x`; the system `python3`
has no bindings) and wires Homebrew's keg-isolated numpy onto the path.

```bash
brew install gnuradio soapysdr soapyhackrf hackrf bash
hackrf_info                 # confirm the HackRF is detected
SoapySDRUtil --find         # confirm SoapySDR sees driver=hackrf
./fpv_scanner.sh --sdr hackrf
```

HackRF RX gains follow the official stages (`AMP` RF amp 0/+11 dB, `LNA` 0–40,
`VGA` 0–62). **The RF amp (`AMP`) is left OFF** — HackRF's max input is −5 dBm and
enabling the amp on a strong signal can destroy the front-end LNA. Use an external
attenuator for very strong transmitters rather than risking the front-end.

Homebrew GNU Radio ships neither the `gnuradio.NTSC` out-of-tree module nor
`video_sdl`. Build the decoder once, into your user prefix:

```bash
brew install cmake pybind11
git clone https://github.com/lscardoso/gr-ntsc-rc.git && cd gr-ntsc-rc
git fetch origin pull/6/head:pr6 && git checkout pr6
git apply ~/dragon-fpv-decoder/patches/gr-ntsc-rc-converter-bounds.patch   # crash fix, see below
PY=/opt/homebrew/opt/python@3.14/bin/python3.14            # match your brew GNU Radio python
export PYTHONPATH=/opt/homebrew/opt/numpy/lib/python3.14/site-packages
cmake -B build -S . -DCMAKE_PREFIX_PATH=/opt/homebrew \
  -DCMAKE_INSTALL_PREFIX=$HOME/.local \
  -DPYTHON_EXECUTABLE=$PY -DGR_PYTHON_DIR=$HOME/.local/lib/python3.14/site-packages
cmake --build build -j4 && cmake --install build
```

The patch fixes an out-of-bounds read in the gr-ntsc-rc video stream converter:
it reads `1.93 × noutput` input samples from a buffer that holds only `noutput`,
which segfaults on a marginal signal (clean ANTSDR signals get lucky and never
crash). The macOS viewer bypasses the converter entirely — it reads the decoder's
x/y/luma ports into a bounds-checked sink — but apply the patch when building
gr-ntsc-rc on the **WarDragon/ANTSDR** too, so its `video_sdl` path is crash-proof.

`fpv_env.sh` adds `~/.local/lib/python3.x/site-packages` to the path automatically.
`video_sdl` is still absent, so the viewer decodes the NTSC stream into a live
ffplay window (`fpv_display.decoder_sink`) instead of the SDL sink:

```bash
"$PYTHON" fpv_viewer.py --sdr hackrf --gain 40 --samp-rate 10e6 --freq 5725e6
```

Note: HackRF captures ~10 MHz of the ~18 MHz analog FPV signal (the decoder runs
at 10 Msps), so tune to the transmitter's true center for the best image. The
WarDragon/ANTSDR captures the full signal and decodes cleaner.

## Usage
```bash
./fpv_scanner.sh                 # ANTSDR / UHD (default)
./fpv_scanner.sh --sdr hackrf    # HackRF via SoapySDR
./fpv_scanner.sh --sdr bladerf --gain 30
```

Flags: `--sdr <name>` `--gain <dB>` `--samp-rate <Hz>` `--power-thresh <dBFS>` `--dev-args <str>` `--antenna <name>` (all also settable via `FPV_*` env vars).

### How scanning works

`scan` runs a **headless** sweep of all channels — **no video window opens** while it searches. Each channel is gated in two stages: RF power must cross a threshold, then the NTSC decoder must achieve sync-lock (this rejects 5.8 GHz Wi-Fi and other non-video carriers). The video window opens **only** when a channel locks. One process owns the radio at a time, so the detector hands the radio off to the viewer on a hit.

### Commands

- `scan` - Headless sweep; window opens only on a locked signal
- `stop` - Stop the sweep
- `set <CH>` - Tune and view a specific channel (e.g., `set R6`, `set A8`)
- `freq <MHz>` - Tune and view an exact frequency (e.g., `freq 5843`)
- `list` - Show all available channels
- `sdr <NAME>` - Switch radio at runtime (`uhd`, `hackrf`, `bladerf`, …)
- `gain <dB>` - Set RX gain
- `dwell <SEC>` - Per-candidate lock dwell time (default: 0.7s)
- `log` - View scan history
- `quit` - Exit

### Supported Channels

- **Raceband**: R1-R8 (5658-5917 MHz)
- **Band A**: A1-A8 (5725-5865 MHz)
- **Band B**: B1-B8 (5733-5866 MHz)
- **Band E**: E1-E8 (5645-5945 MHz)
- **Fatshark**: F1-F8 (5740-5880 MHz)
- **ImmersionRC**: IMD1-IMD6 (5658-5843 MHz)
- **DJI**: D1-D8 (5660-5914 MHz)
- **Low Band**: L1-L8 (5362-5621 MHz)

**Total: 64 channels across 8 bands**

## Supported SDR Hardware

Decoding runs entirely on the **host CPU** in GNU Radio — the SDR only tunes, samples, and streams IQ. There is **no on-FPGA decode**, so FPGA size is irrelevant to this use case (a common misconception). Any radio that reaches 5.8 GHz and streams ~18–20 MHz of bandwidth works.

| SDR | 5.8 GHz | Bandwidth / ADC | Driver | `--sdr` | Verdict |
|-----|:------:|-----------------|--------|---------|---------|
| ANTSDR E200 | ✅ | 56 MHz / 12-bit | UHD | `uhd` | Reference |
| USRP B210 / B200mini | ✅ | 56 MHz / 12-bit | UHD | `uhd` | Best drop-in |
| BladeRF 2.0 micro | ✅ | 56 MHz / 12-bit | SoapySDR | `bladerf` | Great |
| HackRF One | ✅ | 20 MHz / 8-bit | SoapySDR | `hackrf` | Works (marginal BW; 8-bit fine for FM) |
| ADALM-Pluto | ⚠️ hacked fw | 56 MHz / 12-bit | UHD/IIO | `uhd` | Only if already owned |
| LimeSDR / RTL-SDR / Airspy / SDRplay | ❌ | — | — | — | Cannot reach 5.8 GHz |

**HackRF note:** 20 Msps ≈ the minimum bandwidth an analog FPV FM channel occupies, so it's tight but watchable; the 8-bit ADC is a non-issue for constant-envelope FM video. SoapySDR sources (`hackrf`, `bladerf`) require **gr-soapy** plus the matching `SoapyHackRF` / `SoapyBladeRF` plugin installed.

## Architecture

- `fpv_scanner.sh` — interactive orchestrator (channel tables, scan/view handoff, single-radio-owner management)
- `fpv_detect.py` — headless two-stage signal detector (RF power + NTSC sync-lock); opens no window
- `fpv_viewer.py` — gated video viewer; opens one SDL window for one locked channel
- `fpv_sdr.py` — shared UHD/SoapySDR source factory
- `top_block.py` — original standalone UHD flowgraph (kept for reference; not used by the scanner)

## Features

- Real-time NTSC video decoding with SDL display
- **Signal-gated scanning** — headless detection, no blank windows; the video window opens only on a confirmed signal
- **Two-stage presence gate** — RF power + NTSC sync-lock, rejecting Wi-Fi / non-video carriers
- **Multi-SDR** — UHD (ANTSDR/USRP) and SoapySDR (HackRF/BladeRF) via `--sdr`
- In-place retune during the sweep (no per-channel process restart)
- Manual frequency tuning
- Scan logging and history

## Troubleshooting

**No video window during a scan:** This is expected — the sweep is headless and a window opens only when a channel locks. Watch the per-channel `dBFS` / `LOCK` readout. If a window never opens even with a transmitter on, lower `--power-thresh` (e.g. `-60`) or raise `--gain`.

**No video window at all (display issue):**
```bash
export DISPLAY=:0
```

**SoapySDR device not found (`--sdr hackrf`/`bladerf`):**
```bash
SoapySDRUtil --find          # confirm the device is seen
# install gr-soapy + Soapy<Driver> plugin if missing
```

**ANTSDR not detected:**
```bash
ping 192.168.1.10
uhd_find_devices
```

**Static/No Signal:**
- Verify FPV transmitter is powered on
- Check antenna connected to ANTSDR RX2 port
- Confirm frequency matches transmitter channel
- Try increasing gain in scanner

## Credits

- gr-ntsc-rc: https://github.com/lscardoso/gr-ntsc-rc
- ANTSDR: MicroPhase Technology

## Legal Disclaimer

**IMPORTANT: READ BEFORE USE**

This software is designed for receiving and decoding analog video signals in the 5.8 GHz ISM band, commonly used for First Person View (FPV) drone operations. While receiving and decoding analog RF signals is generally legal in most jurisdictions, users are solely responsible for:

- Complying with all applicable local, state, federal, and international laws and regulations
- Ensuring proper authorization before monitoring any communications
- Understanding that monitoring transmissions you are not authorized to receive may be illegal in your jurisdiction
- Obtaining necessary licenses or permissions required by your local regulatory authority
- Using appropriate frequencies and power levels in accordance with local regulations

**The authors, contributors, and maintainers of this software:**
- Make NO WARRANTIES, express or implied, regarding this software
- Accept NO RESPONSIBILITY for any use, misuse, or consequences of using this software
- Accept NO LIABILITY for any legal violations, damages, or harm resulting from use of this software
- Provide this software "AS IS" without any guarantee of fitness for any particular purpose

**By using this software, you acknowledge that:**
- You are solely responsible for your actions and any consequences
- You will use this software only in compliance with all applicable laws
- The authors bear no responsibility for your use of this software

**USE AT YOUR OWN RISK.**
