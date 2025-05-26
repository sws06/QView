# --- START UTILS_PY_HEADER ---
import os
import platform
import webbrowser
import shutil
import subprocess
import pickle
import re
import html
from tkinter import messagebox # For open_chrome_incognito error
import pandas as pd

import config # For THEMES, URL_REGEX (used by format_cell_text_for_gui_html)
# --- END UTILS_PY_HEADER ---

# --- START TERM_COLORS_CLASS ---
class TermColors:
    RESET = '\033[0m'; BOLD = '\033[1m'; LIGHT_RED = '\033[91m'; LIGHT_YELLOW = '\033[93m'
    LIGHT_GRAY = '\033[90m'; BLUE = '\033[94m'; MAGENTA = '\033[95m'; GREEN = '\033[92m'; CYAN = '\033[96m'
# --- END TERM_COLORS_CLASS ---

# --- START THEME_TAGGING ---
def tag_post_with_themes(post_text):
    if not isinstance(post_text, str) or not post_text.strip(): return []
    found_themes = set()
    post_text_lower = post_text.lower()
    for theme, keywords in config.THEMES.items():
        for keyword in keywords:
            if isinstance(keyword, str) and keyword.lower() in post_text_lower:
                found_themes.add(theme); break
    return sorted(list(found_themes))
# --- END THEME_TAGGING ---

# --- START CHROME_LAUNCHER ---
def get_chrome_path_windows():
    try:
        import winreg
        try:
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe")
            chrome_path_reg = winreg.QueryValue(key, None); winreg.CloseKey(key)
            if chrome_path_reg and os.path.exists(chrome_path_reg): return chrome_path_reg
        except FileNotFoundError: pass
        except Exception: pass # Ignore other registry errors
    except ImportError: pass # winreg not available
    env_vars = {"ProgramFiles": "C:\\Program Files", "ProgramFiles(x86)": "C:\\Program Files (x86)"}
    common_paths = [
        os.path.join(os.environ.get("ProgramFiles", env_vars["ProgramFiles"]), "Google\\Chrome\\Application\\chrome.exe"),
        os.path.join(os.environ.get("ProgramFiles(x86)", env_vars["ProgramFiles(x86)"]), "Google\\Chrome\\Application\\chrome.exe"),
    ]
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data: common_paths.append(os.path.join(local_app_data, "Google\\Chrome\\Application\\chrome.exe"))
    for path in common_paths:
        if path and os.path.exists(path): return path
    return shutil.which("chrome.exe") or shutil.which("chrome")

def get_chrome_path():
    if platform.system() == "Windows": return get_chrome_path_windows()
    elif platform.system() == "Darwin": # macOS
        default_path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        if os.path.exists(default_path): return default_path
        return shutil.which("google-chrome") or shutil.which("Google Chrome") or shutil.which("chrome")
    else: # Linux and other OS
        return shutil.which("google-chrome") or shutil.which("chrome") or \
               shutil.which("chromium-browser") or shutil.which("chromium")

CHROME_PATH = get_chrome_path()

def open_chrome_incognito(url):
    if not CHROME_PATH:
        # No messagebox here, just return False. Caller can decide to show error or fallback.
        print("Google Chrome path not found. Cannot open in incognito.")
        return False
    try:
        subprocess.Popen([CHROME_PATH, "--incognito", url])
        print(f"Attempting to open in Chrome Incognito: {url}")
        return True
    except Exception as e:
        # No messagebox here.
        print(f"Failed to open in Chrome Incognito: {e}")
        return False

def open_link_with_preference(url, app_settings):
    """Opens a URL based on user preference in app_settings."""
    preference = app_settings.get("link_opening_preference", "default")

    if preference == "chrome_incognito":
        if not open_chrome_incognito(url): # Try Chrome Incognito
            print("Falling back to system default browser.")
            webbrowser.open_new_tab(url) # Fallback if Chrome fails
    else: # "default" or any other unknown preference
        webbrowser.open_new_tab(url)
# --- END CHROME_LAUNCHER ---

# --- START BOOKMARK_FILE_OPERATIONS ---
def load_bookmarks_from_file(filepath):
    try:
        if os.path.exists(filepath):
            with open(filepath, 'rb') as f:
                bookmarks = pickle.load(f)
                print(f"Loaded {len(bookmarks)} bookmarks from {filepath}")
                return bookmarks
    except Exception as e:
        print(f"Could not load bookmarks from {filepath}: {e}. Starting empty.")
    return set()

def save_bookmarks_to_file(bookmarks_set, filepath):
    try:
        with open(filepath, 'wb') as f:
            pickle.dump(bookmarks_set, f)
            print(f"Saved {len(bookmarks_set)} bookmarks to {filepath}")
    except Exception as e:
        print(f"Could not save bookmarks to {filepath}: {e}")
# --- END BOOKMARK_FILE_OPERATIONS ---

