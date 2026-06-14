#!/usr/bin/env bash

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DETECT_PY="$PROJECT_DIR/fpv_detect.py"
VIEWER_PY="$PROJECT_DIR/fpv_viewer.py"
SCAN_LOG="$PROJECT_DIR/scan_log.txt"
PYTHON="${FPV_PYTHON:-python3}"

SDR="${FPV_SDR:-uhd}"
GAIN="${FPV_GAIN:-}"
GAIN_SET=""; [[ -n "$FPV_GAIN" ]] && GAIN_SET=1
LNA="${FPV_LNA:-}"
VGA="${FPV_VGA:-}"
AMP="${FPV_AMP:-}"
SAMP_RATE="${FPV_SAMP_RATE:-10e6}"
DETECT_SAMP_RATE="${FPV_DETECT_SAMP_RATE:-20e6}"
ROTATE="${FPV_ROTATE:-0}"
CONTRAST="${FPV_CONTRAST:-0.8}"
MARGIN="${FPV_MARGIN:-12}"
SETTLE="${FPV_SETTLE:-0.2}"
CONFIRM="${FPV_CONFIRM:-}"
DEV_ARGS="${FPV_DEV_ARGS:-}"
ANTENNA="${FPV_ANTENNA:-}"
VIEW_EXTRA="${FPV_VIEW_EXTRA:-}"
RECORD="${FPV_RECORD:-}"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --sdr) SDR="$2"; shift 2 ;;
        --gain) GAIN="$2"; GAIN_SET=1; shift 2 ;;
        --lna) LNA="$2"; shift 2 ;;
        --vga) VGA="$2"; shift 2 ;;
        --amp) AMP=1; shift ;;
        --samp-rate) SAMP_RATE="$2"; shift 2 ;;
        --margin) MARGIN="$2"; shift 2 ;;
        --dev-args) DEV_ARGS="$2"; shift 2 ;;
        --antenna) ANTENNA="$2"; shift 2 ;;
        -h|--help)
            echo "Usage: $0 [--sdr uhd|hackrf|bladerf] [--gain N] [--lna N] [--vga N] [--amp] [--samp-rate HZ] [--margin dB] [--dev-args STR] [--antenna NAME]"
            exit 0 ;;
        *) echo "[WARN] unknown arg: $1"; shift ;;
    esac
done

declare -A CHANNELS=(
    ["R1"]=5658 ["R2"]=5695 ["R3"]=5732 ["R4"]=5769
    ["R5"]=5806 ["R6"]=5843 ["R7"]=5880 ["R8"]=5917
    ["A1"]=5865 ["A2"]=5845 ["A3"]=5825 ["A4"]=5805
    ["A5"]=5785 ["A6"]=5765 ["A7"]=5745 ["A8"]=5725
    ["B1"]=5733 ["B2"]=5752 ["B3"]=5771 ["B4"]=5790
    ["B5"]=5809 ["B6"]=5828 ["B7"]=5847 ["B8"]=5866
    ["E1"]=5705 ["E2"]=5685 ["E3"]=5665 ["E4"]=5645
    ["E5"]=5885 ["E6"]=5905 ["E7"]=5925 ["E8"]=5945
    ["F1"]=5740 ["F2"]=5760 ["F3"]=5780 ["F4"]=5800
    ["F5"]=5820 ["F6"]=5840 ["F7"]=5860 ["F8"]=5880
    ["IMD1"]=5658 ["IMD2"]=5695 ["IMD3"]=5732
    ["IMD4"]=5769 ["IMD5"]=5806 ["IMD6"]=5843
    ["D1"]=5660 ["D2"]=5695 ["D3"]=5735 ["D4"]=5770
    ["D5"]=5805 ["D6"]=5878 ["D7"]=5914 ["D8"]=5839
    ["L1"]=5362 ["L2"]=5399 ["L3"]=5436 ["L4"]=5473
    ["L5"]=5510 ["L6"]=5547 ["L7"]=5584 ["L8"]=5621
)

SCAN_ORDER=(
    R1 R2 R3 R4 R5 R6 R7 R8
    A1 A2 A3 A4 A5 A6 A7 A8
    F1 F2 F3 F4 F5 F6 F7 F8
    E1 E2 E3 E4 E5 E6 E7 E8
    B1 B2 B3 B4 B5 B6 B7 B8
    D1 D2 D3 D4 D5 D6 D7 D8
    L1 L2 L3 L4 L5 L6 L7 L8
)

