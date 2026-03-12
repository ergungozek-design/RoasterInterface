from kivy.uix.screenmanager import Screen
from kivy.app import App
from kivy.clock import Clock

from kivy.uix.popup import Popup
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label

#to make exe
#pyinstaller --onefile --windowed --noconfirm --add-data "ui;ui" --add-data "assets;assets" --add-data "profiles;profiles" --hidden-import "widgets.bean_roast_anim" main.py
#.\.venv\Scripts\Activate.ps1

class HomeScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._start_ev = None
        self._close_hold_ev = None
        self._close_popup = None

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

        # hold event varsa iptal
        if self._close_hold_ev:
            self._close_hold_ev.cancel()
            self._close_hold_ev = None

        try:
            w = self.ids.get("roast_anim_home", None)
            if w and hasattr(w, "stop"):
                w.stop()
        except Exception as e:
            print(f"[HomeScreen] roast_anim_home stop error: {e}")

    def go_live(self):
        if self.manager:
            self.manager.current = "live"

    # =========================================================
    # LONG PRESS CLOSE AREA
    # =========================================================
    def start_close_hold(self):
        # eski event varsa iptal
        if self._close_hold_ev:
            self._close_hold_ev.cancel()
            self._close_hold_ev = None

        # 3 saniye basılı tutulursa popup aç
        self._close_hold_ev = Clock.schedule_once(self._show_close_popup, 0.5)

    def cancel_close_hold(self):
        if self._close_hold_ev:
            self._close_hold_ev.cancel()
            self._close_hold_ev = None

    def _show_close_popup(self, dt):
        self._close_hold_ev = None

        # ekrandan çıkılmış olabilir
        if not self.manager or self.manager.current != "home":
            return

        layout = BoxLayout(
            orientation="vertical",
            spacing=20,
            padding=20
        )

        msg = Label(
            text="Do you want to close the program?"
        )

        btn_row = BoxLayout(
            spacing=20,
            size_hint_y=None,
            height=50
        )

        yes_btn = Button(text="Yes")
        no_btn = Button(text="No")

        btn_row.add_widget(yes_btn)
        btn_row.add_widget(no_btn)

        layout.add_widget(msg)
        layout.add_widget(btn_row)

        self._close_popup = Popup(
            title="Close Program",
            content=layout,
            size_hint=(None, None),
            size=(420, 220),
            auto_dismiss=False
        )

        yes_btn.bind(on_release=self._close_program)
        no_btn.bind(on_release=self._dismiss_close_popup)

        self._close_popup.open()

    def _dismiss_close_popup(self, *args):
        try:
            if self._close_popup:
                self._close_popup.dismiss()
        except Exception:
            pass
        self._close_popup = None

    def _close_program(self, *args):
        try:
            if self._close_popup:
                self._close_popup.dismiss()
        except Exception:
            pass
        self._close_popup = None

        try:
            App.get_running_app().stop()
        except Exception as e:
            print(f"[HomeScreen] app stop error: {e}")