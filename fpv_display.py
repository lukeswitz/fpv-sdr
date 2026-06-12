#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0

import os
import numpy as np
from gnuradio import gr
from PIL import Image


class frame_sink(gr.sync_block):
    def __init__(self, width=360, height=240, out_path=None, every=15):
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

    def get_latest(self):
        return self._latest

    def _on_frame(self):
        img = np.clip(self._frame, 0, 255).astype(np.uint8).reshape(self.h, self.w)
        self._latest = img
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
