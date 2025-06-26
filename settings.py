# settings.py

import json
import os
import config

# --- START DEFAULT_SETTINGS ---
DEFAULT_SETTINGS = {
    "theme": "rwb",  # "dark", "light", or "rwb"
    "link_opening_preference": "default",  # "default" or "chrome_incognito"
    "highlight_abbreviations": True, # New setting for abbreviation highlighting
}
# --- END DEFAULT_SETTINGS ---

def load_settings():
    """Loads settings from the settings file. Returns defaults if file not found or invalid."""
    try:
        if os.path.exists(config.SETTINGS_FILE_PATH):
            with open(config.SETTINGS_FILE_PATH, "r") as f:
                loaded_settings = json.load(f)
                settings = DEFAULT_SETTINGS.copy()
                settings.update({k: v for k, v in loaded_settings.items() if k in DEFAULT_SETTINGS})
                return settings
        else:
            save_settings(DEFAULT_SETTINGS.copy())
            return DEFAULT_SETTINGS.copy()
    except Exception as e:
        print(f"Error loading settings file: {e}. Using default settings.")
        return DEFAULT_SETTINGS.copy()

def save_settings(settings_dict):
    """Saves the settings dictionary to the settings file."""
    try:
        os.makedirs(os.path.dirname(config.SETTINGS_FILE_PATH), exist_ok=True)
        settings_to_save = {k: v for k, v in settings_dict.items() if k in DEFAULT_SETTINGS}
        with open(config.SETTINGS_FILE_PATH, "w") as f:
            json.dump(settings_to_save, f, indent=4)
        print(f"Settings saved to {config.SETTINGS_FILE_PATH}")
    except Exception as e:
        print(f"Error saving settings file: {e}")
