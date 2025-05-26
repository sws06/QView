# QView - Q Post Explorer

## Overview

QView is a desktop application meticulously designed for exploring, searching, and analyzing the Q posts dataset. It provides an intuitive graphical user interface (GUI) to navigate through thousands of posts, view detailed content including images and linked articles, and leverage powerful search and filtering tools for in-depth research and analysis. The application also features robust capabilities for offline content archival, ensuring valuable data (images and web articles) remains accessible.

We believe QView has become a significant and powerful tool for anyone looking to seriously engage with and understand this unique dataset.

## Key Features

**1. Data Loading & Rich Display:**
* Efficiently loads Q posts from a local `posts.url-normalized.json` file.
* Presents posts in a sortable and filterable list (columns: Post #, Date, Bookmark status).
* **Detailed Post View:**
    * Displays Post Number, Date/Time (in both UTC and your local timezone).
    * Shows Author and Tripcode, if available.
    * Lists automatically assigned Themes based on keywords within the post content.
    * Presents the full post text with automatically detected, clickable hyperlinks.
    * Clearly renders referenced/quoted posts (if any) within the main post, also with clickable links.
    * Displays thumbnails of attached images directly in a dedicated panel.
    * Allows opening full-size images with an external viewer by clicking thumbnails.
    * Shows the original source link (if provided in the data) and site/board information.

**2. Intuitive Navigation:**
* Navigate sequentially using "Next" and "Previous" post buttons.
* Jump directly to any post by entering its number.
* Utilize keyboard arrow keys for quick navigation within the post list.
* The application remembers your last viewed post in a search/filter.

**3. Powerful & Versatile Search Capabilities:**
* **Search by Post Number:** Find a single post (e.g., `123`), a continuous range (e.g., `100-150`), or a custom list of posts (e.g., `10, 25, 103`).
* **Search by Keyword/Theme:** Perform full-text searches within the post content and across automatically assigned themes.
* **Search by Date:** Use an integrated calendar to select a specific date and view all posts from that day.
* **Delta Search:** Discover posts made on the same month and day but across different years (e.g., all posts from every July 4th).
* **Today's Deltas:** A quick-click button to view posts from the current calendar month/day across all years.
* **View Bookmarked Posts:** Filter the list to show only your bookmarked posts.
* **Show All Posts:** Easily clear any active search or filter to return to the full, chronological post list.

**4. Content Management & Offline Archival:**
* **Dedicated "Content Sync" Window:**
    * **Download Images:** Secure all image attachments linked in posts for offline viewing. The application warns about potential download size (approx. 400-500MB) and intelligently skips already downloaded images.
    * **Download Articles:** Archive the HTML content of web pages linked within posts. This is invaluable for offline research and preserving content. It includes a warning for potentially large download sizes (700MB+) and excludes common imageboards, social media, and file-sharing sites to focus on article content. Already downloaded articles are skipped.
* Locally downloaded images are automatically displayed as thumbnails in the post view.
* A **"View Saved Article" button** dynamically appears for posts if a linked article has been successfully archived locally, allowing for one-click offline viewing.

**5. User Customization & Productivity Tools:**
* **Bookmarking:** Mark any post as a favorite. Bookmarks are saved locally and can be viewed as a filtered list.
* **Export Data:** Export the currently displayed list of posts (whether all posts or search results) to either **HTML** (with formatted text and links) or **CSV** format for external use.
* **Interface Theming:** Instantly switch between a comfortable **Dark theme** and a crisp **Light theme**. Your preference is saved.
* **Link Opening Preference:** Choose in settings whether web links (and saved articles) open in your **System Default Browser** or in **Google Chrome (Incognito Mode)**, if Chrome is detected.
* **"Show Links" Window:** Easily view and click a list of all unique URLs found within the currently displayed post.
* **Organized Data Storage:** User-specific data (settings, bookmarks) and downloaded content (images, articles, cached DataFrame) are neatly stored in a `user_data` subfolder within the application's main directory.

**6. User-Friendly Interface:**
* Clean, two-panel layout: post list on the left, detailed content view on the right.
* Helpful tooltips for less obvious features (e.g., "Today's Deltas" button shows the date it will search for).
* The main window components intelligently resize.
* An integrated **Help & Info window** provides usage tips and links to relevant online Q post resources.
* A standard **About dialog** displays application version information.

## Prerequisites

* Python 3.x (developed with 3.9+)
* The following Python libraries (you can install them using pip: `pip install <library_name>`):
    * `Pillow` (for image processing)
    * `pandas` (for data manipulation and management)
    * `demjson3` (for robustly parsing the input Q posts JSON file)
    * `requests` (for downloading images and articles)
    * `tkcalendar` (for the date selection calendar widget)
    * `tkinter` (typically included with Python standard library, ensure it's available)

## Setup & Running from Source

1.  **Install Prerequisites:** Ensure Python 3 and all libraries listed above are installed in your Python environment.
2.  **Get the Code:** Place all QView application files (`main.py`, `gui.py`, `utils.py`, `config.py`, `data.py`, `settings.py`) in a single directory on your computer.
3.  **Data File:** Obtain the Q posts data file, ensure it's named `posts.url-normalized.json`, and place it in the **same root directory** as the QView application files.
4.  **Run:** Open a terminal or command prompt, navigate to the QView application directory, and execute:
    ```bash
    python main.py
    ```
5.  **User Data Folder:** Upon first run, QView will attempt to create a subfolder named `user_data` within its root directory. This folder will store:
    * `posts_df.pkl`: A cached, processed version of your post data for faster loading.
    * `q_gui_bookmarks.dat`: Your saved bookmarks.
    * `settings.json`: Your application settings (theme, link preferences).
    * `q_images/`: Directory for downloaded post images.
    * `linked_articles/`: Directory for downloaded HTML articles.

## Basic Usage Guide

* **Browse:** The list of posts appears on the left. Click any post to see its full details on the right. Use the "Next >>" and "<< Prev" buttons for sequential navigation.
* **Searching:**
    * **Post # Field:** Enter a specific post number (e.g., `1776`), a range (e.g., `100-200`), or a comma-separated list (e.g., `1, 7, 42`). Click its "Go" button.
    * **Keyword/Theme Field:** Type any word, phrase, or theme. Click its "Go" button.
    * Other search buttons ("Search by Date", "Delta Search", "Today's Deltas", "View Bookmarks") are self-explanatory.
* **Content Sync:** Click the "Content Sync" button (bottom row) to open a new window. From there, you can initiate downloads for all post images or all linked articles. Be mindful of the size warnings!
* **Settings:** Click the "Settings" button to change the application theme or your link opening preferences.
* **Exporting:** Choose "HTML" or "CSV" from the dropdown menu at the bottom, then click "Export Displayed List" to save the posts currently shown in the left-hand list.

---

We genuinely believe QView provides a substantial toolkit for anyone studying this material. Enjoy your research!

## Future Considerations

* Development of a standalone installer for easier distribution.
* Ongoing performance enhancements.
* Exploration of a mobile-friendly version (a longer-term aspiration).