from kivy.uix.widget import Widget
from kivy.properties import ListProperty
from kivy.metrics import dp
from kivy.graphics import Color, Line, Rectangle
from kivy.core.text import Label as CoreLabel


class RoastPlot(Widget):
    x_series = ListProperty([])
    bt_series = ListProperty([])
    set_series = ListProperty([])

    W = 1200.0
    y_min = 0
    y_max = 300

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bind(pos=self._redraw, size=self._redraw)
        self.bind(x_series=self._redraw, bt_series=self._redraw, set_series=self._redraw)

    def _draw_text(self, text, x, y, font_size=12, color=(1, 1, 1, 0.9)):
        lbl = CoreLabel(text=text, font_size=font_size, color=color)
        lbl.refresh()
        Rectangle(texture=lbl.texture, pos=(x, y), size=lbl.texture.size)

    def _redraw(self, *args):
        self.canvas.clear()
        with self.canvas:
            Color(0.07, 0.08, 0.10, 1)
            Rectangle(pos=self.pos, size=self.size)

            pad_l = dp(48)
            pad_r = dp(10)
            pad_t = dp(10)
            pad_b = dp(44)

            px = self.x + pad_l
            py = self.y + pad_b
            pw = self.width - (pad_l + pad_r)
            ph = self.height - (pad_b + pad_t)

            Color(0.06, 0.07, 0.09, 1)
            Rectangle(pos=(px, py), size=(pw, ph))

            Color(0.24, 0.28, 0.36, 1)
            Line(rectangle=(px, py, pw, ph), width=1)

            minor = (0.25, 0.28, 0.36, 0.20)
            major = (0.50, 0.58, 0.74, 0.55)

            y_major_lbl = (0.92, 0.94, 0.98, 0.95)
            y_minor_lbl = (0.78, 0.82, 0.88, 0.85)
            x_minor_lbl = (0.78, 0.82, 0.88, 0.90)
            x_major_lbl = (0.94, 0.96, 0.99, 0.95)

            def xf(sec):
                sec = max(0.0, min(self.W, float(sec)))
                return px + pw * (sec / self.W)

            def yf(v):
                v = max(self.y_min, min(self.y_max, float(v)))
                return py + ph * ((v - self.y_min) / (self.y_max - self.y_min))

            # X grid
            Color(*minor)
            for sec in range(0, int(self.W) + 1, 60):
                xg = xf(sec)
                Line(points=[xg, py, xg, py + ph], width=1)

            Color(*major)
            for sec in range(0, int(self.W) + 1, 300):
                xg = xf(sec)
                Line(points=[xg, py, xg, py + ph], width=1.2)

            # Y grid
            Color(*minor)
            for t in range(0, 301, 50):
                yg = yf(t)
                Line(points=[px, yg, px + pw, yg], width=1)

            Color(*major)
            for t in range(0, 301, 100):
                yg = yf(t)
                Line(points=[px, yg, px + pw, yg], width=1.2)

            # Y labels
            for t in range(0, 301, 50):
                yg = yf(t)
                col = y_major_lbl if (t % 100 == 0) else y_minor_lbl
                self._draw_text(f"{t}°C", self.x + dp(6), yg - dp(8), font_size=12, color=col)

            # X labels
            x_label_y = self.y + dp(8)
            for sec in range(0, int(self.W) + 1, 60):
                xg = xf(sec)
                col = x_major_lbl if (sec % 300 == 0) else x_minor_lbl
                self._draw_text(f"{sec//60}m", xg - dp(10), x_label_y, font_size=12, color=col)

            # Legend
            legend_y = self.y + dp(26)
            legend_x = px + pw / 2 - dp(70)

            Color(1.00, 0.38, 0.38, 0.95)
            Rectangle(pos=(legend_x, legend_y), size=(dp(10), dp(10)))
            self._draw_text("SET", legend_x + dp(14), legend_y - dp(2), font_size=12, color=(0.9, 0.92, 0.95, 0.95))

            Color(0.25, 0.70, 1.00, 1.0)
            Rectangle(pos=(legend_x + dp(56), legend_y), size=(dp(10), dp(10)))
            self._draw_text("BT", legend_x + dp(70), legend_y - dp(2), font_size=12, color=(0.9, 0.92, 0.95, 0.95))

            # plots
            if self.x_series and len(self.x_series) >= 2:
                if self.set_series and len(self.set_series) == len(self.x_series):
                    Color(1.00, 0.38, 0.38, 0.95)
                    pts = []
                    for sx, sy in zip(self.x_series, self.set_series):
                        pts.extend([xf(sx), yf(sy)])
                    Line(points=pts, width=1.2)

                if self.bt_series and len(self.bt_series) == len(self.x_series):
                    Color(0.25, 0.70, 1.00, 1.0)
                    pts = []
                    for bx, by in zip(self.x_series, self.bt_series):
                        pts.extend([xf(bx), yf(by)])
                    Line(points=pts, width=1.4)
