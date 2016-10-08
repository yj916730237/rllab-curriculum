"""
2D rendering framework
"""
from __future__ import division
import os
import six
import sys

if "Apple" in sys.version:
    if 'DYLD_FALLBACK_LIBRARY_PATH' in os.environ:
        os.environ['DYLD_FALLBACK_LIBRARY_PATH'] += ':/usr/lib'
        # (JDS 2016/04/15): avoid bug on Anaconda 2.3.0 / Yosemite

import math
import numpy as np
import cv2
import functools
import numba

RAD2DEG = 57.29577951308232

ID_TRANS = np.eye(3)


class Context(object):
    def __init__(self):
        self.transforms = []

    def enable(self, transform):
        self.transforms.append(transform)

    def disable(self, transform):
        self.transforms.remove(transform)

    def render(self, img, geom):
        for attr in geom.attrs:
            self.enable(attr)

        transform_mat = ID_TRANS

        r, g, b = (0, 0, 0)

        for t in self.transforms:
            if isinstance(t, Transform):
                mat = t.to_matrix()
                transform_mat = mat @ transform_mat
            elif isinstance(t, Color):
                r, g, b = t.vec4[:-1]
            else:
                raise NotImplementedError

        color = (r * 255., g * 255., b * 255.)

        if isinstance(geom, FilledPolygon):
            rot_part = transform_mat[:2, :2].T
            trans_part = transform_mat[:2, -1]
            rot_v = geom.v.dot(rot_part)
            points = rot_v + trans_part
            points = points.astype(np.int)
            cv2.fillConvexPoly(img, points, color)
        else:
            import ipdb;
            ipdb.set_trace()

        for attr in geom.attrs:
            self.disable(attr)

    def update_transform(self):
        transforms = [x.to_matrix() for x in self.transforms if isinstance(x, Transform)]
        self._transform_mat = functools.reduce(np.dot, transforms, np.eye(3))

    def transform_point(self, pt):
        return (self._transform_mat @ np.append(pt, 1))[:-1]

    def get_color(self):
        colors = [x.vec4 for x in self.transforms if isinstance(x, Color)]
        if len(colors) > 0:
            return tuple((np.asarray(colors[-1]) * 255).astype(np.float)[:-1])
        else:
            return (0., 0., 0.)  # np.asarray((0, 0, 0))