# --- START TEXT_SANITIZATION ---
def sanitize_text_for_tkinter(text_content):
    if not isinstance(text_content, str):
        return str(text_content)
    sane_text = text_content.replace('\x00', '') # Remove null characters
    temp_sane_list = []
    for char_val in sane_text:
        char_ord = ord(char_val)
        if 0x00 <= char_ord <= 0x1F and char_ord not in [0x09, 0x0A, 0x0D]:
            pass
        else:
            temp_sane_list.append(char_val)
    return "".join(temp_sane_list)
# --- END TEXT_SANITIZATION ---

# --- START URL_EXTRACTION ---
def _extract_urls_from_text(text_content):
    if not isinstance(text_content, str):
        return []
    return [match.group(0) for match in config.URL_REGEX.finditer(text_content)]
# --- END URL_EXTRACTION ---

# --- START HTML_EXPORT_FORMATTING ---
def format_cell_text_for_gui_html(cell_text):
    if not isinstance(cell_text, str): return ""
    last_end = 0; parts = []
    for match in config.URL_REGEX.finditer(cell_text):
        start, end = match.span(); parts.append(html.escape(cell_text[last_end:start]))
        url = match.group(0); parts.append(f'<a href="{html.escape(url, quote=True)}" target="_blank">{html.escape(url)}</a>')
        last_end = end
    parts.append(html.escape(cell_text[last_end:]))
    return "".join(parts).replace('\n', '<br />\n')
# --- END HTML_EXPORT_FORMATTING ---

# --- START IMAGE_OPENING ---
def open_image_external(image_path, root_for_messagebox=None):
    try:
        abs_path = os.path.abspath(image_path)
        if platform.system() == "Windows":
            os.startfile(abs_path)
        else:
            if platform.system() == "Darwin": # macOS
                subprocess.call(["open", abs_path])
            else: # Linux and other OS
                try:
                    subprocess.call(["xdg-open", abs_path])
                except FileNotFoundError: # Fallback if xdg-open is not available
                    webbrowser.open(f"file://{abs_path}")
        print(f"Attempting to open image externally: {abs_path}")
    except Exception as e:
        print(f"Error opening image {image_path} externally: {e}")
        if root_for_messagebox:
            messagebox.showerror("Image Error", f"Could not open image:\n{image_path}\n\n{e}", parent=root_for_messagebox)
        else:
            messagebox.showerror("Image Error", f"Could not open image:\n{image_path}\n\n{e}")
# --- END IMAGE_OPENING ---

# --- START ARTICLE_DOWNLOADING_UTILS ---
import requests
from urllib.parse import urlparse
import time
import pandas as pd
import os
import re
import config # Ensure config is imported for this block

# LINKED_ARTICLES_DIR is now directly defined in config.py as a full path.
# We will use config.LINKED_ARTICLES_DIR directly in functions below.

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
    sanitized = re.sub(r'[<>:"/\\|?*]', '_', str(component))
    sanitized = re.sub(r'__+', '_', sanitized)
    sanitized = sanitized.strip('_.')
    return sanitized[:100] if sanitized else "sanitized_empty"


def generate_article_filename(post_id_str, url):
    """
    Generates a filename for a downloaded article.
    Format: postID-domain.html
    """
    domain = get_domain(url)
    if not domain:
        domain = "unknown_domain"

    safe_post_id = sanitize_filename_component(post_id_str)
    safe_domain = sanitize_filename_component(domain)

    return f"{safe_post_id}-{safe_domain}.html"

def check_article_exists_util(post_id_str, url):
    """
    Checks if a downloaded article HTML file exists for a given post ID and URL.
    Returns (bool_exists, str_filepath_or_None).
    """
    article_filename = generate_article_filename(post_id_str, url)
    filepath = os.path.join(config.LINKED_ARTICLES_DIR, article_filename)
    return os.path.exists(filepath), filepath

