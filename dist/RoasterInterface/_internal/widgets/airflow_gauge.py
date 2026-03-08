from kivy.uix.widget import Widget
from kivy.properties import NumericProperty, StringProperty, ListProperty
from kivy.graphics import Color, Line


class AirflowGauge(Widget):
    value = NumericProperty(0.56)      # 0..1
    text = StringProperty("168 Pa")
    subtext = StringProperty("normal airflow")

    # ✅ KV'den değiştirilebilir renkler
    gauge_color = ListProperty([0.45, 0.85, 0.65, 1])   # aktif arc rengi
    bg_color = ListProperty([0.25, 0.27, 0.30, 1])      # arkaplan arc rengi

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # ✅ renkler de redraw tetiklesin
        self.bind(
            pos=self._redraw,
            size=self._redraw,
            value=self._redraw,
            gauge_color=self._redraw,
            bg_color=self._redraw,
        )

    def _redraw(self, *_):
        self.canvas.clear()
        with self.canvas:
            cx, cy = self.center
            r = min(self.width, self.height) * 0.42
            thickness = r * 0.08

            # “C” formu açıları
            start_angle = -90
            end_angle = 90

            # toplam sweep (derece)
            total_sweep = abs(end_angle - start_angle)  # 180

            # value clamp (0..1)
            v = float(self.value)
            if v < 0.0:
                v = 0.0
            elif v > 1.0:
                v = 1.0

            # background arc
            Color(*self.bg_color)
            Line(
                circle=(cx, cy, r, start_angle, end_angle),
                width=thickness,
                cap="round"
            )

            # active arc
            # Kivy circle: start_angle -> end_angle (derece)
            # Biz start'tan end'e doğru ilerliyoruz (value kadar)
            active_end = start_angle + (end_angle - start_angle) * v

            Color(*self.gauge_color)
            Line(
                circle=(cx, cy, r, start_angle, active_end),
                width=thickness,
                cap="round"
            )