class Viewer(object):
    def __init__(self, width, height, display=None, mode='human'):
        # display = get_display(display)
        assert display is None
        assert mode == 'rgb_array'

        self.width = width
        self.height = height
        self.mode = mode

        # if self.mode == 'human':
        #     self.window = pyglet.window.Window(width=width, height=height, display=display)
        #     self.window.on_close = self.window_closed_by_user

        self.geoms = []
        self.onetime_geoms = []
        self.transform = Transform()

        self.context = Context()

        # glEnable(GL_BLEND)
        # glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

    def close(self):
        pass
        # if self.mode == 'human':
        #     self.window.close()

    def window_closed_by_user(self):
        self.close()

    def set_bounds(self, left, right, bottom, top):
        assert right > left and top > bottom
        scalex = self.width / (right - left)
        scaley = self.height / (top - bottom)
        self.transform = Transform(
            translation=(-left * scalex, -bottom * scalex),
            scale=(scalex, scaley))

    def add_geom(self, geom):
        self.geoms.append(geom)

    def add_onetime(self, geom):
        self.onetime_geoms.append(geom)

    def render(self, return_rgb_array=False):
        img = np.zeros((self.height, self.width, 3), np.uint8) - 1
        # glClearColor(1,1,1,1)
        # if self.mode == 'human':
        #     self.window.clear()
        #     self.window.switch_to()
        #     self.window.dispatch_events()
        self.context.enable(self.transform)
        for geom in self.geoms:
            self.context.render(img, geom)
            # geom.render(img, self.context)
        for geom in self.onetime_geoms:
            self.context.render(img, geom)
            # geom.render(img, self.context)
        self.context.disable(self.transform)
        # self.transform.disable(self.context)
        # arr = None
        # if return_rgb_array:
        #     buffer = pyglet.image.get_buffer_manager().get_color_buffer()
        #     image_data = buffer.get_image_data()
        #     arr = np.fromstring(image_data.data, dtype=np.uint8, sep='')
        #     # In https://github.com/openai/gym-http-api/issues/2, we
        #     # discovered that someone using Xmonad on Arch was having
        #     # a window of size 598 x 398, though a 600 x 400 window
        #     # was requested. (Guess Xmonad was preserving a pixel for
        #     # the boundary.) So we use the buffer height/width rather
        #     # than the requested one.
        #     arr = arr.reshape(buffer.height, buffer.width, 4)
        #     arr = arr[::-1,:,0:3]
        # if self.mode == 'human':
        #     self.window.flip()
        # self.onetime_geoms = []
        return img  # arr

    # Convenience
    def draw_circle(self, radius=10, res=30, filled=True, **attrs):
        geom = make_circle(radius=radius, res=res, filled=filled)
        _add_attrs(geom, attrs)
        self.add_onetime(geom)
        return geom

    def draw_polygon(self, v, filled=True, **attrs):
        geom = make_polygon(v=v, filled=filled)
        _add_attrs(geom, attrs)
        self.add_onetime(geom)
        return geom

    def draw_polyline(self, v, **attrs):
        geom = make_polyline(v=v)
        _add_attrs(geom, attrs)
        self.add_onetime(geom)
        return geom

    def draw_line(self, start, end, **attrs):
        geom = Line(start, end)
        _add_attrs(geom, attrs)
        self.add_onetime(geom)
        return geom

        # def get_array(self):
        #     if self.mode == 'human':
        #         self.window.flip()
        #     image_data = pyglet.image.get_buffer_manager().get_color_buffer().get_image_data()
        #     if self.mode == 'human':
        #         self.window.flip()
        #     arr = np.fromstring(image_data.data, dtype=np.uint8, sep='')
        #     arr = arr.reshape(self.height, self.width, 4)
        #     return arr[::-1,:,0:3]


def _add_attrs(geom, attrs):
    if "color" in attrs:
        geom.set_color(*attrs["color"])
    if "linewidth" in attrs:
        geom.set_linewidth(attrs["linewidth"])


class Geom(object):
    def __init__(self):
        self._color = Color((0, 0, 0, 1.0))
        self.attrs = [self._color]

    def render(self):
        for attr in reversed(self.attrs):
            attr.enable()
        self.render1()
        for attr in self.attrs:
            attr.disable()

    def render1(self):
        raise NotImplementedError

    def add_attr(self, attr):
        self.attrs.append(attr)

    def set_color(self, r, g, b):
        self._color.vec4 = (r, g, b, 1)


class Attr(object):
    def enable(self):
        raise NotImplementedError

    def disable(self):
        pass


class Transform(Attr):
    def __init__(self, translation=(0.0, 0.0), rotation=0.0, scale=(1, 1)):
        self.set_translation(*translation)
        self.set_rotation(rotation)
        self.set_scale(*scale)
        self._cached_matrix = None

    def set_translation(self, newx, newy):
        self.translation = (float(newx), float(newy))
        self._cached_matrix = None

    def set_rotation(self, new):
        self.rotation = float(new)
        self._cached_matrix = None

    def set_scale(self, newx, newy):
        self.scale = (float(newx), float(newy))
        self._cached_matrix = None

    def to_matrix(self):
        if self._cached_matrix is None:
            sx, sy = self.scale
            tx, ty = self.translation
            cosrot = np.cos(self.rotation)
            sinrot = np.sin(self.rotation)

            sxcos = sx * cosrot
            sxsin = sx * sinrot
            sycos = sy * cosrot
            sysin = sy * sinrot

            self._cached_matrix = np.array([
                [sxcos, - sxsin, tx * sxcos - ty * sxsin],
                [sysin, sycos, tx * sysin + ty * sycos],
                [0, 0, 1]
            ])
            # translate_mat = np.array([
            #     [1, 0, self.translation[0]],
            #     [0, 1, self.translation[1]],
            #     [0, 0, 1]
            # ])
            #
            # rotate_mat = np.array([
            #     [cosrot, -sinrot, 0],
            #     [sinrot, cosrot, 0],
            #     [0, 0, 1],
            # ])
            # scale_mat = np.array([
            #     [self.scale[0], 0, 0],
            #     [0, self.scale[1], 0],
            #     [0, 0, 1]
            # ])
            # self._cached_matrix = scale_mat @ rotate_mat @ translate_mat
        return self._cached_matrix