TB_INSTANCE=""
DETECT_PID=""
SCAN_ACTIVE=0
SCAN_LOOP_ABORT=0
CURRENT_FREQ=""
CURRENT_CHANNEL=""

resolve_gain() {
    if [[ -z "$GAIN" ]]; then
        case "$SDR" in
            hackrf) GAIN=24 ;;
            *) GAIN=40 ;;
        esac
    fi
}

release_sdr() {
    [[ -n "$DETECT_PID" ]] && kill -TERM "$DETECT_PID" 2>/dev/null
    [[ -n "$TB_INSTANCE" ]] && kill -TERM "$TB_INSTANCE" 2>/dev/null
    pkill -TERM -f "fpv_detect.py" >/dev/null 2>&1
    pkill -TERM -f "fpv_viewer.py" >/dev/null 2>&1
    pkill -TERM -f "top_block.py"  >/dev/null 2>&1
    sleep 1.5
    pkill -9 -f "fpv_detect.py" >/dev/null 2>&1
    pkill -9 -f "fpv_viewer.py" >/dev/null 2>&1
    pkill -9 -f "top_block.py"  >/dev/null 2>&1
    DETECT_PID=""
    TB_INSTANCE=""
}

cleanup() {
    echo -e "\n[INFO] Shutting down..."
    SCAN_ACTIVE=0
    release_sdr
    echo "[INFO] Cleanup complete"
    exit 0
}

trap cleanup EXIT INT TERM

set_frequency() {
    local freq_mhz=$1
    local channel_name=$2

    release_sdr

    cd "$PROJECT_DIR" || return 1
    DISPLAY="${DISPLAY:-:0}" "$PYTHON" "$VIEWER_PY" \
        --sdr "$SDR" --freq "${freq_mhz}e6" --gain "$GAIN" --samp-rate "$SAMP_RATE" \
        ${LNA:+--lna "$LNA"} ${VGA:+--vga "$VGA"} ${AMP:+--amp} \
        --rotate "$ROTATE" --contrast "$CONTRAST" \
        ${DEV_ARGS:+--dev-args "$DEV_ARGS"} \
        ${ANTENNA:+--antenna "$ANTENNA"} \
        ${RECORD:+--record "$RECORD"} \
        ${VIEW_EXTRA} \
        >/dev/null 2>&1 &
    TB_INSTANCE=$!

    CURRENT_FREQ=$freq_mhz
    CURRENT_CHANNEL=$channel_name

    echo "[$(date +%H:%M:%S)] Viewing $channel_name ($freq_mhz MHz) [$SDR] - PID: $TB_INSTANCE"
    echo "$(date +%Y-%m-%d_%H:%M:%S),$channel_name,$freq_mhz" >> "$SCAN_LOG"
}

scan_channels() {
    SCAN_ACTIVE=1
    release_sdr

    local tokens=() channel
    for channel in "${SCAN_ORDER[@]}"; do
        tokens+=("${channel}:${CHANNELS[$channel]}e6")
    done

    echo "[INFO] Scanning ${#tokens[@]} channels headless on [$SDR] — no window opens until a signal is found"
    echo "[INFO] (type 'stop' to abort the sweep)"

    local hit_name="" hit_freq=""
    while read -r tag f1 f2 f3 _ f5; do
        [[ $SCAN_ACTIVE -eq 0 ]] && break
        case "$tag" in
            DETECT)
                local mhz
                mhz=$(awk "BEGIN{printf \"%.0f\", $f2/1e6}")
                printf "  %-5s %5s MHz  %7s dBFS  %s\n" "$f1" "$mhz" "$f3" "$f5"
                ;;
            HIT)
                hit_name="$f1"; hit_freq="$f2"
                break
                ;;
        esac
    done < <(
        "$PYTHON" "$DETECT_PY" \
            --sdr "$SDR" --gain "$GAIN" --samp-rate "$DETECT_SAMP_RATE" \
            ${LNA:+--lna "$LNA"} ${VGA:+--vga "$VGA"} ${AMP:+--amp} \
            --settle "$SETTLE" --margin "$MARGIN" \
            ${CONFIRM:+--confirm "$CONFIRM"} \
            ${DEV_ARGS:+--dev-args "$DEV_ARGS"} \
            ${ANTENNA:+--antenna "$ANTENNA"} \
            "${tokens[@]}" 2>/dev/null
    )

    pkill -9 -f "fpv_detect.py" >/dev/null 2>&1
    DETECT_PID=""

    if [[ $SCAN_ACTIVE -eq 0 ]]; then
        echo "[INFO] Scan stopped"
        return
    fi

    if [[ -n "$hit_name" ]]; then
        local mhz
        mhz=$(awk "BEGIN{printf \"%.0f\", $hit_freq/1e6}")
        echo -e "\n[SIGNAL] $hit_name found at ${mhz} MHz — opening viewer"
        echo "$(date +%Y-%m-%d_%H:%M:%S),HIT,$hit_name,$mhz" >> "$SCAN_LOG"
        set_frequency "$mhz" "$hit_name"
    else
        echo "[INFO] No FPV signals found"
    fi
    SCAN_ACTIVE=0
}

