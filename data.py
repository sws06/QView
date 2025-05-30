# --- START DATA_PY_HEADER ---
import os
import re

import demjson3 as demjson
import pandas as pd

import config  # For POSTS_DATA_PATH, DATAFRAME_PICKLE_PATH
import utils  # For tag_post_with_themes

# --- END DATA_PY_HEADER ---


# --- START LOAD_OR_PARSE_DATA ---
def load_or_parse_data():
    df = None
    if os.path.exists(config.DATAFRAME_PICKLE_PATH):
        try:
            print(f"Loading DataFrame from {config.DATAFRAME_PICKLE_PATH}...")
            df = pd.read_pickle(config.DATAFRAME_PICKLE_PATH)
            print("DataFrame loaded successfully.")
            required_cols = [
                "Post Number",
                "Text",
                "Timestamp",
                "Datetime_UTC",
                "ImagesJSON",
            ]
            if not all(col in df.columns for col in required_cols) or (
                "Datetime_UTC" in df.columns and df["Datetime_UTC"].isna().all()
            ):
                print(
                    "Pickle missing essential columns or Datetime_UTC is invalid. Re-parsing."
                )
                df = None

            pickle_modified_during_load = False
            if df is not None:
                if "Themes" not in df.columns:
                    print("Adding 'Themes' column to loaded DataFrame.")
                    if "Text" in df.columns:
                        df["Themes"] = df["Text"].apply(utils.tag_post_with_themes)
                    else:
                        df["Themes"] = pd.Series(
                            [[] for _ in range(len(df))], index=df.index
                        )
                    pickle_modified_during_load = True
                if "ImagesJSON" not in df.columns:
                    print(
                        "Pickle loaded without 'ImagesJSON'. Forcing re-parse to get ImagesJSON correctly."
                    )
                    df = None
                    pickle_modified_during_load = False  # Reset as df is None
                if df is not None and "Referenced Posts Raw" not in df.columns:
                    df["Referenced Posts Raw"] = pd.Series(dtype="object")
                    pickle_modified_during_load = True
                if df is not None and "Referenced Posts Display" not in df.columns:
                    if "Referenced Posts Raw" in df.columns:

                        def fmt_refs_temp(refs):
                            if isinstance(refs, list) and refs:
                                return ", ".join(
                                    [
                                        f"{r.get('reference', '')} ('{str(r.get('text', ''))[:30]}...')"
                                        for r in refs
                                        if isinstance(r, dict)
                                    ]
                                )
                            return ""

                        df["Referenced Posts Display"] = df[
                            "Referenced Posts Raw"
                        ].apply(fmt_refs_temp)
                        pickle_modified_during_load = True

                if pickle_modified_during_load and df is not None:
                    try:
                        df.to_pickle(config.DATAFRAME_PICKLE_PATH)
                        print("DataFrame re-saved with added columns.")
                    except Exception as e:
                        print(f"Error re-saving DataFrame after adding columns: {e}")

        except Exception as e:
            print(
                f"Error loading DataFrame from pickle: {e}. Will try to parse JSON file."
            )
            df = None

    if df is None:
        print(f"Parsing Q posts from {config.POSTS_DATA_PATH}...")
        try:
            with open(config.POSTS_DATA_PATH, "r", encoding="utf-8") as f:
                file_content = f.read()
            data_json = demjson.decode(
                file_content
            )  # Renamed to avoid conflict with module name

            if "posts" not in data_json or not isinstance(data_json["posts"], list):
                print("Decoded data does not contain 'posts' list.")
                return None
            all_posts_data = []
            for i, post_obj in enumerate(data_json["posts"]):
                metadata = post_obj.get("post_metadata", {})
                text_content = post_obj.get("text", "")
                post_num_raw = metadata.get("id", i + 1)
                post_num_cleaned = post_num_raw
                if isinstance(post_num_raw, str):
                    num_match = re.match(r"(\d+)", post_num_raw)
                    if num_match:
                        post_num_cleaned = int(num_match.group(1))
                all_posts_data.append(
                    {
                        "Author": metadata.get("author"),
                        "Tripcode": metadata.get("tripcode"),
                        "Site": metadata.get("source", {}).get("site"),
                        "Board": metadata.get("source", {}).get("board"),
                        "Link": metadata.get("source", {}).get("link"),
                        "Timestamp": metadata.get("time"),
                        "Post Number Raw": post_num_raw,
                        "Post Number": post_num_cleaned,
                        "Author ID": metadata.get("author_id"),
                        "Text": text_content,
                        "Referenced Posts Raw": post_obj.get("referenced_posts"),
                        "Image Count": len(post_obj.get("images", [])),
                        "ImagesJSON": post_obj.get("images", []),
                    }
                )
            if not all_posts_data:
                return pd.DataFrame()
            df = pd.DataFrame(all_posts_data)
            if "Timestamp" in df.columns:
                df["Timestamp"] = pd.to_numeric(df["Timestamp"], errors="coerce")
                df.dropna(subset=["Timestamp"], inplace=True)
                df["Datetime_UTC"] = pd.to_datetime(df["Timestamp"], unit="s", utc=True)
                df.sort_values(by="Datetime_UTC", inplace=True, ignore_index=True)
            else:
                df["Datetime_UTC"] = pd.NaT
            if "Post Number" in df.columns:
                df["Post Number"] = pd.to_numeric(
                    df["Post Number"], errors="coerce"
                ).astype("Int64")
            if "Text" not in df.columns:
                df["Text"] = ""
            df["Themes"] = df["Text"].apply(
                utils.tag_post_with_themes
            )  # Use utils.tag_post_with_themes
            if "Referenced Posts Raw" not in df.columns:
                df["Referenced Posts Raw"] = pd.Series(dtype="object")

            def fmt_refs(refs):
                if isinstance(refs, list) and refs:
                    return ", ".join(
                        [
                            f"{r.get('reference', '')} ('{str(r.get('text', ''))[:30]}...')"
                            for r in refs
                            if isinstance(r, dict)
                        ]
                    )
                return ""

            df["Referenced Posts Display"] = df["Referenced Posts Raw"].apply(fmt_refs)
            if "ImagesJSON" not in df.columns:
                df["ImagesJSON"] = pd.Series(
                    [[] for _ in range(len(df))], index=df.index
                )

            df.to_pickle(config.DATAFRAME_PICKLE_PATH)
            print("DataFrame parsed and saved to pickle.")
        except Exception as e:
            print(f"Error parsing JSON or saving pickle: {e}")
            import traceback

            traceback.print_exc()
            return None

    if df is None or df.empty:
        return None
    if "Datetime_UTC" not in df.columns:
        df["Datetime_UTC"] = pd.NaT
    if "ImagesJSON" not in df.columns:
        print(
            "Critical: 'ImagesJSON' column still missing after load/parse attempt. Adding empty."
        )
        df["ImagesJSON"] = pd.Series([[] for _ in range(len(df))], index=df.index)
    return df


# --- END LOAD_OR_PARSE_DATA ---
