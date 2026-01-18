from kivy.uix.widget import Widget
from kivy.properties import NumericProperty, StringProperty
from kivy.graphics import Color, Line


class AirflowGauge(Widget):
    value = NumericProperty(0.56)      # 0..1
    text = StringProperty("168 Pa")
    subtext = StringProperty("normal airflow")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bind(pos=self._redraw, size=self._redraw, value=self._redraw)

    def _redraw(self, *_):
        self.canvas.clear()
        with self.canvas:
            cx, cy = self.center
            r = min(self.width, self.height) * 0.42
            thickness = r * 0.08

            # görseldeki gibi “C” formu:
            start_angle = -90  #210
            end_angle = 90 #-30
            sweep = start_angle - end_angle  # 240 deg

            # background
            Color(0.25, 0.27, 0.30, 1)
            Line(circle=(cx, cy, r, start_angle, end_angle), width=thickness, cap="round")

            # active
            Color(0.45, 0.85, 0.65, 1)
            Line(
                circle=(cx, cy, r, start_angle, start_angle - sweep * self.value),
                width=thickness,
                cap="round",
            )