scan_loop() {
    local timeout="${1:-}"
    local gap="${FPV_SCAN_LOOP_GAP:-2}"
    SCAN_ACTIVE=1
    SCAN_LOOP_ABORT=0
    release_sdr

    local tokens=() channel
    for channel in "${SCAN_ORDER[@]}"; do
        tokens+=("${channel}:${CHANNELS[$channel]}e6")
    done

    local deadline=0 watchdog=""
    if [[ "$timeout" =~ ^[0-9]+$ && "$timeout" -gt 0 ]]; then
        deadline=$(( $(date +%s) + timeout ))
        ( sleep "$timeout"; pkill -TERM -f "fpv_detect.py" >/dev/null 2>&1 ) &
        watchdog=$!
        echo "[INFO] Continuous scan on [$SDR] — auto-stops after ${timeout}s. Ctrl-C anytime, or ENTER between sweeps."
    else
        echo "[INFO] Continuous scan on [$SDR] — re-sweeping until a valid signal. Ctrl-C anytime, or ENTER between sweeps."
    fi

    trap 'SCAN_LOOP_ABORT=1; SCAN_ACTIVE=0; pkill -TERM -f "fpv_detect.py" >/dev/null 2>&1' INT

    local pass=0 hit_name="" hit_freq=""
    while [[ $SCAN_ACTIVE -eq 1 && $SCAN_LOOP_ABORT -eq 0 ]]; do
        if [[ $deadline -gt 0 && $(date +%s) -ge $deadline ]]; then
            echo "[INFO] Continuous scan time limit reached"
            break
        fi
        pass=$((pass + 1))
        echo -e "\n[INFO] Sweep pass #$pass (${#tokens[@]} channels)…"
        hit_name=""; hit_freq=""
        while read -r tag f1 f2 f3 _ f5; do
            [[ $SCAN_ACTIVE -eq 0 || $SCAN_LOOP_ABORT -eq 1 ]] && break
            case "$tag" in
                DETECT)
                    local mhz
                    mhz=$(awk "BEGIN{printf \"%.0f\", $f2/1e6}")
                    printf "  %-5s %5s MHz  %7s dBFS  %s\n" "$f1" "$mhz" "$f3" "$f5"
                    ;;
                HIT)
                    hit_name="$f1"; hit_freq="$f2"
                    break
                    ;;
            esac
        done < <(
            "$PYTHON" "$DETECT_PY" \
                --sdr "$SDR" --gain "$GAIN" --samp-rate "$DETECT_SAMP_RATE" \
                ${LNA:+--lna "$LNA"} ${VGA:+--vga "$VGA"} ${AMP:+--amp} \
                --settle "$SETTLE" --margin "$MARGIN" \
                ${CONFIRM:+--confirm "$CONFIRM"} \
                ${DEV_ARGS:+--dev-args "$DEV_ARGS"} \
                ${ANTENNA:+--antenna "$ANTENNA"} \
                "${tokens[@]}" 2>/dev/null
        )
        pkill -9 -f "fpv_detect.py" >/dev/null 2>&1
        DETECT_PID=""

        [[ -n "$hit_name" ]] && break
        [[ $SCAN_ACTIVE -eq 0 || $SCAN_LOOP_ABORT -eq 1 ]] && break
        if [[ $deadline -gt 0 && $(date +%s) -ge $deadline ]]; then
            echo "[INFO] Continuous scan time limit reached"
            break
        fi
        echo "[INFO] No signal — next sweep in ${gap}s (press ENTER to stop now)"
        if read -t "$gap" -r _; then
            SCAN_LOOP_ABORT=1
            break
        fi
    done

    trap cleanup EXIT INT TERM
    [[ -n "$watchdog" ]] && kill "$watchdog" >/dev/null 2>&1

    if [[ -n "$hit_name" ]]; then
        local mhz
        mhz=$(awk "BEGIN{printf \"%.0f\", $hit_freq/1e6}")
        echo -e "\n[SIGNAL] $hit_name found at ${mhz} MHz — opening viewer"
        echo "$(date +%Y-%m-%d_%H:%M:%S),HIT,$hit_name,$mhz" >> "$SCAN_LOG"
        set_frequency "$mhz" "$hit_name"
    elif [[ $SCAN_LOOP_ABORT -eq 1 ]]; then
        echo -e "\n[INFO] Continuous scan stopped"
    else
        echo -e "\n[INFO] Continuous scan ended — no valid signal"
    fi
    SCAN_ACTIVE=0
    SCAN_LOOP_ABORT=0
}

