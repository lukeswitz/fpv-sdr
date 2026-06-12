#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0

import os
import sys
import time
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fpv_viewer import viewer

HELP = """commands (type and Enter):
  contrast <x>   live  - lower if frame decodes only partway (try 0.4 - 1.0)
  freq <MHz>     live  - retune (e.g. freq 5728)
  gain <dB>      restart
  rate <Msps>    restart - 10 = steady (no USB overflow), 20 = wider but may break
  rotate <deg>   restart - 0 90 180 270
  help | quit
"""


def freq_hz(s):
    f = float(s)
    return f if f > 1e6 else f * 1e6


def main():
    ap = argparse.ArgumentParser(description="Interactive FPV tuner")
    ap.add_argument('--sdr', default='hackrf')
    ap.add_argument('--gain', type=float, default=40.0)
    ap.add_argument('--rate', type=float, default=10e6)
    ap.add_argument('--freq', type=float, default=5725e6)
    ap.add_argument('--contrast', type=float, default=0.8)
    ap.add_argument('--rotate', type=int, default=0)
    ap.add_argument('--dev-args', default='')
    a = ap.parse_args()

    p = {'gain': a.gain, 'rate': a.rate, 'freq': a.freq,
         'contrast': a.contrast, 'rotate': a.rotate}
    tb = [None]

    def start():
        v = viewer(a.sdr, p['rate'], p['freq'], p['gain'], a.dev_args, None,
                   live=True, rotate=p['rotate'], contrast=p['contrast'], oversample=1)
        v.start()
        tb[0] = v

    def restart():
        if tb[0] is not None:
            tb[0].stop()
            tb[0].wait()
            tb[0] = None
        time.sleep(0.6)
        start()

    def show():
        sys.stderr.write("[tune] rate=%gM gain=%g freq=%.0fMHz contrast=%g rotate=%d\n"
                         % (p['rate'] / 1e6, p['gain'], p['freq'] / 1e6, p['contrast'], p['rotate']))

    start()
    sys.stderr.write(HELP)
    show()

    for line in sys.stdin:
        parts = line.split()
        if not parts:
            continue
        c = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else None
        try:
            if c in ('q', 'quit', 'exit'):
                break
            elif c in ('h', 'help', '?'):
                sys.stderr.write(HELP)
                continue
            elif c == 'contrast' and arg:
                p['contrast'] = float(arg)
                tb[0].set_contrast(p['contrast'])
            elif c == 'freq' and arg:
                p['freq'] = freq_hz(arg)
                tb[0].retune(p['freq'])
            elif c == 'gain' and arg:
                p['gain'] = float(arg)
                restart()
            elif c in ('rate', 'samp', 'samprate') and arg:
                p['rate'] = float(arg) * 1e6 if float(arg) < 1e4 else float(arg)
                restart()
            elif c == 'rotate' and arg:
                p['rotate'] = int(arg)
                restart()
            else:
                sys.stderr.write("?? type 'help'\n")
                continue
        except (ValueError, IndexError, RuntimeError) as e:
            sys.stderr.write("err: %s\n" % e)
            continue
        show()

    if tb[0] is not None:
        tb[0].stop()
        tb[0].wait()


if __name__ == '__main__':
    main()
