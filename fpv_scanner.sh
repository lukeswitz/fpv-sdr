#!/bin/bash

PROJECT_DIR=~/dragon-fpv-decoder/
GRC_FILE="$PROJECT_DIR/NTSC_Video_5GHz_RX.grc"
PY_FILE="$PROJECT_DIR/top_block.py"
SCAN_LOG="$PROJECT_DIR/scan_log.txt"
FIFO="/tmp/fpv_scanner_cmd"

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

DECODER_PID=""
SCAN_ACTIVE=0
SCAN_DWELL_TIME=3
CURRENT_FREQ=""
CURRENT_CHANNEL=""

create_fifo() {
    [[ -p "$FIFO" ]] || mkfifo "$FIFO"
}

kill_decoder_clean() {
    pkill -9 -f "top_block.py" 2>/dev/null
    sleep 0.5
    
    if pgrep -f "top_block.py" >/dev/null; then
        for pid in $(pgrep -f "top_block.py"); do
            kill -9 "$pid" 2>/dev/null
        done
    fi
    
    DECODER_PID=""
}

cleanup() {
    echo -e "\n[INFO] Shutting down..."
    SCAN_ACTIVE=0
    
    pkill -9 -f "top_block.py" 2>/dev/null
    sleep 0.5
    
    for pid in $(pgrep -f "top_block.py"); do
        kill -9 "$pid" 2>/dev/null
    done
    
    rm -f "$FIFO"
    echo "[INFO] Cleanup complete"
    exit 0
}

trap cleanup EXIT INT TERM

set_frequency() {
    local freq_mhz=$1
    local channel_name=$2
    local freq_hz="${freq_mhz}e6"
    
    pkill -9 -f "top_block.py" 2>/dev/null
    sleep 0.5
    
    sed -i "s/frequency_carrier = frequency_carrier = [0-9.]*e[0-9]*/frequency_carrier = frequency_carrier = ${freq_hz}/" "$GRC_FILE"
    
    cd "$PROJECT_DIR"
    grcc NTSC_Video_5GHz_RX.grc &>/dev/null
    
    sed -i "s/input('Press Enter to quit: ')/time.sleep(999999)/" "$PY_FILE"
    
    export DISPLAY=:0
    python3 "$PY_FILE" >/dev/null 2>&1 &
    DECODER_PID=$!
    
    CURRENT_FREQ=$freq_mhz
    CURRENT_CHANNEL=$channel_name
    
    echo "[$(date +%H:%M:%S)] Channel $channel_name ($freq_mhz MHz) - PID: $DECODER_PID"
    echo "$(date +%Y-%m-%d_%H:%M:%S),$channel_name,$freq_mhz" >> "$SCAN_LOG"
}

scan_channels() {
    SCAN_ACTIVE=1
    echo "[INFO] Starting channel scan (${#SCAN_ORDER[@]} channels, ${SCAN_DWELL_TIME}s dwell)"
    
    while [[ $SCAN_ACTIVE -eq 1 ]]; do
        for channel in "${SCAN_ORDER[@]}"; do
            [[ $SCAN_ACTIVE -eq 0 ]] && break
            
            local freq=${CHANNELS[$channel]}
            echo -e "\n[SCAN] Tuning to $channel: $freq MHz"
            set_frequency "$freq" "$channel"
            
            sleep "$SCAN_DWELL_TIME"
        done
        
        [[ $SCAN_ACTIVE -eq 1 ]] && echo -e "\n[INFO] Scan cycle complete, restarting..."
    done
    
    echo "[INFO] Scan stopped"
}

stop_scan() {
    SCAN_ACTIVE=0
}

show_menu() {
    echo -e "\n========================================="
    echo "FPV Channel Scanner & Monitor"
    echo "========================================="
    echo "Current: $CURRENT_CHANNEL ($CURRENT_FREQ MHz)"
    echo ""
    echo "Commands:"
    echo "  scan          - Start auto-scan all channels"
    echo "  stop          - Stop auto-scan"
    echo "  set <CH>      - Tune to channel (e.g., 'set R6')"
    echo "  freq <MHz>    - Tune to frequency (e.g., 'freq 5843')"
    echo "  list          - Show all channels"
    echo "  dwell <SEC>   - Set scan dwell time (default: 3s)"
    echo "  log           - Show scan log"
    echo "  quit          - Exit"
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
    cd "$PROJECT_DIR" || { echo "[ERROR] Project directory not found"; exit 1; }
    
    [[ ! -f "$GRC_FILE" ]] && { echo "[ERROR] GRC file not found"; exit 1; }
    
    if ! grep -q "uhd_usrp_source" "$GRC_FILE"; then
        echo "[ERROR] GRC file uses wrong driver"
        exit 1
    fi
    
    create_fifo
    
    echo "[INFO] FPV Scanner initialized"
    echo "[INFO] Log file: $SCAN_LOG"
    
    set_frequency 5725 "A8"
    
    show_menu
    
    while true; do
        echo -n "> "
        read -r cmd arg1 arg2
        
        case "$cmd" in
            scan) scan_channels & ;;
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
            dwell)
                if [[ "$arg1" =~ ^[0-9]+$ ]] && [[ $arg1 -gt 0 ]]; then
                    SCAN_DWELL_TIME=$arg1
                    echo "[INFO] Dwell time set to ${SCAN_DWELL_TIME}s"
                else
                    echo "[ERROR] Invalid dwell time: $arg1"
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
