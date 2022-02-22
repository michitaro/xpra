# This file is part of Xpra.
# Copyright (C) 2017-2022 Antoine Martin <antoine@xpra.org>
# Xpra is released under the terms of the GNU GPL v2, or, at your option, any
# later version. See the file COPYING for details.

import sys
from gi.repository import GLib, Gtk, Gdk

from xpra.client.gl.gl_window_backing_base import GLWindowBackingBase
from xpra.platform.gl_context import GLContext
from xpra.log import Logger

if not GLContext:
    raise ImportError("no OpenGL context implementation for %s" % sys.platform)

log = Logger("opengl", "paint")


class GLDrawingArea(GLWindowBackingBase):

    def __init__(self, wid : int, window_alpha : bool, pixel_depth : int=0):
        self.on_realize_cb = []
        super().__init__(wid, window_alpha, pixel_depth)

    def __repr__(self):
        return "GLDrawingArea(%s, %s, %s)" % (self.wid, self.size, self.pixel_format)

    def idle_add(self, *args, **kwargs):
        GLib.idle_add(*args, **kwargs)

    def init_gl_config(self):
        self.context = GLContext(self._alpha_enabled)  #pylint: disable=not-callable
        self.window_context = None

    def is_double_buffered(self):
        return self.context.is_double_buffered()

    def init_backing(self):
        da = Gtk.DrawingArea()
        da.connect_after("realize", self.on_realize)
        #da.connect('configure_event', self.on_configure_event)
        #da.connect('draw', self.on_draw)
        #double-buffering is enabled by default anyway, so this is redundant:
        #da.set_double_buffered(True)
        da.set_size_request(*self.size)
        da.set_events(da.get_events() | Gdk.EventMask.POINTER_MOTION_MASK | Gdk.EventMask.POINTER_MOTION_HINT_MASK)
        da.show()
        self._backing = da

    def on_realize(self, *args):
        onrcb = self.on_realize_cb
        log("GLDrawingArea.on_realize%s callbacks=%s", args, onrcb)
        self.on_realize_cb = []
        gl_context = self.gl_context()
        with gl_context:
            for x, args in onrcb:
                try:
                    x(gl_context, *args)
                except Exception:
                    log.error("Error calling realize callback %s", x, exc_info=True)

    def with_gl_context(self, cb, *args):
        da = self._backing
        if da and da.get_mapped():
            gl_context = self.gl_context()
            if gl_context:
                with gl_context:
                    cb(gl_context, *args)
            else:
                cb(None, *args)
        else:
            log("GLDrawingArea.with_gl_context delayed: %s%s", cb, args)
            self.on_realize_cb.append((cb, args))


    def get_bit_depth(self, pixel_depth=0):
        return pixel_depth or self.context.get_bit_depth() or 24

    def gl_context(self):
        b = self._backing
        if not b:
            return None
        gdk_window = b.get_window()
        if not gdk_window:
            raise Exception("backing %s does not have a gdk window!" % b)
        self.window_context = self.context.get_paint_context(gdk_window)
        return self.window_context

    def do_gl_show(self, rect_count):
        if self.is_double_buffered():
            # Show the backbuffer on screen
            log("%s.do_gl_show(%s) swapping buffers now", rect_count, self)
            self.window_context.swap_buffers()
        else:
            #glFlush was enough
            pass

    def close_gl_config(self):
        c = self.context
        if c:
            self.context = None
            c.destroy()

    def draw_fbo(self, _context):
        w, h = self.size
        with self.gl_context():
            self.gl_init()
            self.present_fbo(0, 0, w, h)
