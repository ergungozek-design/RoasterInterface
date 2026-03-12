from kivy.uix.widget import Widget
from kivy.properties import ListProperty, NumericProperty
from kivy.metrics import dp
from kivy.graphics import Color, Line, Rectangle
from kivy.core.text import Label as CoreLabel
from kivy.graphics import Color, Line, Rectangle, Ellipse


class RoastPlot(Widget):
    x_series = ListProperty([])
    bt_series = ListProperty([])
    set_series = ListProperty([])
    ex_series = ListProperty([])     # <-- NEW: Exhaust Temp
    ror_series = ListProperty([])

    # Marker #0 (banner_code=2) -> Open Hopper
    mk0_t = NumericProperty(-1.0)
    mk0_bt = NumericProperty(0.0)

    # Marker #1 (banner_code=5)
    mk1_t = NumericProperty(-1.0)   # seconds
    mk1_bt = NumericProperty(0.0)   # °C

    # Marker #2 (banner_code=7)
    mk2_t = NumericProperty(-1.0)
    mk2_bt = NumericProperty(0.0)

    # Marker #3 (banner_code=9) -> Drop Out
    mk3_t = NumericProperty(-1.0)
    mk3_bt = NumericProperty(0.0)

    # Marker #4 (banner_code=4) -> Turning Point
    mk4_t = NumericProperty(-1.0)
    mk4_bt = NumericProperty(0.0)


    W = 1200.0
    y_min = 0
    y_max = 300

    # RoR 0..40 gibi küçük kaldığı için grafikte görünür yapmak:
    # 1.0 yaparsan "ham" çizer (dipte kalır). 5.0 -> 0..60 yaklaşık 0..300
    ROR_SCALE = 5.0

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bind(pos=self._redraw, size=self._redraw)
        self.bind(
            x_series=self._redraw,
            bt_series=self._redraw,
            set_series=self._redraw,
            ex_series=self._redraw,      # <-- NEW
            ror_series=self._redraw,
            mk0_t=self._redraw,
            mk0_bt=self._redraw,
            mk1_t=self._redraw,
            mk1_bt=self._redraw,
            mk2_t=self._redraw,
            mk2_bt=self._redraw,
            mk4_t=self._redraw,
            mk4_bt=self._redraw,

        )

    def _draw_text(self, text, x, y, font_size=12, color=(1, 1, 1, 1)):
        lbl = CoreLabel(text=text, font_size=font_size)
        lbl.refresh()

        Color(*color)
        Rectangle(texture=lbl.texture, pos=(x, y), size=lbl.texture.size)

    def _draw_text_eski(self, text, x, y, font_size=12, color=(1, 1, 1, 0.9)):
        lbl = CoreLabel(text=text, font_size=font_size, color=color)
        lbl.refresh()
        Rectangle(texture=lbl.texture, pos=(x, y), size=lbl.texture.size)

    def _redraw(self, *args):
        self.canvas.clear()
        with self.canvas:
            # Background
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

            y_major_lbl = (1, 1, 1, 1)
            y_minor_lbl = (1, 1, 1, 1)
            x_minor_lbl = (1, 1, 1, 1)
            x_major_lbl = (1, 1, 1, 1)

            #y_major_lbl = (0.92, 0.94, 0.98, 0.95)
            #y_minor_lbl = (0.78, 0.82, 0.88, 0.85)
            #x_minor_lbl = (0.78, 0.82, 0.88, 0.90)
            #x_major_lbl = (0.94, 0.96, 0.99, 0.95)

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

            # -------------------------------------------------
            # Legend (SET / BT / EXH / ROR)  <-- EXH ROR'dan önce
            # -------------------------------------------------
            legend_y = self.y + dp(26)
            legend_x = px + pw / 2 - dp(150)  # biraz sola çek (4 etiket var)

            # SET
            Color(1.00, 0.38, 0.38, 0.95)
            Rectangle(pos=(legend_x, legend_y), size=(dp(10), dp(10)))
            self._draw_text("SET", legend_x + dp(14), legend_y - dp(2), font_size=12,
                            color=(0.9, 0.92, 0.95, 0.95))

            # BT
            Color(0.25, 0.70, 1.00, 1.0)
            Rectangle(pos=(legend_x + dp(56), legend_y), size=(dp(10), dp(10)))
            self._draw_text("BT", legend_x + dp(70), legend_y - dp(2), font_size=12,
                            color=(0.9, 0.92, 0.95, 0.95))

            # EXH (NEW)  -> ROR'dan önce
            Color(1.00, 0.78, 0.25, 0.95)
            Rectangle(pos=(legend_x + dp(102), legend_y), size=(dp(10), dp(10)))
            self._draw_text("EXH", legend_x + dp(116), legend_y - dp(2), font_size=12,
                            color=(0.9, 0.92, 0.95, 0.95))

            # ROR
            Color(0.40, 0.95, 0.55, 0.95)
            Rectangle(pos=(legend_x + dp(154), legend_y), size=(dp(10), dp(10)))
            ror_lbl = "ROR" if self.ROR_SCALE == 1.0 else f"ROR x{self.ROR_SCALE:.0f}"
            self._draw_text(ror_lbl, legend_x + dp(168), legend_y - dp(2), font_size=12,
                            color=(0.9, 0.92, 0.95, 0.95))

            # plots
            if self.x_series and len(self.x_series) >= 2:

                # SET
                if self.set_series and len(self.set_series) == len(self.x_series):
                    Color(1.00, 0.38, 0.38, 0.95)
                    pts = []
                    for sx, sy in zip(self.x_series, self.set_series):
                        pts.extend([xf(sx), yf(sy)])
                    Line(points=pts, width=1.2)

                # BT
                if self.bt_series and len(self.bt_series) == len(self.x_series):
                    Color(0.25, 0.70, 1.00, 1.0)
                    pts = []
                    for bx, by in zip(self.x_series, self.bt_series):
                        pts.extend([xf(bx), yf(by)])
                    Line(points=pts, width=1.4)



                # ---- MARKERS on BT line by time ----
                def _draw_marker(tsec, btval, inner_rgba):
                    try:
                        tsec = float(tsec)
                        if tsec < 0:
                            return

                        mx = xf(tsec)
                        my = yf(btval)

                        # ---- marker circle ----
                        # outer white ring
                        Color(1, 1, 1, 0.95)
                        Ellipse(pos=(mx - dp(6), my - dp(6)), size=(dp(12), dp(12)))
                        # inner dot
                        Color(*inner_rgba)
                        Ellipse(pos=(mx - dp(4), my - dp(4)), size=(dp(8), dp(8)))

                        # ---- time label above marker (mm:00) ----
                        minutes = int(tsec) // 60
                        seconds = int(tsec) % 60
                        label_txt = f"{minutes:02d}:{seconds:02d}"

                        # biraz yukarı yaz
                        self._draw_text(
                            label_txt,
                            mx - dp(18),  # x offset (ortalamak için)
                            my + dp(10),  # marker'ın üstü
                            font_size=12,
                            color=(1, 1, 1, 0.95)
                        )

                    except Exception:
                        pass

                _draw_marker(self.mk0_t, self.mk0_bt, (0.85, 0.85, 0.85, 0.95))  # gri (HOPPER)
                _draw_marker(self.mk4_t, self.mk4_bt, (0.70, 0.55, 1.00, 0.95))  # mor (TURN)

                # marker #1 (banner_code=6)
                _draw_marker(self.mk1_t, self.mk1_bt, (0.25, 0.70, 1.00, 1.0))  # mavi

                # marker #2 (banner_code=8)
                _draw_marker(self.mk2_t, self.mk2_bt, (1.00, 0.78, 0.25, 0.95))  # sarı

                _draw_marker(self.mk3_t, self.mk3_bt, (1.00, 0.38, 0.38, 0.95))  # kırmızı (DROP)

                # EXH (NEW) - Exhaust Temperature
                if self.ex_series and len(self.ex_series) == len(self.x_series):
                    Color(1.00, 0.78, 0.25, 0.95)
                    pts = []
                    for exx, exv in zip(self.x_series, self.ex_series):
                        pts.extend([xf(exx), yf(exv)])
                    Line(points=pts, width=1.2)

                # ROR
                if self.ror_series and len(self.ror_series) == len(self.x_series):
                    Color(0.40, 0.95, 0.55, 0.95)
                    pts = []
                    for rx, rv in zip(self.x_series, self.ror_series):
                        pts.extend([xf(rx), yf(rv * self.ROR_SCALE)])
                    Line(points=pts, width=1.2)
