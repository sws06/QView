# QView
Your Offline Q Post Research Environment

QView is a standalone, offline application for Windows designed for deep research and analysis of Q posts. It operates entirely on your local machine, ensuring privacy and eliminating the need for an internet connection after the initial data download. It provides powerful search, filtering, annotation, and visualization tools to help users explore the dataset and discover connections.

## Latest in v1.6 (September 2025)

### The Q Clock: A Dynamic Visualization Dashboard
This version introduces the **Q Clock**, a powerful suite of interactive, circular data visualization tools for deep analysis of post timing, connections, and content types.

* **Multi-Clock Dashboard:** View each year of posts on its own interactive clock in a balanced 2x2 grid, complete with a dedicated, always-visible legend.
* **Standalone "Master Clock":** Launch a new, resizable window featuring a chronological "spiral plot" of all posts from all years, allowing for a deep dive into the complete timeline.
* **Advanced Interactivity:**
    * Smooth mouse-wheel zoom and intuitive left-click-drag pan.
    * Dynamic dot scaling keeps posts clear and readable at any zoom level.
    * `Ctrl+Click` to multi-select posts for custom analysis.
    * Context-aware scrolling (zoom on clock, scroll on background).
* **Powerful Analytical Tools:**
    * **Color-Coded Dots:** Instantly identify posts with images (turquoise), links (orange), or both (magenta).
    * **Filter Toggles:** Dynamically show or hide posts by content type using a compact dropdown menu.
    * **Connection Lines:** Click any post to instantly visualize its connections to other posts (Time Deltas, Mirrored Dates, Mirrored Post #s, etc.).
    * **"Today's Date" Highlight:** A real-time slice on the clock highlights the current day of the year for effortless anniversary analysis.
* **Data Integrity & Polish:** Includes a script to fix a common data anomaly in some JSON files where final 2020 posts were incorrectly timestamped to 2022. The entire feature is highly polished with custom themes and a professional layout.

## Core Features
* **Complete Offline Access:** After an initial sync, the entire application and dataset run locally.
* **Advanced Search:** Filter the entire post archive by post number, keywords, date, and post themes.
* **Context Chain Viewer:** Trace conversations and connections between posts.
* **User Notes & Bookmarks:** Add private annotations and bookmark key posts.
* **Gematria Calculator:** An integrated tool for calculating gematria of any selected text.

<details>
<summary><strong>View Previous Version History...</strong></summary>

### v1.5 (September 2025)
* **Search Term Highlighting:** Search results now highlight the matching keyword in the post text.
* **Dynamic Date Selector:** The calendar for date searches is now a persistent, non-modal window.
* **Integrated Delta Search:** Delta search is now an integrated checkbox within the date search calendar.
* **Streamlined UI:** The `Highlight Abbreviations` toggle was moved to the `Settings` window.
* **Bug Fix:** Corrected a crash when a date search returned no results.

### v1.4 (August 2025)
* **Context Chain Viewer:** A new window to trace post connections (quotes, deltas, mirrors) with tooltip previews and navigation history.
* **Enhanced User Notes System:** Added a "View All Notes" window and selective tooltip display.
* **UI & Stability Improvements:** Added "Search by Theme," fixed a critical startup bug, and improved the welcome screen.

</details>

## Getting Started
1.  Ensure you have the `qview_posts_data.json` file in the appropriate data directory.
2.  Run `main.py` to launch the application.
3.  On first launch, the application will process the JSON data and create a faster `.pkl` cache file for subsequent launches.

## Why Offline?
In an environment of censorship and de-platforming, maintaining a local, user-controlled copy of data is essential for independent research. QView will never "phone home," track your activity, or rely on external servers to function.

## Data Source
QView is designed to work with a local copy of the `q_posts.json` dataset. The data parsing and structure are based on the excellent compilation work done by Jack Kingsman and others in the research community.

---
*QView • Local • Independent*