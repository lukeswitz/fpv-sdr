# Tests

Two layers: an **automated smoke test** (no radio needed) and **on-air hardware tests** (need a
powered VTX). The smoke test is one portable script that runs the same on **macOS, Linux, and
WSL2**.

## Install → run, per OS

Two real steps on every OS. `setup.sh` is the installer; `smoke_test.sh` then verifies the
install **and boots the app** (no radio needed):

```bash
./setup.sh            # install the stack + build the bundled decoder (one time)
./tests/smoke_test.sh # verify everything installed AND the scanner boots/runs
```

- **macOS / Linux / DragonOS** — run the two commands above. (DragonOS already has the decoder, so
  `setup.sh` just confirms it.)
- **Windows (WSL2)** — run both **inside the WSL2 Ubuntu shell**, not PowerShell. The test
  auto-detects WSL2 and adds a `lsusb` SDR check. For USB radios, attach the device first from an
  **Administrator PowerShell**:
  ```powershell
  usbipd list
  usbipd attach --wsl --busid <BUSID>
  ```
  A networked ANTSDR needs no attach — check it with `ping 192.168.1.10 && uhd_find_devices`.

One command, no flags. Exit code is `0` when nothing FAILs, `1` otherwise. `WARN`/`SKIP` never
fail the run (a `WARN` is an optional/missing piece; a `SKIP` means a check couldn't run here,
e.g. no GNU Radio yet, so install and re-run).

What it verifies:

| Group | Checks |
|-------|--------|
| 1. Bundled decoder | `vendor/gr-ntsc-rc` present, `VENDORED.md` + GPLv3 `LICENSE` present, **converter-bounds fix baked into the source**, standalone patch kept in `patches/` |
| 2. No moving deps | `setup.sh` does **not** fetch a PR head, `git apply` a patch, or clone upstream — it builds `vendor/` |
| 3. Shell syntax | `bash -n` on every script; `shellcheck` if installed |
| 4. Python | `fpv_env.sh` resolves a GNU Radio Python; `py_compile` of every module |
| 5. Imports | `gnuradio.gr`, `numpy`, `PIL`, `gnuradio.NTSC`, `gnuradio.soapy` |
| 6. SDR drivers | SoapySDR factories, UHD tools, `ffplay`; on WSL2, whether an SDR is in `lsusb` |
| 7. App boots/runs | drives `fpv_scanner.sh` headless (`list` then `quit`): confirms it boots, resolves Python, and runs a command — **no radio needed** |

A clean run on a fully-installed host ends with `… pass / 0 fail / … skip`.

## On-air hardware tests (need a powered VTX)

The smoke test proves the software builds and imports. These confirm real reception. You need an
analog **5.8 GHz VTX** powered on a known channel and the right antenna on the RX port. Same steps
on every OS (inside WSL2 on Windows).

1. **Headless detect — no false window.** With **no** VTX powered:
   ```bash
   ./fpv_scanner.sh --sdr <hackrf|bladerf|uhd>
   # at the prompt:
   scan
   ```
   Expect: per-channel `dBFS`/SNR lines and **`No FPV signals`** — **no video window opens**.

2. **Detect the real channel.** Power a VTX on a known channel (e.g. A8 = 5725) and `scan` again.
   Expect: a `candidate … env-CV … ACCEPT` line on that channel, `[SIGNAL] A8 found …`, and the
   video window opens **only** on that channel. An off-nominal VTX still resolves to the nearest
   channel with the measured offset reported.

3. **Wi-Fi is rejected.** With a busy 5 GHz Wi-Fi AP near the antenna and no VTX, `scan` should
   print `env-CV` well above the threshold and **reject** it (`No FPV signals`) — broadband Wi-Fi
   must not be reported as FPV.

4. **Survey table.** `sweep` prints the per-channel RSSI/SNR table for all channels with no gating
   and no video — the live channel should stand clearly above the noise floor.

5. **Spectrum.** `spectrum` (whole band) or `spectrum A8` should show a hump at the VTX center.

6. **Tune + view directly.** `set A8` (or `freq 5725`) should tune and open the viewer; on
   macOS/brew (no `video_sdl`) the window is an `ffplay` window.

Tuning knobs if a known-live TX is missed or noise sneaks through: `margin <dB>` (SNR gate),
`--env-cv <x>` (FM constant-envelope gate), `gain <dB>` (lower if the floor sits near
−10…−20 dBFS = clipping). See the project README **Troubleshooting** section.
