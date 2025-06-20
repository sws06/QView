# --- START UTILS_PY_HEADER ---
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
from urllib.parse import urlparse

import config
# --- END UTILS_PY_HEADER ---


# --- START TERM_COLORS_CLASS ---
class TermColors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    LIGHT_RED = "\033[91m"
    LIGHT_YELLOW = "\033[93m"
    LIGHT_GRAY = "\033[90m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    GREEN = "\033[92m"
    CYAN = "\033[96m"
# --- END TERM_COLORS_CLASS ---


# --- START THEME_TAGGING ---
def tag_post_with_themes(post_text):
    if not isinstance(post_text, str) or not post_text.strip():
        return []
    found_themes = set()
    post_text_lower = post_text.lower()
    for theme, keywords in config.THEMES.items():
        for keyword in keywords:
            if isinstance(keyword, str) and keyword.lower() in post_text_lower:
                found_themes.add(theme)
                break
    return sorted(list(found_themes))
# --- END THEME_TAGGING ---


# --- START CHROME_LAUNCHER ---
def get_chrome_path_windows():
    try:
        import winreg
        try:
            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe",
            )
            chrome_path_reg = winreg.QueryValue(key, None)
            winreg.CloseKey(key)
            if chrome_path_reg and os.path.exists(chrome_path_reg):
                return chrome_path_reg
        except FileNotFoundError:
            pass
        except Exception:
            pass
    except ImportError:
        pass
    env_vars = {
        "ProgramFiles": "C:\\Program Files",
        "ProgramFiles(x86)": "C:\\Program Files (x86)",
    }
    common_paths = [
        os.path.join(
            os.environ.get("ProgramFiles", env_vars["ProgramFiles"]),
            "Google\\Chrome\\Application\\chrome.exe",
        ),
        os.path.join(
            os.environ.get("ProgramFiles(x86)", env_vars["ProgramFiles(x86)"]),
            "Google\\Chrome\\Application\\chrome.exe",
        ),
    ]
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        common_paths.append(
            os.path.join(local_app_data, "Google\\Chrome\\Application\\chrome.exe")
        )
    for path in common_paths:
        if path and os.path.exists(path):
            return path
    return shutil.which("chrome.exe") or shutil.which("chrome")

def get_chrome_path():
    if platform.system() == "Windows":
        return get_chrome_path_windows()
    elif platform.system() == "Darwin":
        default_path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        if os.path.exists(default_path):
            return default_path
        return (
            shutil.which("google-chrome")
            or shutil.which("Google Chrome")
            or shutil.which("chrome")
        )
    else:
        return (
            shutil.which("google-chrome")
            or shutil.which("chrome")
            or shutil.which("chromium-browser")
            or shutil.which("chromium")
        )

CHROME_PATH = get_chrome_path()

def open_chrome_incognito(url):
    if not CHROME_PATH:
        print("Google Chrome path not found. Cannot open in incognito.")
        return False
    try:
        subprocess.Popen([CHROME_PATH, "--incognito", url])
        print(f"Attempting to open in Chrome Incognito: {url}")
        return True
    except Exception as e:
        print(f"Failed to open in Chrome Incognito: {e}")
        return False

def open_link_with_preference(url, app_settings):
    preference = app_settings.get("link_opening_preference", "default")
    if preference == "chrome_incognito":
        if not open_chrome_incognito(url):
            print("Falling back to system default browser.")
            webbrowser.open_new_tab(url)
    else:
        webbrowser.open_new_tab(url)
# --- END CHROME_LAUNCHER ---


# --- START BOOKMARK_FILE_OPERATIONS ---
def load_bookmarks_from_file(filepath):
    try:
        if os.path.exists(filepath):
            with open(filepath, "rb") as f:
                bookmarks = pickle.load(f)
                print(f"Loaded {len(bookmarks)} bookmarks from {filepath}")
                return bookmarks
    except Exception as e:
        print(f"Could not load bookmarks from {filepath}: {e}. Starting empty.")
    return set()

def save_bookmarks_to_file(bookmarks_set, filepath):
    try:
        with open(filepath, "wb") as f:
            pickle.dump(bookmarks_set, f)
            print(f"Saved {len(bookmarks_set)} bookmarks to {filepath}")
    except Exception as e:
        print(f"Could not save bookmarks to {filepath}: {e}")
