#!/usr/bin/env bash
set -o pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR" || exit 1

OS="$(uname -s)"
NTSC_SRC="${FPV_NTSC_SRC:-$HOME/gr-ntsc-rc}"
CHECK_ONLY=0
case "${1:-}" in
    -c|--check) CHECK_ONLY=1 ;;
    -h|--help)
        echo "Usage: $0 [--check]"
        echo "  (no args)  install everything for this OS (macOS/Linux) and build gr-ntsc-rc"
        echo "  --check    report what is present/missing, install nothing"
        exit 0 ;;
    "") ;;
    *) echo "unknown arg: $1 (try --help)"; exit 1 ;;
esac

say()  { printf '\n\033[1;36m==>\033[0m %s\n' "$*"; }
ok()   { printf '  \033[32m[ok]\033[0m %s\n' "$*"; }
warn() { printf '  \033[33m[--]\033[0m %s\n' "$*"; }
err()  { printf '  \033[31m[XX]\033[0m %s\n' "$*"; }
info() { printf '  \033[36m[i]\033[0m %s\n' "$*"; }
have() { command -v "$1" >/dev/null 2>&1; }
need() { "$@" || { err "command failed: $*"; exit 1; }; }
run_quiet() {
    local log="$1"; shift
    if ! "$@" >>"$log" 2>&1; then
        err "command failed: $*"
        echo "    --- last 25 lines of $log ---"
        tail -25 "$log"
        exit 1
    fi
}

resolve_py() {
    PYTHON=""
    if [[ -f "$PROJECT_DIR/fpv_env.sh" ]]; then
        # shellcheck source=/dev/null
        source "$PROJECT_DIR/fpv_env.sh"
        resolve_fpv_python >/dev/null 2>&1 || true
    fi
    [[ -n "${PYTHON:-}" ]] || PYTHON="python3"
}

doctor() {
    local missing=0
    say "Preflight ($OS)"
    case "$OS" in
        Darwin) if have brew; then ok "Homebrew"; else err "Homebrew missing — https://brew.sh"; missing=1; fi ;;
        Linux)  if have apt-get; then ok "apt"; else warn "no apt — install deps with your package manager"; fi ;;
    esac
    resolve_py
    if "$PYTHON" -c "import gnuradio.gr" 2>/dev/null; then ok "GNU Radio  ($PYTHON)"; else err "GNU Radio bindings not found"; missing=1; fi
    if "$PYTHON" -c "import gnuradio.NTSC" 2>/dev/null; then ok "gr-ntsc-rc NTSC decoder"; else err "gr-ntsc-rc NTSC decoder missing"; missing=1; fi
    if "$PYTHON" -c "import numpy" 2>/dev/null; then ok "numpy"; else err "numpy missing"; missing=1; fi
    if "$PYTHON" -c "import PIL" 2>/dev/null; then ok "Pillow"; else err "Pillow missing"; missing=1; fi
    if have ffmpeg; then ok "ffmpeg"; else warn "ffmpeg missing (live window / recording)"; fi
    if have ffplay; then ok "ffplay"; else warn "ffplay missing (live window when video_sdl absent)"; fi
    if have SoapySDRUtil; then
        local fac
        fac="$(SoapySDRUtil --info 2>/dev/null | sed -n 's/.*Available factories\.\.\. //p')"
        ok "SoapySDR factories: ${fac:-none}"
        [[ "$fac" == *hackrf*  ]] || warn "  no hackrf factory  — install SoapyHackRF for HackRF"
        [[ "$fac" == *bladerf* ]] || warn "  no bladerf factory — install SoapyBladeRF for BladeRF"
    else
        warn "SoapySDR not found (needed for HackRF/BladeRF; UHD radios do not need it)"
    fi
    if have uhd_find_devices; then ok "UHD tools (ANTSDR/USRP)"; else warn "UHD not found (needed for ANTSDR/USRP)"; fi
    return $missing
}

