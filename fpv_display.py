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
                 record_path=None, record_fps=30, live=False, title='Dragon FPV'):
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
        self._pipes = []

        size = '%dx%d' % (self.w, self.h)
        if live:
            self._pipes.append(subprocess.Popen(
                ['ffplay', '-hide_banner', '-loglevel', 'error', '-autoexit',
                 '-f', 'rawvideo', '-pixel_format', 'gray', '-video_size', size,
                 '-framerate', '30', '-window_title', title,
                 '-x', str(self.w * 2), '-y', str(self.h * 2), '-i', '-'],
                stdin=subprocess.PIPE))
            sys.stderr.write("[fpv] live window (ffplay)\n")
        if record_path:
            self._pipes.append(subprocess.Popen(
                ['ffmpeg', '-y', '-loglevel', 'error',
                 '-f', 'rawvideo', '-pix_fmt', 'gray', '-s', size,
                 '-r', str(record_fps), '-i', '-', '-pix_fmt', 'yuv420p', record_path],
                stdin=subprocess.PIPE))
            sys.stderr.write("[fpv] recording to %s\n" % record_path)

    def get_latest(self):
        return self._latest

    def stop(self):
        pipes = self._pipes
        self._pipes = []
        for p in pipes:
            if p.stdin is not None:
                p.stdin.close()
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill()
        return True

    def _on_frame(self):
        img = np.clip(self._frame, 0, 255).astype(np.uint8).reshape(self.h, self.w)
        self._latest = img
        if self._pipes:
            data = img.tobytes()
            alive = []
            for p in self._pipes:
                try:
                    p.stdin.write(data)
                except (BrokenPipeError, ValueError):
                    continue
                alive.append(p)
            self._pipes = alive
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


class decoder_sink(gr.sync_block):
    def __init__(self, width=360, height=240, out_path=None, every=15,
                 record_path=None, record_fps=30, live=False, title='Dragon FPV'):
        gr.sync_block.__init__(self, name='fpv_decoder_sink',
                               in_sig=[np.float32, np.float32, np.float32], out_sig=[])
        self.w = int(width)
        self.h = int(height)
        self.n = self.w * self.h
        self.out_path = out_path
        self.every = max(1, int(every))
        self._frame = np.full((self.h, self.w), 16, dtype=np.uint8)
        self._since = 0
        self._last_y = 0
        self.frame_count = 0
        self.closed = False

        self._live = None
        self._rec = None
        self._latest = None
        self._lock = threading.Lock()
        self._run = True
        self._writer = None

        size = '%dx%d' % (self.w, self.h)
        if live:
            self._live = subprocess.Popen(
                ['ffplay', '-hide_banner', '-loglevel', 'error', '-autoexit',
                 '-fflags', 'nobuffer', '-flags', 'low_delay',
                 '-f', 'rawvideo', '-pixel_format', 'gray', '-video_size', size,
                 '-framerate', '30', '-window_title', title,
                 '-x', str(self.w * 2), '-y', str(self.h * 2), '-i', '-'],
                stdin=subprocess.PIPE)
            sys.stderr.write("[fpv] live window (ffplay)\n")
            self._writer = threading.Thread(target=self._live_writer, daemon=True)
            self._writer.start()
        if record_path:
            self._rec = subprocess.Popen(
                ['ffmpeg', '-y', '-loglevel', 'error',
                 '-f', 'rawvideo', '-pix_fmt', 'gray', '-s', size,
                 '-r', str(record_fps), '-i', '-', '-pix_fmt', 'yuv420p', record_path],
                stdin=subprocess.PIPE)
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

    def _emit(self):
        data = self._frame.tobytes()
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
                Image.fromarray(self._frame, mode='L').save(tmp, format='PNG')
                os.replace(tmp, self.out_path)
            except OSError:
                pass

    def work(self, input_items, output_items):
        xi = input_items[0].astype(np.int32)
        yi = input_items[1].astype(np.int32)
        lm = input_items[2]
        valid = (xi >= 0) & (xi < self.w) & (yi >= 0) & (yi < self.h) & (lm >= 0)
        if valid.any():
            xv = xi[valid]
            yv = yi[valid]
            lv = np.clip(lm[valid], 0, 255).astype(np.uint8)
            flat = self._frame.reshape(-1)
            wraps = list(np.nonzero((yv[1:] <= 2) & (yv[:-1] >= self.h - 40))[0] + 1)
            if self._last_y >= self.h - 40 and yv[0] <= 2:
                wraps.insert(0, 0)
            prev = 0
            for w in wraps:
                if w > prev:
                    flat[yv[prev:w] * self.w + xv[prev:w]] = lv[prev:w]
                self._emit()
                self._since = 0
                prev = w
            flat[yv[prev:] * self.w + xv[prev:]] = lv[prev:]
            self._since += len(xv) - prev
            if self._since >= 2 * self.n:
                self._emit()
                self._since = 0
            self._last_y = int(yv[-1])
        return len(input_items[0])