# --- END BOOKMARK_FILE_OPERATIONS ---


# --- START USER_NOTES_OPERATIONS ---
def load_user_notes(filepath):
    try:
        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                notes = json.load(f)
                print(f"Loaded {len(notes)} user notes from {filepath}")
                return notes
    except (json.JSONDecodeError, IOError, Exception) as e:
        print(f"Could not load user notes from {filepath}: {e}. Starting empty.")
    return {}

def save_user_notes(notes_dict, filepath):
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(notes_dict, f, indent=4)
            print(f"Saved {len(notes_dict)} user notes to {filepath}")
    except (IOError, Exception) as e:
        print(f"Could not save user notes to {filepath}: {e}")
# --- END USER_NOTES_OPERATIONS ---


# --- START TEXT_SANITIZATION ---
def sanitize_text_for_tkinter(text_content):
    if not isinstance(text_content, str):
        return str(text_content)
    sane_text = text_content.replace("\x00", "")
    temp_sane_list = []
    for char_val in sane_text:
        char_ord = ord(char_val)
        if 0x00 <= char_ord <= 0x1F and char_ord not in [0x09, 0x0A, 0x0D]:
            pass
        else:
            temp_sane_list.append(char_val)
    return "".join(temp_sane_list)

def sanitize_filename_component(component):
    if component is None:
        return "unknown_id"
    sanitized = re.sub(r'[<>:"/\\|?*]', "_", str(component))
    sanitized = re.sub(r"__+", "_", sanitized)
    sanitized = sanitized.strip("_.")
    return sanitized[:100] if sanitized else "sanitized_empty"
# --- END TEXT_SANITIZATION ---


# --- START URL_EXTRACTION ---
def _extract_urls_from_text(text_content):
    if not isinstance(text_content, str):
        return []
    return [match.group(0) for match in config.URL_REGEX.finditer(text_content)]
# --- END URL_EXTRACTION ---


# --- START HTML_EXPORT_FORMATTING ---
def format_cell_text_for_gui_html(cell_text):
    if not isinstance(cell_text, str):
        return ""
    last_end = 0
    parts = []
    for match in config.URL_REGEX.finditer(cell_text):
        start, end = match.span()
        parts.append(html.escape(cell_text[last_end:start]))
        url = match.group(0)
        parts.append(
            f'<a href="{html.escape(url, quote=True)}" target="_blank">{html.escape(url)}</a>'
        )
        last_end = end
    parts.append(html.escape(cell_text[last_end:]))
    return "".join(parts).replace("\n", "<br />\n")
# --- END HTML_EXPORT_FORMATTING ---


# --- START IMAGE_OPENING ---
from PIL import Image, ImageTk

def get_or_create_thumbnail(original_image_path, thumbnail_cache_dir, size=(300, 300)):
    if not os.path.exists(original_image_path):
        return None

    original_filename = os.path.basename(original_image_path)
    thumbnail_filename = f"thumb_{original_filename}"
    thumbnail_path = os.path.join(thumbnail_cache_dir, thumbnail_filename)

    try:
        if os.path.exists(thumbnail_path):
            img_pil = Image.open(thumbnail_path)
        else:
            img_pil = Image.open(original_image_path)
            img_pil.thumbnail(size, Image.Resampling.LANCZOS)
            os.makedirs(thumbnail_cache_dir, exist_ok=True)
            img_pil.save(thumbnail_path)
        
        if img_pil.mode not in ("RGB", "RGBA"):
            img_pil = img_pil.convert("RGBA")
            
        photo = ImageTk.PhotoImage(img_pil)
        return photo
    except Exception as e:
        print(f"Error processing thumbnail for {original_image_path}: {e}")
        if os.path.exists(thumbnail_path):
            try:
                if 'cannot identify image file' in str(e).lower() or 'decoder' in str(e).lower():
                     print(f"Deleting potentially corrupted thumbnail: {thumbnail_path}")
                     os.remove(thumbnail_path)
            except Exception as del_e:
                print(f"Error deleting corrupted thumbnail {thumbnail_path}: {del_e}")
        return None

