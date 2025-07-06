# --- START DATA_PY_HEADER ---
import os
import json
import pandas as pd
import datetime
import re
import pickle

import config  # For POSTS_DATA_PATH, DATAFRAME_PICKLE_PATH
import utils   # For tag_post_with_themes
# --- END DATA_PY_HEADER ---

# Global variables to store the maps (accessible via app_data.post_quotes_map etc.)
post_quotes_map = {}
post_quoted_by_map = {}
post_markers_map = {}
post_time_hhmm_map = {}
post_time_hhmms_map = {}
theme_posts_map = {}


def _build_quote_indices(df):
    global post_quotes_map, post_quoted_by_map
    post_quotes_map = {}
    post_quoted_by_map = {}

    for index, row in df.iterrows():
        post_num = row.get('Post Number')
        if pd.isna(post_num):
            continue # Skip posts without a valid Post Number for linking

        quoted_posts_in_this_post = []
        referenced_posts_raw = row.get('Referenced Posts Raw', [])
        if isinstance(referenced_posts_raw, list):
            for ref_data in referenced_posts_raw:
                if isinstance(ref_data, dict) and 'reference' in ref_data:
                    ref_id_raw = str(ref_data['reference']).strip()
                    # Extract numerical part from reference (e.g., ">>1234" or "1234")
                    match = re.search(r'\d+', ref_id_raw)
                    if match:
                        try:
                            quoted_num = int(match.group(0))
                            quoted_posts_in_this_post.append(quoted_num)

                            # Build reverse map (quoted_by)
                            if quoted_num not in post_quoted_by_map:
                                post_quoted_by_map[quoted_num] = []
                            if post_num not in post_quoted_by_map[quoted_num]: # Avoid duplicates
                                post_quoted_by_map[quoted_num].append(post_num)
                        except ValueError:
                            pass # Malformed reference that's not just a number
        
        if quoted_posts_in_this_post:
            post_quotes_map[post_num] = quoted_posts_in_this_post
    
    # Sort quoted_by lists for consistent display
    for num in post_quoted_by_map:
        post_quoted_by_map[num].sort()

    print(f"Quote indices built: {len(post_quotes_map)} posts quoting others, {len(post_quoted_by_map)} posts being quoted.")


def _build_additional_indices(df):
    global post_markers_map, post_time_hhmm_map, post_time_hhmms_map, theme_posts_map
    post_markers_map = {}
    post_time_hhmm_map = {}
    post_time_hhmms_map = {}
    theme_posts_map = {}

    for index, row in df.iterrows():
        post_num = row.get('Post Number')
        if pd.isna(post_num):
            continue

        # --- Build Marker Map ---
        text = row.get('Text', '')
        if isinstance(text, str):
            # Regex to find [ANYTHING_UPPERCASE_OR_NUMBERS_OR_SYMBOLS_INSIDE_BRACKETS]
            # Sticking to Q's typical format: uppercase letters, numbers, some symbols
            marker_matches = re.findall(r'\[([A-Z0-9\s/\\!@#$%^&*()_+\-=\[\]{};\':"|,.<>/?`~]+)\]', text)
            for marker_raw in marker_matches:
                marker = marker_raw.strip()
                if marker:
                    if marker not in post_markers_map:
                        post_markers_map[marker] = []
                    if post_num not in post_markers_map[marker]: # Avoid duplicates
                        post_markers_map[marker].append(post_num)
        
        # --- Build Time Maps (HH:MM and HH:MM:SS) ---
        dt_utc = row.get('Datetime_UTC')
        if pd.notna(dt_utc) and isinstance(dt_utc, (datetime.datetime, pd.Timestamp)):
            time_hhmm = dt_utc.strftime("%H:%M")
            time_hhmms = dt_utc.strftime("%H:%M:%S")

            if time_hhmm not in post_time_hhmm_map:
                post_time_hhmm_map[time_hhmm] = []
            if post_num not in post_time_hhmm_map[time_hhmm]:
                post_time_hhmm_map[time_hhmm].append(post_num)

            if time_hhmms not in post_time_hhmms_map:
                post_time_hhmms_map[time_hhmms] = []
            if post_num not in post_time_hhmms_map[time_hhmms]:
                post_time_hhmms_map[time_hhmms].append(post_num)
        
        # --- Build Theme Posts Map ---
        themes = row.get('Themes', [])
        if isinstance(themes, list):
            for theme_name in themes:
                if theme_name not in theme_posts_map:
                    theme_posts_map[theme_name] = []
                if post_num not in theme_posts_map[theme_name]: # Avoid duplicates
                    theme_posts_map[theme_name].append(post_num)
    
    # Sort lists within maps for consistent display
    for map_obj in [post_markers_map, post_time_hhmm_map, post_time_hhmms_map, theme_posts_map]:
        for key in map_obj:
            map_obj[key].sort()

    print(f"Additional indices built: {len(post_markers_map)} markers, {len(post_time_hhmm_map)} HH:MM times, {len(post_time_hhmms_map)} HH:MM:SS times, {len(theme_posts_map)} themes.")


