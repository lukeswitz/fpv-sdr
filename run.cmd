@echo off
wsl -d Ubuntu -- bash -lc "cd ~/fpv-sdr && ./fpv_scanner.sh %*"
