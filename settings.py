import json
import os
import config # Use the central config for file paths

# --- SETTINGS FILE PATH ---
SETTINGS_FILE_PATH = os.path.join(config.USER_DATA_ROOT, 'settings.json')

# --- DEFAULT SETTINGS ---
DEFAULT_SETTINGS = {
    "theme": "dark",
    "link_opening_preference": "default",
    "highlight_abbreviations": True
}

def load_settings():
    """
    Loads application settings from the JSON file.
    If the file doesn't exist, it creates it with default settings.
    """
    if not os.path.exists(SETTINGS_FILE_PATH):
        # If the file doesn't exist, create it with defaults
        save_settings(DEFAULT_SETTINGS)
        return DEFAULT_SETTINGS
    
    try:
        with open(SETTINGS_FILE_PATH, 'r', encoding='utf-8') as f:
            settings_data = json.load(f)
            # Ensure all default keys are present
            for key, value in DEFAULT_SETTINGS.items():
                settings_data.setdefault(key, value)
            return settings_data
    except (json.JSONDecodeError, IOError) as e:
        print(f"Error loading settings file: {e}. Reverting to default settings.")
        # If the file is corrupted, create a new one with defaults
        save_settings(DEFAULT_SETTINGS)
        return DEFAULT_SETTINGS

def save_settings(settings_data):
    """
    Saves the provided settings dictionary to the JSON file.
    """
    try:
        # Ensure the user_data directory exists
        os.makedirs(os.path.dirname(SETTINGS_FILE_PATH), exist_ok=True)
        
        with open(SETTINGS_FILE_PATH, 'w', encoding='utf-8') as f:
            json.dump(settings_data, f, indent=4)
    except IOError as e:
        print(f"Error saving settings file: {e}")