install_mac() {
    have brew || { err "Install Homebrew first: https://brew.sh"; exit 1; }
    export HOMEBREW_NO_AUTO_UPDATE=1 HOMEBREW_NO_INSTALLED_DEPENDENTS_CHECK=1
    local pkgs=(gnuradio soapysdr uhd ffmpeg bash cmake pybind11 hackrf libbladerf) want=() p
    for p in "${pkgs[@]}"; do
        brew list "$p" >/dev/null 2>&1 || want+=("$p")
    done
    if [[ ${#want[@]} -gt 0 ]]; then
        say "Installing missing Homebrew formulae: ${want[*]}"
        need brew install "${want[@]}"
    else
        ok "all Homebrew deps already present — not reinstalling (leaves your Python untouched)"
    fi
    info "SoapyHackRF/SoapyBladeRF are built from source below — the Homebrew tap formulae"
    info "pull an extra python and fail on modern CMake, so they are deliberately avoided."
}

build_soapy_module() {
    local name="$1" repo="$2" factory="$3" brewpfx
    if SoapySDRUtil --info 2>/dev/null | grep -qi "$factory"; then
        ok "Soapy $factory driver already present — skip"
        return
    fi
    brewpfx="$(brew --prefix)"
    local log="${TMPDIR:-/tmp}/dragon-${name}-build.log"
    : > "$log"
    say "Building $name from source (C++ only — pulls no python; log: $log)"
    local src="${HOME}/.cache/dragon-fpv/$name"
    mkdir -p "$(dirname "$src")"
    [[ -d "$src/.git" ]] || run_quiet "$log" git clone --depth 1 "$repo" "$src"
    cd "$src" || { err "cannot enter $src"; exit 1; }
    run_quiet "$log" cmake -B build \
        -DCMAKE_POLICY_VERSION_MINIMUM=3.5 \
        -DCMAKE_PREFIX_PATH="$brewpfx" \
        -DCMAKE_INSTALL_PREFIX="$brewpfx"
    run_quiet "$log" cmake --build build -j"$(sysctl -n hw.ncpu)"
    run_quiet "$log" cmake --install build
    cd "$PROJECT_DIR" || exit 1
    ok "$name built + installed (final --check below lists the $factory driver)"
}

build_soapy_modules_mac() {
    have SoapySDRUtil || { warn "SoapySDR not found — skipping SDR driver builds"; return; }
    build_soapy_module SoapyHackRF  https://github.com/pothosware/SoapyHackRF.git  hackrf
    build_soapy_module SoapyBladeRF https://github.com/pothosware/SoapyBladeRF.git bladerf
}

install_linux() {
    if ! have apt-get; then
        err "Non-apt Linux detected."
        echo "  Install: gnuradio gnuradio-dev (gr-soapy ships inside gnuradio), soapysdr-tools,"
        echo "  the SoapySDR device modules (hackrf/bladerf), uhd-host, ffmpeg, cmake, g++, git,"
        echo "  python3-numpy python3-pil python3-dev python3-pybind11 libboost-all-dev"
        echo "  then re-run:  ./setup.sh --check"
        exit 1
    fi
    say "Installing GNU Radio + SDR stack via apt (sudo)"
    need sudo apt-get update
    need sudo apt-get install -y \
        gnuradio gnuradio-dev soapysdr-tools \
        soapysdr-module-hackrf soapysdr-module-bladerf \
        uhd-host ffmpeg cmake g++ git pkg-config \
        python3-numpy python3-pil python3-dev python3-pybind11 libboost-all-dev
}

install_pydeps() {
    resolve_py
    if "$PYTHON" -c "import numpy, PIL" 2>/dev/null; then
        ok "numpy + Pillow already importable"
        return
    fi
    say "Installing Python deps (numpy, Pillow) for $PYTHON"
    "$PYTHON" -m pip install --user -r requirements.txt \
        || "$PYTHON" -m pip install --user --break-system-packages -r requirements.txt \
        || { err "pip install failed — install numpy + Pillow for $PYTHON manually"; exit 1; }
}

build_ntsc() {
    resolve_py
    if "$PYTHON" -c "import gnuradio.NTSC" 2>/dev/null; then
        ok "gr-ntsc-rc already installed — skipping build"
        return
    fi
    local log="${TMPDIR:-/tmp}/dragon-gr-ntsc-rc-build.log"
    : > "$log"
    say "Building gr-ntsc-rc (PR6) with the converter-bounds patch (log: $log)"
    if [[ -d "$NTSC_SRC/.git" ]]; then
        ok "reusing $NTSC_SRC"
    else
        need git clone https://github.com/lscardoso/gr-ntsc-rc.git "$NTSC_SRC"
    fi
    cd "$NTSC_SRC" || { err "cannot enter $NTSC_SRC"; exit 1; }
    git fetch origin pull/6/head:pr6 2>/dev/null || true
    need git checkout pr6
    if git apply --check "$PROJECT_DIR/patches/gr-ntsc-rc-converter-bounds.patch" 2>/dev/null; then
        need git apply "$PROJECT_DIR/patches/gr-ntsc-rc-converter-bounds.patch"
        ok "applied converter-bounds patch"
    else
        warn "converter-bounds patch already applied (or not applicable) — continuing"
    fi
    if [[ "$OS" == Darwin ]]; then
        local brewpfx pyver
        brewpfx="$(brew --prefix)"
        pyver="$("$PYTHON" -c 'import sys;print("python%d.%d"%sys.version_info[:2])')"
        run_quiet "$log" cmake -B build \
            -DCMAKE_POLICY_VERSION_MINIMUM=3.5 \
            -DCMAKE_PREFIX_PATH="$brewpfx" \
            -DCMAKE_INSTALL_PREFIX="$HOME/.local" \
            -DPYTHON_EXECUTABLE="$PYTHON" \
            -DGR_PYTHON_DIR="$HOME/.local/lib/$pyver/site-packages"
        run_quiet "$log" cmake --build build -j"$(sysctl -n hw.ncpu)"
        run_quiet "$log" cmake --install build
    else
        run_quiet "$log" cmake -B build -DCMAKE_POLICY_VERSION_MINIMUM=3.5
        run_quiet "$log" cmake --build build -j"$(nproc)"
        run_quiet "$log" sudo cmake --install build
        sudo ldconfig || true
    fi
    cd "$PROJECT_DIR" || exit 1
}

if [[ $CHECK_ONLY -eq 1 ]]; then
    doctor || true
    exit 0
fi

say "Dragon FPV Decoder setup — $OS"
case "$OS" in
    Darwin) install_mac ;;
    Linux)  install_linux ;;
    *) err "Unsupported OS: $OS"; exit 1 ;;
esac
install_pydeps
[[ "$OS" == Darwin ]] && build_soapy_modules_mac
build_ntsc
chmod +x fpv_scanner.sh fpv_detect.py fpv_viewer.py fpv_sdr.py

if doctor; then
    say "Setup complete. Run:"
else
    say "Setup finished with warnings above. Run when ready:"
fi
echo "  ./fpv_scanner.sh                 # ANTSDR / UHD (default)"
echo "  ./fpv_scanner.sh --sdr hackrf    # HackRF  (or: --sdr bladerf)"
echo "  then type 'scan'"
