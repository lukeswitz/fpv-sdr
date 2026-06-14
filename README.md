# Dragon FPV Decoder

NTSC 5.8 GHz FPV video receiver and scanner for ANTSDR E200 using GNU Radio.

## Prerequisites

- ANTSDR configured with **UHD firmware**
- GNU Radio (3.10/3.11) and UHD drivers (pre-installed on WarDragon / DragonOS)
- `gr-ntsc-rc` NTSC decoder (PR6 — see Installation; **already bundled on DragonOS**)
- For SoapySDR radios (HackRF / BladeRF): `gr-soapy` + the matching `SoapyHackRF` / `SoapyBladeRF` plugin
- Python host deps: `numpy`, `Pillow` (`pip3 install -r requirements.txt`)
- `ffmpeg` — used for the live viewer window and recording when GNU Radio's `video_sdl` sink is absent

## Installation (Linux / WarDragon / DragonOS)
```bash
# 1. Clone Dragon FPV Decoder
cd ~/
git clone https://github.com/lukeswitz/dragon-fpv-decoder.git
cd dragon-fpv-decoder
chmod +x fpv_scanner.sh fpv_detect.py fpv_viewer.py fpv_sdr.py

# 2. Python host-decode deps
pip3 install -r requirements.txt          # numpy + Pillow
sudo apt install ffmpeg                    # live window / recording (when video_sdl is absent)

# 3. Build the gr-ntsc-rc NTSC decoder — SKIP if already present (DragonOS ships it)
python3 -c "import gnuradio.NTSC" 2>/dev/null && echo "NTSC already installed — skip" || {
  cd ~/
  git clone https://github.com/lscardoso/gr-ntsc-rc.git && cd gr-ntsc-rc
  git fetch origin pull/6/head:pr6 && git checkout pr6     # PR6 bumps it to GNU Radio 3.10/3.11
  git apply ~/dragon-fpv-decoder/patches/gr-ntsc-rc-converter-bounds.patch   # crash fix (see below)
  mkdir build && cd build
  cmake .. && make -j"$(nproc)" && sudo make install && sudo ldconfig
  cd ~/dragon-fpv-decoder
}
```

The converter-bounds patch fixes an out-of-bounds read in the gr-ntsc-rc video stream
converter (it reads `1.93 × noutput` input samples from a buffer holding only `noutput`),
which segfaults on a marginal signal — clean ANTSDR signals get lucky and never crash.
Apply it on the **WarDragon/ANTSDR** build too so its `video_sdl` decode path is crash-proof.

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

