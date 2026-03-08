from kivy.uix.popup import Popup
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.metrics import dp
from kivy.graphics import Color, RoundedRectangle


# ---------------------------------------------------------
# Rounded button (project-like)
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


class NumericKeypadPopup(Popup):
    """
    Reusable numeric keypad popup

    - TR virgül destekler (",")
    - max_decimals ile ondalık basamak sınırı
    - on_ok callback: on_ok(value_float, text_str)
    - ✅ İlk rakama basınca komple silip yeni rakamı yazar (fresh replace)
    """

    def __init__(
        self,
        title="Enter value",
        initial_text="",
        max_decimals=1,
        min_value=None,
        max_value=None,
        on_ok=None,
        on_cancel=None,
        fullscreen=True,   # ✅ default full screen
        **kwargs
    ):
        super().__init__(**kwargs)

        # --- use custom header, not Popup title bar ---
        self.title = ""
        self.auto_dismiss = False
        self.separator_height = 0
        self.background = ""
        self.background_color = (0, 0, 0, 0)  # transparent

        self._hdr_title = title

        self._s = (initial_text or "").strip()
        self._max_decimals = int(max_decimals)
        self._min_value = min_value
        self._max_value = max_value
        self._on_ok = on_ok
        self._on_cancel = on_cancel

        # ✅ Fresh flag: popup açıldı -> ilk input replace yapsın
        self._fresh = True

        # ✅ Fullscreen ayarı
        if fullscreen:
            self.size_hint = (1, 1)
            self.pos_hint = {"x": 0, "y": 0}
        else:
            self.size_hint = (None, None)
            self.size = (dp(520), dp(640))

        # ---- root layout ----
        root = BoxLayout(orientation="vertical", spacing=dp(14), padding=dp(16))

        # ---- dark card background (rounded) ----
        def _redraw_card(*_):
            root.canvas.before.clear()
            with root.canvas.before:
                Color(0.12, 0.13, 0.16, 1)
                RoundedRectangle(pos=root.pos, size=root.size, radius=[dp(22)] * 4)

        root.bind(pos=_redraw_card, size=_redraw_card)
        _redraw_card()

        # ---- header (project-like title) ----
        header = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(44) if fullscreen else dp(40),
            padding=(dp(10), dp(6), dp(10), dp(6))
        )

        title_lbl = Label(
            text=self._hdr_title,
            font_size="22sp",
            bold=True,
            color=(1, 1, 1, 1),
            halign="left",
            valign="middle",
        )
        title_lbl.bind(size=lambda w, *_: setattr(w, "text_size", w.size))
        header.add_widget(title_lbl)
        root.add_widget(header)

        # ---- display ----
        self._display = Label(
            text=self._s if self._s else "0",
            font_size="48sp" if fullscreen else "36sp",
            bold=True,
            size_hint_y=None,
            height=dp(92) if fullscreen else dp(76),
            color=(1, 1, 1, 1),
            halign="center",
            valign="middle",
        )
        self._display.bind(size=lambda *_: setattr(self._display, "text_size", self._display.size))
        root.add_widget(self._display)

        # ---- keypad grid (NOW includes CANCEL/CLEAR/OK as SAME SIZE) ----
        grid = GridLayout(
            cols=3,
            spacing=dp(12) if fullscreen else dp(10),
            size_hint=(1, 1)
        )

        keys = [
            "1", "2", "3",
            "4", "5", "6",
            "7", "8", "9",
            ",", "0", "⌫",
            "CANCEL", "CLEAR", "OK",
        ]

        for k in keys:
            b = RoundedKeyButton(
                text=k,
                radius_dp=16,
                font_size="40sp" if fullscreen else "24sp",
                bold=True,  # ✅ all bold (including CANCEL/CLEAR/OK)
            )

            if k == "CANCEL":
                b.bind(on_release=lambda *_: self._cancel())
            elif k == "CLEAR":
                b.bind(on_release=lambda *_: self._clear())
            elif k == "OK":
                b.bind(on_release=lambda *_: self._ok())
            else:
                b.bind(on_release=lambda _btn, kk=k: self._on_key(kk))

            grid.add_widget(b)

        root.add_widget(grid)

        # set content
        self.content = root

    # ---------------- internal helpers ----------------
    def _refresh(self):
        self._display.text = self._s if self._s else "0"

    def _set(self, s: str):
        self._s = s
        self._refresh()

    def _clear(self):
        # CLEAR'e basınca artık fresh değil (kullanıcı düzenlemeye başladı)
        self._fresh = False
        self._set("")

    def _backspace(self):
        # backspace -> fresh kapansın
        self._fresh = False
        self._set(self._s[:-1])

    def _append_digit(self, d: str):
        # ✅ İlk rakam basışı: komple replace (telefon gibi)
        if getattr(self, "_fresh", False):
            self._fresh = False
            self._set(d)
            return

        # "0" + "5" -> "5" (virgül yoksa)
        if self._s == "0":
            self._set(d)
            return

        # ondalık sınırı
        if "," in self._s and self._max_decimals >= 0:
            frac = self._s.split(",", 1)[1]
            if len(frac) >= self._max_decimals:
                return

        self._set(self._s + d)

    def _append_comma(self):
        # virgüle basınca da fresh kapansın
        if getattr(self, "_fresh", False):
            self._fresh = False

        if "," in self._s:
            return
        if self._s == "" or self._s == "-":
            self._set("0,")
        else:
            self._set(self._s + ",")

    def _on_key(self, key: str):
        if key == "⌫":
            self._backspace()
            return

        if key == ",":
            self._append_comma()
            return

        if key.isdigit():
            self._append_digit(key)

    def _cancel(self):
        try:
            self.dismiss()
        finally:
            if callable(self._on_cancel):
                self._on_cancel()

    def _ok(self):
        # OK'e basınca fresh kapansın (tekrar açılınca zaten init'te True olacak)
        self._fresh = False

        s = (self._s or "").strip()

        if s in ("", ",", "-", "-,"):
            return

        try:
            val = float(s.replace(",", "."))
        except Exception:
            return

        if (self._min_value is not None) and (val < self._min_value):
            return
        if (self._max_value is not None) and (val > self._max_value):
            return

        try:
            self.dismiss()
        finally:
            if callable(self._on_ok):
                self._on_ok(val, s)
