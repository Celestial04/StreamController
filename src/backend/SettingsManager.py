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
# Import Python modules
import os, json
from loguru import logger as log

class SettingsManager:
    def load_settings_from_file(self, file_path: str) -> dict:
        if not os.path.exists(file_path):
            log.warning(f"Settings file {file_path} not found.")
            return
        with open(file_path) as f:
            return json.load(f)
        
    def save_settings_to_file(self, file_path: str, settings: dict) -> None:
        with open(file_path, "w") as f:
            json.dump(settings, f, indent=4)