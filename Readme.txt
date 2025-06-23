# QView – Local Q Drop Explorer & Delta Analyzer

**QView** is a standalone desktop application for exploring, analyzing, and archiving Q posts. Built for researchers, not just readers — it's private, offline-friendly, and powered by a clean GUI designed for deep digs.

🔍 Explore post metadata, images, links, and deltas  
🧠 Filter by themes, dates, keywords, or custom notes  
🗃️ Download linked content for full offline research  
🎨 Switch between Dark, Light, and Patriot (RWB) themes  
🔧 Export data, calculate Gematria, and right-click to dig deeper  

> 💬 Join the discussion: [Official XDA Thread](https://xdaforums.com/t/tool-win-qview-offline-q-drop-explorer-delta-search-archive-tool-dark-to-light.4742777/)

---

## 🚀 Key Features

### 🔎 Data Explorer
- Sortable, searchable list of all Q posts
- See post number, timestamp (UTC/local), author, and tripcode
- Quoted post linking (jump-to-post + image previews)
- Auto-tagged themes based on post content
- Clickable links + downloadable media

### 📖 Post Viewer
- Side-by-side layout for text + images
- Auto-hiding image panel (if no images exist)
- Bookmarks & personal notes (saved locally)
- Quick jump by post number, range, or comma list

### 🧰 Right-Click Research Toolkit
- Search selected text via Google Books or Internet Archive
- Filter all posts containing the selected word/phrase
- Calculate Gematria (Hebrew, English, Simple)
- Copy text or dismiss menu

### 📅 Search Tools
- Delta Search (same month/day, different years)
- “Today’s Deltas” quick button
- Full calendar-based search by date
- Theme/keyword search with live filtering

### 📥 Offline Archival
- Download post images, quoted images, and linked articles
- Progress bars for each content type
- Stored in local folder structure, accessible offline

### 🎨 UI & Customization
- Switch between Light, Dark, and Patriot (RWB) themes
- Auto-saves theme preference
- Configurable browser preference (Chrome incognito or default)

---

## 🛠 Setup Instructions

### Option 1: Run the Pre-Packaged App (Recommended)
1. [Download latest release](https://github.com/sws06/QView/releases)
2. Extract the `.zip` file
3. Run `QView.exe`
4. A `user_data/` folder will be created on first launch

### Option 2: Run from Source

#### Prereqs
- Python 3.9+
- Required libraries:
  ```bash
  pip install pillow pandas requests tkcalendar lxml
tkinter may require separate install:

bash
Copy code
sudo apt-get install python3-tk  # Linux
Data Setup
Get a posts.url-normalized.json source file (e.g. from jkingsman/JSON-QAnon)

Run the conversion:

bash
Copy code
python create_qview_data.py
It will generate data/qview_posts_data.json — now you’re good to go.

Launch
bash
Copy code
python main.py
📦 Latest Release: v1.2 – June 14, 2025
✨ New Features
 New [Patriot Theme] (Red, White & Blue)

 Right-click menu: Google Books, Archive.org, Gematria, Filter

 Delta Search upgrades: date loops, cleaner UI

 Saved article viewer for offline HTMLs

🐛 Bug Fixes
Fixed theme preference not loading at launch

Restored broken image links in quoted posts

Fixed crash related to welcome image handling

Repaired full "Content Sync" functionality

📂 Post Data Source
Q posts are not included in this repo.
Use a JSON dataset like posts.url-normalized.json from:

📎 https://github.com/jkingsman/JSON-QAnon
Then run create_qview_data.py to convert it.

📌 Special thanks to jkingsman for the archival work.

🔐 Philosophy
No tracking. No telemetry. No internet required.
This is a tool for those who don’t want to rely on public portals.

“Truth doesn’t auto-update. It must be found.”

🧠 Coming Soon / On Deck
Advanced Filter Chains (e.g., theme + delta + date)

Watchlist Mode (encrypted post tagging)

Custom Theme Builder

Broadcast Loader (external lists of notable drops)

Public Notes Export