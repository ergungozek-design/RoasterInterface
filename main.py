from kivy.app import App
from kivy.lang import Builder
from kivy.core.window import Window
from kivy.factory import Factory
from kivy.uix.screenmanager import ScreenManager, FadeTransition

from screens.home_screen import HomeScreen
from screens.live_roast import LiveRoastScreen
from screens.profile_screen import ProfileScreen
from screens.make_profile_screen import MakeProfileScreen
from screens.manual_control_screen import ManualControlScreen
from screens.profile_detail_screen import ProfileDetailScreen

# widgets
from widgets.roast_plot import RoastPlot
from widgets.airflow_gauge import AirflowGauge
from widgets.bar_gauge import BarGauge
from widgets.status_led import StatusLed

# ✅ Modbus
from services.modbus_tcp_client import ModbusTCPClient
from services.mqtt_service import MQTTService
from widgets.status_anim import StatusAnim

from kivy.uix.popup import Popup
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label

from kivy.properties import StringProperty, BooleanProperty, ListProperty
from kivy.clock import Clock


import sys
import os


def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

# ---- Factory register (KV import istemesin) ----
Factory.register("StatusAnim", cls=StatusAnim)
Factory.register("RoastPlot", cls=RoastPlot)
Factory.register("AirflowGauge", cls=AirflowGauge)
Factory.register("BarGauge", cls=BarGauge)
Factory.register("StatusLed", cls=StatusLed)

# ---- Window ----
Window.size = (1280, 800)
Window.borderless = True
Window.fullscreen = False
Window.top = 0
Window.left = 0
Window.minimum_width, Window.minimum_height = (1280, 800)
Window.clearcolor = (0.07, 0.08, 0.10, 1)


