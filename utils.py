# utils.py

import tkinter as tk
import html
import json
import os
import pickle
import platform
import re
import shutil
import subprocess
import webbrowser
import time
import requests
import pandas as pd
from tkinter import messagebox
from urllib.parse import urlparse, quote_plus
from PIL import Image, ImageTk
import config

class TermColors:
    RESET, BOLD, LIGHT_RED, LIGHT_YELLOW, LIGHT_GRAY, BLUE, MAGENTA, GREEN, CYAN = "\033[0m", "\033[1m", "\033[91m", "\033[93m", "\033[90m", "\033[94m", "\033[95m", "\033[92m", "\033[96m"

def tag_post_with_themes(post_text):
    if not isinstance(post_text, str) or not post_text.strip(): return []
    found_themes = set()
    post_text_lower = post_text.lower()
    for theme, keywords in config.THEMES.items():
        for keyword in keywords:
            if isinstance(keyword, str) and keyword.lower() in post_text_lower:
                found_themes.add(theme); break
    return sorted(list(found_themes))

def get_chrome_path():
    if platform.system() == "Windows":
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe")
            path = winreg.QueryValue(key, None)
            if path and os.path.exists(path): return path
        except Exception: pass
        for p in ["ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA"]:
            path = os.path.join(os.environ.get(p, ""), "Google\\Chrome\\Application\\chrome.exe")
            if path and os.path.exists(path): return path
        return shutil.which("chrome.exe")
    elif platform.system() == "Darwin":
        path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        return path if os.path.exists(path) else shutil.which("google-chrome")
    else: return shutil.which("google-chrome") or shutil.which("chromium-browser")

CHROME_PATH = get_chrome_path()

def open_link_with_preference(url, app_settings):
    preference = app_settings.get("link_opening_preference", "default")
    if preference == "chrome_incognito" and CHROME_PATH:
        try:
            subprocess.Popen([CHROME_PATH, "--incognito", url])
            return
        except Exception as e: print(f"Failed to open in Chrome Incognito, falling back. Error: {e}")
    webbrowser.open_new_tab(url)

def load_bookmarks_from_file(filepath):
    if not os.path.exists(filepath): return set()
    try:
        with open(filepath, "rb") as f: return pickle.load(f)
    except Exception as e: print(f"Error loading bookmarks: {e}"); return set()

def save_bookmarks_to_file(bookmarks_set, filepath):
    try:
        with open(filepath, "wb") as f: pickle.dump(bookmarks_set, f)
    except Exception as e: print(f"Could not save bookmarks: {e}")

def load_user_notes(filepath):
    """Loads user notes from the file. Converts old string format to new dict format."""
    if not os.path.exists(filepath):
        return {}
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            raw_notes = json.load(f)
            # Convert any old string-only notes to the new dictionary format
            converted_notes = {}
            for key, value in raw_notes.items():
                if isinstance(value, str):
                    converted_notes[key] = {"content": value, "show_tooltip": True} # Default old notes to show tooltip
                elif isinstance(value, dict) and "content" in value:
                    # Ensure show_tooltip exists, default to True if missing
                    value["show_tooltip"] = value.get("show_tooltip", True)
                    converted_notes[key] = value
                else:
                    print(f"Warning: Skipping malformed note for key {key}: {value}")
            return converted_notes
    except Exception as e:
        print(f"Could not load user notes: {e}. Returning empty notes.")
        return {}
        
def save_user_notes(notes_dict, filepath):
    """Saves the user notes dictionary to the file."""
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(notes_dict, f, indent=4)
    except Exception as e:
        print(f"Could not save user notes: {e}")    

def sanitize_text_for_tkinter(text):
    return str(text).replace("\x00", "") if isinstance(text, str) else str(text)

def _extract_urls_from_text(text):
    return [match.group(0) for match in config.URL_REGEX.finditer(text)] if isinstance(text, str) else []

def open_image_external(image_path, root):
    try:
        if platform.system() == "Windows": os.startfile(os.path.abspath(image_path))
        else: subprocess.call(["open" if platform.system() == "Darwin" else "xdg-open", os.path.abspath(image_path)])
    except Exception as e: messagebox.showerror("Image Error", f"Could not open image:\n{image_path}\n\n{e}", parent=root)

