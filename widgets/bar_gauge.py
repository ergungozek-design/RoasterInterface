from kivy.uix.widget import Widget
from kivy.properties import NumericProperty
from kivy.graphics import Color, RoundedRectangle


class BarGauge(Widget):
    value = NumericProperty(0.48)  # 0..1

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bind(pos=self._redraw, size=self._redraw, value=self._redraw)

    def _redraw(self, *_):
        self.canvas.clear()
        with self.canvas:
            r = min(self.height, self.width) * 0.45

            # bg
            Color(0.20, 0.22, 0.26, 1)
            RoundedRectangle(pos=self.pos, size=self.size, radius=[r])

            # fill
            w = max(0, min(1, self.value)) * self.width
            Color(0.95, 0.74, 0.36, 1)
            RoundedRectangle(pos=self.pos, size=(w, self.height), radius=[r])

