#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0

import os
import sys

BLOCKS = " ▁▂▃▄▅▆▇█"


def supports_color():
    if os.environ.get('NO_COLOR'):
        return False
    if os.environ.get('FORCE_COLOR'):
        return True
    return sys.stdout.isatty()


def _ramp(level):
    if level < 0.0:
        level = 0.0
    elif level > 1.0:
        level = 1.0
    stops = ((40, 60, 100), (0, 110, 200), (0, 200, 150),
             (210, 210, 0), (240, 110, 0), (255, 40, 40))
    x = level * (len(stops) - 1)
    i = int(x)
    if i >= len(stops) - 1:
        return stops[-1]
    f = x - i
    a = stops[i]
    b = stops[i + 1]
    return (int(a[0] + (b[0] - a[0]) * f),
            int(a[1] + (b[1] - a[1]) * f),
            int(a[2] + (b[2] - a[2]) * f))


def _color(ch, level):
    r, g, b = _ramp(level)
    return "\x1b[38;2;%d;%d;%dm%s\x1b[0m" % (r, g, b, ch)


def render(col_db, lo_hz, hi_hz, floor_db, height=16,
           dmin=None, dmax=None, color=True, title=None):
    w = len(col_db)
    if w == 0:
        return "(no spectrum data)"

    vals = [v for v in col_db if v is not None and v > -200.0]
    if dmin is None:
        dmin = (floor_db - 2.0) if floor_db is not None else (min(vals) if vals else -80.0)
    if dmax is None:
        dmax = (max(vals) + 3.0) if vals else 0.0
    if dmax - dmin < 6.0:
        dmax = dmin + 6.0
    span = dmax - dmin

    use_color = color and supports_color()
    levels = []
    eighths = []
    for v in col_db:
        if v is None or v <= -200.0:
            levels.append(0.0)
            eighths.append(0)
            continue
        lv = (v - dmin) / span
        if lv < 0.0:
            lv = 0.0
        elif lv > 1.0:
            lv = 1.0
        levels.append(lv)
        eighths.append(int(round(lv * height * 8)))

    floor_row = None
    if floor_db is not None:
        floor_row = int(round((floor_db - dmin) / span * height))

    out = []
    if title:
        out.append(title)
    for row in range(height, 0, -1):
        base = (row - 1) * 8
        cells = []
        for c in range(w):
            e = eighths[c] - base
            if e >= 8:
                ch = BLOCKS[8]
            elif e <= 0:
                ch = ' '
            else:
                ch = BLOCKS[e]
            if use_color and ch != ' ':
                ch = _color(ch, levels[c])
            cells.append(ch)
        if row == height or row == 1 or row == (height + 1) // 2:
            label = "%5.0f " % (dmin + span * row / height)
        elif floor_row is not None and row == floor_row:
            label = " ~flr "
        else:
            label = "      "
        out.append(label + ''.join(cells))

    axis = [' '] * w
    labels = [' '] * (w + 8)
    span_hz = hi_hz - lo_hz
    for t in range(6):
        c = int(round(t * (w - 1) / 5.0))
        if 0 <= c < w:
            axis[c] = '|'
            s = "%.0f" % ((lo_hz + (c + 0.5) / w * span_hz) / 1e6)
            pos = 6 + c - len(s) // 2
            if pos < 0:
                pos = 0
            if pos + len(s) > len(labels):
                pos = len(labels) - len(s)
            for k, cc in enumerate(s):
                labels[pos + k] = cc
    out.append("      " + ''.join(axis))
    out.append(''.join(labels).rstrip())
    out.append("      dBFS vs MHz  (floor %.0f, range %.0f..%.0f)"
               % (floor_db if floor_db is not None else 0.0, dmin, dmax))
    return '\n'.join(out)
