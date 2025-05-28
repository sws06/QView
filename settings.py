# settings.py

import json
import os

import config  # To get SETTINGS_FILE_PATH

DEFAULT_SETTINGS = {
    "theme": "dark",  # "dark" or "light"
    "link_opening_preference": "default",  # "default" or "chrome_incognito"
}


def load_settings():
    """Loads settings from the settings file. Returns defaults if file not found or invalid."""
    if not hasattr(config, "SETTINGS_FILE_PATH"):
        print(
            "Error: SETTINGS_FILE_PATH not found in config.py. Using default settings."
        )
        return DEFAULT_SETTINGS.copy()

    try:
        if os.path.exists(config.SETTINGS_FILE_PATH):
            with open(config.SETTINGS_FILE_PATH, "r") as f:
                loaded_settings = json.load(f)
                # Validate and merge with defaults to ensure all keys are present
                settings = DEFAULT_SETTINGS.copy()
                # Only update keys that are still valid (now only 'theme')
                if "theme" in loaded_settings:
                    settings["theme"] = loaded_settings["theme"]
                return settings
        else:
            print(
                f"Settings file not found at {config.SETTINGS_FILE_PATH}. Creating with defaults."
            )
            save_settings(DEFAULT_SETTINGS.copy())
            return DEFAULT_SETTINGS.copy()
    except (json.JSONDecodeError, IOError) as e:
        print(f"Error loading settings file: {e}. Using default settings.")
        return DEFAULT_SETTINGS.copy()


def save_settings(settings_dict):
    """Saves the settings dictionary to the settings file."""
    if not hasattr(config, "SETTINGS_FILE_PATH"):
        print("Error: SETTINGS_FILE_PATH not found in config.py. Cannot save settings.")
        return

    try:
        os.makedirs(os.path.dirname(config.SETTINGS_FILE_PATH), exist_ok=True)
        # Ensure only valid settings are saved
        settings_to_save = {
            k: v for k, v in settings_dict.items() if k in DEFAULT_SETTINGS
        }
        with open(config.SETTINGS_FILE_PATH, "w") as f:
            json.dump(settings_to_save, f, indent=4)
        print(f"Settings saved to {config.SETTINGS_FILE_PATH}")
    except IOError as e:
        print(f"Error saving settings file: {e}")
