# --- START DATA_PY_HEADER ---
import os
import sys # <--- ADD THIS LINE
import pandas as pd
import json

import config  # For POSTS_DATA_PATH, DATAFRAME_PICKLE_PATH
import utils  # For tag_post_with_themes

# --- END DATA_PY_HEADER ---


# --- START LOAD_OR_PARSE_DATA ---
def load_or_parse_data():
    df = None
    # 1. Try to load the DataFrame from the pickle file first for speed
    if os.path.exists(config.DATAFRAME_PICKLE_PATH):
        try:
            print(f"Loading DataFrame from {config.DATAFRAME_PICKLE_PATH}...")
            df = pd.read_pickle(config.DATAFRAME_PICKLE_PATH)
            print("DataFrame loaded successfully from pickle.")

            # Basic validation of the pickled DataFrame
            required_cols = ['postNumber', 'text', 'timestamp', 'datetime_utc_str', 'images', 'references']
            if not all(col in df.columns for col in required_cols) or \
               ('timestamp' in df.columns and df['timestamp'].isna().all()): # Check if a key column like timestamp is all NaN
                print("Pickled DataFrame missing essential columns or key data is invalid. Re-processing.")
                df = None # Force re-processing

            pickle_modified_during_load = False
            if df is not None:
                # Ensure 'Themes' column exists (might have been added in later versions)
                if 'Themes' not in df.columns:
                    print("Adding 'Themes' column to loaded DataFrame from pickle.")
                    if 'text' in df.columns: # Ensure 'text' field (new name) exists
                        df['Themes'] = df['text'].apply(utils.tag_post_with_themes)
                    else: # Fallback if 'text' is somehow missing
                        df['Themes'] = pd.Series([[] for _ in range(len(df))], index=df.index)
                    pickle_modified_during_load = True
                
                # Ensure 'Referenced Posts Display' column exists
                if 'Referenced Posts Display' not in df.columns:
                    print("Adding 'Referenced Posts Display' column to loaded DataFrame from pickle.")
                    if 'references' in df.columns: # New key name for references
                        def fmt_refs_from_new_format(refs_list):
                            if isinstance(refs_list, list) and refs_list:
                                return ", ".join([f"{r.get('id', '')} ('{str(r.get('snippet', ''))[:30]}...')" for r in refs_list if isinstance(r, dict)])
                            return ""
                        df['Referenced Posts Display'] = df['references'].apply(fmt_refs_from_new_format)
                    else:
                        df['Referenced Posts Display'] = "" # Fallback
                    pickle_modified_during_load = True

                if pickle_modified_during_load:
                    try:
                        df.to_pickle(config.DATAFRAME_PICKLE_PATH)
                        print("DataFrame re-saved to pickle with added/updated columns.")
                    except Exception as e:
                        print(f"Error re-saving DataFrame to pickle after adding columns: {e}")
            return df # Return the DataFrame loaded from pickle

        except Exception as e:
            print(f"Error loading DataFrame from pickle: {e}. Will try to parse JSON files.")
            df = None # Reset df if pickle loading failed

    # 2. If pickle not loaded, try to parse the new QView standard JSON format
    if df is None and hasattr(config, 'QVIEW_CORE_DATA_PATH') and os.path.exists(config.QVIEW_CORE_DATA_PATH):
        print(f"Parsing QView standard data from {config.QVIEW_CORE_DATA_PATH}...")
        try:
            with open(config.QVIEW_CORE_DATA_PATH, 'r', encoding='utf-8') as f:
                data_list = json.load(f) # Standard json.load for our new format

            if not isinstance(data_list, list):
                print(f"Error: {config.QVIEW_CORE_DATA_FILENAME} does not contain a list of posts."); return None
            
            all_posts_data = []
            for post_obj in data_list:
                # Directly use the fields from our defined structure
                # Add any simple transformations if needed, though most should be in the conversion script
                all_posts_data.append({
                    'Post Number': post_obj.get('postNumber'),
                    'Timestamp': post_obj.get('timestamp'), # This will be used for Datetime_UTC
                    # 'datetime_utc_str': post_obj.get('datetime_utc_str'), # Already a string, can be kept or regenerated
                    'Author': post_obj.get('author'),
                    'Tripcode': post_obj.get('tripcode'),
                    'Text': post_obj.get('text', ""), # Ensure default for text
                    'ImagesJSON': post_obj.get('images', []), # Map to existing 'ImagesJSON' for compatibility with image display
                    'Image Count': len(post_obj.get('images', [])),
                    'Link': post_obj.get('sourceLink'),
                    'Site': post_obj.get('sourceSite'),
                    'Board': post_obj.get('sourceBoard'),
                    'Referenced Posts Raw': post_obj.get('references', []) # Map to existing 'Referenced Posts Raw'
                })
            
            if not all_posts_data:
                print("No post data extracted from QView core data file.")
                return pd.DataFrame() # Return empty DataFrame

            df = pd.DataFrame(all_posts_data)
            # --- Process DataFrame (common logic) ---
            if 'Timestamp' in df.columns:
                df['Timestamp'] = pd.to_numeric(df['Timestamp'], errors='coerce')
                df.dropna(subset=['Timestamp'], inplace=True) # Critical for date conversion
                df['Datetime_UTC'] = pd.to_datetime(df['Timestamp'], unit='s', utc=True)
                df.sort_values(by='Datetime_UTC', inplace=True, ignore_index=True) # Sort by actual datetime
            else:
                df['Datetime_UTC'] = pd.NaT # Ensure column exists even if timestamp was missing

            if 'Post Number' in df.columns:
                df['Post Number'] = pd.to_numeric(df['Post Number'], errors='coerce').astype('Int64')
            
            if 'Text' not in df.columns: df['Text'] = "" # Ensure Text column exists
            df['Themes'] = df['Text'].apply(utils.tag_post_with_themes)

            if 'Referenced Posts Raw' not in df.columns: df['Referenced Posts Raw'] = pd.Series(dtype='object')
            def fmt_refs(refs_list):
                if isinstance(refs_list, list) and refs_list:
                    return ", ".join([f"{r.get('id', '')} ('{str(r.get('snippet', ''))[:30]}...')" for r in refs_list if isinstance(r, dict)])
                return ""
            df['Referenced Posts Display'] = df['Referenced Posts Raw'].apply(fmt_refs)

            if 'ImagesJSON' not in df.columns: df['ImagesJSON'] = pd.Series([[] for _ in range(len(df))], index=df.index)
            # --- End Process DataFrame ---

            df.to_pickle(config.DATAFRAME_PICKLE_PATH)
            print(f"DataFrame created from {config.QVIEW_CORE_DATA_FILENAME} and saved to pickle.")
            return df

        except Exception as e:
            print(f"Error parsing {config.QVIEW_CORE_DATA_FILENAME} or saving pickle: {e}")
            import traceback; traceback.print_exc()
            df = None # Ensure df is None if this step fails

    # 3. If QView core data not found, try to find original and convert
    if df is None and os.path.exists(config.POSTS_DATA_PATH):
        print(f"QView core data file not found. Original '{os.path.basename(config.POSTS_DATA_PATH)}' found.")
        from tkinter import messagebox # Local import for UI element
        
        # Check if convert_data.py exists
        convert_script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "convert_data.py") # Assuming convert_data.py is in root
        if not os.path.exists(convert_script_path):
             # Try another common location relative to current file if data.py is in a subdir
             convert_script_path_alt = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0] if hasattr(sys, 'argv') else __file__)), "convert_data.py")
             if os.path.exists(convert_script_path_alt):
                 convert_script_path = convert_script_path_alt
             else:
                 messagebox.showerror("Conversion Error", f"convert_data.py not found. Please place it in the QView root directory and restart.")
                 return None


        messagebox.showinfo("Data Conversion Required",
                            f"QView needs to convert your '{os.path.basename(config.POSTS_DATA_PATH)}' file "
                            f"into its standard format ('{config.QVIEW_CORE_DATA_FILENAME}').\n\n"
                            "This is a one-time process and may take a few moments.\n"
                            "Click OK to proceed.",
                            parent=None) # No parent for early stage messagebox
        try:
            import convert_data # Assumes convert_data.py is in the same directory or Python path
            if convert_data.convert_to_qview_format(config.POSTS_DATA_PATH, config.QVIEW_CORE_DATA_PATH):
                print("Conversion successful. Attempting to load new data file...")
                # Call self recursively to now load the newly created qview_core_data.json
                return load_or_parse_data() 
            else:
                messagebox.showerror("Conversion Failed",
                                     "Automatic data conversion failed. Please check the console output.\n"
                                     f"You may need to run 'python convert_data.py' manually from the QView directory.",
                                     parent=None)
                return None
        except ImportError:
            messagebox.showerror("Conversion Error",
                                 f"Could not import 'convert_data.py'. Make sure it's in the QView directory.\n"
                                 "You may need to run 'python convert_data.py' manually.",
                                 parent=None)
            return None
        except Exception as e_convert:
            messagebox.showerror("Conversion Failed",
                                 f"An error occurred during automatic data conversion: {e_convert}\n"
                                 "Please check the console output or run 'python convert_data.py' manually.",
                                 parent=None)
            return None

    # 4. If no data files are found at all
    if df is None:
        from tkinter import messagebox # Ensure messagebox is available
        messagebox.showerror("Data Error",
                             f"No data file found. Please ensure either '{config.QVIEW_CORE_DATA_FILENAME}' (in user_data) "
                             f"or '{os.path.basename(config.POSTS_DATA_PATH)}' (in the application root) is present.",
                             parent=None)
        return None

    return df # Should ideally be populated by one of the above paths
# --- END LOAD_OR_PARSE_DATA ---
