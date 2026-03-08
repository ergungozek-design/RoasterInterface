from kivy.uix.screenmanager import Screen
from kivy.app import App
from kivy.clock import Clock

class HomeScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._start_ev = None

    def on_enter(self, *args):
        try:
            App.get_running_app().active_tab = "home"
        except Exception:
            pass

        # önce varsa iptal et
        if self._start_ev:
            self._start_ev.cancel()
            self._start_ev = None

        # layout otursun diye 1 frame
        self._start_ev = Clock.schedule_once(self._start_home_anim, 0)

    def _start_home_anim(self, dt):
        self._start_ev = None

        # hızlı geçişte “home’dan çıkmış olabilir”
        if not self.manager or self.manager.current != "home":
            return

        try:
            w = self.ids.get("roast_anim_home", None)
            if w and hasattr(w, "start"):
                w.start()
        except Exception as e:
            print(f"[HomeScreen] roast_anim_home start error: {e}")

    def on_leave(self, *args):
        # scheduled start varsa iptal
        if self._start_ev:
            self._start_ev.cancel()
            self._start_ev = None

        try:
            w = self.ids.get("roast_anim_home", None)
            if w and hasattr(w, "stop"):
                w.stop()
        except Exception as e:
            print(f"[HomeScreen] roast_anim_home stop error: {e}")

    def go_live(self):
        if self.manager:
            self.manager.current = "live"