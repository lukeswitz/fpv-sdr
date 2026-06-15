@echo off
wsl -d Ubuntu -- bash -lc "cd ~/dragon-fpv-decoder && ./fpv_scanner.sh %*"
