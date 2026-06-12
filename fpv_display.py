#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0

import os
import sys
import subprocess
import numpy as np
from gnuradio import gr
from PIL import Image


class frame_sink(gr.sync_block):
    def __init__(self, width=360, height=240, out_path=None, every=15,
                 record_path=None, record_fps=30):
        gr.sync_block.__init__(self, name='fpv_frame_sink',
                               in_sig=[np.int16], out_sig=[])
        self.w = int(width)
        self.h = int(height)
        self.n = self.w * self.h
        self.out_path = out_path
        self.every = max(1, int(every))
        self._frame = np.zeros(self.n, dtype=np.int16)
        self._fill = 0
        self.frame_count = 0
        self._latest = None
        self._rec = None
        if record_path:
            self._rec = subprocess.Popen(
                ['ffmpeg', '-y', '-loglevel', 'error',
                 '-f', 'rawvideo', '-pix_fmt', 'gray',
                 '-s', '%dx%d' % (self.w, self.h), '-r', str(record_fps), '-i', '-',
                 '-pix_fmt', 'yuv420p', record_path],
                stdin=subprocess.PIPE)
            sys.stderr.write("[fpv] recording to %s\n" % record_path)

    def get_latest(self):
        return self._latest

    def stop(self):
        rec = self._rec
        self._rec = None
        if rec is not None and rec.stdin is not None:
            rec.stdin.close()
            try:
                rec.wait(timeout=5)
            except subprocess.TimeoutExpired:
                rec.kill()
        return True

    def _on_frame(self):
        img = np.clip(self._frame, 0, 255).astype(np.uint8).reshape(self.h, self.w)
        self._latest = img
        if self._rec is not None:
            try:
                self._rec.stdin.write(img.tobytes())
            except (BrokenPipeError, ValueError):
                self._rec = None
        self.frame_count += 1
        if self.out_path and self.frame_count % self.every == 0:
            tmp = self.out_path + '.tmp'
            try:
                Image.fromarray(img, mode='L').save(tmp, format='PNG')
                os.replace(tmp, self.out_path)
            except OSError:
                pass

    def work(self, input_items, output_items):
        x = input_items[0]
        total = len(x)
        i = 0
        while i < total:
            take = min(self.n - self._fill, total - i)
            self._frame[self._fill:self._fill + take] = x[i:i + take]
            self._fill += take
            i += take
            if self._fill >= self.n:
                self._on_frame()
                self._fill = 0
        return total