def open_image_external(image_path, root_for_messagebox=None):
    try:
        abs_path = os.path.abspath(image_path)
        if platform.system() == "Windows":
            os.startfile(abs_path)
        else:
            opener = "open" if platform.system() == "Darwin" else "xdg-open"
            subprocess.call([opener, abs_path])
        print(f"Attempting to open image externally: {abs_path}")
    except Exception as e:
        print(f"Error opening image {image_path} externally: {e}")
        if root_for_messagebox:
            messagebox.showerror("Image Error", f"Could not open image:\n{image_path}\n\n{e}", parent=root_for_messagebox)
        else:
            messagebox.showerror("Image Error", f"Could not open image:\n{image_path}\n\n{e}")
# --- END IMAGE_OPENING ---


# --- START ARTICLE_DOWNLOADING_UTILS ---
def get_domain(url):
    """Extracts the domain name (e.g., 'example.com') from a URL."""
    try:
        parsed_url = urlparse(url)
        domain = parsed_url.netloc
        if domain.startswith("www."):
            domain = domain[4:]
        return domain.lower()
    except Exception:
        return None

def is_excluded_domain(url, excluded_list):
    """Checks if the URL's domain is in the excluded list."""
    domain = get_domain(url)
    if domain:
        for excluded_domain in excluded_list:
            if domain == excluded_domain or domain.endswith("." + excluded_domain):
                return True
    return False

def sanitize_filename_component(component):
    """Sanitizes a string component for use in a filename."""
    if component is None:
        return "unknown_id"
    sanitized = re.sub(r'[<>:"/\\|?*]', "_", str(component))
    sanitized = re.sub(r"__+", "_", sanitized)
    sanitized = sanitized.strip("_.")
    return sanitized[:100] if sanitized else "sanitized_empty"

def generate_article_filename(post_id_str, url):
    """Generates a filename for a downloaded article."""
    domain = get_domain(url) or "unknown_domain"
    safe_post_id = sanitize_filename_component(post_id_str)
    safe_domain = sanitize_filename_component(domain)
    return f"{safe_post_id}-{safe_domain}.html"

def check_article_exists_util(post_id_str, url):
    """Checks if a downloaded article HTML file exists for a given post ID and URL."""
    article_filename = generate_article_filename(post_id_str, url)
    filepath = os.path.join(config.LINKED_ARTICLES_DIR, article_filename)
    return os.path.exists(filepath), filepath

def download_article_util(url, filepath):
    """Downloads the HTML content of a URL and saves it to filepath."""
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}
    try:
        response = requests.get(url, headers=headers, timeout=20, allow_redirects=True)
        response.raise_for_status()
        content_type = response.headers.get("content-type", "").lower()
        if "html" not in content_type:
            return False, f"Skipped (not HTML): {content_type[:50]}"
        with open(filepath, "w", encoding="utf-8", errors="replace") as f:
            f.write(response.text)
        return True, None
    except Exception as e:
        return False, f"Error: {type(e).__name__}"

def scan_and_download_all_articles_util(df_all_posts, status_callback=None, progress_callback=None):
    """Scans all posts, filters links, and downloads articles if they don't already exist."""
    if status_callback: status_callback("Preparing to download articles...")
    os.makedirs(config.LINKED_ARTICLES_DIR, exist_ok=True)
    total_posts, downloaded, skipped, errors, excluded, posts_processed = len(df_all_posts), 0, 0, 0, 0, 0
    
    for index, post_series in df_all_posts.iterrows():
        posts_processed += 1
        if progress_callback: progress_callback(posts_processed, total_posts)
        if status_callback and posts_processed % 20 == 0:
            status_callback(f"Articles: Post {posts_processed}/{total_posts}. D:{downloaded}, S:{skipped}, E:{errors}")

        post_id = str(post_series.get("Post Number", f"index_{index}"))
        urls_to_check = set()
        if post_series.get("Link"): urls_to_check.add(post_series["Link"])
        if post_series.get("Text"): urls_to_check.update(_extract_urls_from_text(post_series["Text"]))

        for url in urls_to_check:
            if not url or not isinstance(url, str) or not url.startswith(("http:", "https:")): continue
            if is_excluded_domain(url, config.EXCLUDED_LINK_DOMAINS):
                excluded += 1; continue
            
            exists, filepath = check_article_exists_util(post_id, url)
            if exists:
                skipped += 1; continue
            
            time.sleep(0.2)
            success, error_msg = download_article_util(url, filepath)
            if success:
                downloaded += 1
            else:
                print(f"    Error downloading Article {url[:70]}: {error_msg}")
                errors += 1
    
    final_summary = f"Article download finished. New: {downloaded}, Skipped: {skipped}, Errors: {errors}, Excluded: {excluded}."
    if status_callback: status_callback(final_summary)
    print(f"\n{final_summary}")

