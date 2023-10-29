"""
Author: Core447
Year: 2023

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
any later version.

This programm comes with ABSOLUTELY NO WARRANTY!

You should have received a copy of the GNU General Public License
along with this program. If not, see <https://www.gnu.org/licenses/>.
"""
# Import gtk modules
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib

# Import Python modules
import cv2
import threading
from loguru import logger as log
from math import floor
from time import sleep

# Import globals
import globals as gl

# Import own modules
from src.backend.DeckManagement.ImageHelpers import image2pixbuf, is_transparent

class DeckGroup(Adw.PreferencesGroup):
    def __init__(self, settings_page):
        super().__init__(title="Deck Settings", description="Applies to the hole deck unless overwritten")
        self.deck_serial_number = settings_page.deck_serial_number

        self.add(Brightness(settings_page, self.deck_serial_number))
        self.add(Screensaver(settings_page, self.deck_serial_number))

class Brightness(Adw.PreferencesRow):
    def __init__(self, settings_page: "PageSettings", deck_serial_number, **kwargs):
        super().__init__()
        self.settings_page = settings_page
        self.deck_serial_number = deck_serial_number
        self.build()

        self.load_default()

    def build(self):
        self.main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, hexpand=True,
                                margin_start=15, margin_end=15, margin_top=15, margin_bottom=15)
        self.set_child(self.main_box)

        self.label = Gtk.Label(label="Brightness", hexpand=True, xalign=0)
        self.main_box.append(self.label)

        self.scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, min=0, max=100, step=1)
        self.scale.set_draw_value(True)
        self.scale.connect("value-changed", self.on_value_changed)
        self.main_box.append(self.scale)

    def on_value_changed(self, scale):
        value = round(scale.get_value())
        # update value in deck settings
        deck_settings = gl.settings_manager.get_deck_settings(self.deck_serial_number)
        deck_settings.setdefault("brightness", {})
        deck_settings["brightness"]["value"] = value
        # save settings
        gl.settings_manager.save_deck_settings(self.deck_serial_number, deck_settings)
        # update brightness if current page does not overwrite
        overwrite = False
        if "brightness" in self.settings_page.deck_controller.active_page:
            if "overwrite" in self.settings_page.deck_controller.active_page["brightness"]:
                overwrite = self.settings_page.deck_controller.active_page["brightness"]["overwrite"]
        if overwrite == False:
            self.settings_page.deck_controller.set_brightness(value)

    def load_default(self):
        original_values = gl.settings_manager.get_deck_settings(self.deck_serial_number)
        
        # Set defaut values 
        original_values.setdefault("brightness", {})
        brightness = original_values["brightness"].setdefault("value", 50)

        # Save if changed
        if original_values != gl.settings_manager.get_deck_settings(self.deck_serial_number):
            gl.settings_manager.save_deck_settings(self.deck_serial_number, original_values)

        # Update ui
        self.scale.set_value(brightness)

