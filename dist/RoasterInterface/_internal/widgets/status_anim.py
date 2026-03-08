# status_anim.py
from kivy.uix.widget import Widget
from kivy.graphics import Color, RoundedRectangle, Line, Ellipse
from kivy.clock import Clock
from kivy.properties import NumericProperty
import math


class StatusAnim(Widget):
    intensity = NumericProperty(0.6)   # 0.0 – 1.0

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._t = 0.0
        Clock.schedule_interval(self._update, 1 / 30)  # düşük FPS

    def _update(self, dt):
        self._t += dt
        self.canvas.clear()
        with self.canvas:
            self._draw_cup()
            self._draw_beans()
            self._draw_smoke()

    # -----------------------------
    # CUP
    # -----------------------------
    def _draw_cup(self):
        w, h = self.size
        cx = self.x + w * 0.55
        cy = self.y + h * 0.35

        Color(0.18, 0.20, 0.24, 1)
        RoundedRectangle(pos=(cx - 90, cy - 35), size=(180, 70), radius=[28])

        # handle
        Line(circle=(cx + 85, cy, 28), width=2)

    # -----------------------------
    # COFFEE BEANS (roast darkening)
    # -----------------------------
    def _draw_beans(self):
        roast = min(1.0, self._t * 0.03)
        r = 0.55 - roast * 0.25
        g = 0.35 - roast * 0.20
        b = 0.20 - roast * 0.15

        cx = self.x + self.width * 0.55
        cy = self.y + self.height * 0.35

        Color(r, g, b, 1)
        for dx, dy in [(-20, 5), (0, -5), (18, 6)]:
            Ellipse(pos=(cx + dx - 6, cy + dy - 4), size=(12, 8))

    # -----------------------------
    # SMOKE (soft & slow)
    # -----------------------------
    def _draw_smoke(self):
        base_x = self.x + self.width * 0.55
        base_y = self.y + self.height * 0.48

        Color(1, 1, 1, 0.25)

        for i in range(3):
            phase = self._t * (0.8 + i * 0.2)
            offset = math.sin(phase) * 18
            height = 60 + i * 18

            Line(
                points=[
                    base_x + offset, base_y,
                    base_x - offset, base_y + height
                ],
                width=1.4
            )
