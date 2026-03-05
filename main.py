from kivy.app import App
from kivy.lang import Builder
from kivy.core.window import Window
from kivy.factory import Factory
from kivy.uix.screenmanager import ScreenManager, FadeTransition
from kivy.properties import StringProperty

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

# ✅ Modbus
from services.modbus_tcp_client import ModbusTCPClient

from widgets.status_anim import StatusAnim


# ---- Factory register (KV import istemesin) ----
Factory.register("StatusAnim", cls=StatusAnim)
Factory.register("RoastPlot", cls=RoastPlot)
Factory.register("AirflowGauge", cls=AirflowGauge)
Factory.register("BarGauge", cls=BarGauge)

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

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.modbus_client = None  # ✅ GLOBAL Modbus client

    def build(self):
        # ---------------- KV dosyaları ----------------
        Builder.load_file("ui/common.kv")
        Builder.load_file("ui/home.kv")
        Builder.load_file("ui/live_roast.kv")
        Builder.load_file("ui/profile.kv")
        Builder.load_file("ui/make_profile.kv")
        Builder.load_file("ui/manual_control.kv")
        Builder.load_file("ui/profile_detail_screen.kv")

        # ---------------- ScreenManager ----------------
        sm = ScreenManager(transition=FadeTransition(duration=0.15))
        sm.add_widget(HomeScreen(name="home"))
        sm.add_widget(LiveRoastScreen(name="live"))
        sm.add_widget(ProfileScreen(name="profile"))
        sm.add_widget(MakeProfileScreen(name="make_profile"))
        sm.add_widget(ManualControlScreen(name="manual"))
        sm.add_widget(ProfileDetailScreen(name="profile_detail"))

        # ---------------- ✅ Modbus TCP Client ----------------
        try:
            self.modbus_client = ModbusTCPClient(
                host="192.168.1.50",
                port=502,
                unit_id=2,
                timeout=1.5
            )
            self.modbus_client.connect()
            print("[App] ModbusTCPClient connected")

            # ✅ QUICK TEST READ (uygulama açılır açılmaz)
            try:
                vals, err = self.modbus_client.read_holding_n(2020, 2)  # MW2020'den 2 register
                print("[App] TEST READ 2020..:", vals, "err=", err)
            except Exception as e:
                print("[App] TEST READ EXC:", e)


        except Exception as e:
            print("[App] ModbusTCPClient init/connect error:", e)
            self.modbus_client = None

        sm.current = "home"
        return sm

    def on_stop(self):
        # Uygulama kapanırken
        try:
            if self.modbus_client:
                self.modbus_client.close()
        except Exception:
            pass

        try:
            if self.root and self.root.has_screen("live"):
                live = self.root.get_screen("live")
                if hasattr(live, "close_serial"):
                    live.close_serial()
        except Exception:
            pass


if __name__ == "__main__":
    RoastDashboardApp().run()









