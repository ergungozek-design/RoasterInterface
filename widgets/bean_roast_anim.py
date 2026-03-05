from kivy.uix.widget import Widget
from kivy.uix.image import Image
from kivy.uix.scatter import Scatter
from kivy.clock import Clock
from kivy.animation import Animation
from kivy.properties import StringProperty, NumericProperty

import os, sys
from pathlib import Path

def resource_path(rel):
    base = getattr(sys, "_MEIPASS", str(Path(__file__).resolve().parents[1]))
    return os.path.join(base, rel)

class BeanRoastAnim(Widget):
    green_source = StringProperty(resource_path("assets/beans/bean_green_transparent.png"))
    dark_source = StringProperty(resource_path("assets/beans/bean_dark_transparent.png"))

    #green_source = StringProperty("assets/beans/bean_green_transparent.png")
    #dark_source = StringProperty("assets/beans/bean_dark_transparent.png")

    intensity = NumericProperty(0.8)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self._scatter = None
        self._green = None
        self._dark = None

        self._float_anim = None
        self._tick_ev = None

        self._roast = 0.0
        self._dir = 1

        self._build()
        self.bind(pos=self._sync, size=self._sync)

    def _build(self):
        self.clear_widgets()

        sc = Scatter(
            do_translation=False,
            do_rotation=False,
            do_scale=False,
            size_hint=(None, None),
        )

        green = Image(
            source=self.green_source,
            allow_stretch=True,
            keep_ratio=True,
            size_hint=(None, None),
            nocache=True
        )

        dark = Image(
            source=self.dark_source,
            allow_stretch=True,
            keep_ratio=True,
            size_hint=(None, None),
            opacity=0.0,
            nocache=True
        )

        sc.add_widget(green)
        sc.add_widget(dark)
        self.add_widget(sc)

        self._scatter = sc
        self._green = green
        self._dark = dark

        self._sync()

    def _sync(self, *_):
        if not self._scatter:
            return

        s = min(self.width, self.height) * 0.95
        if s <= 1:
            return

        self._green.size = (s, s)
        self._dark.size = (s, s)

        self._scatter.size = (s, s)

        # ✅ her sync’de scatter kesin widget merkezine otursun
        self._scatter.center = self.center

        # ✅ eğer animasyon çalışıyorsa, merkez değiştiğinde float anim’i tazele
        if self._float_anim:
            self._float_anim.cancel(self._scatter)
            self._float_anim = self._make_float_anim()
            self._float_anim.start(self._scatter)

    # ✅ ProfileDetailScreen.py ile uyumlu
    def start(self):
        # zaten çalışıyorsa tekrar schedule yapma
        if self._float_anim or self._tick_ev:
            return

        # ✅ start anında da merkez/sizing garanti
        self._sync()

        # 1) float anim
        self._float_anim = self._make_float_anim()
        self._float_anim.start(self._scatter)

        # 2) roast loop tick
        self._tick_ev = Clock.schedule_interval(self._roast_update, 1/30)

    def stop(self):
        if self._float_anim:
            self._float_anim.cancel(self._scatter)
            self._float_anim = None

        if self._tick_ev:
            self._tick_ev.cancel()
            self._tick_ev = None

        # reset
        if self._scatter:
            self._scatter.rotation = 0
            self._scatter.scale = 1.0
            self._scatter.center = self.center

        self._roast = 0.0
        self._dir = 1
        if self._dark:
            self._dark.opacity = 0.0

    def _make_float_anim(self):
        # ✅ scatter.center yerine widget center kullan (garanti doğru)
        base_x, base_y = self.center

        amp_y = 10 + 14 * self.intensity
        amp_r = 4 + 9 * self.intensity
        amp_s = 0.02 + 0.05 * self.intensity

        t = 1.15 - 0.45 * self.intensity

        a1 = Animation(
            center=(base_x, base_y + amp_y),
            rotation=amp_r,
            scale=1.0 + amp_s,
            duration=t,
            t="in_out_sine"
        )
        a2 = Animation(
            center=(base_x, base_y - amp_y),
            rotation=-amp_r,
            scale=1.0 - amp_s,
            duration=t,
            t="in_out_sine"
        )

        a = a1 + a2
        a.repeat = True
        return a

    def _roast_update(self, dt):
        speed = 0.35
        self._roast += dt * speed * self._dir

        if self._roast >= 1.0:
            self._roast = 1.0
            self._dir = -1
        elif self._roast <= 0.0:
            self._roast = 0.0
            self._dir = 1

        if self._dark:
            self._dark.opacity = self._roast