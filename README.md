# Dragon FPV Decoder

Headless NTSC 5.8 GHz FPV video scanner + receiver. Host-side decode in GNU Radio.

**Platform-agnostic.** One codebase runs on **Linux and macOS** with **any supported SDR** —
the radio is chosen by `--sdr` (UHD for ANTSDR/USRP, SoapySDR for HackRF/BladeRF) and platform
differences are detected at runtime. There are no OS-specific code paths; only the install
differs (your package manager) and that's spelled out below.

## Quick start
```bash
git clone https://github.com/lukeswitz/dragon-fpv-decoder.git
cd dragon-fpv-decoder
./setup.sh                 # macOS or Linux: installs the stack + builds the decoder
./fpv_scanner.sh           # ANTSDR / UHD (default);  add --sdr hackrf | bladerf
```
Then type `scan` — no video window opens until a real FPV signal is confirmed.
`./setup.sh --check` reports what's installed or missing and changes nothing.

## Install
**`./setup.sh` does all of this automatically** — it detects macOS vs Linux, installs the
stack, and builds gr-ntsc-rc. The manual steps below are for reference, non-apt Linux, or
custom setups. (`./setup.sh --check` audits an existing install without changing anything.)

`./setup.sh` is the supported path and handles both OSes. The manual steps below mirror exactly
what it does — use them for reference, non-apt Linux, or a custom setup.

### Linux (Debian / Ubuntu / DragonOS)
SoapySDR's apt modules are prebuilt and use the system Python, so there are **no build errors
and no duplicate Python install**.
```bash
# gnuradio bundles gr-soapy; the soapysdr-module-* / uhd-host packages are the SDR drivers.
sudo apt install gnuradio ffmpeg cmake g++ git python3-numpy python3-pil
sudo apt install uhd-host soapysdr-module-hackrf soapysdr-module-bladerf  # whichever your radios need
git clone https://github.com/lukeswitz/dragon-fpv-decoder.git
cd dragon-fpv-decoder && chmod +x fpv_scanner.sh

# gr-ntsc-rc — skip if `python3 -c "import gnuradio.NTSC"` already works (DragonOS bundles it):
git clone https://github.com/lscardoso/gr-ntsc-rc.git && cd gr-ntsc-rc
git fetch origin pull/6/head:pr6 && git checkout pr6        # PR6 = GNU Radio 3.10/3.11
git apply ~/dragon-fpv-decoder/patches/gr-ntsc-rc-converter-bounds.patch
cmake -B build -DCMAKE_POLICY_VERSION_MINIMUM=3.5
cmake --build build -j"$(nproc)" && sudo cmake --install build && sudo ldconfig
```

### macOS (Homebrew)
> **Do not `brew install soapyhackrf` / `soapybladerf`.** Those tap formulae depend on
> SoapySDR's Python and will silently **upgrade your `python@3.14` (a duplicate keg that can
> shadow your GNU Radio Python)**, and their CMake predates 3.5 so they **fail to build** on
> current CMake. Build the two modules from source instead — they are C++ only and pull no
> Python. `setup.sh` does exactly this.

```bash
brew install gnuradio soapysdr uhd ffmpeg bash cmake pybind11 hackrf libbladerf
git clone https://github.com/lukeswitz/dragon-fpv-decoder.git
cd dragon-fpv-decoder && chmod +x fpv_scanner.sh
PFX="$(brew --prefix)"
PY="$PFX/opt/python@3.14/bin/python3.14"          # match your brew GNU Radio Python
"$PY" -m pip install --user -r requirements.txt   # numpy, Pillow

# SoapyHackRF + SoapyBladeRF from source — no Python pulled; the policy flag fixes their old CMake
for m in SoapyHackRF SoapyBladeRF; do
  git clone --depth 1 "https://github.com/pothosware/$m.git" ~/"$m"
  cmake -S ~/"$m" -B ~/"$m/build" -DCMAKE_POLICY_VERSION_MINIMUM=3.5 \
    -DCMAKE_PREFIX_PATH="$PFX" -DCMAKE_INSTALL_PREFIX="$PFX"
  cmake --build ~/"$m/build" -j"$(sysctl -n hw.ncpu)" && cmake --install ~/"$m/build"
done

# gr-ntsc-rc into your user prefix (brew GR ships neither gnuradio.NTSC nor video_sdl)
git clone https://github.com/lscardoso/gr-ntsc-rc.git && cd gr-ntsc-rc
git fetch origin pull/6/head:pr6 && git checkout pr6
git apply ~/dragon-fpv-decoder/patches/gr-ntsc-rc-converter-bounds.patch
cmake -B build -DCMAKE_POLICY_VERSION_MINIMUM=3.5 \
  -DCMAKE_PREFIX_PATH="$PFX" -DCMAKE_INSTALL_PREFIX="$HOME/.local" \
  -DPYTHON_EXECUTABLE="$PY" -DGR_PYTHON_DIR="$HOME/.local/lib/python3.14/site-packages"
cmake --build build -j"$(sysctl -n hw.ncpu)" && cmake --install build
```
With no `video_sdl`, the viewer uses a live `ffplay` window instead of the SDL sink — same decode.

