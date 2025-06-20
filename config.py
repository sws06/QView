# config.py

# --- START CONFIG_PY_HEADER ---
# --- START FILE_PATHS_AND_DIRECTORIES ---
import os
import re
import sys

# --- END CONFIG_PY_HEADER ---


# --- MODIFIED APP_ROOT_DIR DEFINITION ---
# Determine APP_ROOT_DIR dynamically
if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    # If the application is run as a bundle (e.g., by PyInstaller)
    # sys._MEIPASS is the path to the temporary folder where files are unpacked.
    # Based on your finding, PyInstaller is putting our data in an '_internal' subfolder here.
    APP_ROOT_DIR = os.path.join(sys._MEIPASS, '_internal')
    
    # As a fallback, if the '_internal' folder doesn't exist for some reason,
    # or for different PyInstaller versions, still check the base _MEIPASS path.
    if not os.path.exists(os.path.join(APP_ROOT_DIR, 'data')):
        APP_ROOT_DIR = sys._MEIPASS
else:
    # If run as a normal script, __file__ is the path to config.py
    APP_ROOT_DIR = os.path.dirname(os.path.abspath(__file__)) #
# --- END MODIFIED APP_ROOT_DIR DEFINITION ---

# Raw data file (typically shipped with the app or in a 'data' subfolder)
# For now, assume it's at the APP_ROOT_DIR. Consider moving to APP_ROOT_DIR/data/
POSTS_DATA_PATH = os.path.join(APP_ROOT_DIR, "data", "qview_posts_data.json")

# User-specific data, downloaded content, and generated files
# --- MODIFIED USER_DATA_ROOT FOR PACKAGED APP ---
# It's better for the packaged app to create user_data next to the .exe,
# not inside the (potentially temporary or read-only) APP_ROOT_DIR.
# We'll get the exe's directory instead of the temporary _MEIPASS directory.
if getattr(sys, "frozen", False):
    # If frozen, get the directory of the executable itself
    EXE_DIR = os.path.dirname(sys.executable)
    USER_DATA_ROOT = os.path.join(EXE_DIR, "user_data")
else:
    # If not frozen, use the original logic
    USER_DATA_ROOT = os.path.join(APP_ROOT_DIR, "user_data") #
# --- END MODIFIED USER_DATA_ROOT ---

try:
    os.makedirs(USER_DATA_ROOT, exist_ok=True) #
except OSError as e:
    print(f"Warning: Could not create user_data directory at {USER_DATA_ROOT}: {e}") #
    # Fallback to APP_ROOT_DIR if user_data creation fails (e.g. permissions)
    USER_DATA_ROOT = APP_ROOT_DIR


DATAFRAME_PICKLE_PATH = os.path.join(USER_DATA_ROOT, "posts_df.pkl")
BOOKMARKS_FILE_PATH = os.path.join(USER_DATA_ROOT, "q_gui_bookmarks.dat")
SETTINGS_FILE_PATH = os.path.join(USER_DATA_ROOT, "settings.json")
USER_NOTES_FILE_PATH = os.path.join(USER_DATA_ROOT, "user_notes.json")

IMAGE_DIR_NAME = "q_images"  # Just the name, not used for full path construction here
IMAGE_DIR = os.path.join(USER_DATA_ROOT, IMAGE_DIR_NAME)  # Full path

THUMBNAIL_DIR_NAME = "_thumbnails" # Subdirectory for cached thumbnails
THUMBNAIL_DIR = os.path.join(IMAGE_DIR, THUMBNAIL_DIR_NAME) # Full path to thumbnails

LINKED_ARTICLES_DIR_NAME = "linked_articles"  # Just the name
LINKED_ARTICLES_DIR = os.path.join(
    USER_DATA_ROOT, LINKED_ARTICLES_DIR_NAME
)  # Full path

# Ensure these user data subdirectories exist
try:
    os.makedirs(IMAGE_DIR, exist_ok=True)
    os.makedirs(LINKED_ARTICLES_DIR, exist_ok=True)
    os.makedirs(THUMBNAIL_DIR, exist_ok=True) # Ensure thumbnail directory is also created
except OSError as e:
    print(f"Warning: Could not create image/article/thumbnail directories in {USER_DATA_ROOT}: {e}")
    # App might fail to save images/articles if these paths aren't writable / creatable.

# --- END FILE_PATHS_AND_DIRECTORIES ---