# --- START LOAD_OR_PARSE_DATA ---
def load_or_parse_data():
    df = None
    global post_quotes_map, post_quoted_by_map, post_markers_map, post_time_hhmm_map, post_time_hhmms_map, theme_posts_map # Added new globals here

    # Paths for new index pickle files
    QUOTES_MAP_PICKLE = os.path.join(config.USER_DATA_ROOT, "post_quotes_map.pkl")
    QUOTED_BY_MAP_PICKLE = os.path.join(config.USER_DATA_ROOT, "post_quoted_by_map.pkl")
    # New paths for additional index pickle files
    MARKERS_MAP_PICKLE = os.path.join(config.USER_DATA_ROOT, "post_markers_map.pkl")
    TIME_HHMM_MAP_PICKLE = os.path.join(config.USER_DATA_ROOT, "post_time_hhmm_map.pkl")
    TIME_HHMMS_MAP_PICKLE = os.path.join(config.USER_DATA_ROOT, "post_time_hhmms_map.pkl")
    THEME_POSTS_MAP_PICKLE = os.path.join(config.USER_DATA_ROOT, "theme_posts_map.pkl")


    # 1. Try to load from Pickle first
    if os.path.exists(config.DATAFRAME_PICKLE_PATH):
        try:
            print(f"Loading DataFrame from {config.DATAFRAME_PICKLE_PATH}...")
            df = pd.read_pickle(config.DATAFRAME_PICKLE_PATH)
            print("DataFrame loaded successfully.")

            # Try to load existing quote and additional indices from pickle
            if (os.path.exists(QUOTES_MAP_PICKLE) and os.path.exists(QUOTED_BY_MAP_PICKLE) and
                os.path.exists(MARKERS_MAP_PICKLE) and os.path.exists(TIME_HHMM_MAP_PICKLE) and
                os.path.exists(TIME_HHMMS_MAP_PICKLE) and os.path.exists(THEME_POSTS_MAP_PICKLE)): # Added new maps to check existence
                try:
                    with open(QUOTES_MAP_PICKLE, 'rb') as f:
                        post_quotes_map = pickle.load(f)
                    with open(QUOTED_BY_MAP_PICKLE, 'rb') as f:
                        post_quoted_by_map = pickle.load(f)
                    with open(MARKERS_MAP_PICKLE, 'rb') as f: # New load
                        post_markers_map = pickle.load(f)
                    with open(TIME_HHMM_MAP_PICKLE, 'rb') as f: # New load
                        post_time_hhmm_map = pickle.load(f)
                    with open(TIME_HHMMS_MAP_PICKLE, 'rb') as f: # New load
                        post_time_hhmms_map = pickle.load(f)
                    with open(THEME_POSTS_MAP_PICKLE, 'rb') as f: # New load
                        theme_posts_map = pickle.load(f)
                    print("All indices loaded successfully from pickle.")
                except Exception as e:
                    print(f"Error loading indices pickle: {e}. Will rebuild all indices.")
                    post_quotes_map = {}
                    post_quoted_by_map = {}
                    post_markers_map = {} # Clear
                    post_time_hhmm_map = {} # Clear
                    post_time_hhmms_map = {} # Clear
                    theme_posts_map = {} # Clear
            else:
                print("One or more index pickle files not found. Will rebuild all indices.")
                post_quotes_map = {}
                post_quoted_by_map = {}
                post_markers_map = {} # Clear
                post_time_hhmm_map = {} # Clear
                post_time_hhmms_map = {} # Clear
                theme_posts_map = {} # Clear

            # Validate essential columns in the loaded pickle
            required_cols = [
                "Post Number", "Text", "Timestamp", "Datetime_UTC",
                "ImagesJSON", "Author", "Tripcode", "Author ID",
                "Link", "Site", "Board", "Referenced Posts Raw", "Themes"
            ]
            missing_cols = [col for col in required_cols if col not in df.columns]
            if missing_cols:
                print(f"Pickle missing essential columns: {missing_cols}. Re-parsing.")
                df = None
            elif "Datetime_UTC" in df.columns and df["Datetime_UTC"].isna().all() and not df.empty:
                print("Pickle's Datetime_UTC is all invalid. Re-parsing.")
                df = None
            elif df.empty and os.path.exists(config.POSTS_DATA_PATH): # If pickle is empty but source JSON exists
                print("Pickle is empty, but source JSON exists. Re-parsing.")
                df = None

        except Exception as e:
            print(f"Error loading DataFrame from pickle: {e}. Will try to parse JSON file.")
            df = None

    # 2. If Pickle failed or doesn't exist, parse our new qview_posts_data.json
    if df is None:
        if not os.path.exists(config.POSTS_DATA_PATH):
            print(f"ERROR: Source data file not found at {config.POSTS_DATA_PATH}")
            return None # Cannot proceed without the source JSON

        print(f"Parsing Q posts from our standardized JSON: {config.POSTS_DATA_PATH}...")
        try:
            with open(config.POSTS_DATA_PATH, "r", encoding="utf-8") as f:
                # Our new JSON is a list of post objects directly
                qview_posts_list = json.load(f)

            if not isinstance(qview_posts_list, list) or not qview_posts_list:
                print("Standardized JSON data is not a list or is empty.")
                return None

            all_posts_data = []
            for i, post_obj in enumerate(qview_posts_list):
                if not isinstance(post_obj, dict):
                    print(f"Warning: Item at index {i} in JSON is not a dictionary. Skipping.")
                    continue
                
                # Map from our new JSON keys to DataFrame column names
                # Handle potential missing keys gracefully with .get()
                all_posts_data.append({
                    "Post Number": post_obj.get("postNumber"),
                    "Timestamp": post_obj.get("timestamp"), # This will be converted to Datetime_UTC
                    "Text": post_obj.get("text", ""),
                    "Author": post_obj.get("author"),
                    "Tripcode": post_obj.get("tripcode"),
                    "Author ID": post_obj.get("authorId"),
                    # For ImagesJSON, we need to match the structure QView's GUI expects:
                    # list of dicts with "file" and "name" keys.
                    # Our new format has "filename" and "originalName".
                    "ImagesJSON": [
                        {"file": img.get("filename"), "name": img.get("originalName")}
                        for img in post_obj.get("images", []) if isinstance(img, dict)
                    ],
                    "Link": post_obj.get("sourceLink"),
                    "Site": post_obj.get("sourceSite"),
                    "Board": post_obj.get("sourceBoard"),
                    # For Referenced Posts Raw, QView expects a list of dicts with
                    # "reference", "author_id", "text".
                    # Our new format has "referenceID", "referencedPostAuthorID", "textContent".
                    "Referenced Posts Raw": [
                    {
                        "reference": ref.get("referenceID"),
                        "author_id": ref.get("referencedPostAuthorID"),
                        "text": ref.get("textContent"),
                        # Add the images from the referenced post object in the JSON
                        # Ensure the structure matches what gui.py will expect later (file, name)
                        "images": [
                            {"file": img.get("filename"), "name": img.get("originalName")}
                            for img in ref.get("images", []) if isinstance(img, dict)
                        ] if ref.get("images") else [] # Add images if they exist in the ref object
                    }
                    for ref in post_obj.get("referencedPosts", []) if isinstance(ref, dict)
                ],
                    # "Image Count" will be derived after DataFrame creation
                })

            if not all_posts_data:
                print("No valid post data extracted from standardized JSON.")
                return pd.DataFrame() # Return empty DataFrame

            df = pd.DataFrame(all_posts_data)

            # --- Post-processing DataFrame ---
            if "Timestamp" in df.columns:
                df["Timestamp"] = pd.to_numeric(df["Timestamp"], errors="coerce")
                # Keep rows where Timestamp is valid after coercion
                df.dropna(subset=["Timestamp"], inplace=True)
                if not df.empty:
                     df["Datetime_UTC"] = pd.to_datetime(df["Timestamp"], unit="s", utc=True)
                     df.sort_values(by="Datetime_UTC", inplace=True, ignore_index=True)
                else: # If all timestamps were invalid
                    df["Datetime_UTC"] = pd.NaT # Add empty column if df became empty
            else:
                df["Datetime_UTC"] = pd.NaT # Add empty column if Timestamp was missing

            if "Post Number" in df.columns:
                df["Post Number"] = pd.to_numeric(df["Post Number"], errors="coerce").astype("Int64")
            
            if "Text" not in df.columns:
                df["Text"] = ""
            df["Themes"] = df["Text"].apply(utils.tag_post_with_themes)

            if "Referenced Posts Raw" not in df.columns:
                df["Referenced Posts Raw"] = pd.Series([[] for _ in range(len(df))], index=df.index, dtype='object')


            # Create Referenced Posts Display
            def fmt_refs(refs):
                if isinstance(refs, list) and refs:
                    return ", ".join(
                        [
                            f"{r.get('reference', '')} ('{str(r.get('text', ''))[:30]}...')"
                            for r in refs if isinstance(r, dict)
                        ]
                    )
                return ""
            df["Referenced Posts Display"] = df["Referenced Posts Raw"].apply(fmt_refs)

            if "ImagesJSON" not in df.columns:
                df["ImagesJSON"] = pd.Series([[] for _ in range(len(df))], index=df.index, dtype='object')
            
            # Add Image Count column
            df["Image Count"] = df["ImagesJSON"].apply(lambda x: len(x) if isinstance(x, list) else 0)


            if not df.empty:
                try:
                    df.to_pickle(config.DATAFRAME_PICKLE_PATH)
                    print(f"DataFrame parsed from '{config.POSTS_DATA_PATH}' and saved to pickle.")
                except Exception as e:
                    print(f"Error saving new DataFrame to pickle: {e}")
            else:
                print("DataFrame is empty after parsing, not saving pickle.")


        except json.JSONDecodeError as e:
            print(f"Error parsing standardized JSON '{config.POSTS_DATA_PATH}': {e}")
            import traceback; traceback.print_exc(); return None
        except Exception as e:
            print(f"Unexpected error processing standardized JSON or saving pickle: {e}")
            import traceback; traceback.print_exc(); return None

    if df is None or df.empty:
        print("Failed to load or parse any data.")
        return None # Return None if df is still None or empty

    # Final checks for essential columns that GUI expects
    if "Datetime_UTC" not in df.columns and not df.empty:
        df["Datetime_UTC"] = pd.NaT # Ensure column exists even if all NaT
    if "ImagesJSON" not in df.columns and not df.empty:
        df["ImagesJSON"] = pd.Series([[] for _ in range(len(df))], index=df.index, dtype='object')
    
    # --- NEW: Build and save all indices after DataFrame is ready ---
    _build_quote_indices(df)
    _build_additional_indices(df) # NEW: Call to build new indices
    try:
        with open(QUOTES_MAP_PICKLE, 'wb') as f:
            pickle.dump(post_quotes_map, f)
        with open(QUOTED_BY_MAP_PICKLE, 'wb') as f:
            pickle.dump(post_quoted_by_map, f)
        with open(MARKERS_MAP_PICKLE, 'wb') as f: # New save
            pickle.dump(post_markers_map, f)
        with open(TIME_HHMM_MAP_PICKLE, 'wb') as f: # New save
            pickle.dump(post_time_hhmm_map, f)
        with open(TIME_HHMMS_MAP_PICKLE, 'wb') as f: # New save
            pickle.dump(post_time_hhmms_map, f)
        with open(THEME_POSTS_MAP_PICKLE, 'wb') as f: # New save
            pickle.dump(theme_posts_map, f)
        print("All indices saved successfully to pickle.")
    except Exception as e:
        print(f"Error saving indices to pickle: {e}")
    # --- END NEW ---

    return df
# --- END LOAD_OR_PARSE_DATA ---