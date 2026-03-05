from kivy.uix.popup import Popup
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.metrics import dp
from kivy.clock import Clock
from kivy.graphics import Color, RoundedRectangle


# ---------------------------------------------------------
# Rounded button (NumericKeypad style)
# + consumes touch to prevent "click-through" / double actions
# ---------------------------------------------------------
class RoundedKeyButton(Button):
    def __init__(
        self,
        radius_dp=16,
        normal_rgba=(0.35, 0.35, 0.35, 1),
        down_rgba=(0.45, 0.45, 0.45, 1),
        **kwargs
    ):
        super().__init__(**kwargs)
        self._radius_dp = radius_dp
        self._normal_rgba = normal_rgba
        self._down_rgba = down_rgba

        self.background_normal = ""
        self.background_down = ""
        self.background_color = (0, 0, 0, 0)
        self.color = (1, 1, 1, 1)

        self.bind(pos=self._redraw, size=self._redraw, state=self._redraw)
        self._redraw()

    def _redraw(self, *_):
        self.canvas.before.clear()
        with self.canvas.before:
            if self.state == "down":
                Color(*self._down_rgba)
            else:
                Color(*self._normal_rgba)
            RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(self._radius_dp)] * 4)

    # ---- IMPORTANT: consume touch so it doesn't pass to widgets behind ----
    def on_touch_down(self, touch):
        if self.disabled:
            return False
        if self.collide_point(*touch.pos):
            # Let ButtonBehavior handle press, but consume event
            super().on_touch_down(touch)
            return True
        return super().on_touch_down(touch)

    def on_touch_up(self, touch):
        if self.disabled:
            return False
        if self.collide_point(*touch.pos):
            super().on_touch_up(touch)
            return True
        return super().on_touch_up(touch)