class Screensaver(Adw.PreferencesRow):
    def __init__(self, settings_page: "PageSettings", deck_serial_number, **kwargs):
        super().__init__()
        self.settings_page = settings_page
        self.deck_serial_number = deck_serial_number
        self.build()

        self.load_defaults()
    
    def build(self):
        self.main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, hexpand=True,
                                margin_start=15, margin_end=15, margin_top=15, margin_bottom=15)
        self.set_child(self.main_box)

        self.enable_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, hexpand=True)
        self.main_box.append(self.enable_box)

        self.enable_label = Gtk.Label(label="Enable Screensaver", hexpand=True, xalign=0)
        self.enable_box.append(self.enable_label)

        self.enable_switch = Gtk.Switch()
        self.enable_switch.connect("state-set", self.on_toggle_enable)
        self.enable_box.append(self.enable_switch)


        self.config_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, hexpand=True, visible=False)
        self.main_box.append(self.config_box)

        self.config_box.append(Gtk.Separator(hexpand=True, margin_top=10, margin_bottom=10))

        self.time_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, hexpand=True)
        self.config_box.append(self.time_box)

        self.time_label = Gtk.Label(label="Enable after (mins)", hexpand=True, xalign=0)
        self.time_box.append(self.time_label)

        self.time_spinner = Gtk.SpinButton.new_with_range(1, 60, 1)
        self.time_spinner.connect("value-changed", self.on_change_time)
        self.time_box.append(self.time_spinner)

        self.media_selector_label = Gtk.Label(label="Media to show:", hexpand=True, xalign=0)
        self.config_box.append(self.media_selector_label)

        self.media_selector_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, halign=Gtk.Align.CENTER)
        self.config_box.append(self.media_selector_box)

        self.media_selector_button = Gtk.Button(label="Select", css_classes=["page-settings-media-selector"])
        self.media_selector_button.connect("clicked", self.choose_with_file_dialog)
        self.media_selector_box.append(self.media_selector_button)

        self.media_selector_image = Gtk.Image() # Will be bound to the button by self.set_thumbnail()

        self.loop_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, hexpand=True, margin_bottom=15)
        self.config_box.append(self.loop_box)

        self.loop_label = Gtk.Label(label="Loop", hexpand=True, xalign=0)
        self.loop_box.append(self.loop_label)

        self.loop_switch = Gtk.Switch()
        self.loop_switch.connect("state-set", self.on_toggle_loop)
        self.loop_box.append(self.loop_switch)

        self.fps_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, hexpand=True)
        self.config_box.append(self.fps_box)

        self.fps_label = Gtk.Label(label="FPS", hexpand=True, xalign=0)
        self.fps_box.append(self.fps_label)

        self.fps_spinner = Gtk.SpinButton.new_with_range(1, 30, 1)
        self.fps_spinner.connect("value-changed", self.on_change_fps)
        self.fps_box.append(self.fps_spinner)

        self.brightness_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, hexpand=True)
        self.config_box.append(self.brightness_box)

        self.brightness_label = Gtk.Label(label="Brightness", hexpand=True, xalign=0)
        self.brightness_box.append(self.brightness_label)

        self.scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, min=0, max=100, step=1)
        self.scale.connect("value-changed", self.on_change_brightness)
        self.brightness_box.append(self.scale)


    def load_defaults(self):
        original_values = gl.settings_manager.get_deck_settings(self.deck_serial_number)
        
        # Set defaut values 
        original_values.setdefault("screensaver", {})
        enable = original_values["screensaver"].setdefault("enable", True)
        path = original_values["screensaver"].setdefault("path", None)
        loop = original_values["screensaver"].setdefault("loop", False)
        fps = original_values["screensaver"].setdefault("fps", 30)
        time = original_values["screensaver"].setdefault("time-delay", 5)
        brightness = original_values["screensaver"].setdefault("brightness", 30)

        # Save if changed
        if original_values != gl.settings_manager.get_deck_settings(self.deck_serial_number):
            gl.settings_manager.save_deck_settings(self.deck_serial_number, original_values)

        # Update ui
        self.enable_switch.set_active(enable)
        self.config_box.set_visible(enable)
        self.time_spinner.set_value(time)
        self.loop_switch.set_active(loop)
        self.fps_spinner.set_value(fps)
        self.scale.set_value(brightness)
        
    def on_toggle_enable(self, toggle_switch, state):
        config = gl.settings_manager.get_deck_settings(self.deck_serial_number)
        config["screensaver"]["enable"] = state
        # Save
        gl.settings_manager.save_deck_settings(self.deck_serial_number, config)
        # Update
        self.settings_page.deck_controller.screen_saver.set_enable(state)

    def on_toggle_loop(self, toggle_switch, state):
        config = gl.settings_manager.get_deck_settings(self.deck_serial_number)
        config["screensaver"]["loop"] = state
        # Save
        gl.settings_manager.save_deck_settings(self.deck_serial_number, config)
        # Update
        self.settings_page.deck_controller.screen_saver.loop = state

    def on_change_fps(self, spinner):
        config = gl.settings_manager.get_deck_settings(self.deck_serial_number)
        config["screensaver"]["fps"] = spinner.get_value_as_int()
        # Save
        gl.settings_manager.save_deck_settings(self.deck_serial_number, config)
        # Update
        self.settings_page.deck_controller.screen_saver.fps = spinner.get_value_as_int()

    def on_change_time(self, spinner):
        config = gl.settings_manager.get_deck_settings(self.deck_serial_number)
        config["screensaver"]["time-delay"] = spinner.get_value_as_int()
        # Save
        gl.settings_manager.save_deck_settings(self.deck_serial_number, config)
        # Update
        self.settings_page.deck_controller.screen_saver.set_time(spinner.get_value_as_int())

    def on_change_brightness(self, scale):
        config = gl.settings_manager.get_deck_settings(self.deck_serial_number)
        config["screensaver"]["brightness"] = scale.get_value()
        # Save
        gl.settings_manager.save_deck_settings(self.deck_serial_number, config)
        # Update
        self.settings_page.deck_controller.screen_saver.set_brightness(scale.get_value())

    def set_thumbnail(self, file_path):
        if file_path == None:
            return
        image = gl.media_manager.get_thumbnail(file_path)
        pixbuf = image2pixbuf(image)
        self.media_selector_image.set_from_pixbuf(pixbuf)
        self.media_selector_button.set_child(self.media_selector_image)

    def choose_with_file_dialog(self, button):
        dialog = ChooseScreensaverDialog(self)

class ChooseScreensaverDialog(Gtk.FileDialog):
    def __init__(self, screensaver_row: Screensaver):
        super().__init__(title="Select Background",
                         accept_label="Select")
        self.screensaver_row = screensaver_row
        self.open(callback=self.callback)

    def callback(self, dialog, result):
        try:
            selected_file = self.open_finish(result)
            file_path = selected_file.get_path()
        except GLib.Error as err:
            log.error(err)
            return
        
        # Add image as asset to asset manager
        asset_id = gl.asset_manager.add(file_path)
        asset_path = gl.asset_manager.get_by_id(asset_id)["internal-path"]
        
        self.screensaver_row.set_thumbnail(asset_path)
        config = gl.settings_manager.get_deck_settings(self.screensaver_row.deck_serial_number)
        config["screensaver"]["path"] = asset_path
        # Save
        gl.settings_manager.save_deck_settings(self.screensaver_row.deck_serial_number, config)
        # Update
        self.screensaver_row.settings_page.deck_controller.screen_saver.media_path = asset_path