# QView
Your Offline Q Post Research Environment

QView is a standalone, offline application for Windows designed for deep research and analysis of Q posts. It operates entirely on your local machine, ensuring privacy and eliminating the need for an internet connection after the initial data download. It provides powerful search, filtering, annotation, and visualization tools to help users explore the dataset and discover connections.

## Latest in v1.7 (November 2025)

### Universal Calendar & Data Fidelity
This version rebuilds the date-search experience and fixes critical export and search bugs.

* **Universal "Year-at-a-Glance" Calendar:** A completely new, custom-built calendar interface replacing the standard date picker.
    * **Silent Day Tracking:** The calendar now highlights days where **no posts were ever made** (across any year), identifying communication gaps at a glance.
    * **Multi-Year Info Panel:** Clicking any date instantly displays a breakdown of post numbers for that specific day across all years (2017-2020).
    * **Year-Agnostic Grid:** A streamlined 12-month view that eliminates the need to scroll through empty years.
* **HTML Export Upgrade:** The "Export to HTML" feature now correctly preserves line breaks in post text, making long-form posts readable in the browser.
* **Critical Bug Fixes:**
    * **Theme Search:** Fixed a crash caused by case-sensitivity issues when filtering by themes.
    * **List Sorting:** Fixed the sort logic so posts order numerically (1, 2, 10) instead of alphabetically (1, 10, 2).
    * **Stability:** Fixed a crash related to date formatting in the new calendar view.

## Core Features
* **The Q Clock:** A dynamic visualization dashboard for analyzing post timing and connections (Spiral plot, 2x2 grid, Delta mapping).
* **Complete Offline Access:** After an initial sync, the entire application and dataset run locally.
* **Advanced Search:** Filter the entire post archive by post number, keywords, date, and post themes.
* **Context Chain Viewer:** Trace conversations and connections between posts.
* **User Notes & Bookmarks:** Add private annotations and bookmark key posts.
* **Gematria Calculator:** An integrated tool for calculating gematria of any selected text.

<details>
<summary><strong>View Previous Version History...</strong></summary>

### v1.6 (September 2025)
* **The Q Clock:** Introduced the Multi-Clock Dashboard and Master Spiral Clock.
* **Advanced Interactivity:** Zoom, pan, and dynamic dot scaling.
* **Visual Filtering:** Color-coded dots for images/links and connection lines for Deltas/Mirrors.
* **Data Polish:** Fixed timestamp anomalies for late 2020 posts.

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