class Color(Attr):
    def __init__(self, vec4):
        self.vec4 = vec4

        # def enable(self):
        #     glColor4f(*self.vec4)


class LineStyle(Attr):
    def __init__(self, style):
        self.style = style

        # def enable(self):
        #     glEnable(GL_LINE_STIPPLE)
        #     glLineStipple(1, self.style)
        #
        # def disable(self):
        #     glDisable(GL_LINE_STIPPLE)


class LineWidth(Attr):
    def __init__(self, stroke):
        self.stroke = stroke

        # def enable(self):
        #     glLineWidth(self.stroke)


class Point(Geom):
    def __init__(self):
        Geom.__init__(self)

        # def render1(self):
        #     glBegin(GL_POINTS)  # draw point
        #     glVertex3f(0.0, 0.0, 0.0)
        #     glEnd()


class FilledPolygon(Geom):
    def __init__(self, v):
        Geom.__init__(self)
        self.v = np.asarray(v)

        # def render1(self):
        #     if len(self.v) == 4:
        #         glBegin(GL_QUADS)
        #     elif len(self.v) > 4:
        #         glBegin(GL_POLYGON)
        #     else:
        #         glBegin(GL_TRIANGLES)
        #     for p in self.v:
        #         glVertex3f(p[0], p[1], 0)  # draw each vertex
        #     glEnd()


def make_circle(radius=10, res=30, filled=True):
    points = []
    for i in range(res):
        ang = 2 * math.pi * i / res
        points.append((math.cos(ang) * radius, math.sin(ang) * radius))
    if filled:
        return FilledPolygon(points)
    else:
        return PolyLine(points, True)


def make_polygon(v, filled=True):
    if filled:
        return FilledPolygon(v)
    else:
        return PolyLine(v, True)


def make_polyline(v):
    return PolyLine(v, False)


def make_capsule(length, width):
    l, r, t, b = 0, length, width / 2, -width / 2
    box = make_polygon([(l, b), (l, t), (r, t), (r, b)])
    circ0 = make_circle(width / 2)
    circ1 = make_circle(width / 2)
    circ1.add_attr(Transform(translation=(length, 0)))
    geom = Compound([box, circ0, circ1])
    return geom


class Compound(Geom):
    def __init__(self, gs):
        Geom.__init__(self)
        self.gs = gs
        for g in self.gs:
            g.attrs = [a for a in g.attrs if not isinstance(a, Color)]

    def render1(self):
        for g in self.gs:
            g.render()


class PolyLine(Geom):
    def __init__(self, v, close):
        Geom.__init__(self)
        self.v = v
        self.close = close
        self.linewidth = LineWidth(1)
        self.add_attr(self.linewidth)

    # def render1(self):
    #     glBegin(GL_LINE_LOOP if self.close else GL_LINE_STRIP)
    #     for p in self.v:
    #         glVertex3f(p[0], p[1], 0)  # draw each vertex
    #     glEnd()

    def set_linewidth(self, x):
        self.linewidth.stroke = x


class Line(Geom):
    def __init__(self, start=(0.0, 0.0), end=(0.0, 0.0)):
        Geom.__init__(self)
        self.start = start
        self.end = end
        self.linewidth = LineWidth(1)
        self.add_attr(self.linewidth)

        # def render1(self):
        #     glBegin(GL_LINES)
        #     glVertex2f(*self.start)
        #     glVertex2f(*self.end)
        #     glEnd()
