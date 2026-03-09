from kivy.uix.screenmanager import Screen
from kivy.clock import Clock
from kivy.properties import NumericProperty, StringProperty, BooleanProperty

from kivy.uix.popup import Popup
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.metrics import dp
from kivy.app import App
from kivy.graphics import Color, RoundedRectangle

from services.numeric_keypad import NumericKeypadPopup

import time


class LiveRoastScreen(Screen):
    # ---------- KV bindings ----------
    m500_state = NumericProperty(0)  # COIL500 (0/1) -> ACTION button color + popup choice
    m501_state = NumericProperty(0)  # COIL501 (0/1) -> Make Profile button color + lock Profile Start

    # (Eski KV bağları için tutuluyor; m500_state ile senkron)
    profile_state = NumericProperty(0)

    set_text = StringProperty("0,0°C")           # MW2020 (x10)
    bean_text = StringProperty("0,0°C")          # MW2021 (x10)
    env_text = StringProperty("0,0°C")           # MW2022 (x10)

    airflow_ratio = NumericProperty(0.56)
    airflow_text = StringProperty("999 Pa")
    airflow_subtext = StringProperty("normal airflow")

    burner_ratio = NumericProperty(0.48)
    burner_text = StringProperty("48%")

    exhaust_ratio = NumericProperty(0.0)   # <-- Gauge için (0..1)
    speed_text = StringProperty("0%")

    roasttime_text = StringProperty("00:01")     # MW2026.. time
    drytime_text = StringProperty("00:02")
    miltime_text = StringProperty("00:03")
    devtime_text = StringProperty("00:04")
    ror_text = StringProperty("0,0 °C")
    ror_max_text = StringProperty("0,0 °C (max)")
    C_sec_text = StringProperty("0,0 °C/sn")

    profile_mode = StringProperty("standard")   # "standard" veya "dev"
    dev_time_min = StringProperty("00")         # DEV: mm
    dev_time_sec = StringProperty("00")         # DEV: ss

    banner_text = StringProperty("Ready")

    make_profile_ready = BooleanProperty(False)

    last_read = StringProperty("—")              # debug

    comm_ok = BooleanProperty(False)


    def __init__(self, **kw):
        # super() öncesi
        self._poll_ev = None
        self._profile_popup = None

        super().__init__(**kw)

        self.client = None

        # ==========================================================
        # ✅ LIVE ROAST SCREEN MAPPING
        # ==========================================================

        # ---- LIVE BLOCK (READ) MW2020..MW2025 ----
        self.LIVE_START = 2020
        self.LIVE_QTY = 6

        # ---- TIME/PHASE BLOCK (READ) MW2026..MW2042 ----
        # MW2038 -> m500, MW2039 -> banner code, MW2040 -> m501
        self.TIME_START = 2026
        self.TIME_QTY = 18  # 2026..2043

        # ---- SET VALUE (WRITE) MW240 ----
        self.REG_SET_WRITE = 240
        self.REG_EXH_WRITE = 20
        self.REG_BURNER_WRITE = 30

        # ---- PROFILE OVERLAY BLOCK (READ) MW2000..MW2006 ----
        self.PBLOCK_START = 2000
        self.PBLOCK_QTY = 20

        # ---- PROFILE (WRITE) MW200/201/202/203/210 ----
        self.PREG_DD_TEMP = 200
        self.PREG_FC_TEMP = 201
        self.PREG_SC_TEMP = 202
        self.PREG_OUT_TEMP = 203
        self.PREG_HOP_TIME = 210

        # ---- ROAST PROFILE STYLE (READ/WRITE) ----
        self.REG_PROFILE_MODE = 2043   # MW2043: 0=standard, 1=dev
        self.REG_PROFILE_MODE_WRITE = 615
        self.REG_DEV_MIN = 2044        # MW2044
        self.REG_DEV_SEC = 2045        # MW2045

        self.current_profile_name = ""  # PLC string tutmuyor; UI'dan gelen isim

        # ---- client ----
        from kivy.app import App
        app = App.get_running_app()
        self.client = getattr(app, "modbus_client", None)

        if self.client is None:
            print("[LiveRoast] ERROR: app.modbus_client is None")

        # ---- plot buffers ----
        self.xs = []
        self.bts = []
        self.exts = []  # Exhaust Temp series
        self.sets = []
        self.rors = []

        self.last_t = None  # son okunan tsec

        self._prev_banner_code = None
        # marker state (to avoid dropping multiple markers)
        self._mk0_set = False  # Open Hopper (banner=2)
        self._mk1_set = False
        self._mk2_set = False
        self._mk3_set = False
        self._mk4_set = False  # Turning Point (banner=4)

        self._plot_active_prev = False

        # placeholders
        self._airflow_pa = 168
        self._burner_pct = 48

        # ---- long press state (plot hold) ----
        self._plot_hold_touch = None
        self._plot_hold_ev = None
        self._plot_hold_active = False
        self._mode_popup = None

        # ---- reconnect state ----
        self._comm_error = False
        self._reconnect_busy = False
        self._last_reconnect_try = 0.0
        self._reconnect_interval = 2.0   # saniye

    def _check_connection_before_write(self):
        self._refresh_client_from_app()

        if self.client is None:
            self._set_comm_state(False)
            self.last_read = "No Modbus connection"
            return False

        return True

    def _refresh_client_from_app(self):
        try:
            app = App.get_running_app()
            self.client = getattr(app, "modbus_client", None)
        except Exception:
            self.client = None

    def on_enter(self, *args):
        App.get_running_app().active_tab = "live"
        self._attach_client_and_start()

    def on_leave(self, *args):
        self._pause_poll()

    # ---------- lifecycle ----------
    def on_kv_post(self, *_):
        from kivy.clock import Clock
        Clock.schedule_once(self._attach_client_and_start, 0.1)
        Clock.schedule_once(self._attach_client_and_start, 0.3)
        Clock.schedule_once(self._attach_client_and_start, 0.6)
        Clock.schedule_once(self._attach_client_and_start, 1.0)

    def _attach_client_and_start(self, *_):
        self._refresh_client_from_app()

        if self._poll_ev is None:
            print("[LiveRoast] start poll")
            self._resume_poll()


    def close_serial(self):
        self._pause_poll()
        try:
            self.client.close()
        except Exception:
            pass

    def _try_reconnect(self):
        now = time.time()

        if self._reconnect_busy:
            return False

        if (now - self._last_reconnect_try) < self._reconnect_interval:
            return False

        self._last_reconnect_try = now
        self._reconnect_busy = True

        try:
            app = App.get_running_app()

            # Eski client varsa kapat
            old_client = getattr(app, "modbus_client", None)
            if old_client is not None:
                try:
                    old_client.close()
                except Exception:
                    pass

            # App içindeki reconnect fonksiyonunu çağır
            new_client = None
            if hasattr(app, "reconnect_modbus"):
                new_client = app.reconnect_modbus()
            elif hasattr(app, "connect_modbus"):
                new_client = app.connect_modbus()

            self.client = getattr(app, "modbus_client", None)

            if self.client is not None:
                self._comm_error = False
                self._set_comm_state(True)
                self.last_read = "Modbus communication restored"
                return True

            self._set_comm_state(False)
            self.last_read = "Reconnect failed: client is None"
            return False

        except Exception as e:
            self.last_read = f"Reconnect error: {e}"
            return False

        finally:
            self._reconnect_busy = False


    # ---------- poll control ----------
    def _pause_poll(self):
        try:
            if self._poll_ev is not None:
                self._poll_ev.cancel()
        except Exception:
            pass
        self._poll_ev = None

    def _resume_poll(self):
        if self._poll_ev is None:
            Clock.schedule_once(self.poll, 0)
            self._poll_ev = Clock.schedule_interval(self.poll, 1.0)

    def _set_comm_state(self, ok: bool):
        self.comm_ok = bool(ok)

    # ---------- popup helpers ----------
    def _dark_popup(self, content_widget, w=520, h=300):
        pop = Popup(
            title="",
            content=content_widget,
            size_hint=(None, None),
            size=(dp(w), dp(h)),
            auto_dismiss=False,
            separator_height=0,
            background="",
            background_color=(0, 0, 0, 0),
        )
        return pop

    def _make_dark_card(self, inner, radius=22):
        card = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(12))
        card.add_widget(inner)

        def _redraw(*_):
            card.canvas.before.clear()
            with card.canvas.before:
                Color(0.12, 0.13, 0.16, 1)
                RoundedRectangle(pos=card.pos, size=card.size, radius=[dp(radius)] * 4)

        card.bind(pos=_redraw, size=_redraw)
        _redraw()
        return card

    def _popup_close(self, popup_obj):
        try:
            popup_obj.dismiss()
        except Exception:
            pass
        self._resume_poll()

    def _show_warning_popup(self, title_text: str, msg_text: str, w=720, h=320):
        self._pause_poll()
        from kivy.factory import Factory

        inner = BoxLayout(orientation="vertical", spacing=dp(14), padding=(dp(6), dp(6)))

        title = Label(
            text=title_text,
            font_size="22sp",
            bold=True,
            color=(1, 1, 1, 1),
            size_hint_y=None,
            height=dp(34),
            halign="center",
            valign="middle",
        )
        title.bind(size=lambda w, *_: setattr(w, "text_size", w.size))
        inner.add_widget(title)

        msg = Label(
            text=msg_text,
            font_size="18sp",
            color=(1, 1, 1, 1),
            halign="center",
            valign="middle",
        )
        msg.bind(size=lambda w, *_: setattr(w, "text_size", w.size))
        inner.add_widget(msg)

        inner.add_widget(Factory.Widget(size_hint_y=None, height=dp(10)))

        row = BoxLayout(size_hint_y=None, height=dp(56), spacing=dp(14))
        b_ok = Factory.RoundedPopupButtonSmall(text="OK")
        row.add_widget(b_ok)
        inner.add_widget(row)

        card = self._make_dark_card(inner, radius=22)
        pop = self._dark_popup(card, w=w, h=h)

        b_ok.bind(on_release=lambda *_: self._popup_close(pop))
        pop.open()

    def _toggle_profile_mode(self):
        new_mode = "dev" if self.profile_mode != "dev" else "standard"
        new_plc_val = 1 if new_mode == "dev" else 0

        try:
            ok, err = self.client.write_single_register(int(self.REG_PROFILE_MODE_WRITE), int(new_plc_val))
            if ok:
                self.last_read = f"MW{int(self.REG_PROFILE_MODE_WRITE)} <= {new_plc_val} (mode={new_mode})"
                self.profile_mode = new_mode
            else:
                self.last_read = f"MW{int(self.REG_PROFILE_MODE_WRITE)} write FAIL: {err}"
        except Exception as e:
            self.last_read = f"MW{int(self.REG_PROFILE_MODE_WRITE)} write EXC: {e}"


    # ==========================================================
    #  Plot long press (2s) -> confirm popup -> toggle MW2043
    #  KV: PlotHoldArea on_press/on_release burayı çağırır
    # ==========================================================

    def _plot_hold_start(self, *args):
        # tekrar tekrar schedule olmasın
        if self._plot_hold_active:
            return
        self._plot_hold_active = True

        # eski event varsa iptal
        if self._plot_hold_ev is not None:
            try:
                self._plot_hold_ev.cancel()
            except Exception:
                pass
            self._plot_hold_ev = None

        # 2sn sonra confirm popup aç
        self._plot_hold_ev = Clock.schedule_once(self._open_mode_change_confirm, 2.0)

    def _plot_hold_cancel(self, *args):
        self._plot_hold_active = False

        if self._plot_hold_ev is not None:
            try:
                self._plot_hold_ev.cancel()
            except Exception:
                pass
            self._plot_hold_ev = None

    def _open_mode_change_confirm(self, *_):
        # parmak hâlâ basılı mı? (release olduysa cancel zaten çağırır)
        if not self._plot_hold_active:
            return

        # artık tetiklenmesin
        self._plot_hold_active = False
        self._plot_hold_ev = None

        # popup zaten açıksa tekrar açma
        if self._mode_popup is not None:
            return

        # popup sırasında poll çakışmasın
        self._pause_poll()

        from kivy.factory import Factory

        inner = BoxLayout(orientation="vertical", spacing=dp(14), padding=(dp(6), dp(6)))

        title = Label(
            text="CONFIRM",
            font_size="22sp",
            bold=True,
            color=(1, 1, 1, 1),
            size_hint_y=None,
            height=dp(34),
            halign="center",
            valign="middle",
        )
        title.bind(size=lambda w, *_: setattr(w, "text_size", w.size))
        inner.add_widget(title)

        msg = Label(
            text="Are you sure to change\nroasting profile style?",
            font_size="20sp",
            color=(1, 1, 1, 1),
            halign="center",
            valign="middle",
        )
        msg.bind(size=lambda w, *_: setattr(w, "text_size", w.size))
        inner.add_widget(msg)

        inner.add_widget(Factory.Widget(size_hint_y=None, height=dp(8)))

        row = BoxLayout(size_hint_y=None, height=dp(56), spacing=dp(14))
        b_no = Factory.RoundedPopupButtonSmall(text="No")
        b_yes = Factory.RoundedPopupButtonSmall(text="Yes")
        row.add_widget(b_no)
        row.add_widget(b_yes)
        inner.add_widget(row)

        card = self._make_dark_card(inner, radius=22)
        pop = self._dark_popup(card, w=760, h=320)
        self._mode_popup = pop

        def _close(*_):
            try:
                pop.dismiss()
            except Exception:
                pass
            self._mode_popup = None
            self._resume_poll()

        def _yes(*_):
            try:
                current_is_dev = (self.profile_mode == "dev")
                target = 0 if current_is_dev else 1

                ok, err = self.client.write_single_register(int(self.REG_PROFILE_MODE_WRITE), int(target))
                if ok:
                    self.profile_mode = "dev" if int(target) == 1 else "standard"
                    self.last_read = f"MW{int(self.REG_PROFILE_MODE_WRITE)} <= {target}"
                else:
                    self.last_read = f"MW{int(self.REG_PROFILE_MODE_WRITE)} write FAIL: {err}"
            except Exception as e:
                self.last_read = f"MW{int(self.REG_PROFILE_MODE_WRITE)} write EXC: {e}"

            _close()

        b_no.bind(on_release=_close)
        b_yes.bind(on_release=_yes)
        pop.open()

    # ---------- COIL501 helpers ----------
    def _set_m501(self, value: int):
        if not self._check_connection_before_write():
            return False

        try:
            ok, err = self.client.write_single_coil(501, int(value))
            if ok:
                self.last_read = f"COIL501 <= {int(value)}"
                self._set_comm_state(True)
            else:
                self.last_read = f"COIL501 write FAIL: {err}"
                self._set_comm_state(False)
            return ok
        except Exception as e:
            self.last_read = f"COIL501 write EXC: {e}"
            self._set_comm_state(False)
            return False


    def _set_m500(self, value: int):
        """COIL500 yaz (Profile Start/Stop)"""
        if not self._check_connection_before_write():
            return False

        try:
            ok, err = self.client.write_single_coil(500, int(value))
            if ok:
                self.last_read = f"COIL500 <= {int(value)}"
                self._set_comm_state(True)
            else:
                self.last_read = f"COIL500 write FAIL: {err}"
                self._set_comm_state(False)
            return ok
        except Exception as e:
            self.last_read = f"COIL500 write EXC: {e}"
            self._set_comm_state(False)
            return False


    def open_profile_fullscreen_popup(self):

        # ✅ Make Profile aktifken Profile Start/Stop blok
        if int(self.m501_state) == 1:
            self._show_warning_popup(
                "MAKE PROFILE ACTIVE",
                "Make Profile is running.\nPlease finish/cancel Make Profile first."
            )
            return

        """
        KV: Profile Start/Stop butonu burayı çağırıyor.
        m500_state=0 -> Start confirm
        m500_state=1 -> Stop confirm
        """
        self._pause_poll()
        from kivy.factory import Factory

        running = (int(self.m500_state) == 1)
        title_text = "PROFILE STOP" if running else "PROFILE START"
        msg_text = "Do you want to stop the profile?" if running else "Do you want to start the profile?"
        yes_text = "Stop" if running else "Start"

        inner = BoxLayout(orientation="vertical", spacing=dp(14), padding=(dp(6), dp(6)))

        title = Label(
            text=title_text,
            font_size="22sp",
            bold=True,
            color=(1, 1, 1, 1),
            size_hint_y=None,
            height=dp(34),
            halign="center",
            valign="middle",
        )
        title.bind(size=lambda w, *_: setattr(w, "text_size", w.size))
        inner.add_widget(title)

        msg = Label(
            text=msg_text,
            font_size="20sp",
            color=(1, 1, 1, 1),
            halign="center",
            valign="middle",
        )
        msg.bind(size=lambda w, *_: setattr(w, "text_size", w.size))
        inner.add_widget(msg)

        inner.add_widget(Factory.Widget(size_hint_y=None, height=dp(8)))

        row = BoxLayout(size_hint_y=None, height=dp(56), spacing=dp(14))
        b_no = Factory.RoundedPopupButtonSmall(text="Cancel")
        b_yes = Factory.RoundedPopupButtonSmall(text=yes_text)
        row.add_widget(b_no)
        row.add_widget(b_yes)
        inner.add_widget(row)

        card = self._make_dark_card(inner, radius=22)
        pop = self._dark_popup(card, w=760, h=320)

        def _close(*_):
            try:
                pop.dismiss()
            except Exception:
                pass
            self._resume_poll()

        def _yes(*_):
            target = 0 if running else 1

            # COIL500 yaz
            ok = self._set_m500(target)

            # Eğer STOP ise (target=0) MW2200 de sıfırla
            if ok and target == 0:
                try:
                    self.client.write_single_register(2200, 0)
                except Exception as e:
                    print("MW2200 reset error:", e)

            _close()


        b_no.bind(on_release=_close)
        b_yes.bind(on_release=_yes)
        pop.open()


    def deactivate_make_profile(self):
        self._pause_poll()
        try:
            self._set_m501(0)
        finally:
            self._resume_poll()


    def open_profile_tab(self):

        # ✅ Make Profile aktifken Profile ekranına giriş blok + uyarı
        if int(self.m501_state) == 1 :
            self._show_warning_popup(
                "MAKE PROFILE BLOCKED",
                "You cannot start Make Profile\nwhile a profile is running."
            )
            return

        # normal: profile ekranına geç
        try:
            self.manager.current = "profile"
        except Exception as e:
            self.last_read = f"profile screen open failed: {e}"


    def open_make_profile_confirm(self):

        if int(self.m500_state) == 1 and int(self.m501_state) == 0:
            self._show_warning_popup(
                "MAKE PROFILE BLOCKED",
                "You cannot start Make Profile\nwhile a profile is running."
            )
            return

        if int(self.m501_state) == 1:
            try:
                self.manager.current = "make_profile"
            except Exception:
                pass
            return

        self._pause_poll()

        from kivy.factory import Factory

        inner = BoxLayout(orientation="vertical", spacing=dp(14), padding=(dp(6), dp(6)))

        title = Label(
            text="MAKE PROFILE",
            font_size="20sp",
            bold=True,
            color=(1, 1, 1, 1),
            size_hint_y=None,
            height=dp(28),
            halign="center",
            valign="middle",
        )
        title.bind(size=lambda w, *_: setattr(w, "text_size", w.size))
        inner.add_widget(title)

        msg = Label(
            text="Do you want to create a new profile?",
            font_size="22sp",
            bold=True,
            color=(1, 1, 1, 1),
            size_hint_y=None,
            height=dp(40),
            halign="center",
            valign="middle",
        )
        msg.bind(size=lambda w, *_: setattr(w, "text_size", w.size))
        inner.add_widget(msg)

        inner.add_widget(Factory.Widget(size_hint_y=None, height=dp(10)))

        row = BoxLayout(size_hint_y=None, height=dp(56), spacing=dp(14))
        b_cancel = Factory.RoundedPopupButtonSmall(text="Cancel")
        b_yes = Factory.RoundedPopupButtonSmall(text="Yes")
        row.add_widget(b_cancel)
        row.add_widget(b_yes)
        inner.add_widget(row)

        card = self._make_dark_card(inner, radius=22)
        pop = self._dark_popup(card, w=520, h=300)

        def _close(*_):
            try:
                pop.dismiss()
            except Exception:
                pass
            self._resume_poll()

        def _go(*_):
            try:
                pop.dismiss()
            except Exception:
                pass

            try:
                ps = self.manager.get_screen("profile")
                if hasattr(ps, "enter_make_profile_mode"):
                    ps.enter_make_profile_mode()
                self.manager.current = "profile"
            except Exception as e:
                self.last_read = f"open profile failed: {e}"

            self._resume_poll()

        b_cancel.bind(on_release=_close)
        b_yes.bind(on_release=_go)
        pop.open()

    # ---------- keypad ----------
    def open_set_value_keypad(self):
        self._pause_poll()

        current = (self.set_text or "").replace("°C", "").strip()

        def _cancel():
            self._resume_poll()

        def _ok(val_float, _text):
            reg_value = int(round(val_float * 10.0))  # MW240 x10

            if not self._check_connection_before_write():
                self._resume_poll()
                return

            try:
                ok, err = self.client.write_single_register(self.REG_SET_WRITE, reg_value)
                if ok:
                    self.last_read = f"MW{self.REG_SET_WRITE} <= {reg_value} yazıldı"
                    self._set_comm_state(True)
                else:
                    self.last_read = f"MW{self.REG_SET_WRITE} write FAIL: {err}"
                    self._set_comm_state(False)
            except Exception as e:
                self.last_read = f"MW{self.REG_SET_WRITE} write EXC: {e}"
                self._set_comm_state(False)

            self._resume_poll()


        NumericKeypadPopup(
            title="Set Value (°C)",
            initial_text=current,
            max_decimals=1,
            min_value=0,
            max_value=400,
            on_ok=_ok,
            on_cancel=_cancel
        ).open()

    def open_exhaust_speed_keypad(self):
        self._pause_poll()

        current = (self.speed_text or "").replace("%", "").strip()

        def _cancel():
            self._resume_poll()

        def _ok(val_float, _text):
            pct = int(round(val_float))
            if pct < 0:
                pct = 0
            elif pct > 100:
                pct = 100

            raw = int(pct * 5)  # 0..500

            if not self._check_connection_before_write():
                self._resume_poll()
                return

            try:
                ok, err = self.client.write_single_register(self.REG_EXH_WRITE, raw)
                if ok:
                    self.last_read = f"MW{self.REG_EXH_WRITE} <= {raw} (Exhaust {pct}%) yazıldı"
                else:
                    self.last_read = f"MW{self.REG_EXH_WRITE} write FAIL: {err}"
            except Exception as e:
                self.last_read = f"MW{self.REG_EXH_WRITE} write EXC: {e}"

            self._resume_poll()

        NumericKeypadPopup(
            title="Exhaust Speed (%)",
            initial_text=current,
            max_decimals=0,
            min_value=0,
            max_value=100,
            on_ok=_ok,
            on_cancel=_cancel
        ).open()

    def open_burner_keypad(self):
        self._pause_poll()

        current = (self.burner_text or "").replace("%", "").strip()

        def _cancel():
            self._resume_poll()

        def _ok(val_float, _text):
            pct = int(round(val_float))
            if pct < 0:
                pct = 0
            elif pct > 100:
                pct = 100

            reg = getattr(self, "REG_BURNER_WRITE", None)
            if reg is None:
                self.last_read = "REG_BURNER_WRITE tanımlı değil"
                self._resume_poll()
                return

            if not self._check_connection_before_write():
                self._resume_poll()
                return

            ok, err = self.client.write_single_register(int(reg), int(pct))
            if ok:
                self.last_read = f"MW{int(reg)} <= {int(pct)} yazıldı"
            else:
                self.last_read = f"MW{int(reg)} write FAIL: {err}"

            self._resume_poll()

        NumericKeypadPopup(
            title="Burner (%)",
            initial_text=current,
            max_decimals=0,
            min_value=0,
            max_value=100,
            on_ok=_ok,
            on_cancel=_cancel
        ).open()

    # ---------- utils ----------
    @staticmethod
    def _fmt_tr_temp(val: float) -> str:
        return f"{val:.1f}°C".replace(".", ",")

    @staticmethod
    def _fmt_tr_num(val: float, decimals: int = 1) -> str:
        return f"{val:.{decimals}f}".replace(".", ",")

    # ---------- plot helper ----------
    def _reset_series(self):
        self.xs.clear()
        self.bts.clear()
        self.exts.clear()
        self.sets.clear()
        self.rors.clear()

    def _upsert_point(self, tsec: int, bt: float, exh: float, setv: float, ror: float):
        if self.xs and int(self.xs[-1]) == int(tsec):
            self.bts[-1] = bt
            self.exts[-1] = exh
            self.sets[-1] = setv
            self.rors[-1] = ror
        else:
            self.xs.append(float(tsec))
            self.bts.append(bt)
            self.exts.append(exh)
            self.sets.append(setv)
            self.rors.append(ror)

    # ==========================================================
    # Overlay update (PLC -> transparent overlay text)
    # ==========================================================
    #def _update_overlay_from_plc(self, pvals, overlay_mode: str, dev_mmss: str = "00:00"):
    def _update_overlay_from_plc(self, pvals, overlay_mode: str, dev_mmss: str = "00:00", cht_exh_raw=None):
        def _set(k, v):
            try:
                if k in self.ids:
                    self.ids[k].text = v
            except Exception:
                pass

        def _fmt_temp_x10(raw):
            try:
                val = int(raw) / 10.0
                return f"{val:.1f} °C".replace(".", ",")
            except Exception:
                return "-- °C"

        def _fmt_sec(raw):
            try:
                return f"{int(raw)} sec"
            except Exception:
                return "-- sec"

        def _fmt_pct(raw):
            try:
                return f"{int(raw)} %"
            except Exception:
                return "-- %"

        # ---- values ----
        dd_val = pvals[0]
        hop_val = pvals[1]
        ch_val = pvals[2]
        cht_val = pvals[3]
        fc_val = pvals[4]
        sc_val = pvals[5]  # DEV'de de okunur ama gösterilmeyebilir
        out_val = pvals[6]

        # ---- percents ----
        dd_exh = pvals[7]
        hop_exh = pvals[8]
        ch_exh = pvals[9]
        fc_exh = pvals[10]
        sc_exh = pvals[11]
        out_exh = pvals[12]

        dd_flm = pvals[13]
        hop_flm = pvals[14]
        ch_flm = pvals[15]
        cht_flm = pvals[16]
        fc_flm = pvals[17]
        sc_flm = pvals[18]
        out_flm = pvals[19]

        # ---- DD ----
        _set("ov_dd_val", _fmt_temp_x10(dd_val))
        _set("ov_dd_exh", _fmt_pct(dd_exh))
        _set("ov_dd_flm", _fmt_pct(dd_flm))

        # ---- HOP ----
        _set("ov_hop_val", _fmt_sec(hop_val))
        _set("ov_hop_exh", _fmt_pct(hop_exh))
        _set("ov_hop_flm", _fmt_pct(hop_flm))

        # ---- CH (Chaffing) ----
        _set("ov_ch_val", _fmt_sec(ch_val))
        _set("ov_ch_exh", _fmt_pct(ch_exh))
        _set("ov_ch_flm", _fmt_pct(ch_flm))

        # ---- CHT (Chaffing Time) ----
        _set("ov_cht_val", _fmt_sec(cht_val))

        # CHT Exhaust % özel: MW2046’dan gelecek (varsa), yoksa "-- %"
        if cht_exh_raw is None:
            _set("ov_cht_exh", "-- %")
        else:
            _set("ov_cht_exh", _fmt_pct(cht_exh_raw))

        _set("ov_cht_flm", _fmt_pct(cht_flm))


        # ---- FC ----
        _set("ov_fc_val", _fmt_temp_x10(fc_val))
        _set("ov_fc_exh", _fmt_pct(fc_exh))
        _set("ov_fc_flm", _fmt_pct(fc_flm))

        # ✅ SC satırı: MW615=1 ise DEV TIME göster; değilse SC temp göster
        if overlay_mode == "dev":
            _set("ov_sc_val", dev_mmss)  # örn: "03:25"
            _set("ov_sc_exh", "-- %")
            _set("ov_sc_flm", "-- %")
        else:
            _set("ov_sc_val", _fmt_temp_x10(sc_val))
            _set("ov_sc_exh", _fmt_pct(sc_exh))
            _set("ov_sc_flm", _fmt_pct(sc_flm))

        # ---- OUT ----
        _set("ov_out_val", _fmt_temp_x10(out_val))
        _set("ov_out_exh", _fmt_pct(out_exh))
        _set("ov_out_flm", _fmt_pct(out_flm))

        _set("ov_mode", "DEV" if overlay_mode == "dev" else "STD")



    # ---------- main poll ----------
    def poll(self, _dt):
        self._refresh_client_from_app()
        if self.client is None:
            self._set_comm_state(False)
            self.last_read = "Modbus client is None, trying reconnect..."
            self._try_reconnect()
            return

        try:
            live_vals, err = self.client.read_holding_n(self.LIVE_START, self.LIVE_QTY)
        except Exception as e:
            self._comm_error = True
            self._set_comm_state(False)
            self.last_read = f"Read EXC LIVE: {e}"
            self._try_reconnect()
            return

        if live_vals is None or len(live_vals) < 6:
            self._comm_error = True
            self._set_comm_state(False)
            self.last_read = f"Read fail LIVE: {err}"
            self._try_reconnect()
            return


        try:
            tvals, err2 = self.client.read_holding_n(self.TIME_START, self.TIME_QTY)
        except Exception as e:
            self._comm_error = True
            self._set_comm_state(False)
            self.last_read = f"Read EXC TIME: {e}"
            self._try_reconnect()
            return

        if tvals is None or len(tvals) < self.TIME_QTY:
            self._comm_error = True
            self._set_comm_state(False)
            self.last_read = f"Read fail TIME: {err2}"
            self._try_reconnect()
            return

        self._comm_error = False
        self._set_comm_state(True)

        cht_exh_raw = None

        # ==========================================================
        # ✅ PROFILE OVERLAY (READ) + MODE (MW615) + DEV TIME (MW2044/2045)
        # ==========================================================
        cht_exh_raw = None

        try:
            # 1) MW2000..MW2019 oku
            pvals, perr = self.client.read_holding_n(int(self.PBLOCK_START), int(self.PBLOCK_QTY))
            if pvals is None or len(pvals) < int(self.PBLOCK_QTY):
                pvals = None

            # 2) MW615 oku (0=STD, 1=DEV)
            v615, e615 = self.client.read_holding_n(int(self.REG_PROFILE_MODE_WRITE), 1)  # 615
            if v615 is not None and len(v615) >= 1:
                mode_raw_615 = int(v615[0])
                overlay_mode = "dev" if mode_raw_615 == 1 else "standard"
            else:
                overlay_mode = self.profile_mode  # fallback

            # 3) DEV ise MW2044..MW2045 (dev min/sec) oku -> "mm:ss"
            dev_mmss = f"{self.dev_time_min}:{self.dev_time_sec}"
            if overlay_mode == "dev":
                dv, derr = self.client.read_holding_n(int(self.REG_DEV_MIN), 2)  # 2044,2045
                if dv is not None and len(dv) >= 2:
                    dmin = int(dv[0])
                    dsec = int(dv[1])
                    if dmin < 0: dmin = 0
                    if dmin > 99: dmin = 99
                    if dsec < 0: dsec = 0
                    if dsec > 59: dsec = 59
                    dev_mmss = f"{dmin:02d}:{dsec:02d}"
                    self.dev_time_min = f"{dmin:02d}"
                    self.dev_time_sec = f"{dsec:02d}"

            # 3.5) ✅ MW2046 oku (CHT Exhaust %)
            try:
                mv, em = self.client.read_holding_n(int(self.REG_PROFILE_MODE), 4)  # 2043..2046
                if mv is not None and len(mv) >= 4:
                    cht_exh_raw = int(mv[3])  # MW2046
            except Exception:
                pass

            # 4) overlay bas
            if pvals is not None:
                self._update_overlay_from_plc(
                    pvals,
                    overlay_mode,
                    dev_mmss=dev_mmss,
                    cht_exh_raw=cht_exh_raw
                )

        except Exception:
            pass


        # unpack LIVE
        set_raw = int(live_vals[0])
        bt_raw = int(live_vals[1])
        ex_raw = int(live_vals[2])
        sp_raw = int(live_vals[3])  # MW2023 (RAW 0..500)
        burner_raw = int(live_vals[4])
        airflow_raw = int(live_vals[5])

        setv = set_raw / 10.0
        bt = bt_raw / 10.0
        ex_temp = ex_raw / 10.0

        # Exhaust Speed scaling: RAW 0..500 -> % 0..100
        exh_pct = int(round(sp_raw / 5.0))
        if exh_pct < 0:
            exh_pct = 0
        elif exh_pct > 100:
            exh_pct = 100

        self.set_text = self._fmt_tr_temp(setv)
        self.bean_text = self._fmt_tr_temp(bt)
        self.env_text = self._fmt_tr_temp(ex_temp)
        self.speed_text = f"{exh_pct}%"
        self.exhaust_ratio = max(0.0, min(1.0, exh_pct / 100.0))

        self._burner_pct = int(burner_raw)
        self._airflow_pa = int(airflow_raw)

        # unpack TIME/PHASE
        r_min = int(tvals[0])
        r_sec = int(tvals[1])

        dry_min = int(tvals[2])
        dry_sec = int(tvals[3])
        dry_pct = int(tvals[4])

        mil_min = int(tvals[5])
        mil_sec = int(tvals[6])
        mil_pct = int(tvals[7])

        dev_min = int(tvals[8])
        dev_sec = int(tvals[9])
        dev_pct = int(tvals[10])

        ror_raw = int(tvals[11])
        ror = ror_raw / 10.0

        m500_raw = int(tvals[12])  # MW2038
        self.m500_state = 1 if m500_raw != 0 else 0
        self.profile_state = self.m500_state

        banner_code = int(tvals[13])  # MW2039
        m501_raw = int(tvals[14])     # MW2040
        self.m501_state = 1 if m501_raw != 0 else 0

        # MW2041 -> ROR MAX (x10)
        ror_max_raw = int(tvals[15])
        ror_max = ror_max_raw / 10.0
        self.ror_max_text = f"{self._fmt_tr_num(ror_max)} °C (max)"

        # MW2042 -> C/sec (x10)
        csec_raw = int(tvals[16])
        if csec_raw == 999:
            self.C_sec_text = "--- °C/sn"
        else:
            csec = csec_raw / 10.0
            self.C_sec_text = f"{self._fmt_tr_num(csec)} °C/sn"

        # ✅ MW2043..MW2046 oku (profile_mode + dev min/sec + chaffing time exhaust%)
        cht_exh_raw = None
        try:
            mv, em = self.client.read_holding_n(int(self.REG_PROFILE_MODE), 4)  # 2043..2046
            if mv is not None and len(mv) >= 4:
                mode_raw = int(mv[0])
                self.profile_mode = "dev" if mode_raw == 1 else "standard"

                dmin = int(mv[1])
                dsec = int(mv[2])
                self.dev_time_min = f"{dmin:02d}"
                self.dev_time_sec = f"{dsec:02d}"

                cht_exh_raw = int(mv[3])  # ✅ MW2046
        except Exception:
            pass

        # banner map
        banner_map = {
            0: "Machine Ready",
            1: "Heating Machine",
            2: "Open Hopper Gate",
            3: "Close Hopper Gate",
            4: "Turning Point",
            5: "First Crack",
            6: "First Crack",
            7: "Second Crack",
            8: "Second Crack",
            9: "Drop Out Coffee Beans",
            10: "Chaffing",
            11: "Emergency Stop",
        }
        self.banner_text = banner_map.get(banner_code, f"Status: {banner_code}")

        # time total sec (plot X)
        tsec = max(0, r_min * 60 + r_sec)

        # KV bindings (right panel)
        self.roasttime_text = f"{r_min:02d}:{r_sec:02d}"
        self.drytime_text = f"{dry_min:02d}:{dry_sec:02d}  {dry_pct} %"
        self.miltime_text = f"{mil_min:02d}:{mil_sec:02d}  {mil_pct} %"
        self.devtime_text = f"{dev_min:02d}:{dev_sec:02d}  {dev_pct} %"

        self.ror_text = f"{self._fmt_tr_num(ror)} °C"

        # Airflow gauge
        self.airflow_text = f"{self._airflow_pa} Pa"
        self.airflow_subtext = "normal airflow"
        self.airflow_ratio = max(0.0, min(1.0, self._airflow_pa / 300.0))

        # Burner gauge
        self.burner_text = f"{self._burner_pct}%"
        self.burner_ratio = max(0.0, min(1.0, self._burner_pct / 100.0))

        # plot reset (zaman geri sardıysa)
        if self.last_t is not None and tsec < self.last_t:
            self._reset_series()
            self._mk0_set = False
            self._mk1_set = False
            self._mk2_set = False
            self._mk3_set = False
            self._mk4_set = False
            self._prev_banner_code = None
            try:
                if "plot" in self.ids:
                    self.ids.plot.mk0_t = -1.0
                    self.ids.plot.mk1_t = -1.0
                    self.ids.plot.mk2_t = -1.0
                    self.ids.plot.mk3_t = -1.0
                    self.ids.plot.mk4_t = -1.0
            except Exception:
                pass
        self.last_t = tsec

        if int(self.m500_state) == 1 or int(self.m501_state) == 1:
            self._upsert_point(tsec=tsec, bt=bt, setv=setv, exh=ex_temp, ror=ror)

        # markers
        try:
            prev = self._prev_banner_code
            self._prev_banner_code = banner_code

            if (banner_code == 2) and (not self._mk0_set) and (prev != 2):
                self._mk0_set = True
                if "plot" in self.ids:
                    self.ids.plot.mk0_t = float(tsec)
                    self.ids.plot.mk0_bt = float(bt)

            if (banner_code == 4) and (not self._mk4_set) and (prev != 4):
                self._mk4_set = True
                if "plot" in self.ids:
                    self.ids.plot.mk4_t = float(tsec)
                    self.ids.plot.mk4_bt = float(bt)

            if (banner_code == 6) and (not self._mk1_set) and (prev != 6):
                self._mk1_set = True
                if "plot" in self.ids:
                    self.ids.plot.mk1_t = float(tsec)
                    self.ids.plot.mk1_bt = float(bt)

            if (banner_code == 8) and (not self._mk2_set) and (prev != 8):
                self._mk2_set = True
                if "plot" in self.ids:
                    self.ids.plot.mk2_t = float(tsec)
                    self.ids.plot.mk2_bt = float(bt)

            if (banner_code == 9) and (not self._mk3_set) and (prev != 9):
                self._mk3_set = True
                if "plot" in self.ids:
                    self.ids.plot.mk3_t = float(tsec)
                    self.ids.plot.mk3_bt = float(bt)

        except Exception:
            pass

        try:
            if int(self.m500_state) == 1 or int(self.m501_state) == 1:
                plot = self.ids.plot
                plot.x_series = self.xs[:]
                plot.bt_series = self.bts[:]
                plot.ex_series = self.exts[:]
                plot.set_series = self.sets[:]
                plot.ror_series = self.rors[:]
        except Exception:
            pass

        self.last_read = (
            f"SET={setv:.1f} "
            f"BT={bt:.1f} "
            f"EX={ex_temp:.1f} "
            f"t={self.roasttime_text} "
            f"ROR={ror:.1f}"
        ).replace(".", ",")