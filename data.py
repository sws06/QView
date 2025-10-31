import pandas as pd
import json
import os
import pickle
import time
from collections import defaultdict
import re

import config
import symbols

# --- Global variables ---
# These dictionaries store the pre-computed relationships between posts.

# Maps theme keywords to a list of post numbers that contain them.
theme_posts_map = defaultdict(list)

# Maps a post number to a list of post numbers it quotes (e.g., >>123).
post_quotes_map = defaultdict(list)

# Maps a post number to a list of post numbers that quote IT.
quoted_by_map = defaultdict(list)

# Maps a text marker (e.g., "[Marker]") to a list of posts containing it.
marker_posts_map = defaultdict(list)

# Maps a time (HH:MM) to a list of posts made at that time (for deltas).
post_time_hhmm_map = defaultdict(list)

# Maps a time (HH:MM:SS) to a list of posts (for time mirrors).
post_time_hhmmss_map = defaultdict(list)

# Maps a stock symbol/ticker to its aliases and description.
symbol_map = {}

# Stores the aggregate day-by-day count of all symbol mentions.
symbol_timeline = {}

# Stores a separate day-by-day count for each individual symbol.
per_symbol_timeline = {}

def pre_load_indices(df):
    """
    Creates and caches various dictionaries from the main DataFrame
    to speed up lookups in the GUI.
    """
    global post_time_hhmm_map, post_time_hhmms_map, post_quotes_map, post_quoted_by_map, post_markers_map, theme_posts_map, symbol_map, symbol_timeline, per_symbol_timeline

    # --- 1. Time-based Maps ---
    post_time_hhmm_map = defaultdict(list)
    post_time_hhmms_map = defaultdict(list)
    
    for _, row in df.dropna(subset=['Datetime_UTC', 'Post Number']).iterrows():
        dt = row['Datetime_UTC']
        pn = int(row['Post Number'])
        post_time_hhmm_map[dt.strftime('%H:%M')].append(pn)
        post_time_hhmms_map[dt.strftime('%H:%M:%S')].append(pn)

    # --- 2. Quote-based Maps ---
    post_quotes_map = defaultdict(list)
    post_quoted_by_map = defaultdict(list)
    
    for _, row in df.dropna(subset=['Post Number', 'Text']).iterrows():
        current_pn = int(row['Post Number'])
        text = str(row['Text'])
        
        # Find all quotes this post makes (e.g., >>12345)
        quoted_posts = set(re.findall(r'>>(\d+)', text))
        for quoted_pn_str in quoted_posts:
            try:
                quoted_pn_int = int(quoted_pn_str)
                post_quotes_map[current_pn].append(quoted_pn_int)
                post_quoted_by_map[quoted_pn_int].append(current_pn)
            except ValueError:
                continue

    # --- 3. Marker-based Map ---
    post_markers_map = defaultdict(list)
    for _, row in df.dropna(subset=['Post Number', 'Text']).iterrows():
        current_pn = int(row['Post Number'])
        text = str(row['Text'])
        markers = set(re.findall(r'\[([^\]]+)\]', text))
        for marker in markers:
            post_markers_map[marker.strip()].append(current_pn)

    # --- 4. Theme-based Map ---
    theme_posts_map = defaultdict(list)
    if 'Themes' in df.columns:
        for _, row in df.dropna(subset=['Post Number', 'Themes']).iterrows():
            current_pn = int(row['Post Number'])
            themes_list = row['Themes']
            if isinstance(themes_list, list):
                for theme in themes_list:
                    theme_posts_map[theme].append(current_pn)

    # --- 5. Symbol-based Maps ---
    symbol_map = {}
    if os.path.exists(config.SYMBOLS_FILE_PATH):
        try:
            with open(config.SYMBOLS_FILE_PATH, 'r', encoding='utf-8') as f:
                symbol_map = json.load(f)
        except Exception as e:
            print(f"Error loading symbols file: {e}")
            
    symbol_timeline = defaultdict(int)
    per_symbol_timeline = defaultdict(lambda: defaultdict(int))
    
    if 'Text' in df.columns and not df.empty:
        for _, row in df.dropna(subset=['Datetime_UTC', 'Text']).iterrows():
            date_key = row['Datetime_UTC'].date()
            text_lower = str(row['Text']).lower()
            found_symbol_in_post = False
            for symbol, data in symbol_map.items():
                all_terms = [symbol.lower()] + [alias.lower() for alias in data.get("aliases", [])]
                if any(term in text_lower for term in all_terms):
                    per_symbol_timeline[symbol][date_key] += 1
                    found_symbol_in_post = True
            if found_symbol_in_post:
                symbol_timeline[date_key] += 1
                
    # --- Caching Logic (if you want to re-enable it) ---
    # try:
    #     with open(config.INDICES_CACHE_PATH, 'wb') as f:
    #         pickle.dump({
    #             "post_time_hhmm_map": post_time_hhmm_map,
    #             "post_time_hhmms_map": post_time_hhmms_map,
    #             "post_quotes_map": post_quotes_map,
    #             "post_quoted_by_map": post_quoted_by_map,
    #             "post_markers_map": post_markers_map,
    #             "theme_posts_map": theme_posts_map,
    #             "symbol_map": symbol_map,
    #             "symbol_timeline": symbol_timeline,
    #             "per_symbol_timeline": per_symbol_timeline
    #         }, f)
    #     print("--> All indices calculated and cached.")
    # except Exception as e:
    #     print(f"Error saving indices cache: {e}")