HackRF RX gains use the three official stages (`AMP` RF amp 0/+14 dB, `LNA` 0–40,
`VGA` 0–62). `--gain`/`gain` drives the front-end (it maps to LNA + VGA); FPV
transmitters are usually strong and nearby, so the HackRF default is a modest
**24 dB, AMP OFF**, instead of the old 40 that pinned the noise floor up near
−10…−20 dBFS (saturated front-end, collapsed SNR). Lower it further with `gain 16`
if the floor is still hot, or split the stages explicitly with `--lna`/`--vga`.
**The RF amp (`AMP`) stays OFF** — HackRF's max input is −5 dBm and enabling the amp
on a strong signal can destroy the front-end LNA; use an external attenuator for
very strong transmitters instead.

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
"$PYTHON" fpv_viewer.py --sdr hackrf --gain 24 --samp-rate 10e6 --freq 5725e6
```

Note: detection sweeps at 20 Msps (full FFT bandwidth) to localize the carrier, but
the decoder runs at 10 Msps and captures ~10 MHz of the ~18 MHz analog FPV signal —
so tune to the transmitter's true center for the best image. The WarDragon/ANTSDR
captures the full signal and decodes cleaner.

## Usage
```bash
./fpv_scanner.sh                 # ANTSDR / UHD (default)
./fpv_scanner.sh --sdr hackrf    # HackRF via SoapySDR
./fpv_scanner.sh --sdr bladerf --gain 30
```

Flags: `--sdr <name>` `--gain <dB>` (HackRF default 24, UHD 40) `--lna <dB>` `--vga <dB>` `--amp` (optional HackRF overrides) `--samp-rate <Hz>` `--margin <dB>` `--dev-args <str>` `--antenna <name>` (all also settable via `FPV_*` env vars).

### How scanning works

`scan` runs a **headless** sweep — **no video window opens** while it searches. Instead of visiting all ~56 channels one at a time, the detector takes a handful of **wideband FFT snapshots** (≈24 chunks of 16 MHz cover the whole 5.8 band at once) and reads every channel that falls inside each chunk from a single capture — much faster, and the spectrum shape drives the gate.

A channel counts as a **valid signal** (not merely the loudest) only when it clears three gates:

1. **SNR** — in-band power ≥ `--margin` dB over the measured noise floor (default 12).
2. **Narrow-peak** — the carrier is a localized hump above its shoulders, which rejects broadband Wi-Fi that can out-power a real FPV carrier.
3. **Carrier confirm** — on any **SoapySDR** radio (HackRF, BladeRF), a **constant-envelope (FM) test**: analog FPV is frequency-modulated, so its in-band amplitude is near-constant (low coefficient-of-variation), while Wi-Fi/OFDM and noise are not. On **UHD** (ANTSDR/USRP) the NTSC decoder **sync-lock** is used instead. Override the method with `FPV_CONFIRM=cv|ntsc|snr` (or `fpv_detect.py --confirm …`) — `cv` works on any radio, `snr` skips the confirm and accepts on SNR + narrow-peak alone.

The true carrier center is then found by an FFT energy-centroid and mapped to the nearest channel (a VTX radiating a few MHz off-nominal is still identified, with the offset reported). The window opens **only** on a confirmed channel; with no valid carrier it prints `No FPV signals`. One process owns the radio at a time — the detector releases it before the viewer opens.

`sweep` runs the same FFT survey but just prints the per-channel RSSI/SNR table and exits (no gating, no video).

### Commands

- `scan` - Headless FFT sweep; window opens only on a confirmed valid signal
- `sweep` - Fast FFT RSSI/SNR survey of all channels (no video)
- `spectrum [live｜CH｜MHz]` - Draw the FFT as a colored spectrum in the terminal. No arg = whole-band snapshot; `live` = refreshing band waterfall; a channel or frequency (`spectrum A8`, `spectrum 5725`) = a fast single-span live view of that 20 MHz window. Ctrl-C returns to the prompt.
- `stop` - Stop the sweep
- `set <CH>` - Tune and view a specific channel (e.g., `set R6`, `set A8`)
- `freq <MHz>` - Tune and view an exact frequency (e.g., `freq 5843`)
- `list` - Show all available channels
- `sdr <NAME>` - Switch radio at runtime (`uhd`, `hackrf`, `bladerf`, …)
- `gain <dB>` - Set RX gain (all SDRs; on HackRF it drives LNA+VGA, default 24)
- `lna <dB>` / `vga <dB>` - Optional HackRF LNA (0–40) / VGA (0–62) override
- `margin <dB>` - SNR over the noise floor required to call a channel a signal (default 12)
- `dwell <SEC>` - Per-chunk settle time during the sweep
- `rotate <deg>` / `contrast <x>` / `record <file>` - Video display and capture options
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
- `fpv_env.sh` — resolves the Python that has GNU Radio bindings and wires the numpy / `~/.local` out-of-tree paths (sourced by the scanner)
- `fpv_detect.py` — headless FFT chunk-sweep detector (SNR + narrow-peak shape gate, plus an FM constant-envelope confirm on any SoapySDR radio / NTSC sync-lock on UHD); opens no window
- `fpv_viewer.py` — gated video viewer; opens one window for one confirmed channel
- `fpv_display.py` — `frame_sink` GNU Radio block: assembles decoded NTSC frames and pushes them to a live `ffplay` window, PNG snapshots, and/or an `ffmpeg` recording (used when `video_sdl` is unavailable)
- `fpv_spectrum.py` — pure terminal spectrum renderer (Unicode blocks + truecolor; no GNU Radio dependency)
- `fpv_sdr.py` — shared UHD/SoapySDR source factory
- `fpv_tune.py` / `fpv_tune.sh` — standalone manual-tune helper (not used by the scanner)
- `top_block.py` — original standalone UHD flowgraph (kept for reference; not used by the scanner)

## Features

- Real-time NTSC video decoding with live display
- **Signal-gated scanning** — headless detection, no blank windows; the video window opens only on a confirmed signal
- **Wideband FFT sweep** — a few 16 MHz snapshots survey the whole band instead of stepping channel-by-channel
- **Validity gate** — SNR over the noise floor + narrow-peak shape (rejects Wi-Fi), plus a constant-envelope FM test on SoapySDR radios (HackRF/BladeRF) / NTSC sync-lock on UHD (override with `FPV_CONFIRM`)
- **Carrier-centroid channel ID** — measures the true center and reports any off-nominal VTX offset
- **Multi-SDR** — UHD (ANTSDR/USRP) and SoapySDR (HackRF/BladeRF) via `--sdr`
- Modest HackRF gain default (24 dB, AMP off) to keep the front-end out of compression — still fully settable with `gain`/`--lna`/`--vga`
- In-place retune during the sweep (no per-channel process restart)
- Manual frequency tuning
- Scan logging and history

## Troubleshooting

**No video window during a scan:** Expected — the sweep is headless and a window opens only on a confirmed signal. Watch the per-channel `dBFS` / SNR readout and the `candidate … env-CV/lock … ACCEPT/REJECT` lines. If a transmitter you know is live is rejected, lower the SNR gate (`margin 10`) or, on HackRF, loosen the FM test (`--env-cv 0.4`). If the noise floor itself sits near −10…−20 dBFS, the gain is too high — lower it (`gain 16`).

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