class RoastDashboardApp(App):

    # KV içinden okunuyor
    active_tab = StringProperty("home")
    home_icon = StringProperty("")

    modbus_connected = BooleanProperty(False)
    comm_indicator_color = ListProperty([1, 0, 0, 1])
    comm_indicator_on = BooleanProperty(True)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.modbus_client = None  # ✅ GLOBAL Modbus client
        self.mqtt = None

        # ✅ Modbus connection settings
        self.modbus_host = "192.168.1.50"
        self.modbus_port = 502
        self.modbus_unit_id = 2
        self.modbus_timeout = 1.5

        self._modbus_watchdog_ev = None
        self.modbus_connected = False
        self._comm_blink_ev = None

    def start_comm_blink(self):
        if self._comm_blink_ev is None:
            self._comm_blink_ev = Clock.schedule_interval(self._toggle_comm_indicator, 0.5)

    def stop_comm_blink(self):
        if self._comm_blink_ev is not None:
            try:
                self._comm_blink_ev.cancel()
            except Exception:
                pass
            self._comm_blink_ev = None

    def _toggle_comm_indicator(self, dt):
        self.comm_indicator_on = not self.comm_indicator_on

    def _set_comm_indicator(self, ok: bool):
        self.modbus_connected = bool(ok)
        if self.modbus_connected:
            self.comm_indicator_color = [0, 1, 0, 1]
        else:
            self.comm_indicator_color = [1, 0, 0, 1]

    def start_modbus_watchdog(self):
        from kivy.clock import Clock

        if self._modbus_watchdog_ev is None:
            self._modbus_watchdog_ev = Clock.schedule_interval(self._modbus_watchdog, 2.0)

    def _modbus_watchdog(self, dt):
        try:

            # ------------------------------------------------
            # 1) Eğer client yoksa yeniden bağlanmayı dene
            # ------------------------------------------------
            if self.modbus_client is None:

                client = self.connect_modbus()

                if client is not None:
                    self._set_comm_indicator(True)
                else:
                    self._set_comm_indicator(False)

                return

            # ------------------------------------------------
            # 2) Client varsa küçük bir test okuması yap
            # ------------------------------------------------
            vals, err = self.modbus_client.read_holding_n(2020, 1)

            if vals is None or len(vals) < 1:

                try:
                    self.modbus_client.close()
                except Exception:
                    pass

                self.modbus_client = None
                self._set_comm_indicator(False)
                return

            # ------------------------------------------------
            # 3) Okuma başarılı → PLC bağlı
            # ------------------------------------------------
            self._set_comm_indicator(True)


        except Exception as e:

            print("[App] watchdog error:", e)

            try:
                if self.modbus_client is not None:
                    self.modbus_client.close()
            except Exception:
                pass

            self.modbus_client = None
            self._set_comm_indicator(False)

    def connect_modbus(self):
        try:
            # eski client varsa kapat
            if self.modbus_client is not None:
                try:
                    self.modbus_client.close()
                except Exception:
                    pass
                self.modbus_client = None

            # yeni client oluştur
            client = ModbusTCPClient(
                host=self.modbus_host,
                port=self.modbus_port,
                unit_id=self.modbus_unit_id,
                timeout=self.modbus_timeout
            )

            # bağlan
            ok = client.connect()
            print("[App] ModbusTCPClient connect() called, result =", ok)

            if ok:
                self.modbus_client = client

                try:
                    vals, err = self.modbus_client.read_holding_n(2020, 1)
                    print("[App] TEST READ 2020:", vals, "err=", err)

                    if vals is None or len(vals) < 1:
                        raise Exception(f"test read failed: {err}")

                except Exception as e:
                    print("[App] TEST READ EXC:", e)
                    try:
                        self.modbus_client.close()
                    except Exception:
                        pass
                    self.modbus_client = None
                    return None

                return self.modbus_client


            # başarısız bağlantı
            try:
                client.close()
            except Exception:
                pass

            self.modbus_client = None
            print("[App] Modbus connect failed")
            return None

        except Exception as e:
            print("[App] connect_modbus error:", e)
            self.modbus_client = None
            return None


    def reconnect_modbus(self):
        print("[App] reconnect_modbus called")
        return self.connect_modbus()


    def build(self):
        self.home_icon = resource_path("assets/icons/home.png")

        # ---------------- KV dosyaları ----------------
        Builder.load_file(resource_path("ui/common.kv"))
        Builder.load_file(resource_path("ui/home.kv"))
        Builder.load_file(resource_path("ui/live_roast.kv"))
        Builder.load_file(resource_path("ui/profile.kv"))
        Builder.load_file(resource_path("ui/make_profile.kv"))
        Builder.load_file(resource_path("ui/manual_control.kv"))
        Builder.load_file(resource_path("ui/profile_detail_screen.kv"))

        #Builder.load_file("ui/common.kv")
        #Builder.load_file("ui/home.kv")
        #Builder.load_file("ui/live_roast.kv")
        #Builder.load_file("ui/profile.kv")
        #Builder.load_file("ui/make_profile.kv")
        #Builder.load_file("ui/manual_control.kv")
        #Builder.load_file("ui/profile_detail_screen.kv")

        # ---------------- ScreenManager ----------------
        sm = ScreenManager(transition=FadeTransition(duration=0.15))
        sm.add_widget(HomeScreen(name="home"))
        sm.add_widget(LiveRoastScreen(name="live"))
        sm.add_widget(ProfileScreen(name="profile"))
        sm.add_widget(MakeProfileScreen(name="make_profile"))
        sm.add_widget(ManualControlScreen(name="manual"))
        sm.add_widget(ProfileDetailScreen(name="profile_detail"))

        # ---------------- ✅ Modbus TCP Client ----------------
        self.connect_modbus()
        self.start_modbus_watchdog()
        self.start_comm_blink()


        self.mqtt = MQTTService(
            broker="08bb54f5ee234a86ba2d3e07280da8ed.s1.eu.hivemq.cloud",
            port=8883,
            username="roaster",
            password="CemGozek1!",
        )
        self.mqtt.connect()


        sm.current = "home"
        return sm

    def show_shutdown_popup(self):
        layout = BoxLayout(orientation="vertical", spacing=20, padding=20)

        msg = Label(text="Shutdown Computer ?")
        btn_row = BoxLayout(spacing=20, size_hint_y=None, height=50)

        yes_btn = Button(text="Yes")
        no_btn = Button(text="Cancel")

        btn_row.add_widget(yes_btn)
        btn_row.add_widget(no_btn)

        layout.add_widget(msg)
        layout.add_widget(btn_row)

        popup = Popup(
            title="Shutdown",
            content=layout,
            size_hint=(None, None),
            size=(420, 220),
            auto_dismiss=False
        )

        yes_btn.bind(on_press=lambda *_: self._do_shutdown(popup))
        no_btn.bind(on_press=lambda *_: popup.dismiss())

        popup.open()

    def _do_shutdown(self, popup):
        # popup kapan
        try:
            popup.dismiss()
        except Exception:
            pass

        # Uygulamayı kapat (on_stop tetiklenir, modbus close olur)
        try:
            self.stop()
        except Exception:
            pass

        # Windows'u kapat (1 sn gecikme güvenli)
        os.system("shutdown /s /t 1")

    def on_stop(self):
        try:
            if self._modbus_watchdog_ev is not None:
                self._modbus_watchdog_ev.cancel()
                self._modbus_watchdog_ev = None
        except Exception:
            pass

        try:
            if self.root and self.root.has_screen("live"):
                live = self.root.get_screen("live")
                if hasattr(live, "_pause_poll"):
                    live._pause_poll()
        except Exception:
            pass

        try:
            if self.modbus_client:
                self.modbus_client.close()
        except Exception:
            pass

        try:
            if self.mqtt is not None:
                self.mqtt.disconnect()
        except Exception:
            pass


if __name__ == "__main__":
    RoastDashboardApp().run()









