# make_profile_screen.py
import json
import re
import sys
from pathlib import Path

from kivy.app import App
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.properties import (
    StringProperty,
    BooleanProperty,
    ListProperty,
    NumericProperty,
)
from kivy.uix.screenmanager import Screen
from kivy.uix.popup import Popup
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label

from services.numeric_keypad import NumericKeypadPopup
from services.text_keypad import TextKeypadPopup


class MakeProfileScreen(Screen):
    # ---------------------------------------------------------------------
    # PLC ADDRESS MAP (Send-to-PLC mapping ile AYNI)
    # ---------------------------------------------------------------------
    # Temps (x10)
    MW_DD_TEMP = 580
    MW_FC_TEMP = 582
    MW_SC_TEMP = 584
    MW_DO_TEMP = 586

    # Percents
    MW_DD_P1 = 590   # DD Exhaust
    MW_DD_P2 = 600   # DD Flame
    MW_FC_P1 = 592
    MW_FC_P2 = 604
    MW_SC_P1 = 594
    MW_SC_P2 = 605
    MW_DO_P1 = 596
    MW_DO_P2 = 606

    # Hopper / Chaffing
    MW_HOP_TIME = 581
    MW_HOP_P1 = 591
    MW_HOP_P2 = 601
    MW_CHAFF = 700
    MW_CH_P1 = 701
    MW_CH_P2 = 607
    MW_CT_TIME = 702
    MW_CT_P2 = 602


    # Make Profile stage registers
    MW_MP_STATE = 350
    MW_DD_DONE = 351
    MW_FC_DONE = 352
    MW_SC_DONE = 353
    MW_DO_DONE = 354

    MW_PROFILE_MODE = 615
    MW_DEV_MIN = 608
    MW_DEV_SEC = 609

    MW_CUR_DEV_MIN = 339
    MW_CUR_DEV_SEC = 340

    # ✅ NEW: Chaffing Time Exhaust % (READ from 2046, WRITE to 703)
    MW_CT_P1_READ = 2046
    MW_CT_P1_WRITE = 703

    REG_COOLING_CMD = 2201

    # ---------------------------------------------------------------------
    # ✅ STD / DEV MODE (ProfileDetailScreen ile aynı mantık)
    # - "standard": Second Crack + Drop Out görünür
    # - "dev": Development Time görünür (Second Crack/Drop Out saklanır)
    # ---------------------------------------------------------------------

    # PLC: MW615 (0=STD, 1=DEV)
    profile_mode = StringProperty("standard")

    # PLC: MW608/MW609
    dev_time_min = StringProperty("00")
    dev_time_sec = StringProperty("00")
    development_time = StringProperty("00:00")

    dev_min = StringProperty("")  # MW339 -> canlı gösterim
    dev_sec = StringProperty("")  # MW340 -> canlı gösterim

    # -------- from ProfileScreen --------
    selected_profile = StringProperty("")
    selected_folder = StringProperty("")
    selected_path = StringProperty("")

    # -------- Coffee origin --------
    coffee_origin = StringProperty("")
    coffee_origin_png = StringProperty("")

    # -------- Live values (right panel top) --------
    live_bean_temp = StringProperty("--")
    live_exhaust_pct = StringProperty("--")
    live_flame_pct = StringProperty("--")

    # -------- Editable / filled fields --------
    drop_down_temp = StringProperty("")
    first_crack_temp = StringProperty("")
    second_crack_temp = StringProperty("")
    drop_out_temp = StringProperty("")

    hopper_open_time = StringProperty("")
    chaffing = StringProperty("")
    chaffing_time = StringProperty("")

    dd_p1 = StringProperty("")
    dd_p2 = StringProperty("")
    hop_p1 = StringProperty("")
    hop_p2 = StringProperty("")
    ch_p1 = StringProperty("")
    ch_p2 = StringProperty("")
    ct_p1 = StringProperty("")
    ct_p2 = StringProperty("")
    fc_p1 = StringProperty("")
    fc_p2 = StringProperty("")
    sc_p1 = StringProperty("")
    sc_p2 = StringProperty("")
    do_p1 = StringProperty("")
    do_p2 = StringProperty("")


    # -------- PLC stage states --------
    mp_state = NumericProperty(0)   # MW350
    dd_done = NumericProperty(0)    # MW351
    fc_done = NumericProperty(0)    # MW352
    sc_done = NumericProperty(0)    # MW353
    do_done = NumericProperty(0)    # MW354

    # -------- Buttons (KV expects these) --------
    dd_disabled = BooleanProperty(True)
    fc_disabled = BooleanProperty(True)
    sc_disabled = BooleanProperty(True)
    do_disabled = BooleanProperty(True)

    dd_bg = ListProperty([0.16, 0.17, 0.20, 1])
    fc_bg = ListProperty([0.16, 0.17, 0.20, 1])
    sc_bg = ListProperty([0.16, 0.17, 0.20, 1])
    do_bg = ListProperty([0.16, 0.17, 0.20, 1])

    # -------- Stage auto-fill flags (font green control) --------
    dd_filled = BooleanProperty(False)
    fc_filled = BooleanProperty(False)
    sc_filled = BooleanProperty(False)
    do_filled = BooleanProperty(False)


    _poll_ev = None

    # ✅ popup açıkken sync ezmesin
    _editing_field = StringProperty("")

    # ✅ "Bu on_enter çağrısı aktif modda mı?" (girişte hangi sync yapılacak)
    _enter_sync_scheduled = False

    # ---------------- lifecycle ----------------
    def on_enter(self, *args):
        try:
            App.get_running_app().active_tab = "make_profile"
        except Exception:
            pass

        self._start_poll()

        client = self._get_modbus_client()
        if not client:
            return

        # Önce MW350..MW354 oku, sonra full sync.
        Clock.schedule_once(lambda *_: self._enter_sync(client), 0)

    def on_leave(self, *args):
        self._stop_poll()

    def _enter_sync(self, client):
        # Stage flags/state: MW350..MW354 oku
        vals_stage = self._read_n_safe(client, self.MW_MP_STATE, 5)
        if vals_stage and isinstance(vals_stage, (list, tuple)) and len(vals_stage) >= 5:
            self.mp_state = int(vals_stage[0] or 0)
            self.dd_done = int(vals_stage[1] or 0)
            self.fc_done = int(vals_stage[2] or 0)
            self.sc_done = int(vals_stage[3] or 0)
            self.do_done = int(vals_stage[4] or 0)

        # ---- Profile mode + dev time (MW608..609) ----
        vals_mode = self._read_n_safe(client, 2043, 3)
        if vals_mode and isinstance(vals_mode, (list, tuple)) and len(vals_mode) >= 3:
            pm = int(vals_mode[0] or 0)
            dmin = int(vals_mode[1] or 0)
            dsec = int(vals_mode[2] or 0)

            self.profile_mode = "dev" if pm == 1 else "standard"

            new_min = self._pad2(dmin)
            new_sec = self._pad2(dsec)

            if self._editing_field != "dev_time_min":
                self.dev_time_min = new_min
            if self._editing_field != "dev_time_sec":
                self.dev_time_sec = new_sec

            if self._editing_field not in ("dev_time_min", "dev_time_sec"):
                self._sync_dev_time()


        # HER ZAMAN: tüm alanları PLC'den oku
        self._sync_all_fields_from_plc(client)

        # buton durumlarını güncelle
        self._refresh_buttons()

    # ---------------- API from ProfileScreen ----------------
    def set_selected_profile(self, folder_name: str, profile_name: str, full_path: str):
        self.selected_folder = folder_name or ""
        self.selected_profile = profile_name or ""
        self.selected_path = full_path or ""

        print(f"[MakeProfile] selected_folder={self.selected_folder}")
        print(f"[MakeProfile] selected_profile={self.selected_profile}")
        print(f"[MakeProfile] selected_path={self.selected_path}")

    # ---------------- helpers ----------------
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
    #        return Path("../assets/icons").resolve()

    def _sanitize_name(self, s: str) -> str:
        s = (s or "").strip()
        s = re.sub(r"[\\/:*?\"<>|]+", "_", s)
        s = re.sub(r"\s+", " ", s).strip()
        return s

    def _to_int(self, s):
        try:
            return int(float(str(s).replace(",", ".")))
        except Exception:
            return 0

    def _to_float(self, s):
        try:
            return float(str(s).replace(",", "."))
        except Exception:
            return None

    def _fmt_int(self, v) -> str:
        try:
            return str(int(v))
        except Exception:
            return "--"

    def _fmt_temp(self, v) -> str:
        # "123,4"
        try:
            f = float(v)
            return f"{f:.1f}".replace(".", ",")
        except Exception:
            return "--"

    def _parse_ui_temp_to_x10(self, s: str) -> int:
        """UI '123,4' -> 1234 (x10). boş/-- -> 0"""
        try:
            if s is None:
                return 0
            t = str(s).strip()
            if t == "" or t == "--":
                return 0
            v = float(t.replace(",", "."))
            return int(round(v * 10.0))
        except Exception:
            return 0

    def _pad2(self, n) -> str:
        try:
            i = int(n)
            if i < 0:
                i = 0
            if i > 99:
                i = 99
            return f"{i:02d}"
        except Exception:
            return "00"

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

    def _load_mmss_into_fields(self, mmss: str):
        sec = self._parse_mmss_to_seconds(mmss)
        if sec is None:
            self.dev_time_min = "00"
            self.dev_time_sec = "00"
            self.development_time = "00:00"
            return

        self._load_seconds_into_fields(sec)

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




    # ---------------- modbus ----------------
    def _get_modbus_client(self):
        app = App.get_running_app()
        for attr in ("modbus_client", "modbus", "client"):
            if hasattr(app, attr):
                c = getattr(app, attr)
                if c:
                    return c
        return None

    def _read_n_safe(self, client, start_reg: int, qty: int):
        try:
            r = client.read_holding_n(start_reg, qty)
            if isinstance(r, tuple) and len(r) == 2:
                values, err = r
                if err:
                    return None
                return values
            return r
        except Exception:
            return None

    def _read_one_safe(self, client, reg: int):
        vals = self._read_n_safe(client, int(reg), 1)
        if vals and isinstance(vals, (list, tuple)) and len(vals) >= 1:
            return vals[0]
        return None

    def _write_reg_safe(self, client, reg: int, value: int):
        try:
            r = client.write_single_register(int(reg), int(value))
            if isinstance(r, tuple) and len(r) == 2:
                ok, err = r
                return bool(ok)
            return bool(r)
        except Exception:
            return False

    def _write_coil_safe(self, client, coil: int, value: int):
        try:
            r = client.write_single_coil(int(coil), int(value))
            if isinstance(r, tuple) and len(r) == 2:
                ok, err = r
                return bool(ok)
            return bool(r)
        except Exception:
            return False

    # ---------------- polling ----------------
    def _start_poll(self):
        self._stop_poll()
        self._poll_ev = Clock.schedule_interval(self._poll_tick, 0.4)

    def _stop_poll(self):
        if self._poll_ev:
            try:
                self._poll_ev.cancel()
            except Exception:
                pass
        self._poll_ev = None

    def _safe_text(self, v, hint="--"):
        try:
            s = "" if v is None else str(v)
            return s if s.strip() != "" else hint
        except Exception:
            return hint

    def _live_summary(self) -> str:
        bt = self._safe_text(self.live_bean_temp, "--")
        ex = self._safe_text(self.live_exhaust_pct, "--")
        fl = self._safe_text(self.live_flame_pct, "--")

        ex_txt = ex if ex == "--" else f"{ex} %"
        fl_txt = fl if fl == "--" else f"{fl} %"

        return f"\n\nBean: {bt}\n\nExhaust: {ex_txt}\n\nFlame: {fl_txt}"

    def _poll_tick(self, _dt):
        client = self._get_modbus_client()
        if not client:
            return

        # Live values
        vals_live = self._read_n_safe(client, 2050, 3)
        if vals_live and isinstance(vals_live, (list, tuple)) and len(vals_live) >= 3:
            mw2050 = vals_live[0]
            mw2051 = vals_live[1]
            mw2052 = vals_live[2]

            self.live_bean_temp = self._fmt_temp(int(mw2050) / 10.0)
            self.live_exhaust_pct = str(int(mw2051) / 5.0)
            self.live_flame_pct = self._fmt_int(mw2052)

        # Stage flags/state: MW350..MW354
        vals_stage = self._read_n_safe(client, self.MW_MP_STATE, 5)
        if vals_stage and isinstance(vals_stage, (list, tuple)) and len(vals_stage) >= 5:
            self.mp_state = int(vals_stage[0] or 0)
            self.dd_done = int(vals_stage[1] or 0)
            self.fc_done = int(vals_stage[2] or 0)
            self.sc_done = int(vals_stage[3] or 0)
            self.do_done = int(vals_stage[4] or 0)

        # ---- Profile mode + dev time (MW2043..2045) ----
        vals_mode = self._read_n_safe(client, 2043, 3)
        if vals_mode and isinstance(vals_mode, (list, tuple)) and len(vals_mode) >= 3:
            pm = int(vals_mode[0] or 0)
            dmin = int(vals_mode[1] or 0)
            dsec = int(vals_mode[2] or 0)

            self.profile_mode = "dev" if pm == 1 else "standard"

            new_min = self._pad2(dmin)
            new_sec = self._pad2(dsec)

            if self._editing_field != "dev_time_min":
                self.dev_time_min = new_min
            if self._editing_field != "dev_time_sec":
                self.dev_time_sec = new_sec

            if self._editing_field not in ("dev_time_min", "dev_time_sec"):
                self._sync_dev_time()


        # HER ZAMAN: tüm alanları PLC'den oku (AMA popup açıksa ezme)
        self._sync_all_fields_from_plc(client)

        self._refresh_buttons()

    def _set_state_id(self, wid: str, state: str):
        """
        state: 'normal' | 'green' | 'red'
        """
        try:
            w = self.ids.get(wid)
            if not w:
                return
            s = (state or "normal").strip().lower()
            if s not in ("normal", "green", "red"):
                s = "normal"
            w._state = s
        except Exception:
            pass

    def _set_green_id(self, wid: str, flag: bool):
        self._set_state_id(wid, "green" if flag else "normal")

    def _set_red_id(self, wid: str, flag: bool):
        self._set_state_id(wid, "red" if flag else "normal")

    def _clear_state_id(self, wid: str):
        self._set_state_id(wid, "normal")

    def _refresh_buttons(self):
        active = (self.mp_state >= 1)

        self.dd_disabled = not (active and self.dd_done == 0)
        self.fc_disabled = not (active and self.dd_done == 1 and self.fc_done == 0)
        self.sc_disabled = not (active and self.fc_done == 1 and self.sc_done == 0)
        self.do_disabled = not (active and self.sc_done == 1 and self.do_done == 0)

        green_bg = [0.18, 0.60, 0.30, 1]
        dark_bg = [0.16, 0.17, 0.20, 1]

        self.dd_bg = green_bg if (self.dd_done == 1 or (not self.dd_disabled)) else dark_bg
        self.fc_bg = green_bg if (self.fc_done == 1 or (not self.fc_disabled)) else dark_bg
        self.sc_bg = green_bg if (self.sc_done == 1 or (not self.sc_disabled)) else dark_bg
        self.do_bg = green_bg if (self.do_done == 1 or (not self.do_disabled)) else dark_bg

        # ---------------------------------------------------
        # ✅ 3-state: normal / green / red
        # ---------------------------------------------------

        # 1) önce hepsini normalle (var olan id'ler)
        all_ids = (
            "dd_temp_box", "dd_p1_box", "dd_p2_box",
            "hop_time_box", "hop_p1_box", "hop_p2_box",
            "ch_time_box", "ch_p1_box", "ch_p2_box",
            "ct_time_box", "ct_p1_box", "ct_p2_box",
            "fc_temp_box", "fc_p1_box", "fc_p2_box",
            "sc_temp_box", "sc_p1_box", "sc_p2_box",
            "do_temp_box", "do_p1_box", "do_p2_box",
            "dev_min_box", "dev_sec_box",
        )
        for wid in all_ids:
            self._set_state_id(wid, "normal")

        # 2) Hopper + Chaffing + Chaffing Time her zaman green
        for wid in (
                "hop_time_box", "hop_p1_box", "hop_p2_box",
                "ch_time_box", "ch_p1_box", "ch_p2_box",
                "ct_time_box", "ct_p1_box", "ct_p2_box",
        ):
            self._set_state_id(wid, "green")

        # 3) stage done olan satırı green yap
        if self.dd_done == 1:
            for wid in ("dd_temp_box", "dd_p1_box", "dd_p2_box"):
                self._set_state_id(wid, "red")

        if self.fc_done == 1:
            for wid in ("fc_temp_box", "fc_p1_box", "fc_p2_box"):
                self._set_state_id(wid, "red")

        if self.sc_done == 1:
            for wid in ("sc_temp_box", "sc_p1_box", "sc_p2_box"):
                self._set_state_id(wid, "red")

        if self.do_done == 1:
            for wid in ("do_temp_box", "do_p1_box", "do_p2_box"):
                self._set_state_id(wid, "red")

        # 4) Development row (sadece DEV modda görünür)
        if (self.profile_mode or "standard").strip().lower() == "dev":
            # DEV modda Drop Out basıldıysa dev satırı green olsun
            if self.do_done == 1:
                for wid in ("dev_min_box", "dev_sec_box"):
                    self._set_state_id(wid, "red")
            else:
                for wid in ("dev_min_box", "dev_sec_box"):
                    self._set_state_id(wid, "normal")
        else:
            # STD modda görünmüyor ama state temiz kalsın
            for wid in ("dev_min_box", "dev_sec_box"):
                self._set_state_id(wid, "normal")

        # (İstersen filled flag'leri burada tut)
        self.dd_filled = (self.dd_done == 1)
        self.fc_filled = (self.fc_done == 1)
        self.sc_filled = (self.sc_done == 1)
        self.do_filled = (self.do_done == 1)

    def _sync_all_fields_from_plc(self, client):
        def set_if_free(field_name: str, value: str):
            try:
                if self._editing_field == field_name:
                    return
                setattr(self, field_name, value)
            except Exception:
                pass

        try:
            # Hopper/Chaffing
            hop_time = self._read_one_safe(client, self.MW_HOP_TIME)
            hop_p1 = self._read_one_safe(client, self.MW_HOP_P1)
            hop_p2 = self._read_one_safe(client, self.MW_HOP_P2)

            chaff = self._read_one_safe(client, self.MW_CHAFF)
            ch_p1 = self._read_one_safe(client, self.MW_CH_P1)
            ch_p2 = self._read_one_safe(client, self.MW_CH_P2)

            ct_time = self._read_one_safe(client, self.MW_CT_TIME)
            ct_p1 = self._read_one_safe(client, self.MW_CT_P1_READ)
            ct_p2 = self._read_one_safe(client, self.MW_CT_P2)

            if hop_time is not None:
                set_if_free("hopper_open_time", str(int(hop_time)))
            if hop_p1 is not None:
                set_if_free("hop_p1", str(int(hop_p1)))
            if hop_p2 is not None:
                set_if_free("hop_p2", str(int(hop_p2)))

            if chaff is not None:
                set_if_free("chaffing", str(int(chaff)))
            if ch_p1 is not None:
                set_if_free("ch_p1", str(int(ch_p1)))
            if ch_p2 is not None:
                set_if_free("ch_p2", str(int(ch_p2)))

            if ct_time is not None:
                set_if_free("chaffing_time", str(int(ct_time)))
            if ct_p1 is not None:
                set_if_free("ct_p1", str(int(ct_p1)))
            if ct_p2 is not None:
                set_if_free("ct_p2", str(int(ct_p2)))

            # Temps (x10 -> UI) ; sadece 9999 ise boş göster
            dd_temp = self._read_one_safe(client, self.MW_DD_TEMP)
            fc_temp = self._read_one_safe(client, self.MW_FC_TEMP)
            sc_temp = self._read_one_safe(client, self.MW_SC_TEMP)
            do_temp = self._read_one_safe(client, self.MW_DO_TEMP)

            if dd_temp is not None:
                v = int(dd_temp)
                set_if_free("drop_down_temp", "" if v == 9999 else self._fmt_temp(v / 10.0))
            if fc_temp is not None:
                v = int(fc_temp)
                set_if_free("first_crack_temp", "" if v == 9999 else self._fmt_temp(v / 10.0))
            if sc_temp is not None:
                v = int(sc_temp)
                set_if_free("second_crack_temp", "" if v == 9999 else self._fmt_temp(v / 10.0))
            if do_temp is not None:
                v = int(do_temp)
                set_if_free("drop_out_temp", "" if v == 9999 else self._fmt_temp(v / 10.0))

            # Percents
            v = self._read_one_safe(client, self.MW_DD_P1)
            if v is not None:
                set_if_free("dd_p1", str(int(v)))

            v = self._read_one_safe(client, self.MW_DD_P2)
            if v is not None:
                set_if_free("dd_p2", str(int(v)))

            v = self._read_one_safe(client, self.MW_FC_P1)
            if v is not None:
                set_if_free("fc_p1", str(int(v)))

            v = self._read_one_safe(client, self.MW_FC_P2)
            if v is not None:
                set_if_free("fc_p2", str(int(v)))

            v = self._read_one_safe(client, self.MW_SC_P1)
            if v is not None:
                set_if_free("sc_p1", str(int(v)))

            v = self._read_one_safe(client, self.MW_SC_P2)
            if v is not None:
                set_if_free("sc_p2", str(int(v)))

            v = self._read_one_safe(client, self.MW_DO_P1)
            if v is not None:
                set_if_free("do_p1", str(int(v)))

            v = self._read_one_safe(client, self.MW_DO_P2)
            if v is not None:
                set_if_free("do_p2", str(int(v)))

            # --- LIVE DEV TIME (MW339/MW340) -> ekranda sürekli göster ---
            v = self._read_one_safe(client, self.MW_CUR_DEV_MIN)
            if v is not None:
                set_if_free("dev_min", str(int(v)))

            v = self._read_one_safe(client, self.MW_CUR_DEV_SEC)
            if v is not None:
                set_if_free("dev_sec", str(int(v)))

        except Exception:
            pass

    # ---------------------------------------------------------------------
    # ✅ TÜM alanları PLC'den oku -> textboxlara yaz
    #   - temp alanlarında 0 veya 9999 ise boş göster
    #   - popup açıkken (_editing_field) o alanı EZME
    # ---------------------------------------------------------------------
    def _sync_all_fields_from_plc_eski(self, client):
        def set_if_free(field_name: str, value: str):
            try:
                if self._editing_field == field_name:
                    return
                setattr(self, field_name, value)
            except Exception:
                pass

        try:
            # Hopper/Chaffing
            hop_time = self._read_one_safe(client, self.MW_HOP_TIME)
            hop_p1 = self._read_one_safe(client, self.MW_HOP_P1)
            hop_p2 = self._read_one_safe(client, self.MW_HOP_P2)

            chaff = self._read_one_safe(client, self.MW_CHAFF)
            ch_p1 = self._read_one_safe(client, self.MW_CH_P1)
            ch_p2 = self._read_one_safe(client, self.MW_CH_P2)

            ct_time = self._read_one_safe(client, self.MW_CT_TIME)
            ct_p1 = self._read_one_safe(client, self.MW_CT_P1_READ)
            ct_p2 = self._read_one_safe(client, self.MW_CT_P2)

            if hop_time is not None:
                set_if_free("hopper_open_time", str(int(hop_time)) if int(hop_time) != 0 else "")
            if hop_p1 is not None:
                set_if_free("hop_p1", str(int(hop_p1)) if int(hop_p1) != 0 else "")
            if hop_p2 is not None:
                set_if_free("hop_p2", str(int(hop_p2)) if int(hop_p2) != 0 else "")

            if chaff is not None:
                set_if_free("chaffing", str(int(chaff)) if int(chaff) != 0 else "")
            if ch_p1 is not None:
                set_if_free("ch_p1", str(int(ch_p1)) if int(ch_p1) != 0 else "")
            if ch_p2 is not None:
                set_if_free("ch_p2", str(int(ch_p2)) if int(ch_p2) != 0 else "")

            if ct_time is not None:
                set_if_free("chaffing_time", str(int(ct_time)) if int(ct_time) != 0 else "")
            if ct_p1 is not None:
                set_if_free("ct_p1", str(int(ct_p1)) if int(ct_p1) != 0 else "")
            if ct_p2 is not None:
                set_if_free("ct_p2", str(int(ct_p2)) if int(ct_p2) != 0 else "")

            # Temps (x10 -> UI) ; 0 veya 9999 ise boş göster
            dd_temp = self._read_one_safe(client, self.MW_DD_TEMP)
            fc_temp = self._read_one_safe(client, self.MW_FC_TEMP)
            sc_temp = self._read_one_safe(client, self.MW_SC_TEMP)
            do_temp = self._read_one_safe(client, self.MW_DO_TEMP)

            if dd_temp is not None:
                v = int(dd_temp)
                set_if_free("drop_down_temp", "" if (v == 0 or v == 9999) else self._fmt_temp(v / 10.0))
            if fc_temp is not None:
                v = int(fc_temp)
                set_if_free("first_crack_temp", "" if (v == 0 or v == 9999) else self._fmt_temp(v / 10.0))
            if sc_temp is not None:
                v = int(sc_temp)
                set_if_free("second_crack_temp", "" if (v == 0 or v == 9999) else self._fmt_temp(v / 10.0))
            if do_temp is not None:
                v = int(do_temp)
                set_if_free("drop_out_temp", "" if (v == 0 or v == 9999) else self._fmt_temp(v / 10.0))

            # Percents (0 ise boş)
            v = self._read_one_safe(client, self.MW_DD_P1)
            if v is not None:
                set_if_free("dd_p1", str(int(v)) if int(v) != 0 else "")

            v = self._read_one_safe(client, self.MW_DD_P2)
            if v is not None:
                set_if_free("dd_p2", str(int(v)) if int(v) != 0 else "")

            v = self._read_one_safe(client, self.MW_FC_P1)
            if v is not None:
                set_if_free("fc_p1", str(int(v)) if int(v) != 0 else "")

            v = self._read_one_safe(client, self.MW_FC_P2)
            if v is not None:
                set_if_free("fc_p2", str(int(v)) if int(v) != 0 else "")

            v = self._read_one_safe(client, self.MW_SC_P1)
            if v is not None:
                set_if_free("sc_p1", str(int(v)) if int(v) != 0 else "")

            v = self._read_one_safe(client, self.MW_SC_P2)
            if v is not None:
                set_if_free("sc_p2", str(int(v)) if int(v) != 0 else "")

            v = self._read_one_safe(client, self.MW_DO_P1)
            if v is not None:
                set_if_free("do_p1", str(int(v)) if int(v) != 0 else "")

            v = self._read_one_safe(client, self.MW_DO_P2)
            if v is not None:
                set_if_free("do_p2", str(int(v)) if int(v) != 0 else "")

            # --- LIVE DEV TIME (MW339/MW340) -> ekranda sürekli göster ---
            v = self._read_one_safe(client, self.MW_CUR_DEV_MIN)
            if v is not None:
                set_if_free("dev_min", str(int(v)) if int(v) != 0 else "")

            v = self._read_one_safe(client, self.MW_CUR_DEV_SEC)
            if v is not None:
                set_if_free("dev_sec", str(int(v)) if int(v) != 0 else "")


        except Exception:
            pass

    # ---------------- UI actions ----------------
    def go_back(self):
        if self.manager and self.manager.has_screen("live"):
            self.manager.current = "live"
        elif self.manager:
            self.manager.current = self.manager.screens[0].name

    # ✅ KV'deki Traditional / Development butonları burayı çağıracak
    def set_profile_mode(self, mode: str):
        m = (mode or "").strip().lower()

        if m == "development":
            m = "dev"

        if m not in ("standard", "dev"):
            m = "standard"

        self.profile_mode = m

    # ✅ DEV TIME popup'ları (ProfileDetailScreen mantığı)
    def open_dev_min(self):
        self._open_dev_field("dev_time_min", "Development Time (min)", 0, 0, 99)

    def open_dev_sec(self):
        self._open_dev_field("dev_time_sec", "Development Time (sec)", 0, 0, 59)

    def _open_dev_field(self, field_name: str, title: str, decimals: int, vmin: int, vmax: int):
        # popup açıkken sync ezmesin
        self._editing_field = field_name

        cur = getattr(self, field_name, "00")
        cur = "" if cur is None else str(cur).strip()
        if cur == "--":
            cur = ""
        if cur == "":
            cur = "00"

        # OK callback
        def _on_ok(val_float, text_str):
            s = "" if text_str is None else str(text_str).strip()
            try:
                v = int(float(s.replace(",", ".")))
            except Exception:
                v = 0

            if field_name == "dev_time_sec":
                if v < 0:
                    v = 0
                if v > 59:
                    v = 59
            else:
                if v < 0:
                    v = 0
                if v > 99:
                    v = 99

            setattr(self, field_name, f"{v:02d}")
            self._sync_dev_time()
            self._editing_field = ""

            # ✅ PLC'ye yaz
            client = self._get_modbus_client()
            if client:
                if field_name == "dev_time_sec":
                    self._write_reg_safe(client, self.MW_DEV_SEC, int(v))
                else:
                    self._write_reg_safe(client, self.MW_DEV_MIN, int(v))


        def _on_cancel():
            self._editing_field = ""

        try:
            pop = NumericKeypadPopup(
                title=title,
                initial_text=cur,
                max_decimals=int(decimals or 0),
                min_value=vmin,
                max_value=vmax,
                on_ok=_on_ok,
                on_cancel=_on_cancel,
                fullscreen=True,
            )
            pop.open()
        except Exception as e:
            print("[MakeProfile] DevTime popup open error:", e)
            self._editing_field = ""

    def open_origin_picker(self):
        origin_dir = self._project_root() / "assets" / "origin"
        origin_dir.mkdir(parents=True, exist_ok=True)
        items = sorted(origin_dir.glob("*.png"))
        if not items:
            self._toast("No origin png found in assets/origin/")
            return

        from kivy.uix.scrollview import ScrollView
        from kivy.uix.gridlayout import GridLayout
        from kivy.uix.image import Image
        from kivy.uix.button import Button
        from kivy.uix.behaviors import ButtonBehavior
        from kivy.uix.boxlayout import BoxLayout
        from kivy.graphics import Color, RoundedRectangle

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
        gl = GridLayout(cols=5, spacing=dp(16), padding=dp(8), size_hint_y=None)
        gl.bind(minimum_height=gl.setter("height"))

        for p in items:
            cell = BoxLayout(orientation="vertical", size_hint_y=None, height=dp(150), spacing=dp(8))

            icon_hit = IconHit(
                orientation="vertical",
                size_hint=(1, None),
                height=dp(100),
                padding=(dp(10), dp(6), dp(10), dp(6))
            )
            icon_hit.bind(on_release=lambda _w, pp=p: _pick(pp))

            with icon_hit.canvas.before:
                Color(0.16, 0.17, 0.20, 1)
                rr = RoundedRectangle(pos=icon_hit.pos, size=icon_hit.size, radius=[dp(14)] * 4)

            def _sync_rr(*_rr_args, _rr=rr, _w=icon_hit):
                _rr.pos = _w.pos
                _rr.size = _w.size

            icon_hit.bind(pos=_sync_rr, size=_sync_rr)

            icon_hit.add_widget(Image(source=str(p), allow_stretch=True, keep_ratio=True))

            lbl = Label(
                text=p.stem,
                size_hint_y=None,
                height=dp(32),
                font_size="16sp",
                color=(1, 1, 1, 1),
                halign="center",
                valign="middle"
            )
            lbl.bind(size=lambda *_: setattr(lbl, "text_size", lbl.size))

            cell.add_widget(icon_hit)
            cell.add_widget(lbl)
            gl.add_widget(cell)

        sv.add_widget(gl)
        root.add_widget(header)
        root.add_widget(sv)

        pop = Popup(title="", separator_height=0, content=root, size_hint=(1, 1), auto_dismiss=False)
        pop.open()

    # ---------------- stage actions ----------------
    def _confirm(self, title_text: str, yes_cb):
        inner = BoxLayout(orientation="vertical", spacing=dp(14), padding=(dp(16), dp(14)))

        msg = Label(
            text=title_text,
            font_size="20sp",
            bold=True,
            color=(1, 1, 1, 1),
            halign="center",
            valign="top",
        )
        msg.bind(size=lambda w, *_: setattr(w, "text_size", (w.width, None)))
        msg.bind(texture_size=lambda w, *_: setattr(w, "height", w.texture_size[1] + dp(10)))
        inner.add_widget(msg)

        row = BoxLayout(size_hint_y=None, height=dp(56), spacing=dp(14))
        from kivy.factory import Factory
        b_no = Factory.RoundedPopupButtonSmall(text="No")
        b_yes = Factory.RoundedPopupButtonSmall(text="Yes")
        row.add_widget(b_no)
        row.add_widget(b_yes)
        inner.add_widget(row)

        card = BoxLayout(orientation="vertical", padding=dp(16))
        card.add_widget(inner)

        def _redraw(*_):
            card.canvas.before.clear()
            from kivy.graphics import Color, RoundedRectangle
            with card.canvas.before:
                Color(0.12, 0.13, 0.16, 1)
                RoundedRectangle(pos=card.pos, size=card.size, radius=[dp(22)] * 4)

        card.bind(pos=_redraw, size=_redraw)
        _redraw()

        pop = Popup(
            title="",
            content=card,
            size_hint=(None, None),
            size=(dp(680), dp(420)),
            auto_dismiss=False,
            separator_height=0,
            background="",
            background_color=(0, 0, 0, 0),
        )
        b_no.bind(on_release=lambda *_: pop.dismiss())

        def _yes(*_):
            pop.dismiss()
            yes_cb()

        b_yes.bind(on_release=_yes)
        pop.open()

    def _write_stage_values_to_plc(self, client, temp_reg, p1_reg, p2_reg, temp_str, p1_str, p2_str):
        self._write_reg_safe(client, temp_reg, self._parse_ui_temp_to_x10(temp_str))
        self._write_reg_safe(client, p1_reg, self._to_int(p1_str))
        self._write_reg_safe(client, p2_reg, self._to_int(p2_str))

    def on_drop_down_stage(self):
        if self.dd_done == 1 or self.dd_disabled:
            return

        def _yes():
            self.drop_down_temp = self.live_bean_temp if self.live_bean_temp != "--" else self.drop_down_temp
            self.dd_p1 = self.live_exhaust_pct if self.live_exhaust_pct != "--" else self.dd_p1
            self.dd_p2 = self.live_flame_pct if self.live_flame_pct != "--" else self.dd_p2
            self.dd_filled = True

            client = self._get_modbus_client()
            if client:
                self._write_stage_values_to_plc(
                    client,
                    self.MW_DD_TEMP, self.MW_DD_P1, self.MW_DD_P2,
                    self.drop_down_temp, self.dd_p1, self.dd_p2
                )
                self._write_reg_safe(client, self.MW_MP_STATE, 2)
                self._write_reg_safe(client, self.MW_DD_DONE, 1)

            self._toast("Drop Down saved.")
            self._poll_tick(0)

        self._confirm("Are you sure you dropped down the coffee?" + self._live_summary(), _yes)

    def on_first_crack_stage(self):
        if self.fc_done == 1 or self.fc_disabled:
            return

        def _yes():
            self.first_crack_temp = self.live_bean_temp if self.live_bean_temp != "--" else self.first_crack_temp
            self.fc_p1 = self.live_exhaust_pct if self.live_exhaust_pct != "--" else self.fc_p1
            self.fc_p2 = self.live_flame_pct if self.live_flame_pct != "--" else self.fc_p2
            self.fc_filled = True

            client = self._get_modbus_client()
            if client:
                self._write_stage_values_to_plc(
                    client,
                    self.MW_FC_TEMP, self.MW_FC_P1, self.MW_FC_P2,
                    self.first_crack_temp, self.fc_p1, self.fc_p2
                )
                self._write_reg_safe(client, self.MW_MP_STATE, 3)
                self._write_reg_safe(client, self.MW_FC_DONE, 1)

            self._toast("First Crack saved.")
            self._poll_tick(0)

        self._confirm("Are you sure the first crack has occurred?" + self._live_summary(), _yes)

    def on_second_crack_stage(self):
        print("=== SECOND CRACK CLICKED ===")
        print("sc_done =", self.sc_done)
        print("sc_disabled =", self.sc_disabled)

        if self.sc_done == 1 or self.sc_disabled:
            return

        def _yes():
            self.second_crack_temp = self.live_bean_temp if self.live_bean_temp != "--" else self.second_crack_temp
            self.sc_p1 = self.live_exhaust_pct if self.live_exhaust_pct != "--" else self.sc_p1
            self.sc_p2 = self.live_flame_pct if self.live_flame_pct != "--" else self.sc_p2
            self.sc_filled = True

            client = self._get_modbus_client()
            if client:
                self._write_stage_values_to_plc(
                    client,
                    self.MW_SC_TEMP, self.MW_SC_P1, self.MW_SC_P2,
                    self.second_crack_temp, self.sc_p1, self.sc_p2
                )
                self._write_reg_safe(client, self.MW_MP_STATE, 4)
                self._write_reg_safe(client, self.MW_SC_DONE, 1)

            self._toast("Second Crack saved.")
            self._poll_tick(0)

        self._confirm("Are you sure the second crack has occurred?" + self._live_summary(), _yes)

    def on_drop_out_stage(self):
        if self.do_done == 1 or self.do_disabled:
            return

        def _yes():
            self.drop_out_temp = self.live_bean_temp if self.live_bean_temp != "--" else self.drop_out_temp
            self.do_p1 = self.live_exhaust_pct if self.live_exhaust_pct != "--" else self.do_p1
            self.do_p2 = self.live_flame_pct if self.live_flame_pct != "--" else self.do_p2
            self.do_filled = True

            client = self._get_modbus_client()
            if client:
                self._write_stage_values_to_plc(
                    client,
                    self.MW_DO_TEMP, self.MW_DO_P1, self.MW_DO_P2,
                    self.drop_out_temp, self.do_p1, self.do_p2

                )

                self._write_reg_safe(client, self.MW_DEV_MIN, self.dev_min)  # 608
                self._write_reg_safe(client, self.MW_DEV_SEC, self.dev_sec)  # 609

                self._write_reg_safe(client, self.MW_MP_STATE, 5)
                self._write_reg_safe(client, self.MW_DO_DONE, 1)

                #self._write_reg_safe(client, self.MW_MP_STATE, 10)
                #self._write_reg_safe(client, self.MW_DD_DONE, 0)
                #self._write_reg_safe(client, self.MW_FC_DONE, 0)
                #self._write_reg_safe(client, self.MW_SC_DONE, 0)
                #self._write_reg_safe(client, self.MW_DO_DONE, 0)
                self._write_reg_safe(client, 2200, 0)
                #self._write_coil_safe(client, 501, 0)
                #self._write_coil_safe(client, 500, 0)

            # ✅ BURASI DEGISTI
            self._confirm(
                "Drop Out saved.",
                lambda: self._confirm(
                    "Do You Want to Run Cooling Process ?",
                    lambda: self._run_cooling_process()
                )
            )

            self._poll_tick(0)

        self._confirm("Are you sure you dropped out the coffee?" + self._live_summary(), _yes)


    def _run_cooling_process(self):
        client = self._get_modbus_client()
        if not client:
            self._toast("Cooling command failed")
            return

        self._write_reg_safe(client, self.REG_COOLING_CMD, 1)
        self._toast("Cooling started")

    def save_make_profile(self):
        name = self._sanitize_name(self.selected_profile) or "Profile"
        folder = self._sanitize_name(self.selected_folder) or "Default"

        if self.selected_path:
            fpath = Path(self.selected_path)
        else:
            fpath = self._project_root() / "profiles" / folder / f"{name}.json"

        fpath.parent.mkdir(parents=True, exist_ok=True)

        # ProfileDetailScreen ile aynı veri mantığı
        self._sync_dev_time()

        mode = (self.profile_mode or "standard").strip().lower()
        if mode == "development":
            mode = "dev"
        if mode not in ("standard", "dev"):
            mode = "standard"

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

            "profile_mode": mode,
            "development_time": (self.development_time or "00:00"),
            "development_time_sec": self._parse_mmss_to_seconds(self.development_time),

            "dev_time_min": self.dev_time_min,
            "dev_time_sec": self.dev_time_sec,
        }

        try:
            fpath.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            self.selected_path = str(fpath)
            short_path = f"{fpath.parent.name} / {fpath.name}"
            self._toast(f"Profile saved.\n\n{short_path}")
            print(f"[MakeProfile] SAVED -> {fpath}")
        except Exception as e:
            print("[MakeProfile] save error:", e)
            self._toast("Save error!")




    # ---------------- save / end ----------------
    def save_make_profile_eski(self):
        name = self._sanitize_name(self.selected_profile) or "Profile"
        folder = self._sanitize_name(self.selected_folder) or "Default"

        if self.selected_path:
            fpath = Path(self.selected_path)
        else:
            fpath = self._project_root() / "profiles" / folder / f"{name}.json"

        fpath.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "profile_name": name,
            "coffee_origin": self.coffee_origin,
            "coffee_origin_png": self.coffee_origin_png,

            # ✅ NEW: mode + dev time
            "profile_mode": self.profile_mode,
            "dev_time_min": self.dev_time_min,
            "dev_time_sec": self.dev_time_sec,

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
            "ct_p2": self._to_int(self.ct_p2),
            "fc_p1": self._to_int(self.fc_p1),
            "fc_p2": self._to_int(self.fc_p2),
            "sc_p1": self._to_int(self.sc_p1),
            "sc_p2": self._to_int(self.sc_p2),
            "do_p1": self._to_int(self.do_p1),
            "do_p2": self._to_int(self.do_p2),

            "mw350": int(self.mp_state),
            "mw351": int(self.dd_done),
            "mw352": int(self.fc_done),
            "mw353": int(self.sc_done),
            "mw354": int(self.do_done),
        }

        try:
            fpath.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            self.selected_path = str(fpath)
            short_path = f"{fpath.parent.name} / {fpath.name}"
            self._toast(f"Profile saved.\n\n{short_path}")
            print(f"[MakeProfile] SAVED -> {fpath}")
        except Exception as e:
            print("[MakeProfile] save error:", e)
            self._toast("Save error!")

    def end_profile(self):
        def _yes_end():
            client = self._get_modbus_client()
            if client:
                # ✅ Sadece MW350..MW354 sıfır + COIL501 reset
                self._write_reg_safe(client, self.MW_MP_STATE, 0)
                self._write_reg_safe(client, self.MW_DD_DONE, 0)
                self._write_reg_safe(client, self.MW_FC_DONE, 0)
                self._write_reg_safe(client, self.MW_SC_DONE, 0)
                self._write_reg_safe(client, self.MW_DO_DONE, 0)
                self._write_reg_safe(client, 2200, 0)
                self._write_coil_safe(client, 501, 0)
                self._write_coil_safe(client, 500, 0)

            self._toast("Make Profile ended.")
            self.go_back()

        self._confirm("Are you sure you want to end the profile?", _yes_end)

    def open_numeric(self, field_name: str, title: str, decimals: int, vmin: int, vmax: int):
        field_name = (field_name or "").strip()
        if not field_name:
            return

        if not hasattr(self, field_name):
            print(f"[MakeProfile] open_numeric: unknown field '{field_name}'")
            return

        # popup açıkken sync ezmesin
        self._editing_field = field_name

        # mevcut metin
        cur = getattr(self, field_name)
        cur = "" if cur is None else str(cur).strip()
        if cur == "--":
            cur = ""

        # decimals==0 ise "56.0" -> "56"
        if int(decimals or 0) == 0 and cur:
            try:
                curf = float(cur.replace(",", "."))
                cur = str(int(round(curf)))
            except Exception:
                pass

        # OK callback
        def _on_ok(val_float, text_str):
            s = "" if text_str is None else str(text_str).strip()

            if int(decimals or 0) == 1:
                try:
                    v = float(s.replace(",", "."))
                    s = f"{v:.1f}".replace(".", ",")
                except Exception:
                    pass
            else:
                try:
                    v = float(s.replace(",", "."))
                    s = str(int(round(v)))
                except Exception:
                    pass

            setattr(self, field_name, s)

            # popup kapandı
            self._editing_field = ""

            # ✅ anında PLC'ye yaz
            client = self._get_modbus_client()
            if not client:
                return

            reg_map = {
                # temps (x10)
                "drop_down_temp": ("temp_x10", self.MW_DD_TEMP),
                "first_crack_temp": ("temp_x10", self.MW_FC_TEMP),
                "second_crack_temp": ("temp_x10", self.MW_SC_TEMP),
                "drop_out_temp": ("temp_x10", self.MW_DO_TEMP),

                # percents / ints
                "dd_p1": ("int", self.MW_DD_P1),
                "dd_p2": ("int", self.MW_DD_P2),
                "hop_p1": ("int", self.MW_HOP_P1),
                "hop_p2": ("int", self.MW_HOP_P2),
                "ch_p1": ("int", self.MW_CH_P1),
                "ch_p2": ("int", self.MW_CH_P2),
                "ct_p1": ("int", self.MW_CT_P1_WRITE),
                "ct_p2": ("int", self.MW_CT_P2),
                "fc_p1": ("int", self.MW_FC_P1),
                "fc_p2": ("int", self.MW_FC_P2),
                "sc_p1": ("int", self.MW_SC_P1),
                "sc_p2": ("int", self.MW_SC_P2),
                "do_p1": ("int", self.MW_DO_P1),
                "do_p2": ("int", self.MW_DO_P2),

                # times
                "hopper_open_time": ("int", self.MW_HOP_TIME),
                "chaffing": ("int", self.MW_CHAFF),
                "chaffing_time": ("int", self.MW_CT_TIME),
            }

            if field_name not in reg_map:
                return

            kind, reg = reg_map[field_name]
            if kind == "temp_x10":
                self._write_reg_safe(client, reg, self._parse_ui_temp_to_x10(s))
            else:
                self._write_reg_safe(client, reg, self._to_int(s))

        def _on_cancel():
            self._editing_field = ""

        # popup aç
        try:
            pop = NumericKeypadPopup(
                title=title,
                initial_text=cur,
                max_decimals=int(decimals or 0),
                min_value=vmin,
                max_value=vmax,
                on_ok=_on_ok,
                on_cancel=_on_cancel,
                fullscreen=True,
            )
            pop.open()
        except Exception as e:
            print("[MakeProfile] NumericKeypadPopup open error:", e)
            self._editing_field = ""

    # ---------------- small popup ----------------
    def _toast(self, msg: str):
        from kivy.factory import Factory

        inner = BoxLayout(orientation="vertical", spacing=dp(14), padding=(dp(16), dp(14)))

        lbl = Label(
            text=msg,
            font_size="20sp",
            bold=True,
            color=(1, 1, 1, 1),
            halign="center",
            valign="top",
        )
        lbl.bind(size=lambda w, *_: setattr(w, "text_size", (w.width, None)))
        lbl.bind(texture_size=lambda w, *_: setattr(w, "height", w.texture_size[1] + dp(10)))
        inner.add_widget(lbl)

        btn = Factory.RoundedPopupButton(text="OK")
        inner.add_widget(btn)

        card = BoxLayout(orientation="vertical", padding=dp(16))
        card.add_widget(inner)

        def _redraw(*_):
            card.canvas.before.clear()
            from kivy.graphics import Color, RoundedRectangle
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