class TextKeypadPopup(Popup):
    """
    Reusable text keypad popup for touch screens.

    ✅ NumericKeypad style (dark + rounded buttons)
    ✅ First typed key clears existing text (fresh input)
    ✅ OK/CANCEL closes on first tap (no click-through)
    """

    def __init__(
        self,
        title="Enter Text",
        initial_text="",
        max_len=24,
        on_ok=None,
        on_cancel=None,
        fullscreen=True,
        **kwargs
    ):
        super().__init__(**kwargs)

        # popup chrome off (project style)
        self.title = ""
        self.auto_dismiss = False
        self.separator_height = 0
        self.background = ""
        self.background_color = (0, 0, 0, 0)

        self._hdr_title = title
        self._on_ok = on_ok
        self._on_cancel = on_cancel
        self._max_len = int(max_len) if max_len else 999
        self._shift = True  # start UPPER

        # prevent double trigger
        self._closing = False

        # first key press clears
        self._fresh = True

        # Fullscreen
        if fullscreen:
            self.size_hint = (1, 1)
            self.pos_hint = {"x": 0, "y": 0}
        else:
            self.size_hint = (None, None)
            self.size = (dp(760), dp(520))

        # ---- root ----
        root = BoxLayout(orientation="vertical", spacing=dp(14), padding=dp(16))

        def _redraw_card(*_):
            root.canvas.before.clear()
            with root.canvas.before:
                Color(0.12, 0.13, 0.16, 1)
                RoundedRectangle(pos=root.pos, size=root.size, radius=[dp(22)] * 4)

        root.bind(pos=_redraw_card, size=_redraw_card)
        _redraw_card()

        # ---- header ----
        header = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(44) if fullscreen else dp(40),
            padding=(dp(10), dp(6), dp(10), dp(6)),
        )
        title_lbl = Label(
            text=self._hdr_title,
            font_size="22sp" if fullscreen else "18sp",
            bold=True,
            color=(1, 1, 1, 1),
            halign="left",
            valign="middle",
        )
        title_lbl.bind(size=lambda w, *_: setattr(w, "text_size", w.size))
        header.add_widget(title_lbl)
        root.add_widget(header)

        # ---- display (readonly) ----
        self._ti = TextInput(
            text=initial_text or "",
            multiline=False,
            font_size="32sp" if fullscreen else "22sp",
            readonly=True,
            background_normal="",
            background_active="",
            background_color=(0.12, 0.13, 0.16, 1),
            foreground_color=(1, 1, 1, 1),
            cursor_color=(1, 1, 1, 1),
            padding=[dp(14), dp(18), dp(14), dp(14)],
            size_hint_y=None,
            height=dp(86) if fullscreen else dp(54),
        )
        root.add_widget(self._ti)

        # keypad area
        root.add_widget(self._build_keys(fullscreen=fullscreen))

        # bottom buttons
        bottom = BoxLayout(
            size_hint_y=None,
            height=dp(90) if fullscreen else dp(54),
            spacing=dp(12),
        )

        self._btn_cancel = RoundedKeyButton(text="CANCEL", font_size="30sp" if fullscreen else "18sp", bold=True)
        self._btn_ok = RoundedKeyButton(text="OK", font_size="30sp" if fullscreen else "18sp", bold=True)

        # on_release is OK now, because we consume touch (no click-through)
        self._btn_cancel.bind(on_release=lambda *_: self._cancel())
        self._btn_ok.bind(on_release=lambda *_: self._ok())

        bottom.add_widget(self._btn_cancel)
        bottom.add_widget(self._btn_ok)
        root.add_widget(bottom)

        self.content = root

    # ---------------------------------------------------------
    # BUILD KEYS
    # ---------------------------------------------------------
    def _build_keys(self, fullscreen: bool):
        wrap = BoxLayout(orientation="vertical", spacing=dp(12))

        # letters grid
        self._grid = GridLayout(cols=10, spacing=dp(10) if fullscreen else dp(6), size_hint_y=None)
        self._grid.bind(minimum_height=self._grid.setter("height"))
        wrap.add_widget(self._grid)
        self._rebuild_letter_keys(fullscreen=fullscreen)

        # function row
        fn = BoxLayout(size_hint_y=None, height=dp(78) if fullscreen else dp(48), spacing=dp(10))

        self._btn_shift = RoundedKeyButton(text="SHIFT", font_size="24sp" if fullscreen else "18sp", bold=True)
        btn_space = RoundedKeyButton(text="SPACE", font_size="24sp" if fullscreen else "18sp", bold=True)
        btn_back = RoundedKeyButton(text="⌫", font_size="30sp" if fullscreen else "18sp", bold=True)
        btn_clear = RoundedKeyButton(text="CLEAR", font_size="24sp" if fullscreen else "18sp", bold=True)
        btn_dash = RoundedKeyButton(text="-", font_size="28sp" if fullscreen else "18sp", bold=True)
        btn_us = RoundedKeyButton(text="_", font_size="28sp" if fullscreen else "18sp", bold=True)

        self._btn_shift.bind(on_release=lambda *_: self._toggle_shift(fullscreen=fullscreen))
        btn_space.bind(on_release=lambda *_: self._append(" "))
        btn_back.bind(on_release=lambda *_: self._backspace())
        btn_clear.bind(on_release=lambda *_: self._clear())
        btn_dash.bind(on_release=lambda *_: self._append("-"))
        btn_us.bind(on_release=lambda *_: self._append("_"))

        fn.add_widget(self._btn_shift)
        fn.add_widget(btn_space)
        fn.add_widget(btn_back)
        fn.add_widget(btn_clear)
        fn.add_widget(btn_dash)
        fn.add_widget(btn_us)
        wrap.add_widget(fn)

        # numbers row
        nums = GridLayout(
            cols=10,
            spacing=dp(10) if fullscreen else dp(6),
            size_hint_y=None,
            height=dp(78) if fullscreen else dp(48),
        )
        for ch in "0123456789":
            b = RoundedKeyButton(text=ch, font_size="30sp" if fullscreen else "18sp", bold=True)
            b.bind(on_release=lambda _btn, c=ch: self._append(c))
            nums.add_widget(b)
        wrap.add_widget(nums)

        return wrap

    def _rebuild_letter_keys(self, fullscreen: bool):
        self._grid.clear_widgets()

        letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        if not self._shift:
            letters = letters.lower()

        h = dp(74) if fullscreen else dp(44)
        fs = "26sp" if fullscreen else "18sp"

        for ch in letters:
            b = RoundedKeyButton(text=ch, size_hint_y=None, height=h, font_size=fs, bold=True)
            b.bind(on_release=lambda _btn, c=ch: self._append(c))
            self._grid.add_widget(b)

    def _toggle_shift(self, fullscreen: bool):
        self._shift = not self._shift
        self._btn_shift.text = "SHIFT" if self._shift else "shift"
        self._rebuild_letter_keys(fullscreen=fullscreen)

    # ---------------------------------------------------------
    # INPUT LOGIC (fresh clear on first key)
    # ---------------------------------------------------------
    def _ensure_fresh_cleared(self):
        if self._fresh:
            self._ti.text = ""
            self._fresh = False

    def _append(self, s: str):
        self._ensure_fresh_cleared()
        if len(self._ti.text) >= self._max_len:
            return
        self._ti.text = (self._ti.text or "") + s

    def _backspace(self):
        self._ensure_fresh_cleared()
        t = self._ti.text or ""
        if t:
            self._ti.text = t[:-1]

    def _clear(self):
        self._ti.text = ""
        self._fresh = False

    # ---------------------------------------------------------
    # CLOSE HELPERS
    # ---------------------------------------------------------
    def _lock_buttons(self):
        try:
            self._btn_cancel.disabled = True
            self._btn_ok.disabled = True
        except Exception:
            pass

    def _cancel(self):
        if self._closing:
            return
        self._closing = True
        self._lock_buttons()

        # close immediately now (touch is consumed already)
        try:
            self.dismiss()
        except Exception:
            pass

        if callable(self._on_cancel):
            Clock.schedule_once(lambda *_: self._on_cancel(), 0)

    def _ok(self):
        if self._closing:
            return
        self._closing = True
        self._lock_buttons()

        txt = (self._ti.text or "").strip()

        try:
            self.dismiss()
        except Exception:
            pass

        if callable(self._on_ok):
            Clock.schedule_once(lambda *_: self._on_ok(txt), 0)
