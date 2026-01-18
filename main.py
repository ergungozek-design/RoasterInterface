from kivy.app import App
from kivy.lang import Builder
from kivy.core.window import Window
from kivy.factory import Factory

from screens.live_roast import LiveRoastScreen

# widget importları
from widgets.roast_plot import RoastPlot
from widgets.airflow_gauge import AirflowGauge
from widgets.bar_gauge import BarGauge

# Kivy Factory'ye kaydet (KV artık import istemez)
Factory.register("RoastPlot", cls=RoastPlot)
Factory.register("AirflowGauge", cls=AirflowGauge)
Factory.register("BarGauge", cls=BarGauge)

Window.size = (1280, 800)
Window.minimum_width, Window.minimum_height = (1280, 800)
Window.clearcolor = (0.07, 0.08, 0.10, 1)

class RoastDashboardApp(App):
    def build(self):
        Builder.load_file("ui/live_roast.kv")
        return LiveRoastScreen()

    def on_stop(self):
        try:
            self.root.close_serial()
        except Exception:
            pass

if __name__ == "__main__":
    RoastDashboardApp().run()









