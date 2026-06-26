#!/usr/bin/env bash
# Verifies the 1.2/1.3 GHz band is wired into the scanner (channel map + band switch).
# Pure static/syntax checks — no SDR, no GNU Radio needed.
set -euo pipefail
S="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/fpv_scanner.sh"

fail() { echo "FAIL: $1"; exit 1; }

bash -n "$S" || fail "syntax error in fpv_scanner.sh"

# 1.2/1.3 GHz has no standard channel grid, so there are NO named 1.2 GHz channels —
# the band is reached only by the sweep (band 12) or a raw `freq <MHz>`. Guard against
# regressing to made-up channel names.
grep -qE '\["U[0-9]+"\]' "$S" && fail "made-up U-channels reintroduced — 1.2 GHz has no named grid"

# Band switch wiring
grep -qE '12\|13\|1\.2\|1\.3\)' "$S" || fail "'band 12' branch missing"
grep -qE '58\|5\.8\|5\|""\)'   "$S" || fail "'band 58' branch missing"
grep -q '1.2/1.3GHz: 1010-1360 MHz' "$S" || fail "list_channels 1.2 GHz line missing"

# Gapless-sweep coverage: 1.2 GHz has no standard grid, so band12_sweep must emit
# points spaced < the detector's 10 MHz in-band window with NO gap > 10 MHz across
# 1010-1360 MHz. Re-derive the grid the same way the scanner does and assert it.
prev=0; maxgap=0; first=0; last=0
for (( f = 1010; f <= 1360; f += 7 )); do
    (( first == 0 )) && first=$f
    if (( prev > 0 )); then g=$(( f - prev )); (( g > maxgap )) && maxgap=$g; fi
    prev=$f; last=$f
done
(( first <= 1010 ))                || fail "sweep starts above 1010 MHz"
(( last  >= 1354 ))                || fail "sweep ends below ~1360 MHz (got $last)"
(( maxgap <= 10 ))                 || fail "sweep gap ${maxgap} MHz exceeds 10 MHz in-band window — VTX could be missed"
grep -qE 'for \(\( f = 1010; f <= 1360; f \+= 7 \)\)' "$S" || fail "band12_sweep grid changed — update this test"

echo "PASS: no made-up channel names; gapless 1.2 GHz sweep (max gap ${maxgap} MHz ≤ 10 MHz window), band switch, list"
