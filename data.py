# --- START DATA_PY_HEADER ---
import os
import json # Changed from demjson3
import pandas as pd
import datetime # Added for timestamp conversion

import config  # For POSTS_DATA_PATH, DATAFRAME_PICKLE_PATH
import utils   # For tag_post_with_themes
# --- END DATA_PY_HEADER ---


# --- START LOAD_OR_PARSE_DATA ---
def load_or_parse_data():
    df = None
    # 1. Try to load from Pickle first
    if os.path.exists(config.DATAFRAME_PICKLE_PATH):
        try:
            print(f"Loading DataFrame from {config.DATAFRAME_PICKLE_PATH}...")
            df = pd.read_pickle(config.DATAFRAME_PICKLE_PATH)
            print("DataFrame loaded successfully.")
            
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
                            "text": ref.get("textContent")
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
    
    return df
# --- END LOAD_OR_PARSE_DATA ---