sweep_channels() {
    release_sdr
    local tokens=() channel
    for channel in "${SCAN_ORDER[@]}"; do
        tokens+=("${channel}:${CHANNELS[$channel]}e6")
    done
    echo "[INFO] Fast RSSI sweep of ${#tokens[@]} channels on [$SDR] (no video)..."
    local errf="/tmp/fpv_sweep.err"
    "$PYTHON" "$DETECT_PY" \
        --sdr "$SDR" --gain "$GAIN" --samp-rate "$DETECT_SAMP_RATE" \
        ${LNA:+--lna "$LNA"} ${VGA:+--vga "$VGA"} ${AMP:+--amp} \
        --settle "$SETTLE" --margin "$MARGIN" --survey-only \
        ${DEV_ARGS:+--dev-args "$DEV_ARGS"} \
        ${ANTENNA:+--antenna "$ANTENNA"} \
        "${tokens[@]}" 2>"$errf" \
      | awk '/^DETECT/{printf "  %-5s %4.0f MHz  %7.1f dBFS\n", $2, $3/1e6, $4}' \
      | sort -k4 -nr
    grep -o "noise floor.*" "$errf" 2>/dev/null | tail -1 | sed 's/^/[INFO] /'
    DETECT_PID=""
}

show_spectrum() {
    local arg="$1" interval="$2"
    stop_scan
    release_sdr
    local tokens=() channel
    for channel in "${SCAN_ORDER[@]}"; do
        tokens+=("${channel}:${CHANNELS[$channel]}e6")
    done
    local W
    W=$(tput cols 2>/dev/null || echo 100)
    if (( W > 28 )); then W=$((W - 8)); else W=80; fi
    local extra=""
    if [[ "$arg" == "live" ]]; then
        extra="--continuous"
        echo "[INFO] Live band spectrum — Ctrl-C to stop"
    elif [[ -n "$arg" && -n "${CHANNELS[$arg]:-}" ]]; then
        extra="--spec-center ${CHANNELS[$arg]}e6 --continuous"
        echo "[INFO] Live spectrum @ $arg (${CHANNELS[$arg]} MHz) — Ctrl-C to stop"
    elif [[ "$arg" =~ ^[0-9]+$ ]]; then
        extra="--spec-center ${arg}e6 --continuous"
        echo "[INFO] Live spectrum @ ${arg} MHz — Ctrl-C to stop"
    fi
    if [[ "$interval" =~ ^[0-9]+(\.[0-9]+)?$ && "$extra" == *--continuous* ]]; then
        extra="$extra --spec-interval $interval"
        echo "[INFO]   refresh every ${interval}s between frames"
    fi
    "$PYTHON" "$DETECT_PY" \
        --sdr "$SDR" --gain "$GAIN" --samp-rate "$DETECT_SAMP_RATE" \
        ${LNA:+--lna "$LNA"} ${VGA:+--vga "$VGA"} ${AMP:+--amp} \
        --settle 0.1 --chunk-dwell 0.06 --spectrum --spec-width "$W" $extra \
        ${DEV_ARGS:+--dev-args "$DEV_ARGS"} \
        ${ANTENNA:+--antenna "$ANTENNA"} \
        "${tokens[@]}" 2>/dev/null &
    local pid=$!
    trap 'kill -TERM "$pid" 2>/dev/null' INT
    wait "$pid" 2>/dev/null
    trap cleanup EXIT INT TERM
    DETECT_PID=""
    echo
}

