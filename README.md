# Dragon FPV Decoder

NTSC 5.8 GHz FPV video receiver and scanner for ANTSDR E200 using GNU Radio.

## Prerequisites

- WarDragon system with ANTSDR E200
- ANTSDR configured with **UHD firmware** (pre-configured on WarDragon)
- GNU Radio and UHD drivers (pre-installed on WarDragon)
- Specified fork of gr-ntsc-rc

## Installation
```bash
# Clone gr-ntsc-rc decoder module
git clone git@github.com:lscardoso/gr-ntsc-rc.git
cd gr-ntsc-rc
git fetch origin pull/6/head:pr6
git checkout pr6

# Clone Dragon FPV Decoder
cd ~/
git clone https://github.com/lukeswitz/dragon-fpv-decoder.git
cd dragon-fpv-decoder
chmod +x fpv_scanner.sh
```

## Verify ANTSDR Connection
```bash
ping 192.168.1.10
uhd_find_devices
```

## Usage
```bash
./fpv_scanner.sh
```

### Commands

- `scan` - Auto-scan all 64 FPV channels
- `stop` - Stop scanning
- `set <CH>` - Tune to specific channel (e.g., `set R6`, `set A8`)
- `freq <MHz>` - Tune to exact frequency (e.g., `freq 5843`)
- `list` - Show all available channels
- `dwell <SEC>` - Set scan dwell time (default: 3s)
- `log` - View scan history
- `quit` - Exit

### Supported Channels

- **Raceband**: R1-R8 (5658-5917 MHz)
- **Band A**: A1-A8 (5725-5865 MHz)
- **Band B**: B1-B8 (5733-5866 MHz)
- **Band E**: E1-E8 (5645-5945 MHz)
- **Fatshark**: F1-F8 (5740-5880 MHz)
- **ImmersionRC**: IMD1-IMD6 (5658-5843 MHz)
- **DJI**: D1-D8 (5660-5914 MHz)
- **Low Band**: L1-L8 (5362-5621 MHz)

**Total: 64 channels across 8 bands**

## Features

- Real-time NTSC video decoding with SDL display
- Interactive channel scanning
- Manual frequency tuning
- Automatic channel switching
- Scan logging and history
- Clean window management

## Troubleshooting

**No video window:**
```bash
export DISPLAY=:0
```

**ANTSDR not detected:**
```bash
ping 192.168.1.10
uhd_find_devices
```

**Static/No Signal:**
- Verify FPV transmitter is powered on
- Check antenna connected to ANTSDR RX2 port
- Confirm frequency matches transmitter channel
- Try increasing gain in scanner

## Credits

- gr-ntsc-rc: https://github.com/lscardoso/gr-ntsc-rc
- ANTSDR: MicroPhase Technology
