from kivy.uix.popup import Popup
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.metrics import dp


class NumericKeypadPopup(Popup):
    """
    Reusable numeric keypad popup (clean rewrite)

    - TR virgül destekler (",")
    - max_decimals ile ondalık basamak sınırı
    - on_ok callback: on_ok(value_float, text_str)
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
        **kwargs
    ):
        super().__init__(**kwargs)

        self.title = title
        self.size_hint = (None, None)
        self.size = (dp(420), dp(520))
        self.auto_dismiss = False

        self._s = (initial_text or "").strip()
        self._max_decimals = int(max_decimals)
        self._min_value = min_value
        self._max_value = max_value
        self._on_ok = on_ok
        self._on_cancel = on_cancel

        # ---- root layout ----
        root = BoxLayout(orientation="vertical", spacing=dp(10), padding=dp(12))

        # ---- display ----
        self._display = Label(
            text=self._s if self._s else "0",
            font_size="36sp",
            bold=True,
            size_hint_y=None,
            height=dp(70),
            halign="center",
            valign="middle",
        )
        self._display.bind(size=lambda *_: setattr(self._display, "text_size", self._display.size))
        root.add_widget(self._display)

        # ---- keypad grid ----
        grid = GridLayout(cols=3, spacing=dp(8), size_hint_y=None)
        grid.bind(minimum_height=grid.setter("height"))

        keys = [
            "1", "2", "3",
            "4", "5", "6",
            "7", "8", "9",
            ",", "0", "⌫",
        ]

        for k in keys:
            b = Button(
                text=k,
                font_size="24sp",
                size_hint_y=None,
                height=dp(68),
            )
            # IMPORTANT: lambda default arg captures k safely
            b.bind(on_release=lambda _btn, kk=k: self._on_key(kk))
            grid.add_widget(b)

        root.add_widget(grid)

        # ---- bottom buttons ----
        row = BoxLayout(orientation="horizontal", spacing=dp(10), size_hint_y=None, height=dp(56))

        btn_cancel = Button(text="CANCEL", font_size="18sp")
        btn_clear = Button(text="CLEAR", font_size="18sp")
        btn_ok = Button(text="OK", font_size="18sp")

        btn_cancel.bind(on_release=lambda *_: self._cancel())
        btn_clear.bind(on_release=lambda *_: self._set(""))
        btn_ok.bind(on_release=lambda *_: self._ok())

        row.add_widget(btn_cancel)
        row.add_widget(btn_clear)
        row.add_widget(btn_ok)
        root.add_widget(row)

        self.content = root

    # ---------------- internal helpers ----------------
    def _refresh(self):
        self._display.text = self._s if self._s else "0"

    def _set(self, s: str):
        self._s = s
        self._refresh()

    def _backspace(self):
        self._set(self._s[:-1])

    def _append_digit(self, d: str):
        # 0 ile başlayan sayıyı (virgül yoksa) düzelt: "0" + "5" -> "5"
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
        s = (self._s or "").strip()

        # geçersiz girişleri engelle
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
