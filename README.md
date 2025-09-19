# QView
Your Offline Q Post Research Environment

QView is a standalone, offline application for Windows designed for deep research and analysis of Q posts. It operates entirely on your local machine, ensuring privacy and eliminating the need for an internet connection after the initial data download. It provides powerful search, filtering, annotation, and visualization tools to help users explore the dataset and discover connections.

## Latest in v1.5 (September 2025)

### Enhanced Search & UI Refinements
* **Search Term Highlighting:** Search results now highlight the matching keyword or phrase directly in the post text for easier analysis.
* **Dynamic Date Selector:** The calendar for date searches is now a persistent, non-modal window, allowing you to interact with the main viewer and select dates simultaneously.
* **Integrated Delta Search:** The delta search feature (finding posts by month/day across all years) is now an integrated checkbox within the main date search calendar.
* **Streamlined UI:** The `Highlight Abbreviations` toggle has been moved from the main navigation bar to the `Settings` window to reduce clutter.
* **Bug Fix:** Corrected a bug that could cause a crash when a date search returned no results.

## Core Features
* **Complete Offline Access:** After an initial sync, the entire application and dataset run locally. No internet connection required.
* **Advanced Search:** Filter the entire post archive by post number (including ranges and lists), keywords/phrases, date, and post themes.
* **Interactive Q Clock:** A powerful data visualization tool to view posts by time.
    * **Multi-Clock Dashboard:** View each year's posts on a separate, interactive clock.
    * **Master Clock:** Open a standalone window with a chronological "spiral" plot of all posts.
    * **Deep Analysis:** Zoom, pan, filter, and multi-select posts directly on the clock.
    * **Connection Lines:** Instantly visualize mirrored posts and time deltas.
* **Context Chain Viewer:** Trace conversations and connections between posts in a dedicated window.
* **User Notes & Bookmarks:** Add your own private annotations and bookmark key posts for later review.
* **Gematria Calculator:** An integrated tool for calculating the gematria of any selected text.

<details>
<summary><strong>View Previous Version History...</strong></summary>

### Latest in v1.4 (August 2025)
* **Context Chain Viewer:** A new window to trace post connections, including quotes, deltas, and mirrored matches, with tooltip previews and navigation history.
* **Enhanced User Notes System:** Added a "View All Notes" window and the ability to selectively show notes as tooltips in the main post list.
* **UI & Stability Improvements:** Added a "Search by Theme" option, fixed a critical startup bug, and improved the welcome screen display.

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