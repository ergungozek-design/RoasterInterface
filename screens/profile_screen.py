import json
import shutil
from pathlib import Path

from kivy.app import App
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.properties import StringProperty, ObjectProperty, BooleanProperty
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.popup import Popup
from kivy.uix.label import Label
from kivy.uix.screenmanager import Screen
from kivy.graphics import Color, RoundedRectangle

from services.text_keypad import TextKeypadPopup


# ---------------------------------------------------------
# Tile with short press + long press (>=1s)
# ---------------------------------------------------------
class FolderTile(ButtonBehavior, BoxLayout):
    display_name = StringProperty("")
    icon_source = StringProperty("")          # filled item icon (folder.png or file.png)
    empty_icon_source = StringProperty("")    # empty slot icon (folder_new.png or file_new.png)
    payload = StringProperty("")              # folder name OR file name
    is_empty = BooleanProperty(True)

    on_short_press = ObjectProperty(None, allownone=True)
    on_long_press = ObjectProperty(None, allownone=True)

    _lp_ev = None
    _lp_fired = False

    def on_touch_down(self, touch):
        if not self.collide_point(*touch.pos):
            return super().on_touch_down(touch)

        ret = super().on_touch_down(touch)

        self._lp_fired = False
        if self.on_long_press is not None and not self.is_empty:
            self._lp_ev = Clock.schedule_once(self._fire_long_press, 1.0)

        return ret

    def on_touch_up(self, touch):
        if self._lp_ev is not None:
            self._lp_ev.cancel()
            self._lp_ev = None

        if not self.collide_point(*touch.pos):
            return super().on_touch_up(touch)

        # long press fired -> ignore click
        if self._lp_fired:
            return super().on_touch_up(touch)

        # ✅ short press: önce biz çalıştırıyoruz
        if self.on_short_press is not None:
            self.on_short_press(self)

        # ✅ ve burada True dönerek ButtonBehavior'ın ekstra on_release zincirini kesiyoruz
        return True


    def _fire_long_press(self, *_):
        self._lp_fired = True
        if self.on_long_press is not None:
            self.on_long_press(self)


