from kivy.uix.widget import Widget
from kivy.properties import (
    ListProperty,
    BooleanProperty,
    NumericProperty,
    StringProperty,
)
from kivy.clock import Clock
from kivy.graphics import Color, Ellipse
from kivy.metrics import dp


class StatusLed(Widget):
    led_color = ListProperty([0, 1, 0, 1])
    blink = BooleanProperty(True)
    led_on = BooleanProperty(True)
    state = StringProperty("on")   # "on", "off", "warn"
    blink_interval = NumericProperty(0.5)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._blink_ev = None

        self.bind(
            pos=self._redraw,
            size=self._redraw,
            led_color=self._redraw,
            led_on=self._redraw,
            blink=self._update_blink,
            blink_interval=self._update_blink,
            state=self._apply_state,
        )

        self._apply_state()
        self._update_blink()
        self._redraw()

    def _apply_state(self, *args):
        if self.state == "on":
            self.led_color = [0, 1, 0, 1]
        elif self.state == "off":
            self.led_color = [1, 0, 0, 1]
        elif self.state == "warn":
            self.led_color = [1, 0.75, 0, 1]
        else:
            self.led_color = [0.7, 0.7, 0.7, 1]

    def _update_blink(self, *args):
        if self._blink_ev is not None:
            try:
                self._blink_ev.cancel()
            except Exception:
                pass
            self._blink_ev = None

        if self.blink:
            self._blink_ev = Clock.schedule_interval(self._toggle_blink, self.blink_interval)
        else:
            self.led_on = True

    def _toggle_blink(self, dt):
        self.led_on = not self.led_on

    def _redraw(self, *args):
        self.canvas.clear()

        x, y = self.pos
        w, h = self.size

        with self.canvas:
            # dış metal halka
            Color(0.08, 0.08, 0.08, 1)
            Ellipse(pos=(x - dp(4), y - dp(4)), size=(w + dp(8), h + dp(8)))

            # dış glow
            Color(
                self.led_color[0],
                self.led_color[1],
                self.led_color[2],
                0.28 if self.led_on else 0.08,
            )
            Ellipse(pos=(x - dp(8), y - dp(8)), size=(w + dp(16), h + dp(16)))

            # orta glow
            Color(
                self.led_color[0],
                self.led_color[1],
                self.led_color[2],
                0.18 if self.led_on else 0.04,
            )
            Ellipse(pos=(x - dp(5), y - dp(5)), size=(w + dp(10), h + dp(10)))

            # ana cam küre
            Color(
                self.led_color[0],
                self.led_color[1],
                self.led_color[2],
                0.97 if self.led_on else 0.45,
            )
            Ellipse(pos=(x, y), size=(w, h))

            # alt gölge
            Color(0, 0, 0, 0.28)
            Ellipse(pos=(x + dp(6), y + dp(2)), size=(w * 0.68, h * 0.68))

            # iç parlama
            Color(1, 1, 1, 0.12 if self.led_on else 0.05)
            Ellipse(pos=(x + dp(4), y + dp(4)), size=(w * 0.52, h * 0.52))

            # üst ana parlama
            Color(1, 1, 1, 0.52 if self.led_on else 0.18)
            Ellipse(pos=(x + dp(4), y + dp(14)), size=(w * 0.30, h * 0.30))

            # ince ikinci parlama
            Color(1, 1, 1, 0.20 if self.led_on else 0.08)
            Ellipse(pos=(x + dp(9), y + dp(18)), size=(w * 0.12, h * 0.12))

    def on_parent(self, widget, parent):
        if parent is None and self._blink_ev is not None:
            try:
                self._blink_ev.cancel()
            except Exception:
                pass
            self._blink_ev = None