def sanitize_filename_component(component):
    return re.sub(r'[<>:"/\\|?*]', "_", str(component or "")).strip("_.")[:100]

def get_domain(url):
    try:
        domain = urlparse(url).netloc
        return domain[4:] if domain.startswith("www.") else domain.lower()
    except: return "unknown_domain"

def check_article_exists_util(post_id, url):
    filename = f"{sanitize_filename_component(post_id)}-{sanitize_filename_component(get_domain(url))}.html"
    return os.path.exists(os.path.join(config.LINKED_ARTICLES_DIR, filename)), os.path.join(config.LINKED_ARTICLES_DIR, filename)

def _download_image(url, path):
    try:
        response = requests.get(url, stream=True, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
        response.raise_for_status()
        with open(path, "wb") as f:
            for chunk in response.iter_content(8192): f.write(chunk)
        return True
    except Exception: return False

def download_all_post_images_util(df, status_callback=None, progress_callback=None):
    if status_callback: status_callback("Preparing to download main images...")
    os.makedirs(config.IMAGE_DIR, exist_ok=True)
    total, downloaded, skipped, errors, processed = len(df), 0, 0, 0, 0
    for index, row in df.iterrows():
        processed += 1
        if progress_callback: progress_callback(processed, total)
        if status_callback and processed % 20 == 0: status_callback(f"Images: Post {processed}/{total}. D:{downloaded}, S:{skipped}, E:{errors}")
        for img_data in row.get("ImagesJSON", []):
            filename = img_data.get("file")
            if not filename: continue
            url = config.QANON_PUB_MEDIA_BASE_URL + filename if not filename.startswith("http") else filename
            path = os.path.join(config.IMAGE_DIR, sanitize_filename_component(os.path.basename(filename)))
            if os.path.exists(path): skipped += 1; continue
            if _download_image(url, path): downloaded += 1
            else: errors += 1
    summary = f"Main Image download finished. New:{downloaded}, Skipped:{skipped}, Errors:{errors}"
    if status_callback: status_callback(summary); print(summary)

def download_all_quoted_images_util(df, status_callback=None, progress_callback=None):
    if status_callback: status_callback("Preparing to download quoted images...")
    os.makedirs(config.IMAGE_DIR, exist_ok=True)
    total, downloaded, skipped, errors, processed = len(df), 0, 0, 0, 0
    for index, post in df.iterrows():
        processed += 1
        if progress_callback: progress_callback(processed, total)
        if status_callback and processed % 50 == 0: status_callback(f"Quoted Imgs: Post {processed}/{total}. D:{downloaded}, S:{skipped}, E:{errors}")
        for ref in post.get("Referenced Posts Raw", []):
            for img_meta in ref.get("images", []):
                filename = img_meta.get("file")
                if not filename: continue
                url = "https://www.qanon.pub/data/media/" + filename if not filename.startswith("http") else filename
                path = os.path.join(config.IMAGE_DIR, sanitize_filename_component(os.path.basename(filename)))
                if os.path.exists(path): skipped += 1; continue
                if _download_image(url, path): downloaded += 1
                else: errors += 1
    summary = f"Quoted Image download finished. New:{downloaded}, Skipped:{skipped}, Errors:{errors}"
    if status_callback: status_callback(summary); print(summary)

# --- START NEW AND CORRECTED FUNCTIONS ---

def is_excluded_domain(url, excluded_list):
    """Checks if a URL's domain is in the exclusion list."""
    try:
        domain = get_domain(url)
        return domain in excluded_list
    except:
        return True # Exclude if URL is malformed

def download_article_util(url, path):
    """Downloads the HTML content of a URL to a specified path."""
    try:
        response = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
        response.raise_for_status()
        # Use errors='replace' to handle potential encoding issues in web pages
        with open(path, "w", encoding='utf-8', errors='replace') as f:
            f.write(response.text)
        return True, None
    except requests.exceptions.RequestException as e:
        return False, str(e)
    except Exception as e:
        return False, str(e)

def scan_and_download_all_articles_util(df, status_callback=None, progress_callback=None):
    if status_callback: status_callback("Preparing to download articles...")
    os.makedirs(config.LINKED_ARTICLES_DIR, exist_ok=True)
    total, downloaded, skipped, errors, excluded, processed = len(df), 0, 0, 0, 0, 0
    for index, post in df.iterrows():
        processed += 1
        if progress_callback: progress_callback(processed, total)
        if status_callback and processed % 20 == 0: status_callback(f"Articles: Post {processed}/{total}. D:{downloaded}, S:{skipped}, E:{errors}")
        
        urls_to_scan = set(_extract_urls_from_text(post.get("Text", "")))
        if post.get("Link") and isinstance(post.get("Link"), str):
            urls_to_scan.add(post.get("Link"))

        for url in urls_to_scan:
            if not url or not url.startswith(("http:", "https:")):
                continue
            if is_excluded_domain(url, config.EXCLUDED_LINK_DOMAINS):
                excluded += 1
                continue
            
            post_id = str(post.get("Post Number", f"index_{index}"))
            exists, filepath = check_article_exists_util(post_id, url)
            if exists:
                skipped += 1
                continue
            
            time.sleep(0.1) # Be polite to servers
            success, err_msg = download_article_util(url, filepath)
            if success:
                downloaded += 1
            else:
                errors += 1
                print(f"Article DL Error: {err_msg} for {url}")

    summary = f"Article download finished. New:{downloaded}, Skipped:{skipped}, Errors:{errors}, Excluded:{excluded}"
    if status_callback: status_callback(summary)
    print(summary)
    
def format_cell_text_for_gui_html(text): # <--- INSERT THIS ENTIRE FUNCTION
    """Formats text for HTML table cells, replacing newlines with <br />."""
    if pd.isna(text) or text is None:
        return ""
    text_str = str(text)
    # Escape HTML special characters first, then replace newlines
    escaped_text = html.escape(text_str)
    return escaped_text.replace('\n', '<br />\n')

def _show_text_widget_context_menu(event):
    """Binds a right-click event to show the default Tkinter Text widget context menu."""
    widget = event.widget
    # Create a temporary menu
    menu = tk.Menu(widget, tearoff=0)

    # Add standard commands
    menu.add_command(label="Cut", command=lambda: widget.event_generate("<<Cut>>"))
    menu.add_command(label="Copy", command=lambda: widget.event_generate("<<Copy>>"))
    menu.add_command(label="Paste", command=lambda: widget.event_generate("<<Paste>>"))

    # Display the menu
    menu.tk_popup(event.x_root, event.y_root)    

# --- END NEW AND CORRECTED FUNCTIONS ---


def calculate_gematria(text):
    if not isinstance(text, str): text = str(text)
    text_upper = text.upper()
    results = {"simple": 0, "reverse": 0, "hebrew": 0, "english": 0}
    simple_map = {chr(ord('A') + i): i + 1 for i in range(26)}
    reverse_map = {chr(ord('A') + i): 26 - i for i in range(26)}
    hebrew_map = {'A':1,'B':2,'C':3,'D':4,'E':5,'F':80,'G':3,'H':8,'I':10,'K':20,'L':30,'M':40,'N':50,'O':70,'P':80,'Q':100,'R':200,'S':300,'T':400,'U':6,'V':6,'W':6,'X':600,'Y':10,'Z':7}
    english_map = {'A':1,'B':2,'C':3,'D':4,'E':5,'F':6,'G':7,'H':8,'I':9,'J':1,'K':2,'L':3,'M':4,'N':5,'O':6,'P':7,'Q':8,'R':9,'S':1,'T':2,'U':3,'V':4,'W':5,'X':6,'Y':7,'Z':8}
    for char in text_upper:
        if char in simple_map:
            results["simple"] += simple_map.get(char, 0)
            results["reverse"] += reverse_map.get(char, 0)
            results["hebrew"] += hebrew_map.get(char, 0)
            results["english"] += english_map.get(char, 0)
    return results