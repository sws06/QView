# QView – Your Offline Q Post Research Companion

**QView** is a cross-platform desktop application designed for in-depth exploration, analysis, and secure local archiving of Q posts. It provides a private, offline-first environment with a streamlined graphical interface, built for dedicated researchers and digital historians.
---

## ✨ Key Features & Highlights (v1.4)

* **Advanced Context Engine (New in v1.4):** Go beyond simple replies with a powerful analytical tool. The completely overhauled Context Viewer now reveals deeper connections between posts, including:
    * **Shared Markers:** Instantly see all posts that share the same `[MARKERS]`.
    * **Time/Delta Matches:** Find posts made at the same `HH:MM` time across different days.
    * **Shared Themes:** View posts that are linked by common thematic tags.
    * **Mirrored Matches:** Uncover abstract patterns with connections based on mirrored dates, reversed post numbers, and reversed timestamps based on Q Clock logic.
    * **Navigation History:** A new **`< Back`** button allows you to retrace your steps while exploring complex context chains.

* **Comprehensive Data Exploration:** Access a sortable, searchable list of all Q posts, complete with timestamps, author details, and tripcodes.

* **Intuitive Post Viewer:** Experience a clean side-by-side layout for post text and associated images. The image panel now displays a welcome image on startup and can be resized, but not fully closed, to ensure you always see attached media.

* **Advanced Search & Filtering:** Precisely locate posts using keywords, numerical ranges, specific dates, or a dedicated **Theme Search**.

* **Intelligent Cross-Referencing:** Click on `>>` numbers to instantly navigate to quoted posts, featuring inline image previews.

* **Integrated Research Tools:** Right-click on selected text for direct searches on Google Books or Internet Archive, or to perform instant **Gematria calculations**.

* **Personalized Workflow:** Create local **bookmarks** and add private, customizable **notes** to any post. A new **"View All Notes"** option in the Tools menu lets you see all your annotations in one place. Notes can also optionally appear as tooltips in the post list.

* **Offline Archival:** Download and permanently store all linked images (from posts and quotes) and external web articles as local HTML files.

* **Customizable Interface:** Choose from **Dark, Light, or a patriotic Red, White & Blue (RWB) theme**. Your theme preference is saved automatically.

---

## 📥 Getting Started

### Option 1: Run the Pre-Packaged App (Recommended for Windows)

1.  [**Download the latest release (v1.4)**](https://github.com/sws06/QView/releases)
2.  Extract the downloaded `.zip` file.
3.  Run `QView.exe`.
4.  A `user_data/` folder will be automatically created on first launch to store your notes, bookmarks, and downloaded content.

### Option 2: Run from Source

1.  **Clone the Repository:**
    ```bash
    git clone [https://github.com/sws06/QView.git](https://github.com/sws06/QView.git)
    cd QView
    ```

2.  **Install Prerequisites:**
    * Python 3.9+ is required.
    * Install the necessary libraries using pip:
      ```bash
      pip install pillow pandas requests tkcalendar lxml
      ```
    * On some Linux systems, `tkinter` may need to be installed separately:
      ```bash
      sudo apt-get install python3-tk
      ```

3.  **Launch the Application:**
    The necessary post data is included in the repository. Simply run the main script:
    ```bash
    python main.py
    ```
---
## 🔑 Philosophy
QView is built on principles of privacy, autonomy, and direct access.

No tracking. No telemetry. No internet required for core functionality.

It is a tool designed for independent verification and personal knowledge management, free from external influence or dependency. "Truth doesn’t auto-update. It must be found."

---
## 🤝 Contribution & Support
QView is a community-driven, open-source project. Your feedback and contributions are welcome.

Join the conversation at XDA Forums https://xdaforums.com/t/tool-win-qview-offline-q-drop-explorer-delta-search-archive-tool-dark-to-light.4742777/

View Source & Fork: https://github.com/sws06/QView

Report Issues / Suggest Features: GitHub Issues

Contact: qview1776@gmail.com

Support Development: If you find QView valuable, consider supporting its ongoing development.
☕ Buy me a coffee