# --- START THEME_DEFINITIONS ---
THEMES = {
    "pain_is_coming": ["pain is coming", "expect pain", "pain coming"],
    "justice_coming": ["justice", "arrests", "tribunals"],
    "not_silenced": [
        "we will not be silenced",
        "can't silence us",
        "they can't stop what's coming",
        "cannot be stopped",
    ],
    "ten_days_darkness": [
        "10 days of darkness",
        "ten days darkness",
        "10 days of dark",
    ],
    "castle_clean": ["castle clean", "castle is clean"],
    "the_storm": [
        "the storm",
        "storm is here",
        "storm is coming",
        "eye of the storm",
        "calm before the storm",
    ],
    "truth_blocked_fail": ["they will try to block the truth. they will fail"],
    "pain_general": ["pain", "suffering", "hurt", "agony"],
    "darkness_general": [
        "dark",
        "darkness",
        "shadow",
        "evil",
        "gloomy",
        "lucifer",
        "satan",
        "dark to light",
    ],
    "light_hope": [
        "light",
        "enlightenment",
        "hope",
        "dawn",
        "awakening",
        "bring the light",
        "future proves past",
    ],
    "truth_revealed": [
        "truth",
        "true",
        "reveal",
        "disclose",
        "facts",
        "information",
        "the truth will light the way",
        "truth will be revealed",
    ],
    "patience_trust_plan": [
        "patience",
        "trust the plan",
        "trust",
        "wait",
        "soon",
        "timing is everything",
        "plan is in motion",
    ],
    "wwg1wga": ["wwg1wga", "where we go one we go all"],
    "declas_info": [
        "declass",
        "declassification",
        "release information",
        "unseal",
        "info dump",
    ],
    "boom_event": [
        "boom",
        "bang",
        "explosion",
        "big event",
        "it's coming",
        "eventually",
    ],
}
# --- END THEME_DEFINITIONS ---

# --- START URL_REGEX_DEFINITION ---
URL_REGEX = re.compile(
    r"""(?i)\b((?:https?://|www\d{0,3}[.]|[a-z0-9.\-]+[.][a-z]{2,4}/)(?:[^\s()<>]+|\(([^\s()<>]+|(\([^\s()<>]+\)))*\))+(?:\(([^\s()<>]+|(\([^\s()<>]+\)))*\)|[^\s`!()\[\]{};:'".,<>?«»“”‘’]))"""
)
# --- END URL_REGEX_DEFINITION ---



# --- START EXPORT_CONFIGURATION ---
EXPORT_COLUMNS = [
    "Post Number",
    "Datetime_UTC",
    "Author",
    "Text",
    "Themes",
    "Link",
    "Referenced Posts Display",
    "Image Count",
    "ImagesJSON",
    "Site",
    "Board",
]
# --- END EXPORT_CONFIGURATION ---

# --- START PLACEHOLDER_TEXTS ---
PLACEHOLDER_POST_NUM = "Post #"
PLACEHOLDER_KEYWORD = "Keyword/Theme"
# --- END PLACEHOLDER_TEXTS ---

# --- START ARTICLE_DOWNLOAD_CONFIG ---
# LINKED_ARTICLES_DIR_NAME is now just a name, full path is LINKED_ARTICLES_DIR
EXCLUDED_LINK_DOMAINS = [
    "4chan.org",
    "www.4chan.org",
    "8ch.net",
    "www.8ch.net",
    "8kun.top",
    "www.8kun.top",
    "8kun.net",
    "googleusercontent.com",  # Covers various Google content like YouTube embeds
    "youtube.com",
    "youtu.be",
    "vimeo.com",
    "bitchute.com",
    "rumble.com",
    "twitter.com",
    "x.com",  # Social media
    "facebook.com",
    "www.facebook.com",
    "instagram.com",
    "www.instagram.com",
    "reddit.com",
    "www.reddit.com",
    "archive.org",
    "archive.is",
    "archive.ph",
    "gab.com",
    "t.me",  # Telegram
    "mega.nz",  # File hosting
    "mediafire.com",
    "dropbox.com",
    "filezilla-project.org",
    "wikileaks.org",
    "google.com",
    "duckduckgo.com",
    "wikipedia.org",
    "imgur.com",
    "i.imgur.com",
    "imgbb.com",
    "ibb.co",
    "postimg.cc",
    "gyazo.com",
    "prnt.sc",
    "giphy.com",
    "tenor.com",
    "files.wordpress.com",
    "cloudfront.net",
]
QANON_PUB_MEDIA_BASE_URL = (
    "https://www.qanon.pub/data/media/"  # Corrected base URL for images from qanon.pub
)
# --- END ARTICLE_DOWNLOAD_CONFIG ---

# --- START SETTINGS_CONFIG ---
# SETTINGS_FILE_PATH is defined in FILE_PATHS_AND_DIRECTORIES now
# --- END SETTINGS_CONFIG ---