stop_scan() {
    SCAN_ACTIVE=0
    pkill -9 -f "fpv_detect.py" >/dev/null 2>&1
    DETECT_PID=""
}

show_menu() {
    echo -e "\n========================================="
    echo "FPV Channel Scanner & Monitor"
    echo "========================================="
    echo "SDR: $SDR  |  Gain: $GAIN dB${LNA:+  LNA:$LNA}${VGA:+ VGA:$VGA}${AMP:+ AMP:on}  |  Current: ${CURRENT_CHANNEL:-none}${CURRENT_FREQ:+ (${CURRENT_FREQ} MHz)}"
    echo ""
    echo "Commands:"
    printf "  %-16s %s\n" \
        "scan"            "sweep once, view strongest valid signal" \
        "scan loop [SEC]" "re-sweep until signal; Ctrl-C/ENTER stop; SEC auto-stops" \
        "sweep"           "fast RSSI survey, no video" \
        "spectrum [X] [SEC]" "terminal FFT; X=live|CH|MHz, SEC=refresh delay" \
        "stop"            "stop the sweep" \
        "set <CH>"        "tune + view a channel (e.g. set R6)" \
        "freq <MHz>"      "tune + view a frequency (e.g. freq 5843)" \
        "list"            "list all channels" \
        "sdr <NAME>"      "switch radio (uhd|hackrf|bladerf)" \
        "gain <dB>"       "RX gain (HackRF drives LNA+VGA)" \
        "lna <dB>"        "HackRF LNA 0-40, optional override" \
        "vga <dB>"        "HackRF VGA 0-62, optional override" \
        "dwell <SEC>"     "per-channel scan time (def ${SETTLE})" \
        "margin <dB>"     "detect threshold over floor (def ${MARGIN})" \
        "record <file>"   "record video; bare 'record' = off" \
        "rotate <deg>"    "0|90|180|270 (def ${ROTATE})" \
        "contrast <x>"    "demod contrast (def ${CONTRAST})" \
        "log"             "show scan log" \
        "quit"            "exit"
    echo "========================================="
}

list_channels() {
    echo -e "\nAvailable Channels:"
    echo "Raceband:   R1-R8 (5658-5917 MHz)"
    echo "Band A:     A1-A8 (5725-5865 MHz)"
    echo "Band B:     B1-B8 (5733-5866 MHz)"
    echo "Band E:     E1-E8 (5645-5945 MHz)"
    echo "Fatshark:   F1-F8 (5740-5880 MHz)"
    echo "ImmersionRC: IMD1-IMD6 (5658-5843 MHz)"
    echo "DJI:        D1-D8 (5660-5914 MHz)"
    echo "Low Band:   L1-L8 (5362-5621 MHz)"
}

