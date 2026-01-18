from kivy.uix.screenmanager import Screen
from kivy.clock import Clock
from kivy.properties import NumericProperty, StringProperty

from kivy.uix.popup import Popup
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.metrics import dp

from services.modbus_client import ModbusClient
from widgets.numeric_keypad import NumericKeypadPopup


class LiveRoastScreen(Screen):
    # ---------- KV bindings ----------
    profile_state = NumericProperty(0)           # HR106 -> buton rengi
    set_text = StringProperty("0,0°C")           # HR100

    bean_text = StringProperty("0,0°C")          # BT
    env_text = StringProperty("0,0°C")           # ENV (şimdilik bt+offset)
    speed_text = StringProperty("50,0 Hz")       # placeholder

    airflow_ratio = NumericProperty(0.56)
    airflow_text = StringProperty("168 Pa")
    airflow_subtext = StringProperty("normal airflow")

    burner_ratio = NumericProperty(0.48)
    burner_text = StringProperty("48%")

    roasttime_text = StringProperty("00:01")     # HR105 mm:ss
    drytime_text = StringProperty("00:02")
    miltime_text = StringProperty("00:03")
    devtime_text = StringProperty("00:04")
    ror_text = StringProperty("0,0 °C/sn")

    last_read = StringProperty("—")              # debug

    def __init__(self, **kw):
        # super() öncesi
        self._poll_ev = None
        self._profile_popup = None

        super().__init__(**kw)

        # ---- Modbus mapping ----
        self.START_REG = 100
        self.QTY = 11                     # HR100..HR110

        self.REG_SET = 100                # HR100
        self.REG_BT = 104                 # HR104
        self.REG_TIME = 105               # HR105
        self.REG_PROFILE = 106            # HR106
        self.REG_DRYTIME = 107            # HR107
        self.REG_MILTIME = 108            # HR108
        self.REG_DEVTIME = 109            # HR109
        self.REG_ROR = 110                # HR110

        # ---- client ----
        self.client = ModbusClient(port="COM5", baud=9600, slave=2, timeout=1.5)
        self.client.connect()

        # ---- plot buffers ----
        self.xs = []
        self.bts = []
        self.sets = []
        self.rors = []

        self.last_t = None  # son okunan tsec

        # placeholders
        self._airflow_pa = 168
        self._burner_pct = 48

    # ---------- lifecycle ----------
    def on_kv_post(self, *_):
        self._resume_poll()

    def close_serial(self):
        self._pause_poll()
        try:
            self.client.close()
        except Exception:
            pass

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
            self._poll_ev = Clock.schedule_interval(self.poll, 5.0)

    # ---------- keypad ----------
    def open_set_value_keypad(self):
        self._pause_poll()

        current = (self.set_text or "").replace("°C", "").strip()

        def _cancel():
            self._resume_poll()

        def _ok(val_float, _text):
            reg_value = int(round(val_float * 10.0))  # HR100 x10

            ok, err = self.client.write_single_register(self.REG_SET, reg_value)
            if ok:
                self.last_read = f"HR100 <= {reg_value} yazıldı"
            else:
                self.last_read = f"HR100 write FAIL: {err}"

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

    # ---------- popup ----------
    def open_profile_confirm(self):
        self._pause_poll()

        root = BoxLayout(orientation="vertical", spacing=dp(12), padding=dp(14))

        if int(self.profile_state) == 1:
            msg_text = "Devam Eden Profil İptal Edilsin mi ?"
            title = "PROFILE CANCEL"
        else:
            msg_text = "Seçilen profile başlasın mı?"
            title = "PROFILE START"

        msg = Label(text=msg_text, font_size="18sp", halign="center", valign="middle")
        msg.bind(size=lambda *_: setattr(msg, "text_size", msg.size))

        row = BoxLayout(orientation="horizontal", spacing=dp(12),
                        size_hint_y=None, height=dp(48))

        btn_yes = Button(text="EVET")
        btn_no = Button(text="HAYIR")

        row.add_widget(btn_yes)
        row.add_widget(btn_no)

        root.add_widget(msg)
        root.add_widget(row)

        self._profile_popup = Popup(
            title=title,
            content=root,
            size_hint=(None, None),
            size=(dp(520), dp(200)),
            auto_dismiss=False,
        )

        btn_no.bind(on_press=lambda *_: self._profile_no())
        btn_yes.bind(on_press=lambda *_: self._profile_yes())

        self._profile_popup.open()

    def _profile_no(self):
        try:
            if self._profile_popup:
                self._profile_popup.dismiss()
        except Exception:
            pass
        self._resume_poll()

    def _profile_yes(self):
        try:
            if self._profile_popup:
                self._profile_popup.dismiss()
        except Exception:
            pass

        value = 0 if int(self.profile_state) == 1 else 1
        self._write_profile(value)
        self._resume_poll()

    def _write_profile(self, value: int):
        try:
            ok, err = self.client.write_single_register(self.REG_PROFILE, int(value))
            if not ok:
                self.last_read = f"HR106 write FAIL: {err}"
                return

            vals, rerr = self.client.read_holding_n(self.REG_PROFILE, 1)
            if vals is None:
                self.last_read = f"HR106 write OK, readback FAIL: {rerr}"
                return

            self.profile_state = 1 if int(vals[0]) == 1 else 0
            self.last_read = f"HR106={int(vals[0])}"

        except Exception as e:
            self.last_read = f"HR106 exception: {e}"

    # ---------- utils ----------
    @staticmethod
    def _mmss(tsec: int) -> str:
        tsec = max(0, int(tsec))
        return f"{tsec // 60:02d}:{tsec % 60:02d}"

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
        self.sets.clear()
        self.rors.clear()

    def _upsert_point(self, tsec: int, bt: float, setv: float, ror: float):
        """
        Aynı saniye tekrar geldiyse son noktayı overwrite et,
        yeni saniyeyse append et.
        BT/SET/ROR aynı hızda, aynı indekslerle gider.
        """
        if self.xs and int(self.xs[-1]) == int(tsec):
            self.bts[-1] = bt
            self.sets[-1] = setv
            self.rors[-1] = ror
        else:
            self.xs.append(float(tsec))
            self.bts.append(bt)
            self.sets.append(setv)
            self.rors.append(ror)

    # ---------- main poll ----------
    def poll(self, _dt):
        vals, err = self.client.read_holding_n(self.START_REG, self.QTY)
        if vals is None:
            self.last_read = f"Read fail: {err}"
            return

        # --- unpack ---
        setv_raw = int(vals[0])            # HR100 x10
        bt_raw = int(vals[4])              # HR104
        tsec = int(vals[5])                # HR105
        profile = int(vals[6])             # HR106
        drysec = int(vals[7])              # HR107
        millsec = int(vals[8])             # HR108
        devsec = int(vals[9])              # HR109
        ror_raw = int(vals[10])            # HR110 x10

        setv = setv_raw / 10.0
        ror = ror_raw / 10.0

        # BT format (senin eski mantığın)
        bt = bt_raw / 10.0 if bt_raw > 300 else float(bt_raw)
        env = bt + 4.6

        # --- KV bindings ---
        self.profile_state = 1 if profile == 1 else 0
        self.roasttime_text = self._mmss(tsec)

        if tsec > 0:
            percent_dry = int((drysec / tsec) * 100)
            percent_mill = int((millsec / tsec) * 100)
            percent_dev = int((devsec / tsec) * 100)
        else:
            percent_dry = 0
            percent_mill = 0
            percent_dev = 0

        self.drytime_text = f"{self._mmss(drysec)}  {percent_dry} %"
        self.miltime_text = f"{self._mmss(millsec)}  {percent_mill} %"
        self.devtime_text = f"{self._mmss(devsec)}  {percent_dev} %"

        self.set_text = self._fmt_tr_temp(setv)
        self.bean_text = self._fmt_tr_temp(bt)
        self.env_text = self._fmt_tr_temp(env)

        self.ror_text = f"{self._fmt_tr_num(ror)} °C/sn"

        self.airflow_text = f"{self._airflow_pa} Pa"
        self.airflow_subtext = "normal airflow"
        self.airflow_ratio = max(0.0, min(1.0, self._airflow_pa / 300.0))

        self.burner_text = f"{self._burner_pct}%"
        self.burner_ratio = max(0.0, min(1.0, self._burner_pct / 100.0))

        # --- plot reset (zaman geri sardıysa) ---
        if self.last_t is not None and tsec < self.last_t:
            self._reset_series()

        self.last_t = tsec

        # --- upsert point (BT/SET/ROR aynı hızda) ---
        self._upsert_point(tsec=tsec, bt=bt, setv=setv, ror=ror)

        # --- push to plot widget ---
        try:
            plot = self.ids.plot
            plot.x_series = self.xs[:]       # time
            plot.bt_series = self.bts[:]      # BT
            plot.set_series = self.sets[:]    # SET
            plot.ror_series = self.rors[:]    # ROR
        except Exception:
            pass

        self.last_read = (
            f"HR100={setv:.1f} "
            f"BT={self._fmt_tr_temp(bt)} "
            f"t={self.roasttime_text} "
            f"HR106={profile} "
            f"ROR={ror:.1f}"
        ).replace(".", ",")






