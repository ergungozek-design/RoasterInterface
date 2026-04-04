import json
import re
import sys
from pathlib import Path

from kivy.app import App
from kivy.uix.screenmanager import Screen
from kivy.properties import StringProperty
from kivy.uix.popup import Popup
from kivy.uix.label import Label
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.metrics import dp
from kivy.uix.image import Image
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.graphics import Color, RoundedRectangle
from kivy.uix.behaviors import ButtonBehavior
from kivy.properties import NumericProperty
from kivy.metrics import dp

from services.numeric_keypad import NumericKeypadPopup
from services.text_keypad import TextKeypadPopup


class ProfileDetailScreen(Screen):
    mode_buttons_height = NumericProperty(0)


    return_to_files = False
    return_screen = StringProperty("profile")
    active_folder = StringProperty("")
    loaded_stem = StringProperty("")

    # ---------------- Profile Type ----------------
    profile_mode = StringProperty("standard")   # "standard" or "dev"

    # DEV time (UI)
    dev_time_min = StringProperty("00")         # "00".."99"
    dev_time_sec = StringProperty("00")         # "00".."59"
    development_time = StringProperty("00:00")  # "mm:ss" internal

    # DEV registers:
    #   - Minute -> MW608
    #   - Second -> MW609
    #   - STD=0, DEV=1
    MW_DEV_MIN = 608
    MW_DEV_SEC = 609
    MW_MODE_FLAG = 615

    # (Opsiyonel / geriye dönük): toplam saniye yazmak istersen
    # 0 kalırsa yazılmaz.
    MW_DEV_TIME = 0

    # ---------------- UI ----------------
    title_text = StringProperty("")
    profile_name = StringProperty("")

    coffee_origin = StringProperty("")
    coffee_origin_png = StringProperty("")

    # ---------------- Main value column ----------------
    drop_down_temp = StringProperty("")
    hopper_open_time = StringProperty("")
    chaffing = StringProperty("")
    chaffing_time = StringProperty("")
    first_crack_temp = StringProperty("")
    second_crack_temp = StringProperty("")
    drop_out_temp = StringProperty("")

    # ---------------- Percent columns (2 adet) ----------------
    dd_p1 = StringProperty("")
    dd_p2 = StringProperty("")
    hop_p1 = StringProperty("")
    hop_p2 = StringProperty("")
    ch_p1 = StringProperty("")
    ch_p2 = StringProperty("")
    ct_p1 = StringProperty("")   # KV boş (kalabilir)
    ct_p2 = StringProperty("")
    fc_p1 = StringProperty("")
    fc_p2 = StringProperty("")
    sc_p1 = StringProperty("")
    sc_p2 = StringProperty("")
    do_p1 = StringProperty("")
    do_p2 = StringProperty("")

    def on_enter(self, *args):
        App.get_running_app().active_tab = "profile"

        # ✅ Ekran açılır açılmaz PLC'den mode flag oku
        self.read_mode_from_plc()

        try:
            if "roast_anim" in self.ids and hasattr(self.ids["roast_anim"], "start"):
                self.ids["roast_anim"].start()
        except Exception as e:
            print(f"[ProfileDetailScreen] roast_anim start error: {e}")

    def on_leave(self, *args):
        try:
            if "roast_anim" in self.ids and hasattr(self.ids["roast_anim"], "stop"):
                self.ids["roast_anim"].stop()
        except Exception as e:
            print(f"[ProfileDetailScreen] roast_anim stop error: {e}")

    # ---------------------------------------------------------
    # Called from ProfileScreen
    # ---------------------------------------------------------
    def load_profile(self, profile_name, data, folder_name=None):
        self.mode_buttons_height = 0

        self.profile_name = profile_name
        self.active_folder = folder_name or ""
        self.loaded_stem = profile_name or ""

        if folder_name:
            self.title_text = folder_name or "Profile"

        def fnum(x, dec=1):
            try:
                return f"{float(x):.{dec}f}"
            except Exception:
                return ""

        def fint(x):
            try:
                return str(int(float(x)))
            except Exception:
                return ""

        # ---------------- profile mode ----------------
        mode = (data.get("profile_mode") or "standard").strip().lower()
        if mode not in ("standard", "dev"):
            mode = "standard"
        self.profile_mode = mode

        # ---------------- development time ----------------
        # JSON'da development_time "mm:ss" veya saniye olabilir
        dt = data.get("development_time")
        if isinstance(dt, str) and dt.strip():
            sec = self._parse_mmss_to_seconds(dt.strip())
        else:
            try:
                sec = int(float(dt)) if dt is not None else None
            except Exception:
                sec = None

        if sec is None:
            self._load_mmss_into_fields("00:00")
        else:
            self._load_seconds_into_fields(sec)

        # origin fields
        self.coffee_origin = (data.get("coffee_origin") or "").strip()
        saved_png = (data.get("coffee_origin_png") or "").strip()

        if saved_png:
            p = Path(saved_png)
            if p.is_absolute() and p.exists():
                self.coffee_origin_png = str(p)
            else:
                rel = (self._project_root() / saved_png)
                if rel.exists():
                    self.coffee_origin_png = str(rel)
                else:
                    self.coffee_origin_png = self._resolve_origin_png(self.coffee_origin) if self.coffee_origin else ""
        else:
            self.coffee_origin_png = self._resolve_origin_png(self.coffee_origin) if self.coffee_origin else ""

        # main values
        self.drop_down_temp = fnum(data.get("drop_down_temp"), 1)
        self.first_crack_temp = fnum(data.get("first_crack_temp"), 1)
        self.second_crack_temp = fnum(data.get("second_crack_temp"), 1)
        self.drop_out_temp = fnum(data.get("drop_out_temp"), 1)

        self.hopper_open_time = fint(data.get("hopper_open_time"))
        self.chaffing = fint(data.get("chaffing"))
        self.chaffing_time = fint(data.get("chaffing_time"))

        # percents
        self.dd_p1 = fint(data.get("dd_p1"))
        self.dd_p2 = fint(data.get("dd_p2"))
        self.hop_p1 = fint(data.get("hop_p1"))
        self.hop_p2 = fint(data.get("hop_p2"))

        self.ch_p1 = fint(data.get("ch_p1"))
        self.ch_p2 = fint(data.get("ch_p2"))

        self.ct_p1 = fint(data.get("ct_p1"))
        self.ct_p2 = fint(data.get("ct_p2"))

        self.fc_p1 = fint(data.get("fc_p1"))
        self.fc_p2 = fint(data.get("fc_p2"))
        self.sc_p1 = fint(data.get("sc_p1"))
        self.sc_p2 = fint(data.get("sc_p2"))
        self.do_p1 = fint(data.get("do_p1"))
        self.do_p2 = fint(data.get("do_p2"))

        # DEV modda ekranda SC/DO görünmüyor ama data okunabilir kalsın.
        # İstersen DEV mod açılınca temizleme set_profile_mode içinde.

    # ---------------------------------------------------------
    # UI actions
    # ---------------------------------------------------------
    def open_name_keypad(self):
        def _on_ok(val):
            self.profile_name = (val or "").strip()

        TextKeypadPopup(
            title="Profile Name",
            initial_text=self.profile_name,
            on_ok=_on_ok
        ).open()

    def open_origin_picker(self):
        origin_dir = self._project_root() / "assets" / "origin"
        origin_dir.mkdir(parents=True, exist_ok=True)

        items = sorted(origin_dir.glob("*.png"))
        if not items:
            self._toast("No origin png found in assets/origin/")
            return

        class IconHit(ButtonBehavior, BoxLayout):
            pass

        root = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(10))

        header = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(64),
            spacing=dp(10),
            padding=(dp(10), dp(10), dp(10), dp(10)),
        )

        with header.canvas.before:
            Color(0.12, 0.13, 0.16, 1)
            bg = RoundedRectangle(pos=header.pos, size=header.size, radius=[dp(18)] * 4)

        def _sync_bg(*_):
            bg.pos = header.pos
            bg.size = header.size

        header.bind(pos=_sync_bg, size=_sync_bg)

        def _pick(p: Path):
            self.coffee_origin = p.stem
            self.coffee_origin_png = str(p)
            pop.dismiss()

        btn_back = Button(
            text="⟵ Back",
            size_hint=(None, 1),
            width=dp(220),
            font_size="22sp",
            bold=True,
            background_normal="",
            background_color=(0.16, 0.17, 0.20, 1),
        )
        btn_back.bind(on_release=lambda *_: pop.dismiss())

        title = Label(
            text="Select Coffee Origin",
            font_size="22sp",
            bold=True,
            color=(1, 1, 1, 1),
            halign="center",
            valign="middle",
        )
        title.bind(size=lambda *_: setattr(title, "text_size", title.size))

        header.add_widget(btn_back)
        header.add_widget(title)

        sv = ScrollView()
        gl = GridLayout(
            cols=5,
            spacing=dp(16),
            padding=dp(8),
            size_hint_y=None
        )
        gl.bind(minimum_height=gl.setter("height"))

        for p in items:
            cell = BoxLayout(
                orientation="vertical",
                size_hint_y=None,
                height=dp(150),
                spacing=dp(8)
            )

            icon_hit = IconHit(
                orientation="vertical",
                size_hint=(1, None),
                height=dp(100),
                padding=(dp(10), dp(6), dp(10), dp(6))
            )
            icon_hit.bind(on_release=lambda _w, pp=p: _pick(pp))

            with icon_hit.canvas.before:
                Color(0.16, 0.17, 0.20, 1)
                r = RoundedRectangle(pos=icon_hit.pos, size=icon_hit.size, radius=[dp(14)] * 4)

            def _sync_r(*_):
                r.pos = icon_hit.pos
                r.size = icon_hit.size

            icon_hit.bind(pos=_sync_r, size=_sync_r)

            img = Image(
                source=str(p),
                allow_stretch=True,
                keep_ratio=True
            )
            icon_hit.add_widget(img)

            lbl = Label(
                text=p.stem,
                size_hint_y=None,
                height=dp(32),
                font_size="16sp",
                color=(1, 1, 1, 1),
                halign="center",
                valign="middle",
            )
            lbl.bind(size=lambda *_: setattr(lbl, "text_size", lbl.size))

            cell.add_widget(icon_hit)
            cell.add_widget(lbl)
            gl.add_widget(cell)

        sv.add_widget(gl)

        root.add_widget(header)
        root.add_widget(sv)

        pop = Popup(
            title="",
            separator_height=0,
            content=root,
            size_hint=(1, 1),
            auto_dismiss=False
        )
        pop.open()

    def open_numeric(self, field_name, title, decimals, min_v, max_v):
        def _on_ok(value_float, text_str):
            setattr(self, field_name, (text_str or "").strip())

        NumericKeypadPopup(
            title=title,
            initial_text=getattr(self, field_name, ""),
            max_decimals=decimals,
            min_value=min_v,
            max_value=max_v,
            on_ok=_on_ok
        ).open()

    # ---------------------------------------------------------
    # DEV TIME (minute + second separate)
    # ---------------------------------------------------------
    def set_profile_mode(self, mode: str):
        mode = (mode or "").strip().lower()
        if mode not in ("standard", "dev"):
            mode = "standard"

        if self.profile_mode == mode:
            return

        self.profile_mode = mode

        if mode == "dev":
            # DEV mod açılınca dev time boşsa default
            if not (self.development_time or "").strip():
                self._load_mmss_into_fields("00:00")
            else:
                self._load_mmss_into_fields(self.development_time)

            # DEV modda SC/DO UI boşalt (görünmüyor ama veri karışmasın diye)
            #self.second_crack_temp = ""
            #self.sc_p1 = ""
            #self.sc_p2 = ""
            #self.drop_out_temp = ""
            #self.do_p1 = ""
            #self.do_p2 = ""

    def _parse_mmss_to_seconds(self, s: str):
        try:
            s = (s or "").strip()
            if not s:
                return None

            if ":" not in s:
                v = int(float(s))
                return v if v >= 0 else None

            parts = s.split(":")
            if len(parts) != 2:
                return None

            mm = int(parts[0].strip())
            ss = int(parts[1].strip())
            if mm < 0:
                return None
            if ss < 0 or ss > 59:
                return None

            return mm * 60 + ss
        except Exception:
            return None

    def _format_seconds_to_mmss(self, sec: int):
        try:
            sec = int(sec)
            if sec < 0:
                sec = 0
            mm = sec // 60
            ss = sec % 60
            return f"{mm:02d}:{ss:02d}"
        except Exception:
            return "00:00"

    def _load_mmss_into_fields(self, mmss: str):
        sec = self._parse_mmss_to_seconds(mmss)
        if sec is None:
            self.dev_time_min = "00"
            self.dev_time_sec = "00"
            self.development_time = "00:00"
            return
        self._load_seconds_into_fields(sec)

    def _load_seconds_into_fields(self, sec: int):
        try:
            sec = int(sec)
        except Exception:
            sec = 0
        if sec < 0:
            sec = 0
        mm = sec // 60
        ss = sec % 60
        if mm < 0:
            mm = 0
        if mm > 99:
            mm = 99
        if ss < 0:
            ss = 0
        if ss > 59:
            ss = 59
        self.dev_time_min = f"{mm:02d}"
        self.dev_time_sec = f"{ss:02d}"
        self.development_time = f"{mm:02d}:{ss:02d}"

    def _sync_dev_time(self):
        try:
            mm = int(float((self.dev_time_min or "0").replace(",", ".")))
        except Exception:
            mm = 0
        try:
            ss = int(float((self.dev_time_sec or "0").replace(",", ".")))
        except Exception:
            ss = 0

        if mm < 0:
            mm = 0
        if mm > 99:
            mm = 99
        if ss < 0:
            ss = 0
        if ss > 59:
            ss = 59

        self.dev_time_min = f"{mm:02d}"
        self.dev_time_sec = f"{ss:02d}"
        self.development_time = f"{mm:02d}:{ss:02d}"

    def open_dev_min(self):
        def _on_ok(value_float, text_str):
            try:
                v = int(float((text_str or "0").replace(",", ".")))
            except Exception:
                v = 0
            if v < 0:
                v = 0
            if v > 99:
                v = 99
            self.dev_time_min = f"{v:02d}"
            self._sync_dev_time()

        NumericKeypadPopup(
            title="Development Time - Minutes",
            initial_text=self.dev_time_min or "00",
            max_decimals=0,
            min_value=0,
            max_value=99,
            on_ok=_on_ok
        ).open()

    def open_dev_sec(self):
        def _on_ok(value_float, text_str):
            try:
                v = int(float((text_str or "0").replace(",", ".")))
            except Exception:
                v = 0
            if v < 0:
                v = 0
            if v > 59:
                v = 59
            self.dev_time_sec = f"{v:02d}"
            self._sync_dev_time()

        NumericKeypadPopup(
            title="Development Time - Seconds",
            initial_text=self.dev_time_sec or "00",
            max_decimals=0,
            min_value=0,
            max_value=59,
            on_ok=_on_ok
        ).open()

    # ---------------------------------------------------------
    # Save
    # ---------------------------------------------------------
    def _project_root(self) -> Path:
        try:
            if getattr(sys, "frozen", False):
                return Path(sys.executable).resolve().parent
            return Path(__file__).resolve().parents[1]
        except Exception:
            return Path(".").resolve()

    #def _project_root(self) -> Path:
    #    try:
    #        return Path(__file__).resolve().parents[1]
    #    except Exception:
    #        return Path(".").resolve()

    def _sanitize_name(self, s: str) -> str:
        s = (s or "").strip()
        s = re.sub(r"[\\/:*?\"<>|]+", "_", s)
        s = re.sub(r"\s+", " ", s).strip()
        return s

    def _to_int(self, s):
        try:
            return int(float(str(s).replace(",", ".")))
        except Exception:
            return None

    def _to_float(self, s):
        try:
            return float(str(s).replace(",", "."))
        except Exception:
            return None

    def _resolve_origin_png(self, stem: str) -> str:
        if not stem:
            return ""
        p = self._project_root() / "assets" / "origin" / f"{stem}.png"
        return str(p) if p.exists() else ""

    def save_profile(self):
        name = self._sanitize_name(self.profile_name) or "Profile"
        folder = self._sanitize_name(self.active_folder) or "Default"

        target_dir = self._project_root() / "profiles" / folder
        target_dir.mkdir(parents=True, exist_ok=True)

        fpath = target_dir / f"{name}.json"

        # dev time sync (her ihtimale karşı)
        self._sync_dev_time()

        data = {
            "profile_name": name,
            "coffee_origin": self.coffee_origin,
            "coffee_origin_png": self.coffee_origin_png,

            "drop_down_temp": self._to_float(self.drop_down_temp),
            "first_crack_temp": self._to_float(self.first_crack_temp),
            "second_crack_temp": self._to_float(self.second_crack_temp),
            "drop_out_temp": self._to_float(self.drop_out_temp),

            "hopper_open_time": self._to_int(self.hopper_open_time),
            "chaffing": self._to_int(self.chaffing),
            "chaffing_time": self._to_int(self.chaffing_time),

            "dd_p1": self._to_int(self.dd_p1),
            "dd_p2": self._to_int(self.dd_p2),
            "hop_p1": self._to_int(self.hop_p1),
            "hop_p2": self._to_int(self.hop_p2),
            "ch_p1": self._to_int(self.ch_p1),
            "ch_p2": self._to_int(self.ch_p2),
            "ct_p1": self._to_int(self.ct_p1),
            "ct_p2": self._to_int(self.ct_p2),
            "fc_p1": self._to_int(self.fc_p1),
            "fc_p2": self._to_int(self.fc_p2),
            "sc_p1": self._to_int(self.sc_p1),
            "sc_p2": self._to_int(self.sc_p2),
            "do_p1": self._to_int(self.do_p1),
            "do_p2": self._to_int(self.do_p2),

            "profile_mode": (self.profile_mode or "standard"),
            "development_time": (self.development_time or "00:00"),
            "development_time_sec": self._parse_mmss_to_seconds(self.development_time),

            # İstersen JSON’da ayrı da dursun:
            "dev_time_min": self.dev_time_min,
            "dev_time_sec": self.dev_time_sec,
        }

        try:
            fpath.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"[ProfileDetailScreen] SAVED -> {fpath}")

            old = (self.loaded_stem or "").strip()
            if old and old != name:
                old_path = target_dir / f"{old}.json"
                if old_path.exists() and old_path != fpath:
                    try:
                        old_path.unlink()
                    except Exception as e:
                        print(f"[ProfileDetailScreen] old file delete error: {e}")

            self.loaded_stem = name
            self._toast(f"Saved: {name}")

        except Exception as e:
            print(f"[ProfileDetailScreen] Save error: {e}")
            self._toast("Save error!")

    def confirm_send_to_plc(self):
        from kivy.factory import Factory

        inner = BoxLayout(orientation="vertical", spacing=dp(14), padding=(dp(6), dp(6)))

        msg = Label(
            text="Send this profile to PLC?",
            font_size="20sp",
            bold=True,
            color=(1, 1, 1, 1),
            size_hint_y=None,
            height=dp(34),
            halign="center",
            valign="middle",
        )
        msg.bind(size=lambda w, *_: setattr(w, "text_size", w.size))
        inner.add_widget(msg)

        name = Label(
            text=self.profile_name or "",
            font_size="22sp",
            bold=True,
            color=(1, 1, 1, 1),
            size_hint_y=None,
            height=dp(34),
            halign="center",
            valign="middle",
        )
        name.bind(size=lambda w, *_: setattr(w, "text_size", w.size))
        inner.add_widget(name)

        inner.add_widget(Factory.Widget(size_hint_y=None, height=dp(10)))

        row = BoxLayout(size_hint_y=None, height=dp(56), spacing=dp(14))
        b_no = Factory.RoundedPopupButtonSmall(text="No")
        b_yes = Factory.RoundedPopupButtonSmall(text="Yes")
        row.add_widget(b_no)
        row.add_widget(b_yes)
        inner.add_widget(row)

        card = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(12))
        card.add_widget(inner)

        def _redraw(*_):
            card.canvas.before.clear()
            with card.canvas.before:
                Color(0.12, 0.13, 0.16, 1)
                RoundedRectangle(pos=card.pos, size=card.size, radius=[dp(22)] * 4)

        card.bind(pos=_redraw, size=_redraw)
        _redraw()

        pop = Popup(
            title="",
            content=card,
            size_hint=(None, None),
            size=(dp(560), dp(300)),
            auto_dismiss=False,
            separator_height=0,
            background="",
            background_color=(0, 0, 0, 0),
        )

        b_no.bind(on_release=lambda *_: pop.dismiss())

        def _yes(*_):
            pop.dismiss()
            self.send_to_plc()

        b_yes.bind(on_release=_yes)
        pop.open()

    def exit_screen(self):
        target = self.return_screen or "profile"
        if self.manager and self.manager.has_screen(target):
            scr = self.manager.get_screen(target)
            if self.return_to_files and hasattr(scr, "_keep_mode"):
                scr._keep_mode = True
                scr._keep_folder = self.active_folder or ""
            self.manager.current = target
        else:
            self.manager.current = "profile"

    # ---------------------------------------------------------
    # Toast
    # ---------------------------------------------------------
    def _toast(self, msg: str):
        from kivy.factory import Factory

        inner = BoxLayout(orientation="vertical", spacing=dp(14))

        lbl = Label(
            text=msg,
            font_size="20sp",
            bold=True,
            color=(1, 1, 1, 1),
            halign="center",
            valign="middle",
        )
        lbl.bind(size=lambda w, *_: setattr(w, "text_size", w.size))
        inner.add_widget(lbl)

        btn = Factory.RoundedPopupButton(text="OK")
        inner.add_widget(btn)

        card = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(12))
        card.add_widget(inner)

        def _redraw(*_):
            card.canvas.before.clear()
            with card.canvas.before:
                Color(0.12, 0.13, 0.16, 1)
                RoundedRectangle(pos=card.pos, size=card.size, radius=[dp(22)] * 4)

        card.bind(pos=_redraw, size=_redraw)
        _redraw()

        pop = Popup(
            title="",
            content=card,
            size_hint=(None, None),
            size=(dp(520), dp(240)),
            auto_dismiss=False,
            separator_height=0,
            background="",
            background_color=(0, 0, 0, 0),
        )

        btn.bind(on_release=lambda *_: pop.dismiss())
        pop.open()

    # ---------------------------------------------------------
    # PLC write helpers
    # ---------------------------------------------------------
    def _get_modbus_client(self):
        try:
            if self.manager and self.manager.has_screen("live"):
                live = self.manager.get_screen("live")
                c = getattr(live, "client", None)
                if c:
                    return c
        except Exception:
            pass

        app = App.get_running_app()
        for attr in ("modbus_client", "modbus", "client"):
            c = getattr(app, attr, None)
            if c:
                return c
        return None

    def _write_register_safe(self, client, reg: int, value: int):
        try:
            r = client.write_single_register(reg, int(value))
            if isinstance(r, tuple) and len(r) == 2:
                ok, err = r
                return bool(ok), err
            return bool(r), None
        except Exception as e:
            return False, str(e)

    def read_mode_from_plc(self):
        client = self._get_modbus_client()
        if not client:
            print("[ProfileDetailScreen] Modbus client not found while reading MW615.")
            return

        vals, err = client.read_holding_n(int(self.MW_MODE_FLAG), 1)  # MW615 oku
        if vals is None or len(vals) < 1:
            print(f"[ProfileDetailScreen] MW{self.MW_MODE_FLAG} read error: {err}")
            return

        mode_raw = int(vals[0])
        print(f"[ProfileDetailScreen] MW{self.MW_MODE_FLAG} = {mode_raw}")

        if mode_raw == 1:
            self.set_profile_mode("dev")
        else:
            self.set_profile_mode("standard")


    def _mw_map_from_ui(self):
        """
        SEND TO PLC mapping (STD/DEV fark etmez -> TÜM parametreler yazılır)

        Temps/Times:
          MW580 drop_down_temp (x10)
          MW581 hopper_open_time
          MW700 chaffing
          MW702 chaffing_time
          MW582 first_crack_temp (x10)
          MW584 second_crack_temp (x10)
          MW586 drop_out_temp (x10)

        Percents:
          MW590 dd_p1
          MW600 dd_p2
          MW591 hop_p1
          MW601 hop_p2
          MW701 ch_p1
          MW607 ch_p2
          MW602 ct_p2
          MW592 fc_p1
          MW604 fc_p2
          MW594 sc_p1
          MW605 sc_p2
          MW596 do_p1
          MW606 do_p2

        Extra:
          MW615 mode flag (STD=0, DEV=1)
          MW608 dev_time_min (HER ZAMAN yazılır)
          MW609 dev_time_sec (HER ZAMAN yazılır)

        Not:
          - DEV/STD ayrımıyla hiçbir parametre silinmez.
          - MW_DEV_TIME (toplam saniye) yazılmaz.
        """
        m = {}

        # --- MODE FLAG: her zaman yazılsın (STD=0, DEV=1)
        mode = (self.profile_mode or "standard").strip().lower()
        m[int(self.MW_MODE_FLAG)] = 1 if mode == "dev" else 0

        def t10(s):
            try:
                v = self._to_float(s)
                if v is None:
                    return 0
                return int(round(v * 10.0))
            except Exception:
                return 0

        # --- Temperature / Time
        m[580] = t10(self.drop_down_temp)
        m[581] = self._to_int(self.hopper_open_time) or 0
        m[700] = self._to_int(self.chaffing) or 0
        m[702] = self._to_int(self.chaffing_time) or 0
        m[582] = t10(self.first_crack_temp)

        # --- Second Crack / Drop Out (STD/DEV fark etmeden yazılır)
        m[584] = t10(self.second_crack_temp)
        m[586] = t10(self.drop_out_temp)

        # --- Percents (STD/DEV fark etmeden yazılır)
        m[590] = self._to_int(self.dd_p1) or 0
        m[600] = self._to_int(self.dd_p2) or 0
        m[591] = self._to_int(self.hop_p1) or 0
        m[601] = self._to_int(self.hop_p2) or 0
        m[701] = self._to_int(self.ch_p1) or 0
        m[607] = self._to_int(self.ch_p2) or 0
        m[703] = self._to_int(self.ct_p1) or 0  # ✅ NEW: Chaffing Time Exhaust %
        m[602] = self._to_int(self.ct_p2) or 0
        m[592] = self._to_int(self.fc_p1) or 0
        m[604] = self._to_int(self.fc_p2) or 0

        m[594] = self._to_int(self.sc_p1) or 0
        m[605] = self._to_int(self.sc_p2) or 0
        m[596] = self._to_int(self.do_p1) or 0
        m[606] = self._to_int(self.do_p2) or 0

        # --- Development Time: HER ZAMAN yaz (STD/DEV fark etmez)
        self._sync_dev_time()

        try:
            mm = int(self.dev_time_min or "0")
        except Exception:
            mm = 0

        try:
            ss = int(self.dev_time_sec or "0")
        except Exception:
            ss = 0

        if mm < 0:
            mm = 0
        if mm > 99:
            mm = 99
        if ss < 0:
            ss = 0
        if ss > 59:
            ss = 59

        m[int(self.MW_DEV_MIN)] = int(mm)  # MW608
        m[int(self.MW_DEV_SEC)] = int(ss)  # MW609

        # NOT: MW_DEV_TIME (toplam saniye) yazmıyoruz (istenmedi)

        return m


    def send_to_plc(self):
        client = self._get_modbus_client()
        if not client:
            self._toast("Modbus client not found in App (modbus_client/modbus/client).")
            return

        # DEV validation
        if (self.profile_mode or "standard") == "dev":
            self._sync_dev_time()

            # mm/ss valid mi
            try:
                mm = int(self.dev_time_min or "0")
                ss = int(self.dev_time_sec or "0")
            except Exception:
                self._toast("DEV mode: Development Time invalid.")
                return

            if mm < 0 or mm > 99 or ss < 0 or ss > 59:
                self._toast("DEV mode: Development Time out of range.")
                return

            # register check
            if int(self.MW_DEV_MIN or 0) <= 0 or int(self.MW_DEV_SEC or 0) <= 0:
                self._toast("DEV mode: MW_DEV_MIN / MW_DEV_SEC is not set!")
                return

        mw_map = self._mw_map_from_ui()

        errors = []
        for reg in sorted(mw_map.keys()):
            ok, err = self._write_register_safe(client, reg, mw_map[reg])
            if not ok:
                errors.append(f"MW{reg}: {err or 'write failed'}")

        if errors:
            print("[ProfileDetailScreen] PLC write errors:", errors)
            self._toast("PLC write error!\n" + "\n".join(errors[:6]))
            return

        self.manager.current = "live"


        print("[ProfileDetailScreen] Screen 'live' not found.")
        if self.manager:
            print("Available:", [s.name for s in self.manager.screens])