def load_or_parse_data():
    """
    Parses the raw JSON data, processes it into a structured DataFrame
    (including adding themes), and then pre-loads search indices.
    """
    print("Parsing and processing data from raw JSON...")
    processed_posts_list = []
    
    with open(config.POSTS_DATA_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)

    for post_data in data:
        processed_post = {
            'Post Number': post_data.get('postNumber'),
            'Timestamp': post_data.get('timestamp'),
            'Text': post_data.get('text'),
            'Author': post_data.get('author'),
            'Tripcode': post_data.get('tripcode'),
            'Author ID': post_data.get('authorId'),
            'Link': post_data.get('sourceLink'),
            'ImagesJSON': post_data.get('images', []),
            'Referenced Posts Raw': post_data.get('referencedPosts', [])
        }
        
        post_themes = []
        post_text_lower = str(processed_post['Text']).lower() if processed_post['Text'] else ""

        for theme_name, keywords in config.THEMES.items():
            if any(keyword.lower() in post_text_lower for keyword in keywords):
                post_themes.append(theme_name)
        
        processed_post['Themes'] = post_themes

        processed_posts_list.append(processed_post)

    df = pd.DataFrame(processed_posts_list)
    df['Datetime_UTC'] = pd.to_datetime(df['Timestamp'], unit='s', errors='coerce')
    
    # This will now work, as pre_load_indices is defined in the same file
    pre_load_indices(df)
    
    print("Data is ready.")
    
    return df

def _build_symbol_timeline(df, symbol_map):
    """Builds an aggregate timeline of mentions for all symbols combined."""
    print("Building aggregate symbol timeline...")
    
    # 1. Collect all aliases from every symbol into one big list
    all_aliases = []
    for symbol_data in symbol_map.values():
        aliases = symbol_data.get("aliases", [])
        if aliases:
            all_aliases.extend([a.lower() for a in aliases])
    
    # 2. If there are no aliases to search for, stop early
    if not all_aliases:
        print("Warning: No aliases found in symbol map. Returning empty timeline.")
        return {}

    # 3. Create a single, efficient regex pattern to find any alias
    # This is much faster than looping through every alias for every post
    pattern = r'\b(' + '|'.join(map(re.escape, all_aliases)) + r')\b'
    
    daily_counts = defaultdict(int)
    
    # 4. Go through every row in the dataframe
    for _, row in df.iterrows():
        date = row['Datetime_UTC'].date()
        text = row.get('Text', '')
        # Make sure the text is actually a string before searching
        if isinstance(text, str):
            matches = re.findall(pattern, text, re.IGNORECASE)
            # Add the number of times any alias was found to the day's count
            daily_counts[date] += len(matches)
            
    print("Aggregate symbol timeline built.")
    
    # 5. Return the final dictionary of {date: count}
    return dict(daily_counts)
    
def _build_per_symbol_timelines(df, symbol_map):
    """Builds a separate timeline for each individual symbol."""
    print("Building per-symbol timeline data...")
    timelines = {}
    for symbol, data in symbol_map.items():
        aliases = data.get("aliases", [])
        if not aliases: continue
        
        pattern = r'\b(' + '|'.join(map(re.escape, [a.lower() for a in aliases])) + r')\b'
        daily_counts = defaultdict(int)
        
        for _, row in df.iterrows():
            date = row['Datetime_UTC'].date()
            text = row.get('Text', '')
            if isinstance(text, str):
                matches = re.findall(pattern, text, re.IGNORECASE)
                daily_counts[date] += len(matches)
        
        if daily_counts:
            timelines[symbol] = dict(daily_counts)
            
    print("Per-symbol timeline data built.")
    return timelines