The converter-bounds patch fixes an out-of-bounds read in the video stream converter (it reads
`1.93 × noutput` samples from an `noutput` buffer) that segfaults on a marginal signal — apply it
on every build. `fpv_env.sh` finds the right Python automatically (system `python3` on Linux,
Homebrew's on macOS) and wires the numpy / `~/.local` paths; set `FPV_PYTHON` to override.
ANTSDR also needs UHD firmware; confirm with `ping 192.168.1.10 && uhd_find_devices`.

## Usage
```bash
./fpv_scanner.sh                       # ANTSDR / UHD (default)
./fpv_scanner.sh --sdr hackrf
./fpv_scanner.sh --sdr bladerf --gain 30
```
Flags (each also a `FPV_*` env var): `--sdr <name>` · `--gain <dB>` (HackRF 24, UHD 40) ·
`--lna`/`--vga`/`--amp` (optional HackRF overrides) · `--samp-rate <Hz>` · `--margin <dB>` ·
`--dev-args <str>` · `--antenna <name>` · `FPV_CONFIRM=cv|ntsc|snr`.

### How scanning works
`scan` is headless — no window while it searches. Instead of stepping through all ~56
channels, the detector takes a few wideband **FFT snapshots** (≈24 chunks of 16 MHz cover
the whole band) and reads every channel inside each chunk from one capture. A channel is a
**valid signal** (not merely the loudest) only when it clears three gates:

1. **SNR** — in-band power ≥ `--margin` dB over the measured noise floor (default 12).
2. **Narrow-peak** — a localized hump above its shoulders; rejects broadband Wi-Fi that can out-power a real FPV carrier.
3. **Carrier confirm** — SoapySDR radios (HackRF/BladeRF) use a **constant-envelope FM test** (analog FPV is near-constant amplitude; Wi-Fi/OFDM and noise are not); UHD uses the NTSC **sync-lock**. Override with `FPV_CONFIRM` / `--confirm` — `cv` works on any radio, `snr` accepts on SNR + narrow-peak alone.

The true carrier center is then found by an FFT energy-centroid and mapped to the nearest
channel (an off-nominal VTX is still identified, with the offset reported). The window opens
**only** on a confirmed channel; otherwise it prints `No FPV signals`. One process owns the
radio at a time — the detector releases it before the viewer opens. `sweep` runs the same
survey but only prints the per-channel RSSI/SNR table (no gating, no video).

### Commands
- `scan` — headless FFT sweep; window opens only on a confirmed valid signal
- `scan loop [SEC]` — re-sweep until a signal; Ctrl-C/ENTER stops; `SEC` auto-stops
- `sweep` — fast FFT RSSI/SNR survey of all channels (no video)
- `spectrum [live｜CH｜MHz] [SEC]` — colored terminal FFT. No arg = whole-band snapshot; `live` = refreshing band; `spectrum A8`/`spectrum 5725` = fast single-span; `SEC` = refresh delay. Ctrl-C returns to the prompt
- `stop` — stop the sweep
- `set <CH>` — tune + view a channel (e.g. `set R6`)
- `freq <MHz>` — tune + view an exact frequency (e.g. `freq 5843`)
- `list` — list all channels
- `sdr <NAME>` — switch radio at runtime (`uhd`, `hackrf`, `bladerf`, …)
- `gain <dB>` — RX gain (all SDRs; on HackRF drives LNA+VGA, default 24)
- `lna <dB>` / `vga <dB>` — optional HackRF LNA (0–40) / VGA (0–62) override
- `margin <dB>` — SNR over the noise floor to call a channel a signal (default 12)
- `dwell <SEC>` — per-chunk settle time during the sweep
- `rotate <deg>` / `contrast <x>` / `record <file>` — video display + capture
- `log` — view scan history
- `quit` — exit

### Channels (64 across 8 bands)
Raceband R1–R8 (5658–5917) · Band A A1–A8 (5725–5865) · Band B B1–B8 (5733–5866) ·
Band E E1–E8 (5645–5945) · Fatshark F1–F8 (5740–5880) · ImmersionRC IMD1–IMD6 (5658–5843) ·
DJI D1–D8 (5660–5914) · Low Band L1–L8 (5362–5621). All MHz.

## Supported SDRs
Decoding runs entirely on the **host CPU** — the SDR only tunes, samples, and streams IQ.
There is **no on-FPGA decode**, so FPGA size is irrelevant (a common misconception). Any
radio that reaches 5.8 GHz and streams ~18–20 MHz of bandwidth works.

| SDR | 5.8 GHz | Bandwidth / ADC | Driver | `--sdr` | Verdict |
|-----|:------:|-----------------|--------|---------|---------|
| ANTSDR E200 | ✅ | 56 MHz / 12-bit | UHD | `uhd` | Reference |
| USRP B210 / B200mini | ✅ | 56 MHz / 12-bit | UHD | `uhd` | Best drop-in |
| BladeRF 2.0 micro | ✅ | 56 MHz / 12-bit | SoapySDR | `bladerf` | Great |
| HackRF One | ✅ | 20 MHz / 8-bit | SoapySDR | `hackrf` | Works (tight BW; 8-bit fine for FM) |
| ADALM-Pluto | ⚠️ hacked fw | 56 MHz / 12-bit | UHD/IIO | `uhd` | Only if already owned |
| LimeSDR / RTL-SDR / Airspy / SDRplay | ❌ | — | — | — | Cannot reach 5.8 GHz |

**HackRF gains** use three stages — `AMP` (0/+14 dB), `LNA` (0–40), `VGA` (0–62). `--gain`
drives LNA+VGA; default is a modest **24 dB, AMP OFF** (40 pinned the floor near −10…−20 dBFS
and collapsed SNR). **Leave `AMP` off** — HackRF's max input is −5 dBm and the amp on a strong
signal can destroy the front-end LNA; use an external attenuator instead. Detection sweeps at
20 Msps; the decoder runs at 10 Msps (~10 of the ~18 MHz signal), so tune to the true center
for the best image — the ANTSDR captures the full signal and decodes cleaner.

## Architecture
- `setup.sh` — one-command installer (macOS/Linux); `--check` audits an existing install
- `fpv_scanner.sh` — interactive orchestrator (channel tables, scan/view handoff, single-radio-owner management)
- `fpv_env.sh` — resolves the Python with GNU Radio bindings and wires the numpy / `~/.local` paths (sourced by the scanner)
- `fpv_detect.py` — headless FFT chunk-sweep detector (SNR + narrow-peak gate, plus FM constant-envelope confirm on SoapySDR / NTSC sync-lock on UHD); opens no window
- `fpv_viewer.py` — gated video viewer; opens one window for one confirmed channel
- `fpv_display.py` — `frame_sink` block: decoded frames → live `ffplay` window, PNG snapshots, and/or `ffmpeg` recording (when `video_sdl` is absent)
- `fpv_spectrum.py` — pure terminal spectrum renderer (Unicode blocks + truecolor; no GNU Radio dependency)
- `fpv_sdr.py` — shared UHD/SoapySDR source factory
- `fpv_tune.py` / `fpv_tune.sh` — standalone manual-tune helper (not used by the scanner)
- `top_block.py` — original standalone UHD flowgraph (kept for reference; not used by the scanner)

## Troubleshooting
- **No window during a scan** — expected; it's headless until a signal confirms. Watch the per-channel `dBFS`/SNR and `candidate … env-CV/lock … ACCEPT/REJECT` lines. A known-live TX getting rejected → lower `margin 10`, or loosen the FM test `--env-cv 0.4`. Floor near −10…−20 dBFS → gain too high, `gain 16`.
- **No window at all** — `export DISPLAY=:0`.
- **SoapySDR device not found** — `SoapySDRUtil --find`; install `gr-soapy` + the `Soapy<Driver>` plugin if missing.
- **ANTSDR not detected** — `ping 192.168.1.10 && uhd_find_devices`.
- **Static / no signal** — TX powered? Antenna on the RX port? Frequency matches the channel? Try more gain.

## Credits
- gr-ntsc-rc — https://github.com/lscardoso/gr-ntsc-rc
- ANTSDR — MicroPhase Technology

## Legal
For receiving analog video in the 5.8 GHz band (FPV). You are solely responsible for
complying with all applicable laws and obtaining any authorization required to monitor a
given transmission — this may be restricted in your jurisdiction. Provided **AS IS**, with
no warranty and no liability for any use, misuse, or consequences. **USE AT YOUR OWN RISK.**