main() {
    cd "$PROJECT_DIR" || { echo "[ERROR] Project directory not found: $PROJECT_DIR"; exit 1; }

    [[ ! -f "$DETECT_PY" ]] && { echo "[ERROR] Detector not found: $DETECT_PY"; exit 1; }
    [[ ! -f "$VIEWER_PY" ]] && { echo "[ERROR] Viewer not found: $VIEWER_PY"; exit 1; }

    if [[ -f "$PROJECT_DIR/fpv_env.sh" ]]; then
        source "$PROJECT_DIR/fpv_env.sh"
        resolve_fpv_python || { echo "[ERROR] No Python with GNU Radio bindings; set FPV_PYTHON"; exit 1; }
    fi

    resolve_gain
    echo "[INFO] FPV Scanner initialized (SDR: $SDR, gain: $GAIN, samp_rate: $SAMP_RATE)"
    echo "[INFO] Python: $PYTHON"
    echo "[INFO] Log file: $SCAN_LOG"
    echo "[INFO] No video window opens until a signal is detected — type 'scan' to begin."

    show_menu
    
    while true; do
        echo -n "> "
        read -r cmd arg1 arg2
        
        case "$cmd" in
            scan)
                case "$arg1" in
                    loop|continuous|keep) scan_loop "$arg2" ;;
                    *) scan_channels ;;
                esac
                ;;
            sweep) sweep_channels ;;
            spectrum|fft) show_spectrum "$arg1" "$arg2" ;;
            stop) stop_scan ;;
            set)
                if [[ -n "${CHANNELS[$arg1]}" ]]; then
                    stop_scan
                    set_frequency "${CHANNELS[$arg1]}" "$arg1"
                else
                    echo "[ERROR] Unknown channel: $arg1"
                fi
                ;;
            freq)
                if [[ "$arg1" =~ ^[0-9]+$ ]]; then
                    stop_scan
                    set_frequency "$arg1" "MANUAL"
                else
                    echo "[ERROR] Invalid frequency: $arg1"
                fi
                ;;
            list) list_channels ;;
            sdr)
                if [[ -n "$arg1" ]]; then
                    stop_scan
                    release_sdr
                    SDR="$arg1"
                    if [[ -z "$GAIN_SET" ]]; then GAIN=""; resolve_gain; fi
                    echo "[INFO] SDR set to $SDR (gain $GAIN dB)"
                else
                    echo "[INFO] Current SDR: $SDR"
                fi
                ;;
            gain)
                if [[ "$arg1" =~ ^[0-9]+(\.[0-9]+)?$ ]]; then
                    GAIN="$arg1"; GAIN_SET=1
                    echo "[INFO] Gain set to $GAIN dB (applies on next tune/scan)"
                else
                    echo "[ERROR] Invalid gain: $arg1"
                fi
                ;;
            lna)
                if [[ "$arg1" =~ ^[0-9]+(\.[0-9]+)?$ ]]; then
                    LNA="$arg1"
                    echo "[INFO] HackRF LNA gain set to $LNA dB (applies on next tune/scan)"
                else
                    echo "[ERROR] Invalid LNA gain: $arg1"
                fi
                ;;
            vga)
                if [[ "$arg1" =~ ^[0-9]+(\.[0-9]+)?$ ]]; then
                    VGA="$arg1"
                    echo "[INFO] HackRF VGA gain set to $VGA dB (applies on next tune/scan)"
                else
                    echo "[ERROR] Invalid VGA gain: $arg1"
                fi
                ;;
            dwell)
                if [[ "$arg1" =~ ^[0-9]+(\.[0-9]+)?$ ]]; then
                    SETTLE="$arg1"
                    echo "[INFO] Per-channel scan time set to ${SETTLE}s"
                else
                    echo "[ERROR] Invalid time: $arg1"
                fi
                ;;
            margin)
                if [[ "$arg1" =~ ^[0-9]+(\.[0-9]+)?$ ]]; then
                    MARGIN="$arg1"
                    echo "[INFO] Detection margin set to ${MARGIN} dB over noise floor"
                else
                    echo "[ERROR] Invalid margin: $arg1"
                fi
                ;;
            record)
                if [[ -n "$arg1" ]]; then
                    RECORD="$arg1"
                    echo "[INFO] Recording to $RECORD — re-tune (set/scan) to start; 'record' alone stops"
                else
                    RECORD=""
                    echo "[INFO] Recording off"
                fi
                ;;
            rotate)
                if [[ "$arg1" =~ ^(0|90|180|270)$ ]]; then
                    ROTATE="$arg1"
                    echo "[INFO] Rotation set to ${ROTATE} deg (applies on next tune)"
                    [[ -n "$CURRENT_CHANNEL" ]] && set_frequency "$CURRENT_FREQ" "$CURRENT_CHANNEL"
                else
                    echo "[ERROR] rotate must be 0, 90, 180 or 270"
                fi
                ;;
            contrast)
                if [[ "$arg1" =~ ^[0-9]+(\.[0-9]+)?$ ]]; then
                    CONTRAST="$arg1"
                    echo "[INFO] Contrast set to ${CONTRAST} (applies on next tune)"
                    [[ -n "$CURRENT_CHANNEL" ]] && set_frequency "$CURRENT_FREQ" "$CURRENT_CHANNEL"
                else
                    echo "[ERROR] Invalid contrast: $arg1"
                fi
                ;;
            log) [[ -f "$SCAN_LOG" ]] && tail -20 "$SCAN_LOG" || echo "[INFO] No log entries" ;;
            menu|help) show_menu ;;
            quit|exit) cleanup ;;
            "") continue ;;
            *) echo "[ERROR] Unknown command: $cmd" ;;
        esac
    done
}

main