def _load_indices_from_pickle(path):
    """Loads all pre-computed indices from a pickle file."""
    global theme_posts_map, post_quotes_map, quoted_by_map, marker_posts_map, \
           post_time_hhmm_map, post_time_hhmmss_map, symbol_map, symbol_timeline, \
           per_symbol_timeline
    
    try:
        with open(path, 'rb') as f:
            indices = pickle.load(f)
            
            # These are the missing lines to load all the other maps
            theme_posts_map.update(indices.get('themes', {}))
            post_quotes_map.update(indices.get('quotes', {}))
            quoted_by_map.update(indices.get('quoted_by', {}))
            marker_posts_map.update(indices.get('markers', {}))
            post_time_hhmm_map.update(indices.get('hhmm', {}))
            post_time_hhmmss_map.update(indices.get('hhmmss', {}))
            
            # This is the part that was already working
            symbol_map.update(indices.get('symbols', {}))
            symbol_timeline.update(indices.get('symbol_timeline', {}))
            per_symbol_timeline.update(indices.get('per_symbol_timeline', {}))
            
            print("--> All indices loaded successfully from pickle.")
            return True
    except (FileNotFoundError, EOFError, pickle.UnpicklingError) as e:
        # This is not an error, just means we need to build from scratch
        return False

def _save_indices_to_pickle(path):
    """Saves all computed indices to a pickle file."""
    print(f"--> Attempting to save indices to pickle file: {path}")
    try:
        # This is the dictionary of all data to save
        indices = {
            'themes': theme_posts_map,
            'quotes': post_quotes_map,
            'quoted_by': quoted_by_map,
            'markers': marker_posts_map,
            'hhmm': post_time_hhmm_map,
            'hhmmss': post_time_hhmmss_map,
            'symbols': symbol_map,
            'symbol_timeline': symbol_timeline,
            'per_symbol_timeline': per_symbol_timeline
        }

        # These are the missing lines that actually write the file
        with open(path, 'wb') as f:
            pickle.dump(indices, f)
            
        print("--> Successfully saved indices to pickle file.")
    except Exception as e:
        print(f"!!! CRITICAL ERROR: Failed to save pickle file at {path}: {e}")

def _build_indices(df):
    """Builds all necessary indices from the DataFrame in a single pass."""
    global theme_posts_map, post_quotes_map, quoted_by_map, marker_posts_map, \
           post_time_hhmm_map, post_time_hhmmss_map, symbol_map, symbol_timeline, \
           per_symbol_timeline

    print("Building indices from scratch...")
    # Clear all maps to ensure a fresh start
    theme_posts_map.clear(); post_quotes_map.clear(); quoted_by_map.clear()
    marker_posts_map.clear(); post_time_hhmm_map.clear(); post_time_hhmmss_map.clear()
    
    # --- Build Symbol-Related Data (already correct) ---
    symbol_map = symbols.load_symbols()
    symbol_timeline = _build_symbol_timeline(df, symbol_map)
    per_symbol_timeline = _build_per_symbol_timelines(df, symbol_map)
    
    # --- Main Loop to build all other indices ---
    print("Processing all posts to build relationship maps...")
    quote_pattern = re.compile(r'>>(\d+)')
    marker_pattern = re.compile(r'\[([^\]]+)\]')

    # Create a new column in the DataFrame to store themes for each post
    df['Themes'] = [[] for _ in range(len(df))]

    for index, row in df.iterrows():
        post_num = row.get('Post Number')
        text = row.get('Text', '')
        timestamp = row.get('Datetime_UTC')

        if pd.isna(post_num):
            continue

        # 1. Build Time Maps
        if pd.notna(timestamp):
            post_time_hhmm_map[timestamp.strftime('%H:%M')].append(post_num)
            post_time_hhmmss_map[timestamp.strftime('%H:%M:%S')].append(post_num)

        if not isinstance(text, str): text = ''

        # 2. Build Theme Map and add Themes to the DataFrame row
        post_themes = []
        for theme, keywords in config.THEMES.items():
            for keyword in keywords:
                if re.search(r'\b' + re.escape(keyword) + r'\b', text, re.IGNORECASE):
                    theme_posts_map[theme].append(post_num)
                    if theme not in post_themes:
                        post_themes.append(theme)
        df.at[index, 'Themes'] = post_themes

        # 3. Build Quote Maps
        quoted_posts = quote_pattern.findall(text)
        if quoted_posts:
            post_quotes_map[post_num].extend([int(p) for p in quoted_posts])
            for quoted_num in quoted_posts:
                quoted_by_map[int(quoted_num)].append(post_num)

        # 4. Build Marker Map
        markers = marker_pattern.findall(text)
        for marker in markers:
            marker_posts_map[marker.strip()].append(post_num)

    print("All relationship maps built successfully.")

# (The load_or_parse_data function does not need to be changed)