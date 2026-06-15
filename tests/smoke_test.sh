#!/usr/bin/env bash
set -o pipefail
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR" || exit 1

case "${1:-}" in
    -h|--help) printf 'usage: %s\n  run after ./setup.sh — checks the install and boots the app (no radio needed)\n' "$0"; exit 0 ;;
esac

PASS=0; FAIL=0; SKIP=0
pass(){ printf '  \033[32m[PASS]\033[0m %s\n' "$*"; PASS=$((PASS+1)); }
fail(){ printf '  \033[31m[FAIL]\033[0m %s\n' "$*"; FAIL=$((FAIL+1)); }
skip(){ printf '  \033[33m[SKIP]\033[0m %s\n' "$*"; SKIP=$((SKIP+1)); }
warn(){ printf '  \033[33m[WARN]\033[0m %s\n' "$*"; }
hdr(){  printf '\n\033[1;36m== %s ==\033[0m\n' "$*"; }
have(){ command -v "$1" >/dev/null 2>&1; }

OS="$(uname -s)"
WSL=""
grep -qi microsoft /proc/version 2>/dev/null && WSL=" (WSL2)"
printf '\033[1mDragon FPV Decoder smoke test\033[0m — %s%s\n' "$OS" "$WSL"
printf 'repo: %s\n' "$PROJECT_DIR"

hdr "1. Bundled decoder (vendored, frozen)"
V="vendor/gr-ntsc-rc"
[[ -f "$V/CMakeLists.txt" ]] && pass "vendor tree present ($V)" || fail "vendor tree missing ($V) — re-clone the repo"
[[ -f "$V/VENDORED.md" ]] && pass "VENDORED.md provenance present" || fail "VENDORED.md missing"
[[ -f "$V/LICENSE" ]] && pass "vendored GPLv3 LICENSE present" || warn "vendored LICENSE missing"
if grep -Fq "const int ninput = noutput_items * decimation();" \
        "$V/lib/video_stream_converter_c_impl.cc" 2>/dev/null; then
    pass "converter-bounds fix baked into vendored source"
else
    fail "converter-bounds fix NOT in vendored source (patch not applied)"
fi
[[ -f patches/gr-ntsc-rc-converter-bounds.patch ]] && pass "standalone patch kept (patches/)" || warn "patches/ diff missing"
if grep -Fq "decoder_c::make(float samp_rate, int standard)" "$V/lib/decoder_c_impl.cc" 2>/dev/null; then
    pass "PAL/NTSC standard support baked into vendored decoder"
else
    fail "PAL support NOT in vendored decoder (pal-support patch not applied)"
fi
[[ -f patches/gr-ntsc-rc-pal-support.patch ]] && pass "PAL patch kept (patches/)" || warn "patches/ PAL diff missing"

hdr "2. setup.sh has no moving build-time deps"
if grep -Eq "pull/6|git apply|git clone[^\"]*lscardoso" setup.sh; then
    fail "setup.sh still fetches a PR head / applies a patch / clones upstream — should build vendor/"
    grep -nE "pull/6|git apply|git clone[^\"]*lscardoso" setup.sh | sed 's/^/      /'
else
    pass "setup.sh builds the vendored tree only (no PR fetch / patch apply / upstream clone)"
fi
grep -Fq 'cmake -S "$src"' setup.sh && pass "build_ntsc builds out-of-tree from vendor/" || warn "build_ntsc does not reference vendor/ out-of-tree build"

hdr "3. Shell syntax"
for f in setup.sh fpv_scanner.sh fpv_env.sh tests/smoke_test.sh; do
    if bash -n "$f" 2>/dev/null; then pass "bash -n $f"; else fail "bash -n $f"; bash -n "$f"; fi
done
if have shellcheck; then
    if shellcheck -e SC1091 -e SC2034 setup.sh fpv_scanner.sh fpv_env.sh >/dev/null 2>&1; then
        pass "shellcheck (setup/scanner/env)"
    else
        warn "shellcheck reported issues (informational):"
        shellcheck -e SC1091 -e SC2034 setup.sh fpv_scanner.sh fpv_env.sh 2>&1 | sed 's/^/      /' | head -20
    fi
else
    skip "shellcheck not installed"
fi

hdr "4. Python + module compile"
PYTHON=""
source "$PROJECT_DIR/fpv_env.sh" 2>/dev/null && resolve_fpv_python >/dev/null 2>&1
if [[ -n "${PYTHON:-}" ]]; then
    pass "fpv_env.sh resolved a GNU Radio Python: $PYTHON"
    GR_PY="$PYTHON"
else
    skip "fpv_env.sh found no GNU Radio Python (runtime checks limited)"
    GR_PY=""
