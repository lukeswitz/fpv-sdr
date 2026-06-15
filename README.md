# Dragon FPV Decoder

Headless **5.8 GHz analog FPV** (NTSC) video scanner and receiver. All decoding runs on the
**host CPU** in GNU Radio — the SDR only tunes, samples, and streams IQ.

Runs on **Linux, macOS, and Windows (via WSL2)** with any SDR that reaches 5.8 GHz: ANTSDR /
USRP over UHD, or HackRF / BladeRF over SoapySDR. One codebase, no OS-specific code paths — the
radio is chosen with `--sdr` and platform differences are detected at runtime. Only the
*install* differs per OS, and `./setup.sh` handles it.

## Quick start
```bash
git clone https://github.com/lukeswitz/dragon-fpv-decoder.git
cd dragon-fpv-decoder
./setup.sh                     # Linux / macOS: install the stack + build the bundled decoder
./fpv_scanner.sh               # ANTSDR / UHD by default;  add --sdr hackrf | bladerf
```
Then type `scan`. **No video window opens until a real FPV signal is confirmed.**
`./setup.sh --check` audits an existing install and changes nothing.

## The bundled NTSC decoder
The NTSC decode comes from the [gr-ntsc-rc](https://github.com/lscardoso/gr-ntsc-rc) GNU Radio
module. To keep the build reproducible, this repo **vendors** it at `vendor/gr-ntsc-rc/`:
upstream **PR #6** (GNU Radio 3.10 / 3.11 support) with the **converter-bounds fix already
applied**, pinned to a single commit. `setup.sh` builds that local copy.

Nothing fetches a moving PR head or applies a patch at build time — both used to be points of
failure. The standalone diff lives in `patches/` for upstreaming; see
`vendor/gr-ntsc-rc/VENDORED.md` for the pinned commit and how to re-sync. (The fix repairs an
out-of-bounds read in the video stream converter that segfaulted on marginal signals.)

## Install

`./setup.sh` is the supported path on Linux and macOS. It detects the OS, installs the stack,
and builds the bundled decoder (and skips that build automatically when the decoder is already
present, e.g. on DragonOS). The per-OS notes below are exactly what it does — for reference,
non-apt Linux, or a custom setup.

### DragonOS — fastest, the decoder is prebuilt
DragonOS ships GNU Radio **and gr-ntsc-rc** prebuilt against the system Python, so there is
nothing to compile and no duplicate-Python pitfalls.
```bash
git clone https://github.com/lukeswitz/dragon-fpv-decoder.git
cd dragon-fpv-decoder && chmod +x fpv_scanner.sh
./setup.sh --check               # confirms GNU Radio + NTSC decoder + SDR drivers
./fpv_scanner.sh --sdr hackrf    # or: --sdr uhd | bladerf
```
If `--check` reports the NTSC decoder present (it will on DragonOS), the build is skipped. Run
plain `./setup.sh` only if `--check` flags something missing.

### Linux (Debian / Ubuntu)
apt's SoapySDR modules are prebuilt against the system Python — no build errors, no duplicate
Python. `gnuradio` already bundles `gr-soapy` (there is no standalone `gr-soapy` package).
```bash
sudo apt install gnuradio gnuradio-dev soapysdr-tools \
                 soapysdr-module-hackrf soapysdr-module-bladerf uhd-host \
                 ffmpeg cmake g++ git pkg-config python3-numpy python3-pil \
                 python3-dev python3-pybind11 libboost-all-dev
git clone https://github.com/lukeswitz/dragon-fpv-decoder.git
cd dragon-fpv-decoder
./setup.sh        # builds the bundled gr-ntsc-rc (auto-skipped if already installed)
```

### macOS (Homebrew)
> **Do not `brew install soapyhackrf` / `soapybladerf`.** Those tap formulae depend on
> SoapySDR's Python and will silently **upgrade your `python@3.14`** (a duplicate keg that can
> shadow GNU Radio's Python), and their CMake predates 3.5 so they **fail to build** on current
> CMake. `setup.sh` builds those two modules from C++ source instead — no Python is pulled.
```bash
brew install gnuradio soapysdr uhd ffmpeg bash cmake pybind11 hackrf libbladerf
git clone https://github.com/lukeswitz/dragon-fpv-decoder.git
cd dragon-fpv-decoder
./setup.sh
```
brew's GNU Radio ships neither `gnuradio.NTSC` nor `video_sdl`. `setup.sh` builds the bundled
gr-ntsc-rc into `~/.local` and the viewer falls back to a live **`ffplay`** window instead of
the SDL sink — same decode. `fpv_env.sh` finds the GNU Radio Python automatically and wires the
numpy / `~/.local` paths; set `FPV_PYTHON` to override.

### Windows (WSL2)
Native Windows is not supported — the orchestrator is bash. Run it inside **WSL2 Ubuntu**, which
uses the Linux path verbatim. Requires **Windows 11**.
```powershell
wsl --install -d Ubuntu          # reboot, open Ubuntu, finish first-run user setup
```
Inside Ubuntu, follow the **Linux** steps above (`sudo apt install …`, then `./setup.sh`).

- **Networked SDR (ANTSDR / USRP over Ethernet) — easiest:** WSL2 reaches it through Windows
  networking with no USB passthrough. Just `ping 192.168.1.10 && uhd_find_devices` inside WSL.
- **USB SDR (HackRF / BladeRF / USB USRP):** pass the device into WSL2 with
  [`usbipd-win`](https://github.com/dorssel/usbipd-win). In an **Administrator PowerShell**:
  ```powershell
  winget install dorssel.usbipd-win    # once
  usbipd list                          # find the SDR's BUSID
  usbipd bind   --busid <BUSID>        # once per device (admin)
  usbipd attach --wsl --busid <BUSID>  # each WSL session
  ```
  Then `lsusb` inside WSL should list it. HackRF passthrough over usbipd is occasionally flaky
  (re-run `attach`, or replug); a networked ANTSDR avoids USB entirely. The decoded-video window
  uses **WSLg** (built into Windows 11) — no X server to install.

### Manual build of the bundled decoder
`setup.sh` does this for you; here it is by hand from the vendored tree.
```bash
# Linux
cmake -S vendor/gr-ntsc-rc -B /tmp/ntsc-build -DCMAKE_POLICY_VERSION_MINIMUM=3.5
cmake --build /tmp/ntsc-build -j"$(nproc)" && sudo cmake --install /tmp/ntsc-build && sudo ldconfig

# macOS (into ~/.local, against brew's GNU Radio Python)
PFX="$(brew --prefix)"; PY="$PFX/opt/python@3.14/bin/python3.14"
cmake -S vendor/gr-ntsc-rc -B /tmp/ntsc-build -DCMAKE_POLICY_VERSION_MINIMUM=3.5 \
  -DCMAKE_PREFIX_PATH="$PFX" -DCMAKE_INSTALL_PREFIX="$HOME/.local" \
  -DPYTHON_EXECUTABLE="$PY" -DGR_PYTHON_DIR="$HOME/.local/lib/python3.14/site-packages"
cmake --build /tmp/ntsc-build -j"$(sysctl -n hw.ncpu)" && cmake --install /tmp/ntsc-build
```
ANTSDR also needs its UHD firmware reachable — confirm with `ping 192.168.1.10 && uhd_find_devices`.

## Usage
```bash
./fpv_scanner.sh                       # ANTSDR / UHD (default)
./fpv_scanner.sh --sdr hackrf
./fpv_scanner.sh --sdr bladerf --gain 30
```
Flags (each also a `FPV_*` env var): `--sdr <name>` · `--gain <dB>` (default HackRF 24,
BladeRF 20, ANTSDR/UHD 30 — kept low to avoid clipping a strong nearby VTX) ·
`--lna` / `--vga` / `--amp` (optional HackRF stage overrides) · `--samp-rate <Hz>` ·
`--margin <dB>` · `--dev-args <str>` · `--antenna <name>` · `FPV_CONFIRM=cv|ntsc|snr`.

### How scanning works
`scan` is headless — no window while it searches. Rather than stepping channel by channel, the
detector takes a handful of wideband **FFT snapshots** (≈16 MHz chunks covering the whole band)
and reads every channel inside each chunk from one capture. A channel counts as a **valid
signal** (not merely the loudest) only when it clears three gates:

1. **SNR** — in-band power ≥ `--margin` dB over the measured noise floor (default 12).
2. **Narrow-peak** — a localized hump above its shoulders; rejects broadband Wi-Fi that can
   out-power a real FPV carrier.
3. **Carrier confirm** — a **constant-envelope FM test** (analog FPV is near-constant
   amplitude; Wi-Fi/OFDM and noise are not). This is the gate on every radio. Where the NTSC
   decoder is built (ANTSDR/USRP, BladeRF) an NTSC **sync-lock** runs as an *additive* second
   pass: a lock can *rescue* a borderline signal but can never reject one the FM test accepts,
   so a flaky lock can't hide a real channel. Override with `FPV_CONFIRM` / `--confirm` —
   `cv` (FM only), `ntsc` (lock only), `snr` (no carrier confirm).

The true carrier center is then found by an FFT energy-centroid and mapped to the nearest
channel (an off-nominal VTX is still identified, with the offset reported). The window opens
**only** on a confirmed channel; otherwise it prints `No FPV signals`. One process owns the
radio at a time — the detector releases it before the viewer opens. `sweep` runs the same survey
but only prints the per-channel RSSI/SNR table (no gating, no video).

### Commands

<img width="934" height="392" alt="Dragon FPV Decoder scan output" src="https://github.com/user-attachments/assets/45fb7a73-4ede-482d-9ffd-cde08f0434ab" />

- `scan` — headless FFT sweep; window opens only on a confirmed valid signal
- `scan loop [SEC]` — re-sweep until a signal; Ctrl-C / ENTER stops; `SEC` auto-stops
- `sweep` — fast FFT RSSI/SNR survey of all channels (no video)
- `spectrum [live｜CH｜MHz] [SEC]` — colored terminal FFT. No arg = whole-band snapshot;
  `live` = refreshing band; `spectrum A8` / `spectrum 5725` = fast single-span; `SEC` = refresh
  delay. Ctrl-C returns to the prompt
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
Decoding runs entirely on the **host CPU** — the SDR only tunes, samples, and streams IQ. There
is **no on-FPGA decode**, so FPGA size is irrelevant (a common misconception). Any radio that
reaches 5.8 GHz and streams ~18–20 MHz of bandwidth works.

| SDR | 5.8 GHz | Max BW / ADC (hardware) | Driver | `--sdr` | Verdict |
|-----|:------:|-----------------|--------|---------|---------|
| ANTSDR E200 | ✅ | 56 MHz / 12-bit | UHD | `uhd` | Reference |
| USRP B210 / B200mini | ✅ | 56 MHz / 12-bit | UHD | `uhd` | Best drop-in |
| BladeRF 2.0 micro | ✅ | 56 MHz / 12-bit | SoapySDR | `bladerf` | Great |
| HackRF One | ✅ | 20 MHz / 8-bit | SoapySDR | `hackrf` | Works (tight BW; 8-bit fine for FM) |
| ADALM-Pluto | ⚠️ hacked fw | 56 MHz / 12-bit | UHD/IIO | `uhd` | Only if already owned |
| LimeSDR / RTL-SDR / Airspy / SDRplay | ❌ | — | — | — | Cannot reach 5.8 GHz |

The **Max BW / ADC** column is each radio's hardware ceiling, not what the tool runs. The scanner
actually uses **40 MHz for detection/sweep/spectrum** (HackRF **20 MHz**, its maximum) and
**10 MHz for decoding** — comfortably within every supported radio. The 56 MHz figures are
headroom, never used; override with `FPV_DETECT_SAMP_RATE` / `--samp-rate`.

**HackRF gains** use three stages — `AMP` (0/+14 dB), `LNA` (0–40), `VGA` (0–62). `--gain`
drives LNA+VGA; the default is a modest **24 dB, AMP OFF** (40 pinned the floor near −10…−20 dBFS
and collapsed SNR). **Leave `AMP` off** — HackRF's max input is −5 dBm and the amp on a strong
signal can destroy the front-end LNA; use an external attenuator instead. The decoder runs at
10 Msps (~10 of the ~18 MHz signal), so tune to the true center for the best image — the ANTSDR
captures the full signal and decodes cleaner.

## Architecture
- `setup.sh` — one-command installer (Linux / macOS); `--check` audits an existing install
- `fpv_scanner.sh` — interactive orchestrator (channel tables, scan/view handoff, single-radio-owner management)
- `fpv_env.sh` — resolves the Python with GNU Radio bindings and wires the numpy / `~/.local` paths (sourced by the scanner)
- `fpv_detect.py` — headless FFT chunk-sweep detector (SNR + narrow-peak gate + FM constant-envelope confirm, plus an additive NTSC sync-lock pass where the decoder is built); opens no window
- `fpv_viewer.py` — gated video viewer; opens one window for one confirmed channel
- `fpv_display.py` — `frame_sink` block: decoded frames → live `ffplay` window, PNG snapshots, and/or `ffmpeg` recording (when `video_sdl` is absent)
- `fpv_spectrum.py` — pure terminal spectrum renderer (Unicode blocks + truecolor; no GNU Radio dependency)
- `fpv_sdr.py` — shared UHD / SoapySDR source factory
- `vendor/gr-ntsc-rc/` — bundled NTSC decoder (gr-ntsc-rc PR #6 + converter-bounds fix, pinned; built by `setup.sh`)
- `patches/` — the standalone converter-bounds diff (kept for upstreaming; already baked into `vendor/`)
- `tools/fpv_tune.py` / `tools/fpv_tune.sh` — standalone manual-tune helper (not used by the scanner)
- `reference/top_block.py` / `reference/NTSC_Video_5GHz_RX.grc` — original standalone GNU Radio flowgraph + its GRC source (kept for reference; not used by the scanner)

## Troubleshooting
- **No window during a scan** — expected; it's headless until a signal confirms. Watch the
  per-channel `dBFS`/SNR and `candidate … env-CV/lock … ACCEPT/REJECT` lines. A known-live TX
  getting rejected → lower `margin 10`, or loosen the FM test `--env-cv 0.4`. Floor near
  −10…−20 dBFS → gain too high, `gain 16`.
- **No window at all** — `export DISPLAY=:0` (on WSL2, WSLg provides the display automatically).
- **SoapySDR device not found** — `SoapySDRUtil --find`; install `gr-soapy` + the `Soapy<Driver>`
  plugin if missing.
- **WSL2: device not in `lsusb`** — re-run `usbipd attach --wsl --busid <BUSID>` from an admin
  PowerShell (it must be re-attached each WSL session); for HackRF, replug if `attach` succeeds
  but the device still doesn't enumerate.
- **BladeRF sees the device but finds no signal** — its FPGA must be loaded every power-on.
  libbladeRF autoloads `~/.config/Nuand/bladeRF/hostedxA4.rbf` (xA4) or `hostedxA9.rbf` (xA9) —
  note the **exact** name (the nuand.com download is `hostedxA4-latest.rbf`; rename it).
  `./setup.sh` fetches/renames it; `./setup.sh --check` reports it. Use a **USB 3.0** port —
  USB 2.0 caps the BladeRF at ~5–8 Msps, below the 20 Msps sweep.
- **ANTSDR not detected** — `ping 192.168.1.10 && uhd_find_devices`.
- **Static / no signal** — TX powered? Antenna on the RX port? Frequency matches the channel?
  Try more gain.

## Credits
- gr-ntsc-rc — https://github.com/lscardoso/gr-ntsc-rc (GPLv3; vendored from PR #6, see
  `vendor/gr-ntsc-rc/VENDORED.md`)
- ANTSDR — MicroPhase Technology

## License
This project is MIT (see `LICENSE`). The vendored `vendor/gr-ntsc-rc/` tree is **GPLv3** and is
governed by its own `LICENSE` file.

## Legal
For receiving analog video in the 5.8 GHz band (FPV). You are solely responsible for complying
with all applicable laws and obtaining any authorization required to monitor a given
transmission — this may be restricted in your jurisdiction. Provided **AS IS**, with no warranty
and no liability for any use, misuse, or consequences. **USE AT YOUR OWN RISK.**
