from kivy.uix.screenmanager import Screen
from kivy.app import App
from kivy.clock import Clock
from kivy.properties import StringProperty, NumericProperty

from services.numeric_keypad import NumericKeypadPopup


def fmt_tr_temp(val_c: float) -> str:
    try:
        return f"{val_c:.1f}°C".replace(".", ",")
    except Exception:
        return "0,0°C"


def fmt_pct(v: int) -> str:
    try:
        return f"{int(v)}%"
    except Exception:
        return "0%"


def fmt_mmss(total_seconds: int) -> str:
    try:
        if total_seconds < 0:
            total_seconds = 0
        m = total_seconds // 60
        s = total_seconds % 60
        return f"{m:02d}:{s:02d}"
    except Exception:
        return "00:00"


class ManualControlScreen(Screen):
    # ---------------- top cards ----------------
    set_text = StringProperty("0,0°C")          # editable
    drum_temp_text = StringProperty("0,0°C")    # read-only
    exhaust_temp_text = StringProperty("0,0°C") # read-only

    # ---------------- edit cards ----------------
    burner_pct_text = StringProperty("0%")
    exhaust_pct_text = StringProperty("0%")
    drum_pct_text = StringProperty("0%")
    cooling_time_text = StringProperty("00:00")

    mixer_on_text = StringProperty("00:00")
    mixer_off_text = StringProperty("00:00")

    cooling_start_delay_text = StringProperty("0")  # MW3014 (sec)
    shutdown_start_delay_text = StringProperty("0")  # MW3014 (sec)

    # ---------------- button status (0/1/2) read from MW200.. ----------------
    drum_status = NumericProperty(0)     # MW200
    burner_status = NumericProperty(0)   # MW201
    mixer_status = NumericProperty(0)    # MW202
    cooler_status = NumericProperty(0)   # MW203
    cooling_status = NumericProperty(0)  # MW204
    destoner_status = NumericProperty(0)  # MW3015 (0/1/2) -> Destoner button
    shutdown_status = NumericProperty(0)

    last_msg = StringProperty("—")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.client = None
        self._poll_ev = None

        # =========================================================
        # NEW PLC MAP (senin verdiğin)
        # =========================================================

        # ---- COIL toggles (M bits) ----
        self.COIL_DRUM   = 50   # M50
        self.COIL_BURNER = 51   # M51
        self.COIL_MIXER  = 52   # M52
        self.COIL_COOLER = 53   # M53

        self.COIL_DESTONER = 55  # M55

        self.COIL_SHUTDOWN = 59  # M59

        # COOLING artık COIL değil -> MW2201 (0/1)
        self.REG_COOLING_CMD = 2201

        # ---- WRITE registers (manual edits) ----
        self.REG_EXHAUST_PCT      = 20
        self.REG_BURNER_PCT       = 30
        self.REG_DRUM_PCT         = 200
        self.REG_SET_VALUE_X10    = 240   # x10
        self.REG_BEAN_X10         = 250   # x10 (şimdilik sadece okuma göstereceğiz)
        self.REG_EXHTEMP_X10      = 260   # x10 (şimdilik sadece okuma göstereceğiz)

        self.REG_COOLING_TIME_SEC = 2260
        self.REG_MIXER_ON_SEC     = 2261
        self.REG_MIXER_OFF_SEC    = 2262

        # ---- READ block (tek seferde) MW3000..MW3014 (15 word) ----
        self.READ_BASE = 3000
        self.READ_QTY = 17  # MW3000..MW3016

    # =========================================================
    # lifecycle
    # =========================================================
    def on_enter(self, *args):
        try:
            App.get_running_app().active_tab = "manual"
        except Exception:
            pass

        self._attach_client_from_live()
        self._resume_poll()

    def on_leave(self, *args):
        self._pause_poll()

    def go_back(self):
        try:
            if self.manager:
                self.manager.current = "live"
        except Exception:
            pass

    def _attach_client_from_live(self):
        c = None
        src = ""

        if self.manager:
            # 1) live
            try:
                live = self.manager.get_screen("live")
                c = getattr(live, "client", None) or getattr(live, "modbus", None)
                src = 'manager.get_screen("live")'
            except Exception:
                c = None

            # 2) live_roast
            if c is None:
                try:
                    live2 = self.manager.get_screen("live_roast")
                    c = getattr(live2, "client", None) or getattr(live2, "modbus", None)
                    src = 'manager.get_screen("live_roast")'
                except Exception:
                    c = None

        # 3) App attribute (opsiyonel)
        if c is None:
            try:
                app = App.get_running_app()
                c = getattr(app, "client", None) or getattr(app, "modbus_client", None)
                if c is not None:
                    src = "App attribute"
            except Exception:
                c = None

        self.client = c
        self.last_msg = f"Client OK ({src})" if self.client else "Client yok"

    # =========================================================
    # polling
    # =========================================================
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
            self._poll_ev = Clock.schedule_interval(self.poll, 0.5)

    @staticmethod
    def _safe_int(x, default=0) -> int:
        try:
            return int(x)
        except Exception:
            return default


    def poll(self, _dt):

        if not self.client:
            return

        # Tek blok okuma: MW3000..MW3017
        try:
            vals, err = self.client.read_holding_n(self.READ_BASE, self.READ_QTY)
        except Exception as e:
            self.last_msg = f"MW read exception: {e}"
            return

        if vals is None or len(vals) < self.READ_QTY:
            self.last_msg = f"MW read fail: {err}"
            return

        print("[MANUAL] MW3000..MW3014 =", vals)

        # ---- Status (MW3000..MW3004) ----
        self.drum_status    = self._safe_int(vals[0], 0)
        self.burner_status  = self._safe_int(vals[1], 0)
        self.mixer_status   = self._safe_int(vals[2], 0)
        self.cooler_status  = self._safe_int(vals[3], 0)
        self.cooling_status = self._safe_int(vals[4], 0)
        self.destoner_status = self._safe_int(vals[15], 0)  # MW3015
        self.shutdown_status = self._safe_int(vals[16], 0)  # MW3016

        # ---- Percents ----
        exh_raw = self._safe_int(vals[5], 0)  # MW3005 (RAW 0..500)
        exh_pct = exh_raw // 5  # RAW 0..500 -> % 0..100
        self.exhaust_pct_text = fmt_pct(exh_pct)

        burner_pct = self._safe_int(vals[6], 0)   # MW3006

        drum_raw = self._safe_int(vals[7], 0)  # MW3007
        drum_pct = drum_raw / 10  # integer böl
        self.drum_pct_text = fmt_pct(drum_pct)

        #self.exhaust_pct_text = fmt_pct(exh_pct)
        self.burner_pct_text  = fmt_pct(burner_pct)
        #self.drum_pct_text    = fmt_pct(drum_pct)

        # ---- Temps / Set ----
        set_raw  = self._safe_int(vals[8], 0)     # MW3008 (x10)
        bean_raw = self._safe_int(vals[9], 0)     # MW3009 (x10)
        exh_raw  = self._safe_int(vals[10], 0)    # MW3010 (x10)

        self.set_text          = fmt_tr_temp(set_raw / 10.0)
        self.drum_temp_text    = fmt_tr_temp(bean_raw / 10.0)    # UI'da Drum Temp yazıyorsa ama sen BEAN veriyorsun: İstersen isim değiştiririz
        self.exhaust_temp_text = fmt_tr_temp(exh_raw / 10.0)

        # ---- Times ----
        cool_sec = self._safe_int(vals[11], 0)    # MW3011
        mix_on   = self._safe_int(vals[12], 0)    # MW3012
        mix_off  = self._safe_int(vals[13], 0)    # MW3013

        cool_start_delay = self._safe_int(vals[14], 0)  # MW3014
        self.cooling_start_delay_text = str(int(cool_start_delay))

        self.cooling_time_text = str(int(cool_sec))
        self.mixer_on_text = str(int(mix_on))
        self.mixer_off_text = str(int(mix_off))



    # =========================================================
    # KV -> open_edit("...")
    # =========================================================
    def open_edit(self, target: str):
        if not self.client:
            self.last_msg = "Client yok"
            return

        # --- hangi alan, hangi register? ---
        if target == "set":
            title = "Set Value (°C)"
            current = (self.set_text or "").replace("°C", "").strip()
            if not current:
                current = "0,0"
            reg = self.REG_SET_VALUE_X10
            scale_x10 = True
            vmin, vmax = 0, 400

        elif target == "burner_pct":
            title = "Burner (%)"
            current = (self.burner_pct_text or "0%").replace("%", "").strip()
            reg = self.REG_BURNER_PCT
            scale_x10 = False
            vmin, vmax = 0, 100

        elif target == "exhaust_pct":
            title = "Exhaust (%)"
            current = (self.exhaust_pct_text or "0%").replace("%", "").strip()
            reg = self.REG_EXHAUST_PCT
            scale_x10 = False  # burada önemsiz; aşağıda özel çevireceğiz
            vmin, vmax = 0, 100

        elif target == "drum_pct":
            title = "Drum (%)"
            current = (self.drum_pct_text or "0%").replace("%", "").strip()
            reg = self.REG_DRUM_PCT
            scale_x10 = True
            vmin, vmax = 0, 100

        elif target == "cooling_time":
            title = "Cooling Time (sec)"
            # mm:ss -> saniye çevirmeyelim, kullanıcı direkt saniye girsin
            current = "0"
            reg = self.REG_COOLING_TIME_SEC
            scale_x10 = False
            vmin, vmax = 0, 60 * 60

        elif target == "mixer_on":
            title = "Mixer ON Time (sec)"
            current = "0"
            reg = self.REG_MIXER_ON_SEC
            scale_x10 = False
            vmin, vmax = 0, 60 * 60

        elif target == "mixer_off":
            title = "Mixer OFF Time (sec)"
            current = "0"
            reg = self.REG_MIXER_OFF_SEC
            scale_x10 = False
            vmin, vmax = 0, 60 * 60

        else:
            self.last_msg = f"Unknown edit target: {target}"
            return

        def _ok(val_float, _text):
            try:
                # Exhaust % özel scaling: %0..100 -> RAW 0..500
                if target == "exhaust_pct":
                    pct = int(val_float)  # ondalık yok
                    reg_value = pct * 5  # % -> RAW

                elif scale_x10:
                    # val_float bazen "39,7" gibi gelebilir -> güvenli parse
                    v = float(str(val_float).replace(",", "."))
                    reg_value = int(round(v * 10.0))
                else:
                    reg_value = int(val_float)


                ok, err = self.client.write_single_register(reg, reg_value)
                if ok:
                    self.last_msg = f"HR{reg} <= {reg_value}"
                else:
                    self.last_msg = f"HR{reg} write FAIL: {err}"
            except Exception as e:
                self.last_msg = f"Write exception: {e}"

        NumericKeypadPopup(
            title=title,
            initial_text=str(current),
            max_decimals=(1 if scale_x10 else 0),
            min_value=vmin,
            max_value=vmax,
            on_ok=_ok,
            on_cancel=lambda: None
        ).open()

    # =========================================================
    # coil toggles (FC05)
    # =========================================================
    def _toggle_coil(self, coil_addr: int):
        if not self.client:
            self.last_msg = "Client yok"
            return

        # Hangi coil hangi status'a bağlı?
        status_map = {
            self.COIL_DRUM: ("DRUM", int(getattr(self, "drum_status", 0))),
            self.COIL_BURNER: ("BURNER", int(getattr(self, "burner_status", 0))),
            self.COIL_MIXER: ("MIXER", int(getattr(self, "mixer_status", 0))),
            self.COIL_COOLER: ("COOLER", int(getattr(self, "cooler_status", 0))),
            self.COIL_DESTONER: ("DESTONER", int(getattr(self, "destoner_status", 0))),
            self.COIL_SHUTDOWN: ("SHUTDOWN", int(getattr(self, "shutdown_status", 0))),
        }

        name, cur = status_map.get(coil_addr, ("COIL", 0))
        new_val = False if cur == 1 else True  # toggle

        try:
            ok, err = self.client.write_single_coil(int(coil_addr), bool(new_val))
            if ok:
                self.last_msg = f"{name} -> {1 if new_val else 0}"
            else:
                self.last_msg = f"{name} FAIL: {err}"
        except Exception as e:
            self.last_msg = f"{name} exception: {e}"


    def toggle_drum(self):
        self._toggle_coil(self.COIL_DRUM)

    def toggle_burner(self):
        self._toggle_coil(self.COIL_BURNER)

    def toggle_mixer(self):
        self._toggle_coil(self.COIL_MIXER)

    def toggle_cooler(self):
        self._toggle_coil(self.COIL_COOLER)

    def toggle_destoner(self):
        self._toggle_coil(self.COIL_DESTONER)

    def toggle_cooling(self):
        if not self.client:
            self.last_msg = "Client yok"
            return

        # Status MW3004'ten geliyor: 0/1
        cur = int(getattr(self, "cooling_status", 0))
        new_val = 0 if cur == 1 else 1

        try:
            ok, err = self.client.write_single_register(int(self.REG_COOLING_CMD), int(new_val))
            if ok:
                self.last_msg = f"MW{self.REG_COOLING_CMD} <= {new_val}"
            else:
                self.last_msg = f"MW{self.REG_COOLING_CMD} write FAIL: {err}"
        except Exception as e:
            self.last_msg = f"Cooling write exception: {e}"


    def toggle_shutdown(self):
        self._toggle_coil(self.COIL_SHUTDOWN)