class ProfileScreen(Screen):
    top_title = StringProperty("PROFILE")
    current_folder = StringProperty("")  # "" => folder view, else file view
    MAX_SLOTS = 20

    # ✅ Make Profile akışı için MOD
    make_profile_mode = BooleanProperty(False)

    _keep_mode = False
    _keep_folder = ""

    _text_kp = None

    def on_enter(self, *args):
        try:
            App.get_running_app().active_tab = "profile"
        except Exception:
            pass

        # ✅ detail'den geri dönüşte file listesine dön
        if getattr(self, "_keep_mode", False) and getattr(self, "_keep_folder", ""):
            folder = self._keep_folder
            self._keep_mode = False
            self._keep_folder = ""
            self.show_files(folder)
            return

        # ✅ Make Profile mode aktifse: klasör listesi ile başla
        if self.make_profile_mode:
            self.show_folders()
            return

        self.show_folders()

    # ---------------------------------------------------------
    # ✅ Dışarıdan çağrılacak: Make Profile seçim moduna gir
    # ---------------------------------------------------------
    def enter_make_profile_mode(self):
        self.make_profile_mode = True
        self.current_folder = ""
        self.top_title = "SELECT FOLDER"
        self.show_folders()

    # ---------------------------------------------------------
    # Paths
    # ---------------------------------------------------------
    def _project_root(self) -> Path:
        return Path(__file__).resolve().parent.parent

    def _profiles_dir(self) -> Path:
        pdir = self._project_root() / "profiles"
        pdir.mkdir(parents=True, exist_ok=True)
        return pdir

    def _folder_path(self, folder_name: str) -> Path:
        return self._profiles_dir() / folder_name

    def _profile_path(self, folder_name: str, profile_name: str) -> Path:
        return self._folder_path(folder_name) / f"{profile_name}.json"

    # ---------------------------------------------------------
    # Icons
    # ---------------------------------------------------------
    def _icon(self, filename: str) -> str:
        p = self._project_root() / "assets" / "icons" / filename
        return str(p) if p.exists() else ""

    def _folder_icon(self) -> str:
        return self._icon("folder.png")

    def _folder_empty_icon(self) -> str:
        return self._icon("folder_new.png")

    def _file_icon(self) -> str:
        return self._icon("file.png")

    def _file_empty_icon(self) -> str:
        return self._icon("file_new.png")

    # ---------------------------------------------------------
    # Listing
    # ---------------------------------------------------------
    def _list_folder_names(self):
        pdir = self._profiles_dir()
        dirs = [p for p in pdir.iterdir() if p.is_dir() and not p.name.startswith(".")]
        dirs.sort(key=lambda x: x.name.lower())
        return [d.name for d in dirs]

    def _list_profiles_in_folder(self, folder_name: str):
        fdir = self._folder_path(folder_name)
        if not fdir.exists():
            return []
        files = [p for p in fdir.glob("*.json") if p.is_file()]
        files.sort(key=lambda x: x.name.lower())
        return [f.stem for f in files]

    # ---------------------------------------------------------
    # UI Helpers
    # ---------------------------------------------------------
    def _grid(self):
        grid = self.ids.get("grid_profiles")
        if not grid:
            print("[ProfileScreen] ERROR: grid_profiles id not found")
        return grid

    def _sanitize_name(self, s: str) -> str:
        s = (s or "").strip()
        bad = '<>:"/\\|?*'
        for ch in bad:
            s = s.replace(ch, "_")
        s = s.replace("\n", " ").replace("\r", " ")
        s = " ".join(s.split())
        return s

    # ---------------------------------------------------------
    # ✅ TextKeypad open
    # ---------------------------------------------------------
    def _open_text_keypad(self, title: str, initial_text: str, on_ok, max_len: int = 24):
        # ✅ Eğer popup zaten açıksa tekrar açma (double-open fix)
        if getattr(self, "_text_kp", None) is not None and self._text_kp.parent:
            return

        def _release():
            self._text_kp = None

        def _ok(txt):
            try:
                on_ok(self._sanitize_name(txt))
            finally:
                _release()

        def _cancel():
            _release()

        self._text_kp = TextKeypadPopup(
            title=title,
            initial_text=initial_text or "",
            max_len=max_len,
            fullscreen=True,
            on_ok=_ok,
            on_cancel=_cancel,
        )
        self._text_kp.open()


    # ---------------------------------------------------------
    # Dark Card Popup (Rename/Delete menu + confirm)
    # ---------------------------------------------------------
    def _dark_popup(self, content_widget, w=420, h=320):
        pop = Popup(
            title="",
            content=content_widget,
            size_hint=(None, None),
            size=(dp(w), dp(h)),
            auto_dismiss=False,
            separator_height=0,
            background="",
            background_color=(0, 0, 0, 0)
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

    def _menu_popup_folder(self, folder_name: str):
        # ✅ Make Profile modunda rename/delete menüsü kapalı
        if self.make_profile_mode:
            return

        inner = BoxLayout(orientation="vertical", spacing=dp(12))

        title = Label(
            text=folder_name,
            font_size="18sp",
            bold=True,
            size_hint_y=None,
            height=dp(36),
            color=(1, 1, 1, 1),
        )

        inner.add_widget(title)

        from kivy.factory import Factory

        b_rename = Factory.RoundedPopupButton(text="Rename")
        b_delete = Factory.RoundedPopupButton(text="Delete")
        b_cancel = Factory.RoundedPopupButton(text="Cancel")

        inner.add_widget(b_rename)
        inner.add_widget(b_delete)
        inner.add_widget(b_cancel)

        card = self._make_dark_card(inner)
        pop = self._dark_popup(card, w=440, h=320)

        def _rename(*_):
            pop.dismiss()

            def _rename_to(new_name: str):
                new_name = self._sanitize_name(new_name)
                if not new_name or new_name == folder_name:
                    return

                src = self._folder_path(folder_name)
                dst = self._folder_path(new_name)

                if dst.exists():
                    self._toast("Target name already exists")
                    return

                try:
                    src.rename(dst)
                    self.show_folders()
                except Exception as e:
                    self._toast(f"Rename failed: {e}")

            self._open_text_keypad("Rename Folder", folder_name, _rename_to)

        def _delete(*_):
            pop.dismiss()
            self._confirm_delete_folder(folder_name)

        b_rename.bind(on_release=_rename)
        b_delete.bind(on_release=_delete)
        b_cancel.bind(on_release=lambda *_: pop.dismiss())

        pop.open()

    def _confirm_delete_folder(self, folder_name: str):
        # ✅ Make Profile modunda silme kapalı
        if self.make_profile_mode:
            return

        from kivy.factory import Factory

        inner = BoxLayout(orientation="vertical", spacing=dp(14), padding=(dp(6), dp(6)))

        msg = Label(
            text="Delete folder?",
            font_size="20sp",
            bold=True,
            color=(1, 1, 1, 1),
            size_hint_y=None,
            height=dp(28),
            halign="center",
            valign="middle",
        )
        msg.bind(size=lambda w, *_: setattr(w, "text_size", w.size))
        inner.add_widget(msg)

        name = Label(
            text=folder_name,
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

        card = self._make_dark_card(inner, radius=22)
        pop = self._dark_popup(card, w=520, h=300)

        b_no.bind(on_release=lambda *_: pop.dismiss())

        def _yes(*_):
            pop.dismiss()
            try:
                shutil.rmtree(self._folder_path(folder_name))
                self.show_folders()
            except Exception as e:
                self._toast(f"Delete failed: {e}")

        b_yes.bind(on_release=_yes)
        pop.open()

    # ---------------------------------------------------------
    # Folder view (20 slot)
    # ---------------------------------------------------------
    def show_folders(self):
        self.current_folder = ""
        self.top_title = "SELECT FOLDER" if self.make_profile_mode else "PROFILE"

        grid = self._grid()
        if not grid:
            return

        grid.clear_widgets()

        folder_names = self._list_folder_names()
        filled_count = min(len(folder_names), self.MAX_SLOTS)

        from kivy.factory import Factory

        for i in range(self.MAX_SLOTS):
            name = folder_names[i] if i < filled_count else ""

            tile = Factory.FolderTile()
            tile.display_name = name
            tile.payload = name
            tile.is_empty = (name == "")

            tile.icon_source = self._folder_icon() if not tile.is_empty else ""
            tile.empty_icon_source = self._folder_empty_icon()

            if tile.is_empty:
                # ✅ Make Profile modunda boş klasör slotuna tıklamayı kapat
                if self.make_profile_mode:
                    tile.on_short_press = None
                    tile.on_long_press = None
                else:
                    tile.on_short_press = self._empty_folder_clicked
                    tile.on_long_press = None
            else:
                tile.on_short_press = self._folder_clicked
                tile.on_long_press = self._folder_long_pressed

            grid.add_widget(tile)

    def _empty_folder_clicked(self, tile: FolderTile):
        def _create_folder(name: str):
            name = self._sanitize_name(name)
            if not name:
                return

            fdir = self._folder_path(name)
            if fdir.exists():
                self._toast(f"Folder exists: {name}")
                return

            try:
                fdir.mkdir(parents=True, exist_ok=False)
                self.show_folders()
            except Exception as e:
                self._toast(f"Create failed: {e}")

        self._open_text_keypad("New Folder Name", "", _create_folder)

    def _folder_clicked(self, tile: FolderTile):
        self.show_files(tile.payload)

    def _folder_long_pressed(self, tile: FolderTile):
        self._menu_popup_folder(tile.payload)

    # ---------------------------------------------------------
    # File view (inside folder): 20 slot
    # ---------------------------------------------------------
    def show_files(self, folder_name: str):
        self.current_folder = folder_name
        self.top_title = folder_name if not self.make_profile_mode else f"SELECT SLOT: {folder_name}"

        grid = self._grid()
        if not grid:
            return
        grid.clear_widgets()

        names = self._list_profiles_in_folder(folder_name)
        filled_count = min(len(names), self.MAX_SLOTS)

        from kivy.factory import Factory

        for i in range(self.MAX_SLOTS):
            pname = names[i] if i < filled_count else ""

            tile = Factory.FolderTile()
            tile.display_name = pname
            tile.payload = pname
            tile.is_empty = (pname == "")

            tile.icon_source = self._file_icon() if not tile.is_empty else ""
            tile.empty_icon_source = self._file_empty_icon()

            if tile.is_empty:
                tile.on_short_press = self._empty_file_clicked
                tile.on_long_press = None
            else:
                tile.on_short_press = self._file_clicked
                tile.on_long_press = self._file_long_pressed

            grid.add_widget(tile)

    def _file_clicked(self, tile: FolderTile):
        # ✅ Make Profile modunda dolu profile'a girilmez
        if self.make_profile_mode:
            self._toast("Only empty slots can be used to create a new profile.")
            return

        folder_name = self.current_folder
        profile_name = tile.payload
        fpath = self._profile_path(folder_name, profile_name)

        try:
            data = json.loads(fpath.read_text(encoding="utf-8"))
        except Exception as e:
            self._toast(f"JSON read error: {e}")
            data = {}

        try:
            detail = self.manager.get_screen("profile_detail")
        except Exception as e:
            self._toast(f"profile_detail not found: {e}")
            return

        if hasattr(detail, "load_profile"):
            detail.return_screen = "profile"
            detail.return_to_files = True
            detail.load_profile(profile_name, data, folder_name=folder_name)
        else:
            self._toast("profile_detail.load_profile not found")
            return

        self.manager.current = "profile_detail"

    def _empty_file_clicked(self, tile: FolderTile):
        folder_name = self.current_folder
        if not folder_name:
            return

        def _create_profile(pname: str):
            pname = self._sanitize_name(pname)
            if not pname:
                return

            fpath = self._profile_path(folder_name, pname)

            if fpath.exists():
                self._toast(f"Profile exists: {pname}")
                return

            try:
                # ✅ boş bir profil json’u oluştur
                fpath.write_text(json.dumps({}, ensure_ascii=False, indent=2), encoding="utf-8")

                # ✅ Make Profile modundaysak: ProfileDetail’e gitme -> MakeProfile ekranına dön + seçimi yaz
                # ✅ Make Profile modundaysak: ProfileDetail’e gitme -> MakeProfile ekranına dön + seçimi yaz
                if self.make_profile_mode:
                    # moddan çık
                    self.make_profile_mode = False
                    self.current_folder = ""
                    self.top_title = "PROFILE"

                    # MakeProfile ekranına seçimi aktar
                    try:
                        makep = self.manager.get_screen("make_profile")
                        if hasattr(makep, "set_selected_profile"):
                            makep.set_selected_profile(folder_name, pname, str(fpath))
                    except Exception as e:
                        print("[ProfileScreen] set_selected_profile failed:", e)

                    # ✅ PLC: Make Profile aktif → COIL501 = 1
                    try:
                        live = self.manager.get_screen("live")
                        ok, err = live.client.write_single_coil(501, 1)
                        live.last_read = "COIL501=1 (Make Profile Active)" if ok else f"COIL501 FAIL: {err}"
                    except Exception as e:
                        try:
                            live.last_read = f"COIL501 EXC: {e}"
                        except Exception:
                            pass

                    # MakeProfile ekranına geç
                    try:
                        if self.manager and self.manager.has_screen("make_profile"):
                            self.manager.current = "make_profile"
                        else:
                            self._toast('Screen "make_profile" not found')
                    except Exception:
                        pass
                    return


                # normal mod: listeyi yenile
                self.show_files(folder_name)

                # normal mod: istersen direkt profile_detail aç
                try:
                    detail = self.manager.get_screen("profile_detail")
                    if hasattr(detail, "load_profile"):
                        detail.load_profile(pname, {}, folder_name=folder_name)
                        self.manager.current = "profile_detail"
                except Exception as e:
                    self._toast(f"profile_detail open failed: {e}")

            except Exception as e:
                self._toast(f"Create failed: {e}")

        self._open_text_keypad("New Profile Name", "", _create_profile)

    def _file_long_pressed(self, tile: FolderTile):
        # ✅ Make Profile modunda rename/delete menüsü yok
        if self.make_profile_mode:
            return
        self._menu_popup_file(tile.payload)

    def _menu_popup_file(self, profile_name: str):
        folder_name = self.current_folder
        if not folder_name:
            return

        from kivy.factory import Factory

        inner = BoxLayout(orientation="vertical", spacing=dp(12))

        title = Label(
            text=profile_name,
            font_size="21sp",
            bold=True,
            size_hint_y=None,
            height=dp(40),
            color=(1, 1, 1, 1),
            halign="center",
            valign="middle",
        )
        title.bind(size=lambda w, *_: setattr(w, "text_size", w.size))
        inner.add_widget(title)

        b_rename = Factory.RoundedPopupButton(text="Rename")
        b_delete = Factory.RoundedPopupButton(text="Delete")
        b_cancel = Factory.RoundedPopupButton(text="Cancel")

        inner.add_widget(b_rename)
        inner.add_widget(b_delete)
        inner.add_widget(b_cancel)

        card = self._make_dark_card(inner, radius=22)
        pop = self._dark_popup(card, w=520, h=330)

        def _rename(*_):
            pop.dismiss()

            def _rename_to(new_name: str):
                new_name = self._sanitize_name(new_name)
                if not new_name or new_name == profile_name:
                    return

                src = self._profile_path(folder_name, profile_name)
                dst = self._profile_path(folder_name, new_name)

                if dst.exists():
                    self._toast("Target name already exists")
                    return

                try:
                    src.rename(dst)
                    self.show_files(folder_name)
                except Exception as e:
                    self._toast(f"Rename failed: {e}")

            self._open_text_keypad("Rename Profile", profile_name, _rename_to)

        def _delete(*_):
            pop.dismiss()
            self._confirm_delete_file(folder_name, profile_name)

        b_rename.bind(on_release=_rename)
        b_delete.bind(on_release=_delete)
        b_cancel.bind(on_release=lambda *_: pop.dismiss())

        pop.open()

    def _confirm_delete_file(self, folder_name: str, profile_name: str):
        from kivy.factory import Factory

        inner = BoxLayout(orientation="vertical", spacing=dp(14), padding=(dp(6), dp(6)))

        msg = Label(
            text="Delete profile?",
            font_size="20sp",
            bold=True,
            color=(1, 1, 1, 1),
            size_hint_y=None,
            height=dp(28),
            halign="center",
            valign="middle",
        )
        msg.bind(size=lambda w, *_: setattr(w, "text_size", w.size))
        inner.add_widget(msg)

        name = Label(
            text=profile_name,
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

        card = self._make_dark_card(inner, radius=22)
        pop = self._dark_popup(card, w=520, h=300)

        b_no.bind(on_release=lambda *_: pop.dismiss())

        def _yes(*_):
            pop.dismiss()
            try:
                fpath = self._profile_path(folder_name, profile_name)
                if fpath.exists():
                    fpath.unlink()
                self.show_files(folder_name)
            except Exception as e:
                self._toast(f"Delete failed: {e}")

        b_yes.bind(on_release=_yes)
        pop.open()

    # ---------------------------------------------------------
    # Back
    # ---------------------------------------------------------
    def on_back(self):
        # klasör içindeysek önce folder listesine dön
        if self.current_folder:
            self.show_folders()
            return

        # root seviyedeysek hangi modda olursa olsun live'a dön
        self.make_profile_mode = False
        self.current_folder = ""
        self.top_title = "PROFILE"
        self._keep_mode = False
        self._keep_folder = ""

        if self.manager:
            if self.manager.has_screen("live"):
                self.manager.current = "live"
            elif self.manager.has_screen("live_roast"):
                self.manager.current = "live_roast"
            else:
                try:
                    self.manager.current = self.manager.screen_names[0]
                except Exception:
                    pass

    def on_back_eski(self):
        # ✅ Make Profile modunda:
        # - klasör içindeysek folder listesine dön
        # - folder listesinde isek make_profile ekranına dön
        if self.make_profile_mode:
            if self.current_folder:
                self.show_folders()
                return
            try:
                if self.manager and self.manager.has_screen("make_profile"):
                    self.manager.current = "make_profile"
                else:
                    self.manager.current = "live"
            except Exception:
                pass
            return

        # normal mod
        if self.current_folder:
            self.show_folders()
            return

        if self.manager:
            if self.manager.has_screen("live"):
                self.manager.current = "live"
            elif self.manager.has_screen("live_roast"):
                self.manager.current = "live_roast"
            else:
                try:
                    self.manager.current = self.manager.screen_names[0]
                except Exception:
                    pass

    # ---------------------------------------------------------
    # Toast (simple)
    # ---------------------------------------------------------
    def _toast(self, msg: str):
        print("[ProfileScreen]", msg)

        inner = BoxLayout(orientation="vertical", spacing=dp(10))
        inner.add_widget(Label(text=msg, color=(1, 1, 1, 1)))

        card = self._make_dark_card(inner, radius=18)
        pop = self._dark_popup(card, w=520, h=180)
        pop.open()
        Clock.schedule_once(lambda *_: pop.dismiss(), 1.0)