fi
CC_PY="${GR_PY:-$(command -v python3)}"
if [[ -n "$CC_PY" ]]; then
    if "$CC_PY" -m py_compile \
        fpv_detect.py fpv_viewer.py fpv_sdr.py fpv_spectrum.py fpv_display.py tools/fpv_tune.py 2>/tmp/dragon-pycompile.log; then
        pass "py_compile all modules ($CC_PY)"
    else
        fail "py_compile failed"; sed 's/^/      /' /tmp/dragon-pycompile.log
    fi
    if "$CC_PY" tests/test_pal_decode.py >/tmp/dragon-pal.log 2>&1; then
        pass "PAL/NTSC decode math ($(grep -c -- '-> PASS' /tmp/dragon-pal.log) gradient checks; $(grep -q 'real decoder' /tmp/dragon-pal.log && echo 'incl. live C++' || echo 'model only'))"
    else
        fail "PAL/NTSC decode math model failed"; sed 's/^/      /' /tmp/dragon-pal.log
    fi
else
    skip "no python3 found — cannot py_compile"
fi

hdr "5. GNU Radio + decoder import"
if [[ -n "$GR_PY" ]]; then
    if "$GR_PY" -c "import gnuradio.gr" 2>/dev/null; then
        pass "import gnuradio.gr ($("$GR_PY" -c 'import gnuradio.gr;print(gnuradio.gr.version())' 2>/dev/null))"
    else
        fail "import gnuradio.gr failed"
    fi
    "$GR_PY" -c "import numpy" 2>/dev/null && pass "import numpy ($("$GR_PY" -c 'import numpy;print(numpy.__version__)' 2>/dev/null))" || fail "import numpy failed"
    "$GR_PY" -c "import PIL" 2>/dev/null && pass "import PIL (Pillow)" || warn "import PIL failed (snapshots/recording need Pillow)"
    if "$GR_PY" -c "import gnuradio.NTSC" 2>/dev/null; then
        pass "import gnuradio.NTSC (decoder installed)"
    else
        warn "gnuradio.NTSC not installed — run ./setup.sh"
    fi
    "$GR_PY" -c "import gnuradio.soapy" 2>/dev/null && pass "gr-soapy present (HackRF/BladeRF path)" || warn "gr-soapy missing (needed for HackRF/BladeRF; UHD radios don't need it)"
else
    skip "no GNU Radio Python — skipping import checks (install per README, then re-run)"
fi

hdr "6. SDR drivers (informational)"
if have SoapySDRUtil; then
    fac="$(SoapySDRUtil --info 2>/dev/null | sed -n 's/.*Available factories\.\.\. //p')"
    pass "SoapySDR factories: ${fac:-none}"
else
    skip "SoapySDRUtil not found (install soapysdr-tools for HackRF/BladeRF)"
fi
have uhd_find_devices && pass "UHD tools present (ANTSDR/USRP)" || skip "uhd_find_devices not found (needed for ANTSDR/USRP)"
have ffplay && pass "ffplay present (live window when video_sdl absent)" || warn "ffplay missing (macOS/brew-GR viewer needs it)"
if [[ -n "$WSL" ]]; then
    have lsusb && { n="$(lsusb 2>/dev/null | grep -ciE 'great scott|hackrf|nuand|ettus|analog devices')"; [[ "$n" -gt 0 ]] && pass "WSL2: an SDR is visible to lsusb ($n)" || warn "WSL2: no SDR in lsusb — run 'usbipd attach --wsl --busid <id>' in admin PowerShell"; } || skip "lsusb not found"
fi

hdr "7. App boots and runs (no radio needed)"
if [[ -z "$GR_PY" ]]; then
    skip "no GNU Radio Python — the scanner won't start (install per README, then re-run)"
else
    boot="$(printf 'list\nquit\n' | FPV_PYTHON="$GR_PY" ./fpv_scanner.sh 2>&1)"; brc=$?
    if [[ "$brc" -eq 0 ]] && printf '%s' "$boot" | grep -q "FPV Scanner initialized"; then
        pass "fpv_scanner.sh boots (sources env, resolves Python, renders menu)"
    else
        fail "fpv_scanner.sh did not boot cleanly (exit $brc)"; printf '%s\n' "$boot" | tail -8 | sed 's/^/      /'
    fi
    printf '%s' "$boot" | grep -q "Raceband" && pass "scanner ran a command ('list' rendered the channel table)" || fail "'list' produced no channel table"
fi

printf '\n\033[1m== summary ==\033[0m  \033[32m%d pass\033[0m / \033[31m%d fail\033[0m / \033[33m%d skip\033[0m\n' "$PASS" "$FAIL" "$SKIP"
if [[ "$FAIL" -gt 0 ]]; then
    printf '\033[31mFAIL\033[0m — fix the items above.\n'; exit 1
fi
printf '\033[32mOK\033[0m — install verified; on-air hardware tests in tests/README.md.\n'
exit 0