def download_all_post_images_util(df_all_posts, status_callback=None, progress_callback=None):
    if status_callback: status_callback("Preparing to download main images...")
    os.makedirs(config.IMAGE_DIR, exist_ok=True)
    total_posts, downloaded, skipped, errors, posts_processed = len(df_all_posts), 0, 0, 0, 0

    for index, row in df_all_posts.iterrows():
        posts_processed += 1
        if progress_callback: progress_callback(posts_processed, total_posts)
        if status_callback and posts_processed % 20 == 0:
            status_callback(f"Images: Post {posts_processed}/{total_posts}. D:{downloaded}, S:{skipped}, E:{errors}")
        
        images_in_post_json = row.get("ImagesJSON", [])
        if not isinstance(images_in_post_json, list): continue

        for img_data in images_in_post_json:
            img_filename = img_data.get("file")
            if not img_filename: continue
            
            image_url = config.QANON_PUB_MEDIA_BASE_URL + img_filename if not img_filename.startswith(("http:", "https:")) else img_filename
            local_path = os.path.join(config.IMAGE_DIR, sanitize_filename_component(os.path.basename(img_filename)))

            if not os.path.exists(local_path):
                time.sleep(0.1)
                try:
                    response = requests.get(image_url, stream=True, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
                    response.raise_for_status()
                    with open(local_path, "wb") as f:
                        for chunk in response.iter_content(8192): f.write(chunk)
                    downloaded += 1
                except Exception as e:
                    print(f"    Error downloading Image {image_url}: {type(e).__name__}")
                    errors += 1
            else:
                skipped += 1

    final_summary = f"Main Image download finished. New: {downloaded}, Skipped: {skipped}, Errors: {errors}."
    if status_callback: status_callback(final_summary)
    print(f"\n{final_summary}")

def download_all_quoted_images_util(df_all_posts, status_callback=None, progress_callback=None):
    if status_callback: status_callback("Preparing to download quoted images...")
    os.makedirs(config.IMAGE_DIR, exist_ok=True)
    total_posts, downloaded, skipped, errors, posts_processed = len(df_all_posts), 0, 0, 0, 0

    for index, post_series in df_all_posts.iterrows():
        posts_processed += 1
        if progress_callback: progress_callback(posts_processed, total_posts)
        if status_callback and posts_processed % 50 == 0:
            status_callback(f"Quoted Imgs: Post {posts_processed}/{total_posts}. D:{downloaded}, S:{skipped}, E:{errors}")
        
        referenced_posts_raw = post_series.get("Referenced Posts Raw", [])
        if not isinstance(referenced_posts_raw, list): continue

        for ref_data in referenced_posts_raw:
            quoted_images = ref_data.get("images", [])
            if not isinstance(quoted_images, list): continue
            
            for img_meta in quoted_images:
                img_filename = img_meta.get("file")
                if not img_filename: continue

                image_url = "https://www.qanon.pub/data/media/" + img_filename if not img_filename.startswith(("http:", "https:")) else img_filename
                local_path = os.path.join(config.IMAGE_DIR, sanitize_filename_component(os.path.basename(img_filename)))

                if not os.path.exists(local_path):
                    time.sleep(0.1)
                    try:
                        response = requests.get(image_url, stream=True, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
                        response.raise_for_status()
                        with open(local_path, "wb") as f:
                            for chunk in response.iter_content(8192): f.write(chunk)
                        downloaded += 1
                    except Exception as e:
                        errors += 1
                else:
                    skipped += 1
    
    final_summary = f"Quoted Image download finished. New: {downloaded}, Skipped: {skipped}, Errors: {errors}."
    if status_callback: status_callback(final_summary)
    print(f"\n{final_summary}")
# --- END ARTICLE_DOWNLOADING_UTILS ---