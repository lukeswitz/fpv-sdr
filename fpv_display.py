#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0

import os
import sys
import time
import threading
import subprocess
import numpy as np
from gnuradio import gr
from PIL import Image


class frame_sink(gr.sync_block):
    def __init__(self, width=360, height=240, out_path=None, every=15,
                 record_path=None, record_fps=30, live=False, title='FPV-SDR',
                 rotate=0):
        gr.sync_block.__init__(self, name='fpv_frame_sink',
                               in_sig=[np.int16], out_sig=[])
        self.w = int(width)
        self.h = int(height)
        self.n = self.w * self.h
        self.out_path = out_path
        self.every = max(1, int(every))
        self._buf = np.zeros(self.n, dtype=np.int16)
        self._fill = 0
        self.frame_count = 0
        self.closed = False

        self.rotate = int(rotate) % 360
        self._rot_k = {0: 0, 90: 3, 180: 2, 270: 1}.get(self.rotate, 0)
        if self.rotate in (90, 270):
            ow, oh = self.h, self.w
        else:
            ow, oh = self.w, self.h

        self._live = None
        self._rec = None
        self._latest = None
        self._lock = threading.Lock()
        self._run = True
        self._writer = None

        size = '%dx%d' % (ow, oh)
        if live:
            self._live = subprocess.Popen(
                ['ffplay', '-hide_banner', '-loglevel', 'error', '-nostats', '-autoexit',
                 '-fflags', 'nobuffer', '-flags', 'low_delay',
                 '-f', 'rawvideo', '-pixel_format', 'gray', '-video_size', size,
                 '-framerate', '30', '-window_title', title,
                 '-x', str(ow * 2), '-y', str(oh * 2), '-i', '-'],
                stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
            sys.stderr.write("[fpv] live window (ffplay)\n")
            self._writer = threading.Thread(target=self._live_writer, daemon=True)
            self._writer.start()
        if record_path:
            self._rec = subprocess.Popen(
                ['ffmpeg', '-y', '-loglevel', 'error', '-nostats',
                 '-f', 'rawvideo', '-pix_fmt', 'gray', '-s', size,
                 '-r', str(record_fps), '-i', '-', '-pix_fmt', 'yuv420p', record_path],
                stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
            sys.stderr.write("[fpv] recording to %s\n" % record_path)

    def _live_writer(self):
        while self._run:
            with self._lock:
                data = self._latest
                self._latest = None
            if data is None:
                time.sleep(0.005)
                continue
            try:
                self._live.stdin.write(data)
                self._live.stdin.flush()
            except (BrokenPipeError, ValueError, OSError):
                self.closed = True
                return

    def stop(self):
        self._run = False
        if self._writer is not None:
            self._writer.join(timeout=1)
        for p in (self._live, self._rec):
            if p is None:
                continue
            if p.stdin is not None:
                try:
                    p.stdin.close()
                except (BrokenPipeError, OSError):
                    pass
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill()
        self._live = None
        self._rec = None
        return True

    def _emit(self, frame):
        if self._rot_k:
            img = np.ascontiguousarray(np.rot90(frame, self._rot_k))
        else:
            img = frame
        data = img.tobytes()
        if self._live is not None:
            with self._lock:
                self._latest = data
        if self._rec is not None:
            try:
                self._rec.stdin.write(data)
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
            self._buf[self._fill:self._fill + take] = x[i:i + take]
            self._fill += take
            i += take
            if self._fill >= self.n:
                frame = np.clip(self._buf, 0, 255).astype(np.uint8).reshape(self.h, self.w)
                self._emit(frame)
                self._fill = 0
        return total
