# Testing

Testing is the **same 3 steps on every OS**:

1. `./setup.sh` — installs the stack + builds the bundled decoder. Should finish with no error.
2. `./tests/smoke_test.sh` — should print `0 fail`.
3. Plug in a radio, power a 5.8 GHz VTX, then `./fpv_scanner.sh --sdr hackrf` → type `scan` —
   should find the channel and show video.

Steps 1–2 prove the **software installs and runs** on that OS (no radio needed). Step 3 proves
**real reception** (needs hardware).

## Getting each OS to test on

| OS | Where to run it |
|----|-----------------|
| **macOS** | your Mac (needs Homebrew). |
| **Linux / DragonOS** | a real Linux box, a VM (UTM / Parallels / VirtualBox), or **Docker** (see below). |
| **Windows** | a Windows 11 PC: install WSL2 (`wsl --install -d Ubuntu`), then run the Linux steps **inside** the Ubuntu shell. |

Supported Linux = Debian/Ubuntu family (apt): **Ubuntu 20.04 / 22.04 / 24.04, Debian 12, Kali,
Raspberry Pi OS, Linux Mint, Pop!_OS, DragonOS**. On DragonOS the decoder is prebuilt, so
`./setup.sh` just confirms it. Non-apt distros (Fedora/Arch) aren't automated — `setup.sh` stops
and prints the packages to install by hand, then you re-run.

## Docker — validate the Linux install from your Mac

One job: run **steps 1–2 for Linux** on your Mac, in a throwaway Ubuntu/Debian container, without
building a VM. It does **not** do step 3 (no radio passthrough) and is **Linux only**.

```bash
./tests/docker_test.sh                 # ubuntu 24.04 + 22.04 + debian 12
./tests/docker_test.sh ubuntu:24.04    # just one (faster)
```

Each container runs `./setup.sh` then `./tests/smoke_test.sh` and the matrix prints `PASS`/`FAIL`
per distro. Your repo is mounted read-only, so nothing on the host changes. Needs Docker Desktop
running. First run pulls images + builds GNU Radio, so allow ~10–20 min per distro.

## What the smoke test checks

One command, no flags. Exit `0` = nothing failed, `1` = something failed. `WARN`/`SKIP` never fail
the run (an optional piece is missing, or a check couldn't run here yet — install and re-run).

| Group | Checks |
|-------|--------|
| 1. Bundled decoder | `vendor/gr-ntsc-rc` present, `VENDORED.md` + GPLv3 `LICENSE` present, converter-bounds fix baked into the source, patch kept in `patches/` |
| 2. No moving deps | `setup.sh` builds `vendor/` — no PR fetch, no `git apply`, no upstream clone |
| 3. Shell syntax | `bash -n` every script; `shellcheck` if installed |
| 4. Python | `fpv_env.sh` resolves a GNU Radio Python; `py_compile` every module |
| 5. Imports | `gnuradio.gr`, `numpy`, `PIL`, `gnuradio.NTSC`, `gnuradio.soapy` |
| 6. SDR drivers | SoapySDR factories, UHD tools, `ffplay`; on WSL2, whether an SDR is in `lsusb` |
| 7. App boots/runs | drives `fpv_scanner.sh` headless (`list` then `quit`) — confirms it boots, resolves Python, runs a command (no radio) |

## Step 3 — on-air hardware tests (need a powered VTX)

Same on every OS (inside WSL2 on Windows). Need an analog 5.8 GHz VTX on a known channel and the
right antenna on the RX port.

1. **No false window:** with no VTX powered, `scan` prints per-channel dBFS/SNR and `No FPV signals`
   — no video window opens.
2. **Finds the real channel:** power a VTX (e.g. A8 = 5725), `scan` → `[SIGNAL] A8 found …`, window
   opens only on that channel. An off-nominal VTX still maps to the nearest channel, offset reported.
3. **Rejects Wi-Fi:** busy 5 GHz Wi-Fi near the antenna, no VTX → `scan` rejects it (`No FPV signals`).
4. **Survey table:** `sweep` prints per-channel RSSI/SNR (no gating, no video).
5. **Spectrum:** `spectrum` or `spectrum A8` shows a hump at the VTX center.
6. **Direct view:** `set A8` (or `freq 5725`) tunes and opens the viewer (an `ffplay` window on
   macOS/brew).

Knobs if a live TX is missed or noise sneaks through: `margin <dB>`, `--env-cv <x>`, `gain <dB>`
(lower if the floor sits near −10…−20 dBFS = clipping). See the main README **Troubleshooting**.