def download_article_util(url, filepath):
    """
    Downloads the HTML content of a URL and saves it to filepath.
    Returns (bool_success, str_error_message_or_None).
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    try:
        response = requests.get(url, headers=headers, timeout=20, allow_redirects=True)
        response.raise_for_status()

        content_type = response.headers.get('content-type', '').lower()
        if 'html' not in content_type:
            return False, f"Skipped (not HTML): {content_type[:50]}"

        with open(filepath, 'w', encoding='utf-8', errors='replace') as f:
            f.write(response.text)
        return True, None
    except requests.exceptions.HTTPError as e:
        return False, f"HTTP error {e.response.status_code}"
    except requests.exceptions.ConnectionError:
        return False, "Connection error"
    except requests.exceptions.Timeout:
        return False, "Timeout"
    except requests.exceptions.RequestException as e:
        return False, f"Request error: {type(e).__name__}"
    except IOError as e:
        return False, f"File save error: {type(e).__name__}"
    except Exception as e:
        return False, f"Unexpected error: {type(e).__name__}"

def scan_and_download_all_articles_util(df_all_posts, status_callback=None):
    """
    Scans all posts, filters links, and downloads articles if they don't already exist.
    """
    if status_callback: status_callback("Preparing to download articles...")
    os.makedirs(config.LINKED_ARTICLES_DIR, exist_ok=True)
    print(f"Starting article scan. Saving to: {config.LINKED_ARTICLES_DIR}")

    total_posts = len(df_all_posts)
    downloaded_count = 0
    skipped_count = 0
    error_count = 0
    excluded_count = 0

    for index, post_series in df_all_posts.iterrows():
        post_number_val = post_series.get('Post Number')
        post_id_for_filename_base = str(post_number_val if pd.notna(post_number_val) else index)
        safe_post_id_for_filename = sanitize_filename_component(post_id_for_filename_base)

        if status_callback and (index + 1) % 20 == 0 :
             status_callback(f"Articles: Post {index + 1}/{total_posts}. D:{downloaded_count}, S:{skipped_count}, E:{error_count}")
        if (index + 1) % 100 == 0:
            print(f"Processing Articles for Post ID: {safe_post_id_for_filename} ({index+1}/{total_posts})")

        urls_to_check = []
        main_link = post_series.get('Link')
        if main_link and isinstance(main_link, str) and main_link.strip():
            urls_to_check.append(main_link.strip())

        text_content = post_series.get('Text', '')
        if text_content:
            urls_in_text = _extract_urls_from_text(text_content)
            urls_to_check.extend(urls_in_text)

        processed_urls_for_this_post = set()
        unique_urls_this_post = []
        for url in urls_to_check:
            if url not in processed_urls_for_this_post:
                unique_urls_this_post.append(url)
                processed_urls_for_this_post.add(url)

        if not unique_urls_this_post:
            continue

        for url_idx, url in enumerate(unique_urls_this_post):
            if not url or not isinstance(url, str) or not url.startswith(('http://', 'https://')):
                continue

            if is_excluded_domain(url, config.EXCLUDED_LINK_DOMAINS):
                excluded_count +=1
                continue

            exists, filepath = check_article_exists_util(safe_post_id_for_filename, url)

            if exists:
                skipped_count += 1
                continue

            time.sleep(0.2)
            success, error_msg = download_article_util(url, filepath)
            if success:
                downloaded_count += 1
            else:
                print(f"    Error downloading Article {url[:70]}: {error_msg}")
                error_count += 1

    final_summary = f"Article download finished. New: {downloaded_count}, Skipped: {skipped_count}, Errors: {error_count}, Excluded: {excluded_count}."
    print(f"\n{final_summary}")
    if status_callback: status_callback(final_summary)

def download_all_post_images_util(df_all_posts, status_callback=None):
    """
    Downloads images for posts from the DataFrame based on ImagesJSON.
    """
    if status_callback: status_callback("Preparing to download images...")
    os.makedirs(config.IMAGE_DIR, exist_ok=True)
    print(f"Starting image download. Saving to: {config.IMAGE_DIR}")

    total_images_downloaded = 0
    total_images_skipped = 0
    image_error_count = 0
    posts_processed = 0
    total_posts = len(df_all_posts)

    for index, row in df_all_posts.iterrows():
        posts_processed += 1
        if status_callback and posts_processed % 20 == 0:
            status_callback(f"Images: Post {posts_processed}/{total_posts}. D:{total_images_downloaded}, S:{total_images_skipped}, E:{image_error_count}")
        if posts_processed % 100 == 0:
            print(f"Processing Images for post {posts_processed}/{total_posts}...")

        images_in_post_json = row.get('ImagesJSON', [])

        if not images_in_post_json or not isinstance(images_in_post_json, list):
            continue

        post_id_display = str(row.get('Post Number', f"index_{index}"))

        for img_data in images_in_post_json:
            if not isinstance(img_data, dict):
                continue

            img_filename = img_data.get('file')
            if not img_filename:
                continue

            if not img_filename.startswith(('http://', 'https://')):
                image_url = config.QANON_PUB_MEDIA_BASE_URL + img_filename
            else:
                image_url = img_filename

            local_image_path = os.path.join(config.IMAGE_DIR, sanitize_filename_component(os.path.basename(img_filename)))

            if not os.path.exists(local_image_path):
                time.sleep(0.1)
                headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
                try:
                    response = requests.get(image_url, stream=True, timeout=20, headers=headers)
                    response.raise_for_status()

                    with open(local_image_path, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            f.write(chunk)
                    total_images_downloaded += 1
                except requests.exceptions.HTTPError as e:
                    print(f"    HTTP Error downloading Image {image_url}: {e.response.status_code}")
                    image_error_count +=1
                except requests.exceptions.RequestException as e:
                    print(f"    Error downloading Image {image_url}: {type(e).__name__}")
                    image_error_count +=1
                except Exception as e:
                    print(f"    An unexpected error occurred with Image {image_url}: {e}")
                    image_error_count +=1
            else:
                total_images_skipped += 1

    final_summary = f"Image download finished. New: {total_images_downloaded}, Skipped: {total_images_skipped}, Errors: {image_error_count}."
    print(f"\n{final_summary}")
    if status_callback: status_callback(final_summary)

# --- END ARTICLE_DOWNLOADING_UTILS ---