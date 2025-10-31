import json
import os
import config

# Define the path to the symbols file within the user_data directory
SYMBOLS_FILE_PATH = os.path.join(config.USER_DATA_ROOT, 'symbols.json')

def load_symbols():
    """
    Loads the symbol dictionary from the JSON file.
    Returns an empty dictionary if the file doesn't exist or is invalid.
    """
    if not os.path.exists(SYMBOLS_FILE_PATH):
        print("symbols.json not found, skipping symbol loading.")
        return {}
    
    try:
        with open(SYMBOLS_FILE_PATH, 'r', encoding='utf-8') as f:
            symbols_data = json.load(f)
            print(f"Successfully loaded {len(symbols_data)} symbols.")
            return symbols_data
    except (json.JSONDecodeError, IOError) as e:
        print(f"Error loading symbols.json: {e}")
        return {}
        