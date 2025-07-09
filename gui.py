# --- START GUI_PY_HEADER ---

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from tkcalendar import Calendar
from PIL import Image, ImageTk
import pandas as pd
import datetime
import os
import webbrowser
import urllib.parse
import threading
import re # For parsing post numbers from references
import config
import utils
import data as app_data
import settings

# --- END GUI_PY_HEADER ---

# --- START TOOLTIP_CLASS ---

class Tooltip:
    def __init__(self, widget, text_generator, delay=700, follow=True, bind_widget_events=True):
        self.widget = widget
        self.text_generator = text_generator
        self.delay = delay
        self.follow = follow
        self.tip_window = None
        self.id = None
        # Only bind to the whole widget if explicitly told to
        if bind_widget_events:
            self.widget.bind("<Enter>", self.enter)
            self.widget.bind("<Leave>", self.leave)
            self.widget.bind("<ButtonPress>", self.leave)

    def enter(self, event=None):
        self.schedule()

    def leave(self, event=None):
        self.unschedule()
        self.hidetip()

    def schedule(self):
        self.unschedule()
        self.id = self.widget.after(self.delay, self.showtip)

    def unschedule(self):
        id_ = self.id
        self.id = None
        if id_:
            self.widget.after_cancel(id_)

    def showtip(self):
        if self.tip_window:
            return
        text_to_show = self.text_generator()
        if not text_to_show:
            return

        # Adjust position to appear near the mouse, especially for Text widgets
        # If a widget has an event, use event.x/y, else use widget's position
        x, y = self.widget.winfo_pointerx(), self.widget.winfo_pointery() # Get mouse screen coordinates

        # Optionally offset slightly from cursor to avoid covering it
        offset_x = 10
        offset_y = 20

        self.tip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x + offset_x}+{y + offset_y}") # Position relative to mouse

        label = tk.Label(tw, text=text_to_show, justify=tk.LEFT,
                         background="#FFFFE0", foreground="#000000",
                         relief=tk.SOLID, borderwidth=1,
                         font=("tahoma", "9", "normal"), padx=5, pady=3)
        label.pack(ipadx=1)

    def hidetip(self):
        tw = self.tip_window
        self.tip_window = None
        if tw:
            tw.destroy()

# --- END TOOLTIP_CLASS ---

# --- START QPOSTVIEWER_CLASS_DEFINITION ---

class QPostViewer:

# --- START __INIT__ ---

    def __init__(self, root):
        self.root = root
        self.root.title("QView")
        window_width = 1024
        window_height = 720
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        center_x = int(screen_width/2 - window_width / 2)
        center_y = int(screen_height/2 - window_height / 2)
        if center_y + window_height > screen_height - 40:
             center_y = screen_height - 40 - window_height
        if center_y < 0: center_y = 0
        self.root.geometry(f'{window_width}x{window_height}+{center_x}+{center_y}')
        self.root.minsize(800, 600)

        self.displayed_images_references = []
        self._quote_image_references = [] # For inline quote images
        self.current_post_urls = []
        self.current_post_downloaded_article_path = None
        self.context_history = []
        self._is_navigating_context_back = False
        
        self._context_expand_vars = {} # Stores BooleanVars for collapsible sections
        self._context_tag_refs = [] # Stores Tooltip instances for clickable links

        self.app_settings = settings.load_settings()
        self.bookmarked_posts = utils.load_bookmarks_from_file(config.BOOKMARKS_FILE_PATH)
        self.user_notes = utils.load_user_notes(config.USER_NOTES_FILE_PATH)

        self.df_all_posts = app_data.load_or_parse_data()
        self.df_displayed = pd.DataFrame() # Will be populated after initial check
        self.current_search_active = False
        self.current_display_idx = -1

        self.current_theme = self.app_settings.get("theme", settings.DEFAULT_SETTINGS["theme"])
        self.placeholder_fg_color_dark = "grey"
        self.placeholder_fg_color_light = "#757575"
        self.link_label_fg_dark = "#6DAEFF"
        self.link_label_fg_light = "#0056b3"
        self.highlight_abbreviations_var = tk.BooleanVar(value=self.app_settings.get("highlight_abbreviations", settings.DEFAULT_SETTINGS["highlight_abbreviations"]))

        self.style = ttk.Style()
        self.theme_var = tk.StringVar(value=self.current_theme) # For settings window radio buttons, if needed centrally

# --- Main Layout Grid Setup ---

        self.tree_frame = ttk.Frame(root)
        self.tree_frame.grid(row=0, column=0, padx=10, pady=(10,0), sticky="nswe")
        root.grid_rowconfigure(0, weight=1)
        root.grid_columnconfigure(0, weight=1, minsize=280) # Treeview column, no horizontal resizing from here

# --- Treeview Setup (Left Pane Content) ---

        self.post_tree = ttk.Treeview(self.tree_frame, columns=("Post #", "Date", "Notes", "Bookmarked"), show="headings")
        self.scrollbar_y = ttk.Scrollbar(self.tree_frame, orient="vertical", command=self.post_tree.yview)
        self.post_tree.configure(yscrollcommand=self.scrollbar_y.set)
        self.post_tree.heading("Post #", text="Post #", anchor='w', command=lambda: self.sort_treeview_column("Post #", False))
        self.post_tree.heading("Date", text="Date", anchor='w', command=lambda: self.sort_treeview_column("Date", False))
        self.post_tree.heading("Notes", text="♪", anchor='center', command=lambda: self.sort_treeview_column("Notes", False)) # New Notes heading
        self.post_tree.heading("Bookmarked", text="★", anchor='center', command=lambda: self.sort_treeview_column("Bookmarked", False))
        self.post_tree.column("Post #", width=70, stretch=tk.NO, anchor='w')
        self.post_tree.column("Date", width=110, stretch=tk.YES, anchor='w')
        self.post_tree.column("Notes", width=25, stretch=tk.NO, anchor='center') # Width for Notes column
        self.post_tree.column("Bookmarked", width=30, stretch=tk.NO, anchor='center')
        self.post_tree.grid(row=0, column=0, sticky="nswe")
        self.scrollbar_y.grid(row=0, column=1, sticky="ns")
        self.tree_frame.grid_rowconfigure(0, weight=1)
        self.tree_frame.grid_columnconfigure(0, weight=1)

# --- END Treeview Setup ---

# --- START TREEVIEW_NOTE_TOOLTIP_SETUP ---
        self.treeview_note_tooltip = Tooltip(self.post_tree, self._get_note_tooltip_text, delay=500)
        self.post_tree.bind("<Motion>", self._on_treeview_motion_for_tooltip)
        self.post_tree.bind("<Leave>", self._on_treeview_leave_for_tooltip)
# --- END TREEVIEW_NOTE_TOOLTIP_SETUP ---

# --- START TREEVIEW_NOTE_TOOLTIP_SETUP ---
        self.treeview_note_tooltip = Tooltip(self.post_tree, self._get_note_tooltip_text, delay=500)
        self.post_tree.bind("<Motion>", self._on_treeview_motion_for_tooltip)
        self.post_tree.bind("<Leave>", self._on_treeview_leave_for_tooltip)
# --- END TREEVIEW_NOTE_TOOLTIP_SETUP ---

# --- Right Pane (Text Area + Image Display) with Panedwindow ---

        self.details_outer_frame = ttk.Frame(root)
        self.details_outer_frame.grid(row=0, column=1, padx=(0,10), pady=(10,0), sticky="nswe")
        root.grid_columnconfigure(1, weight=3) # Main content column, allows it to expand
# Panedwindow for Text and Image Split (Vertical Splitter)
        self.text_image_paned_window = ttk.Panedwindow(self.details_outer_frame, orient=tk.HORIZONTAL) # Changed to HORIZONTAL for vertical separator
        self.text_image_paned_window.pack(fill=tk.BOTH, expand=True)

# --- Text Area Setup (Left pane of the text-image split) ---
        self.text_area_frame = ttk.Frame(self.text_image_paned_window)
        self.text_image_paned_window.add(self.text_area_frame, weight=3) # Text area gets more weight horizontally
        self.text_area_frame.grid_rowconfigure(0, weight=1)
        self.text_area_frame.grid_columnconfigure(0, weight=1)

        self.post_text_area = tk.Text(self.text_area_frame, wrap=tk.WORD,
                                   relief=tk.FLAT, borderwidth=1, font=("TkDefaultFont", 11),
                                   padx=10, pady=10)
        self.default_text_area_cursor = self.post_text_area.cget("cursor")
        self.post_text_scrollbar = ttk.Scrollbar(self.text_area_frame, orient="vertical", command=self.post_text_area.yview)
        self.post_text_area.configure(yscrollcommand=self.post_text_scrollbar.set)
        self.post_text_area.grid(row=0, column=0, sticky="nswe")
        self.post_text_scrollbar.grid(row=0, column=1, sticky="ns")

# --- Image Display Frame Setup (Right pane of the text-image split, now scrollable) ---
        self.image_display_frame = ttk.Frame(self.text_image_paned_window)
# MODIFIED: Removed 'minsize=0' from add. Will set minsize via pane later.
        self.text_image_paned_window.add(self.image_display_frame, weight=0) # Start minimized (weight=0)
        
# Create a canvas and scrollbar *within* the image_display_frame
        self.image_canvas = tk.Canvas(self.image_display_frame, highlightthickness=0)
        self.image_scrollbar = ttk.Scrollbar(self.image_display_frame, orient="vertical", command=self.image_canvas.yview)
        self.image_scrollable_frame = ttk.Frame(self.image_canvas) # This frame will hold the actual images

        self.image_scrollable_frame.bind(
            "<Configure>",
            lambda e: self.image_canvas.configure(
                scrollregion=self.image_canvas.bbox("all")
            )
        )
        self.image_canvas_window = self.image_canvas.create_window((0, 0), window=self.image_scrollable_frame, anchor="nw")
        self.image_canvas.configure(yscrollcommand=self.image_scrollbar.set)

        self.image_canvas.pack(side="left", fill="both", expand=True)
        self.image_scrollbar.pack(side="right", fill="y")

# Make the canvas window resize with the canvas
        self.image_canvas.bind("<Configure>", lambda e: self.image_canvas.itemconfig(self.image_canvas_window, width=e.width))
# --- END Image Display Setup ---

        self.post_text_area.bind("<KeyPress>", self._prevent_text_edit)
        
# --- START CONTEXT_MENU_SETUP ---

# Create the pop-up menu
        self.context_menu = tk.Menu(self.post_text_area, tearoff=0)
# Add other search providers as needed here

# Bind the right-click event to the show_context_menu method
        self.post_text_area.bind("<Button-3>", self._show_context_menu)

# --- END CONTEXT_MENU_SETUP ---

        self.configure_text_tags()
# --- Controls Setup ---
        controls_main_frame = ttk.Frame(root)
        controls_main_frame.grid(row=1, column=0, columnspan=2, padx=10, pady=(5,10), sticky="ew")

        nav_frame = ttk.Frame(controls_main_frame)
        nav_frame.pack(pady=(0,5), fill=tk.X)
        
 # --- MODIFIED: Relocated Prev/Next Post buttons for better grouping ---
        self.prev_button = ttk.Button(nav_frame, text="<< Prev", command=self.prev_post, width=8)
        self.prev_button.pack(side="left", padx=2)
        self.next_button = ttk.Button(nav_frame, text="Next >>", command=self.next_post, width=8) # Moved next button here
        self.next_button.pack(side="left", padx=2)

        self.post_number_label = ttk.Label(nav_frame, text="", width=35, anchor="center", font=('Arial', 11, 'bold'))
        self.post_number_label.pack(side="left", padx=5, expand=True, fill=tk.X)

        # NEW: Highlight Abbreviations Toggle
        self.highlight_abbreviations_checkbutton = ttk.Checkbutton(
            nav_frame,
            text="Highlight Abbreviations",
            variable=self.highlight_abbreviations_var,
            command=self.on_highlight_abbreviations_toggle
        )
        self.highlight_abbreviations_checkbutton.pack(side="left", padx=5)

        actions_frame = ttk.Labelframe(controls_main_frame, text="Search & Actions", padding=(10,5))
        actions_frame.pack(pady=5, fill=tk.X, expand=True)
        
        search_fields_frame = ttk.Frame(actions_frame)
        search_fields_frame.pack(fill=tk.X, pady=2)
# --- MODIFIED: Removed 'Go' buttons, adjusted packing for entries ---
        self.post_entry = ttk.Entry(search_fields_frame, width=12, font=('Arial', 10))
        self.post_entry.pack(side=tk.LEFT, padx=(0,5), expand=True, fill=tk.X) # Increased padx for spacing
        self.post_entry.bind("<FocusIn>", lambda e, p=config.PLACEHOLDER_POST_NUM: self.clear_placeholder(e, p, self.post_entry))
        self.post_entry.bind("<FocusOut>", lambda e, p=config.PLACEHOLDER_POST_NUM: self.restore_placeholder(e, p, self.post_entry))
        self.post_entry.bind("<Return>", lambda event: self.search_post_by_number()) # Enter key for search

        self.keyword_entry = ttk.Entry(search_fields_frame, width=20, font=('Arial', 10))
        self.keyword_entry.pack(side=tk.LEFT, padx=(0,0), expand=True, fill=tk.X) # Adjusted padx
        self.keyword_entry.bind("<FocusIn>", lambda e, p=config.PLACEHOLDER_KEYWORD: self.clear_placeholder(e, p, self.keyword_entry))
        self.keyword_entry.bind("<FocusOut>", lambda e, p=config.PLACEHOLDER_KEYWORD: self.restore_placeholder(e, p, self.keyword_entry))
        self.keyword_entry.bind("<Return>", lambda event: self.search_by_keyword()) # Enter key for search
# --- END MODIFIED ---

# --- MODIFIED: Consolidated Date/Delta Searches into a menu ---
        search_buttons_frame = ttk.Frame(actions_frame)
        search_buttons_frame.pack(fill=tk.X, pady=(5,2))

# Advanced Search Menu Button
        self.search_menu_button = ttk.Menubutton(search_buttons_frame, text="Advanced Search", style="TButton")
        self.search_menu = tk.Menu(self.search_menu_button, tearoff=0)
        self.search_menu_button["menu"] = self.search_menu
        
        self.search_menu.add_command(label="Search by Date", command=self.show_calendar)
        self.search_menu.add_command(label="Delta Search", command=self.show_day_delta_dialog)
        self.search_menu.add_command(label="Today's Deltas", command=self.search_today_deltas)
        self.search_menu.add_command(label="Search by Theme", command=self.show_theme_selection_dialog) # NEW: Search by Theme
        Tooltip(self.search_menu_button, lambda: "Advanced search options including by specific date, or by month/day across all years.")

        self.search_menu_button.pack(side=tk.LEFT, padx=2, expand=True, fill=tk.X)

        self.clear_search_button = ttk.Button(search_buttons_frame, text="Show All Posts", command=self.clear_search_and_show_all, state=tk.DISABLED)
        self.clear_search_button.pack(side=tk.LEFT, padx=2, expand=True, fill=tk.X)
# --- END MODIFIED ---

# Original buttons_frame2 now combined with buttons_frame3 for current post actions
        current_post_actions_frame = ttk.Frame(actions_frame)
        current_post_actions_frame.pack(fill=tk.X, pady=2)

        self.show_links_button = ttk.Button(current_post_actions_frame, text="Show Links", command=self.show_post_links_window_external, state=tk.DISABLED)
        self.show_links_button.pack(side=tk.LEFT, padx=2, expand=True, fill=tk.X)
        self.view_article_button = ttk.Button(current_post_actions_frame, text="Article Not Saved", command=lambda: None, state=tk.DISABLED)
        self.view_article_button.pack(side=tk.LEFT, padx=2, expand=True, fill=tk.X)
        self.bookmark_button = ttk.Button(current_post_actions_frame, text="Bookmark This Post", command=self.toggle_current_post_bookmark, state=tk.DISABLED)
        self.bookmark_button.pack(side=tk.LEFT, padx=2, expand=True, fill=tk.X)
        self.view_bookmarks_button = ttk.Button(current_post_actions_frame, text=f"View Bookmarks ({len(self.bookmarked_posts)})", command=self.view_bookmarked_gui_posts)
        self.view_bookmarks_button.pack(side=tk.LEFT, padx=2, expand=True, fill=tk.X)
        self.view_edit_note_button = ttk.Button(current_post_actions_frame, text="View/Edit Note", command=self.show_note_popup, state=tk.DISABLED)
        self.view_edit_note_button.pack(side=tk.LEFT, padx=2, expand=True, fill=tk.X)
        self.view_context_button = ttk.Button(current_post_actions_frame, text="View Context", command=self.show_context_chain_viewer_window, state=tk.DISABLED)
        self.view_context_button.pack(side=tk.LEFT, padx=2, expand=True, fill=tk.X)

# --- MODIFIED: Consolidated Bottom Buttons per user request ---
        bottom_main_bar_frame = ttk.Frame(controls_main_frame)
        bottom_main_bar_frame.pack(pady=(10,0), fill=tk.X, expand=True)

# Export Menu Button
        self.export_menu_button = ttk.Menubutton(bottom_main_bar_frame, text="Export", style="TButton")
        self.export_menu = tk.Menu(self.export_menu_button, tearoff=0)
        self.export_menu_button["menu"] = self.export_menu
        self.export_menu.add_command(label="Export as HTML", command=lambda: self.export_displayed_list(file_format="HTML"))
        self.export_menu.add_command(label="Export as CSV", command=lambda: self.export_displayed_list(file_format="CSV"))
        self.export_menu_button.pack(side=tk.LEFT, padx=(0,2), fill=tk.X, expand=True)
        Tooltip(self.export_menu_button, lambda: "Export the currently displayed posts to HTML or CSV.") # Tooltip for export menu

# Settings
        self.settings_button = ttk.Button(bottom_main_bar_frame, text="Settings", command=self.show_settings_window)
        self.settings_button.pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)

# About
        self.about_button = ttk.Button(bottom_main_bar_frame, text="About", command=self.show_about_dialog)
        self.about_button.pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)
        Tooltip(self.about_button, lambda: "Information about QView and its data source.") # Tooltip for About button

# Tools Menu
        self.tools_menu_button = ttk.Menubutton(bottom_main_bar_frame, text="Tools", style="TButton")
        self.tools_menu = tk.Menu(self.tools_menu_button, tearoff=0)
        self.tools_menu_button["menu"] = self.tools_menu
        
        self.tools_menu.add_command(label="Gematria Calc", command=self.show_gematria_calculator_window)
        self.tools_menu.add_command(label="Content Sync", command=self.show_download_window)
        self.tools_menu.add_command(label="Help & Info", command=self.show_help_window)

        self.tools_menu_button.pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)
        Tooltip(self.tools_menu_button, lambda: "Access various utilities like Gematria calculator, content sync, and help.") # Tooltip for Tools menu


# Quit App
        ttk.Button(bottom_main_bar_frame, text="Quit App", command=self.on_closing).pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)
# --- END MODIFIED ---

        if self.current_theme == "light":
            self.apply_light_theme()
        elif self.current_theme == "rwb":
            self.apply_rwb_theme()
        else: 
# Default to dark if theme is "dark" or unknown
            self.apply_dark_theme()

        self.restore_placeholder(None, config.PLACEHOLDER_POST_NUM, self.post_entry)
        self.restore_placeholder(None, config.PLACEHOLDER_KEYWORD, self.keyword_entry)

        self.post_tree.bind("<<TreeviewSelect>>", self.on_tree_select)
        self.post_tree.bind("<Up>", self.on_tree_arrow_nav)
        self.post_tree.bind("<Down>", self.on_tree_arrow_nav)
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        self._init_complete = False
        if self.df_all_posts is not None and not self.df_all_posts.empty:
            self.df_all_posts = self.df_all_posts.reset_index(drop=True)
            self.df_displayed = self.df_all_posts.copy()
            self.repopulate_treeview(self.df_displayed, select_first_item=False)
        elif self.df_all_posts is None:
            messagebox.showerror("Critical Error", "Failed to load any post data. Application cannot continue.")
            self.root.destroy()
            return

        self.show_welcome_message()
        self._init_complete = True

# --- END __INIT__ ---

# --- START _PREVENT_TEXT_EDIT ---

    def _prevent_text_edit(self, event):
        if event.state & 0x0004: # If Control key is pressed
            if event.keysym.lower() == 'c': return # Allow Ctrl+C
            if event.keysym.lower() == 'a': return # Allow Ctrl+A
        allowed_nav_keys = ["Left", "Right", "Up", "Down", "Prior", "Next", "Home", "End",
                            "Control_L", "Control_R", "Shift_L", "Shift_R", "Alt_L", "Alt_R",
                            "leftarrow", "rightarrow", "uparrow", "downarrow", "PageUp", "PageDown"]
        if event.keysym in allowed_nav_keys: return
        return "break"

# --- END _PREVENT_TEXT_EDIT ---

# --- START _INSERT_TEXT_WITH_CLICKABLE_URLS ---

    # This helper now ONLY handles clickable URLs.
    def _insert_text_with_clickable_urls(self, text_widget, text_content_raw, base_tags_tuple, link_event_tag_prefix):
        if pd.isna(text_content_raw) or not str(text_content_raw).strip():
            text_widget.insert(tk.END, "", base_tags_tuple if base_tags_tuple else ())
            return
        text_content = utils.sanitize_text_for_tkinter(text_content_raw)
        if not isinstance(text_content, str) or not text_content.strip():
            text_widget.insert(tk.END, str(text_content) if pd.notna(text_content) else "", base_tags_tuple if base_tags_tuple else ())
            return

        last_end = 0
        for url_match in config.URL_REGEX.finditer(text_content):
            start, end = url_match.span()
            if start > last_end:
                text_widget.insert(tk.END, text_content[last_end:start], base_tags_tuple)

            url = url_match.group(0)
            clickable_tag_instance = f"{link_event_tag_prefix}_url_{url_match.start()}"
            current_tags = list(base_tags_tuple) if base_tags_tuple else []
            current_tags.extend(['clickable_link_style', clickable_tag_instance])

            text_widget.insert(tk.END, url, tuple(current_tags))
            text_widget.tag_bind(clickable_tag_instance, "<Button-1>", lambda e, u=url: utils.open_link_with_preference(u, self.app_settings))
            last_end = end

        if last_end < len(text_content):
            text_widget.insert(tk.END, text_content[last_end:], base_tags_tuple)

# --- END _INSERT_TEXT_WITH_CLICKABLE_URLS ---

# --- START _INSERT_TEXT_WITH_ABBREVIATIONS_AND_URLS ---

    def _insert_text_with_abbreviations_and_urls(self, text_widget, text_content_raw, base_tags_tuple, post_id_for_tagging):
        if pd.isna(text_content_raw) or not str(text_content_raw).strip():
            text_widget.insert(tk.END, "", base_tags_tuple if base_tags_tuple else ())
            return

        text_content = utils.sanitize_text_for_tkinter(text_content_raw)
        if not isinstance(text_content, str) or not text_content.strip():
            text_widget.insert(tk.END, str(text_content) if pd.notna(text_content) else "", base_tags_tuple if base_tags_tuple else ())
            return

        highlight_enabled = self.highlight_abbreviations_var.get()

        # This will store (start_char_idx, end_char_idx, abbreviation_text, is_bracketed) tuples
        abbreviation_spans = []

        # 1. Find all potential abbreviations
        # Sorted keys for greedy matching of longer abbreviations first
        sorted_abbreviations = sorted(config.Q_ABBREVIATIONS.keys(), key=len, reverse=True)

        for abbr in sorted_abbreviations:
        # Pattern for standalone abbreviation (word boundary)
        # Using re.escape to handle special characters in abbreviations
            standalone_pattern = r'\b' + re.escape(abbr) + r'\b'
            for match in re.finditer(standalone_pattern, text_content):
                abbreviation_spans.append((match.start(), match.end(), abbr, False))

        # Pattern for bracketed abbreviation
            bracketed_pattern = r'\[' + re.escape(abbr) + r'\]'
            for match in re.finditer(bracketed_pattern, text_content):
                abbreviation_spans.append((match.start(), match.end(), abbr, True))

        # Sort spans by their start index. If start indices are the same, longer matches first.
        abbreviation_spans.sort(key=lambda x: (x[0], -x[1]))

        # Filter overlapping matches, prioritizing longer ones that start earlier
        non_overlapping_abbreviations = []
        last_added_end = -1
        for start, end, abbr_text, is_bracketed in abbreviation_spans:
            if start >= last_added_end:
                non_overlapping_abbreviations.append((start, end, abbr_text, is_bracketed))
                last_added_end = end
            else:
        # If this abbreviation is completely contained within the last added one, skip.
        # If it's a partial overlap, the sorting already prioritized the "best" (longest-starting-earliest).
                pass

        # 2. Iterate through text and apply tags
        current_pos = 0

        # Iterate through the content, processing segments between abbreviations, and then the abbreviations themselves.
        # This will also handle URLs within non-abbreviation text segments by calling _insert_text_with_clickable_urls.
        for start, end, abbr_text, is_bracketed in non_overlapping_abbreviations:
        # Insert text before the current abbreviation match
            if start > current_pos:
                segment = text_content[current_pos:start]
                self._insert_text_with_clickable_urls(text_widget, segment, base_tags_tuple, f"{post_id_for_tagging}_seg_{current_pos}")

        # Insert the abbreviation with its specific tags
            matched_abbr_full_text = text_content[start:end] # e.g., "ROTH" or "[ROTH]"

            abbr_tags = list(base_tags_tuple)
            if highlight_enabled:
                abbr_tags.append('abbreviation_tag')

        # For the purpose of applying the context menu, we can bind to the entire text area
        # and use index. But to apply specific tags for highlighting, we insert.
            text_widget.insert(tk.END, matched_abbr_full_text, tuple(abbr_tags))

            current_pos = end

        # Insert any remaining text after the last abbreviation
        if current_pos < len(text_content):
            segment = text_content[current_pos:]
            self._insert_text_with_clickable_urls(text_widget, segment, base_tags_tuple, f"{post_id_for_tagging}_final_{current_pos}")

# --- END _INSERT_TEXT_WITH_ABBREVIATIONS_AND_URLS ---

# --- START UPDATE_DISPLAY ---

    def update_display(self):
        for widget in self.image_scrollable_frame.winfo_children(): widget.destroy()
        self.displayed_images_references = []; self._quote_image_references = []; self.current_post_urls = []; self.current_post_downloaded_article_path = None
        self.post_text_area.config(state=tk.NORMAL); self.post_text_area.delete(1.0, tk.END)
        show_images = True
        if self.df_displayed is None or self.df_displayed.empty or not (0 <= self.current_display_idx < len(self.df_displayed)):
            self.show_welcome_message(); return
        
        original_df_index = self.df_displayed.index[self.current_display_idx]
        post = self.df_all_posts.loc[original_df_index]
        post_number_val = post.get('Post Number'); safe_filename_post_id = utils.sanitize_filename_component(str(post_number_val if pd.notna(post_number_val) else original_df_index))
        pn_display_raw = post.get('Post Number', original_df_index); pn_str = f"#{pn_display_raw}" if pd.notna(pn_display_raw) else f"(Idx:{original_df_index})"
        is_bookmarked = original_df_index in self.bookmarked_posts; bookmark_indicator_text_raw = "[BOOKMARKED]" if is_bookmarked else ""
        
        self.post_text_area.insert(tk.END, utils.sanitize_text_for_tkinter(f"QView Post {pn_str} "), "post_number_val")
        if is_bookmarked: self.post_text_area.insert(tk.END, utils.sanitize_text_for_tkinter(bookmark_indicator_text_raw) + "\n", "bookmarked_header")
        else: self.post_text_area.insert(tk.END, "\n")
        
        dt_val = post.get('Datetime_UTC')
        if pd.notna(dt_val):
            dt_utc = dt_val.tz_localize('UTC') if dt_val.tzinfo is None else dt_val; dt_local = dt_utc.tz_convert(None)
            date_local_str=f"{dt_local.strftime('%Y-%m-%d %H:%M:%S %Z')} (Local)\n"; date_utc_str=f"{dt_utc.strftime('%Y-%m-%d %H:%M:%S %Z')} (UTC)\n"
            self.post_text_area.insert(tk.END, "Date: ", "bold_label"); self.post_text_area.insert(tk.END, date_local_str, "date_val"); self.post_text_area.insert(tk.END, "      ", "bold_label"); self.post_text_area.insert(tk.END, date_utc_str, "date_val")
        else: self.post_text_area.insert(tk.END, "Date: No Date\n", "bold_label")
        
        author_text_raw=post.get('Author',''); tripcode_text_raw=post.get('Tripcode',''); author_text=utils.sanitize_text_for_tkinter(author_text_raw); tripcode_text=utils.sanitize_text_for_tkinter(tripcode_text_raw)
        if author_text and pd.notna(author_text_raw): self.post_text_area.insert(tk.END, "Author: ", "bold_label"); self.post_text_area.insert(tk.END, f"{author_text}\n", "author_val")
        if tripcode_text and pd.notna(tripcode_text_raw): self.post_text_area.insert(tk.END, "Tripcode: ", "bold_label"); self.post_text_area.insert(tk.END, f"{tripcode_text}\n", "author_val")
        
        themes_list = post.get('Themes', [])
        if themes_list and isinstance(themes_list, list) and len(themes_list) > 0: themes_str = utils.sanitize_text_for_tkinter(f"{', '.join(themes_list)}\n"); self.post_text_area.insert(tk.END, "Themes: ", "bold_label"); self.post_text_area.insert(tk.END, themes_str, "themes_val")
        
        referenced_posts_raw_data = post.get('Referenced Posts Raw')
        if isinstance(referenced_posts_raw_data, list) and referenced_posts_raw_data:
            self.post_text_area.insert(tk.END, "\nReferenced Content:\n", ("bold_label"))
            for ref_idx, ref_post_data in enumerate(referenced_posts_raw_data):
                if not isinstance(ref_post_data, dict): continue
                ref_num_raw = ref_post_data.get('reference', ''); ref_author_id_raw = ref_post_data.get('author_id'); ref_text_content_raw = ref_post_data.get('text', '[No text in reference]')
                ref_num_san = utils.sanitize_text_for_tkinter(str(ref_num_raw)); ref_auth_id_san = utils.sanitize_text_for_tkinter(str(ref_author_id_raw))
                
                self.post_text_area.insert(tk.END, "↪ Quoting ", ("quoted_ref_header"))
                clickable_ref_id_tag = f"clickable_ref_id_{original_df_index}_{ref_idx}_{ref_num_raw}"
                target_post_num_for_ref = None 
                if ref_num_san: 
                    self.post_text_area.insert(tk.END, f"{ref_num_san} ", ("quoted_ref_header", "clickable_link_style", clickable_ref_id_tag))
                    try: 
                        actual_post_num_match = re.search(r'\d+', ref_num_raw)
                        if actual_post_num_match: 
                            target_post_num_for_ref = int(actual_post_num_match.group(0))
                            self.post_text_area.tag_bind(clickable_ref_id_tag, "<Button-1>", lambda e, pn=target_post_num_for_ref: self.jump_to_post_number_from_ref(pn))
                    except ValueError: pass 
                
                if ref_auth_id_san and str(ref_auth_id_san).strip(): self.post_text_area.insert(tk.END, f"(by {ref_auth_id_san})", ("quoted_ref_header"))
                self.post_text_area.insert(tk.END, ":\n", ("quoted_ref_header"))
                
                quoted_images_list = ref_post_data.get('images', [])
                if quoted_images_list and isinstance(quoted_images_list, list):
                    self.post_text_area.insert(tk.END, "    ", ("quoted_ref_text_body"))

                    for q_img_idx, quote_img_data in enumerate(quoted_images_list):
                        img_filename_from_quote = quote_img_data.get('file')
                        if img_filename_from_quote:
                            local_image_path_from_quote = os.path.join(config.IMAGE_DIR, utils.sanitize_filename_component(os.path.basename(img_filename_from_quote)))
                            
                            if os.path.exists(local_image_path_from_quote):
                                try:
                                    img_pil_quote = Image.open(local_image_path_from_quote)
                                    img_pil_quote.thumbnail((75, 75))
                                    photo_quote = ImageTk.PhotoImage(img_pil_quote)
                                    self._quote_image_references.append(photo_quote)
                                    
                                    clickable_quote_img_tag = f"quote_img_open_{original_df_index}_{ref_idx}_{q_img_idx}"
                                    
# Insert the thumbnail image
                                    self.post_text_area.image_create(tk.END, image=photo_quote)
# Insert a clickable link icon (chain) next to it
                                    self.post_text_area.insert(tk.END, " 🔗", ('clickable_link_style', clickable_quote_img_tag))
# Bind the click event to open the full image
                                    self.post_text_area.tag_bind(
                                        clickable_quote_img_tag, 
                                        "<Button-1>", 
                                        lambda e, p=local_image_path_from_quote: utils.open_image_external(p, self.root)
                                    )
                                    if q_img_idx < len(quoted_images_list) - 1:
                                        self.post_text_area.insert(tk.END, "  ")
                                except Exception as e_quote_img:
                                    print(f"Error displaying inline quote img {img_filename_from_quote}: {e_quote_img}")
                                    self.post_text_area.insert(tk.END, f"[ErrImg]", ("quoted_ref_text_body", "image_val"))
                                    if q_img_idx < len(quoted_images_list) - 1:
                                        self.post_text_area.insert(tk.END, " ")
                            else: 
                                self.post_text_area.insert(tk.END, f"[ImgN/F]", ("quoted_ref_text_body", "image_val"))
                                if q_img_idx < len(quoted_images_list) - 1:
                                    self.post_text_area.insert(tk.END, " ")
                    
                    self.post_text_area.insert(tk.END, "\n", ("quoted_ref_text_body"))

# --- MODIFIED: Use the new helper to insert text with abbreviations and URLs ---
                self._insert_text_with_abbreviations_and_urls(self.post_text_area, ref_text_content_raw, ("quoted_ref_text_body",), f"qref_{original_df_index}_{ref_idx}")
                self.post_text_area.insert(tk.END, "\n")
            self.post_text_area.insert(tk.END, "\n")
        
# --- MODIFIED: Use the new helper to insert main text with abbreviations and URLs ---
        main_text_content_raw = post.get('Text', '')
        self.post_text_area.insert(tk.END, "Post Text:\n", ("bold_label"))
        self._insert_text_with_abbreviations_and_urls(self.post_text_area, main_text_content_raw, (), f"main_{original_df_index}")
        
        if show_images:
            images_json_data = post.get('ImagesJSON', [])
            if images_json_data and isinstance(images_json_data, list) and len(images_json_data) > 0:
                self.post_text_area.insert(tk.END, f"\n\n--- Images ({len(images_json_data)}) ---\n", "bold_label")
                
# Restore sash if it was forgotten and set initial width
                image_pane_index = self.text_image_paned_window.panes().index(self.image_display_frame)
                sash_index = image_pane_index - 1

                if not self.text_image_paned_window.sash_exists(sash_index):
                    self.text_image_paned_window.pane(self.image_display_frame, weight=1, width=250) # Set weight and desired width
                else:
                    self.text_image_paned_window.pane(self.image_display_frame, weight=1, width=250) # Just set weight and width if already there

# Ensure the sash is visible by moving it to the desired position
                self.text_image_paned_window.update_idletasks() # Ensure sizes are calculated
# Set sash position to give 250px to image pane (from right)
# This is complex with horizontal panedwindow, need to calculate total width.
# Best approach: set it based on current overall width of parent.
                parent_width = self.text_image_paned_window.winfo_width()
                if parent_width > 0: # Only if window has a width
                     self.text_image_paned_window.sash_place(sash_index, parent_width - 250, self.text_image_paned_window.winfo_height() // 2)

                for img_data in images_json_data:
                    img_filename = img_data.get('file')
                    if img_filename:
                        local_image_path = os.path.join(config.IMAGE_DIR, utils.sanitize_filename_component(os.path.basename(img_filename)))

                        if os.path.exists(local_image_path):
                            try:                              
                                img_pil = Image.open(local_image_path)
                                img_pil.thumbnail((300, 300))
                                photo = ImageTk.PhotoImage(img_pil)
                                img_label = ttk.Label(self.image_scrollable_frame, image=photo, cursor="hand2")
                                img_label.image = photo
                                img_label.pack(pady=2, anchor='nw')
                                img_label.bind("<Button-1>", lambda e, p=local_image_path: utils.open_image_external(p, self.root))
                                self.displayed_images_references.append(photo)
                            except Exception as e:            
                                print(f"Err display img {local_image_path}: {e}")
                                self.post_text_area.insert(tk.END, f"[Err display img: {img_filename}]\n", "image_val")
                        else:                             
                            self.post_text_area.insert(tk.END, f"[Img not found: {img_filename}]\n", "image_val")
                
                self.image_scrollable_frame.update_idletasks() # Ensure geometry is calculated
                self.image_canvas.config(scrollregion=self.image_canvas.bbox("all"))

            else: 
                img_count_from_data = post.get('Image Count', 0)
                if img_count_from_data == 0 : 
                    self.post_text_area.insert(tk.END, "\n\nImage Count: 0\n", "image_val")
                else: 
                    self.post_text_area.insert(tk.END, f"\n\n--- Images ({img_count_from_data}) - metadata mismatch or files not found ---\n", "image_val")
                
# Collapse the image pane if no images
                image_pane_index = self.text_image_paned_window.panes().index(self.image_display_frame)
                sash_index = image_pane_index - 1
                
                self.text_image_paned_window.pane(self.image_display_frame, weight=0, width=0) # Collapse it and set width to 0
                if sash_index >= 0 and self.text_image_paned_window.sash_exists(sash_index):
                     self.text_image_paned_window.sash_forget(sash_index) # Hide sash

# After hiding, update idletasks to ensure it collapses visually
                self.text_image_paned_window.update_idletasks()
            
            metadata_link_raw = post.get('Link')
            if metadata_link_raw and pd.notna(metadata_link_raw) and len(str(metadata_link_raw).strip()) > 0 :
                actual_metadata_link_str = utils.sanitize_text_for_tkinter(str(metadata_link_raw).strip())
                # --- MODIFIED: Use the new helper for source link too ---
                self.post_text_area.insert(tk.END, "\nSource Link: ", "bold_label")
                self._insert_text_with_abbreviations_and_urls(self.post_text_area, actual_metadata_link_str, ("clickable_link_style",) , f"metalink_{original_df_index}")
                self.post_text_area.insert(tk.END, "\n")
            elif post.get('Site') and post.get('Board'): site_text=utils.sanitize_text_for_tkinter(post.get('Site','')); board_text=utils.sanitize_text_for_tkinter(post.get('Board','')); self.post_text_area.insert(tk.END, "\nSource: ", "bold_label"); self.post_text_area.insert(tk.END, f"{site_text}/{board_text}\n", "author_val")
        
        article_found_path = None; urls_to_scan_for_articles = []
        if metadata_link_raw and isinstance(metadata_link_raw, str) and metadata_link_raw.strip(): urls_to_scan_for_articles.append(metadata_link_raw.strip())
        if main_text_content_raw: urls_to_scan_for_articles.extend(utils._extract_urls_from_text(main_text_content_raw))
        unique_urls_for_article_check = list(dict.fromkeys(urls_to_scan_for_articles))
        for url in unique_urls_for_article_check:
            if not url or not isinstance(url,str) or not url.startswith(('http://','https://')): continue
            if utils.is_excluded_domain(url, config.EXCLUDED_LINK_DOMAINS): continue
            exists, filepath = utils.check_article_exists_util(safe_filename_post_id, url)
            if exists: article_found_path = filepath; break
        
        if hasattr(self,'view_article_button'):
            if article_found_path: self.view_article_button.config(text="View Saved Article", state=tk.NORMAL, command=lambda p=article_found_path: self.open_downloaded_article(p))
            else: self.view_article_button.config(text="Article Not Saved", state=tk.DISABLED, command=lambda: None)
        if hasattr(self,'show_links_button'):
            if self.current_post_urls: self.show_links_button.config(state=tk.NORMAL)
            else: self.show_links_button.config(state=tk.DISABLED)
        if hasattr(self,'view_edit_note_button'):
            if self.df_displayed is not None and not self.df_displayed.empty and 0 <= self.current_display_idx < len(self.df_displayed): self.view_edit_note_button.config(state=tk.NORMAL)
            else: self.view_edit_note_button.config(state=tk.DISABLED)
        
        self.post_text_area.config(state=tk.DISABLED)
        self.update_post_number_label(); self.update_bookmark_button_status()
        self.root.update_idletasks()

# --- END UPDATE_DISPLAY ---

# --- START SHOW_WELCOME_MESSAGE ---

    def show_welcome_message(self):
        self.post_text_area.config(state=tk.NORMAL); self.post_text_area.delete(1.0, tk.END)
        
# Clear existing images and references
        for widget in self.image_scrollable_frame.winfo_children(): widget.destroy()
        self.displayed_images_references = []; self._quote_image_references = []; self.current_post_urls = []
        
# Collapse the image pane if showing welcome message
        if self.image_display_frame in self.text_image_paned_window.panes():
            sash_index = self.text_image_paned_window.panes().index(self.image_display_frame) - 1
            self.text_image_paned_window.pane(self.image_display_frame, weight=0, width=0) # Collapse it and set width to 0
            if sash_index >= 0: # Ensure sash exists before trying to forget it
                self.text_image_paned_window.sash_forget(sash_index)


        title="QView – Offline Q Post Explorer\n";
        para1="QView is a standalone desktop application designed for serious research into the full Q post archive. Built from the ground up for speed, clarity, and privacy, QView lets you search, explore, and annotate thousands of drops without needing an internet connection."
        para2="Unlike web-based tools that can disappear or go dark, QView gives you complete control—local images, saved article archives, powerful search tools, and customizable settings wrapped in a clean, user-friendly interface. No tracking. No fluff. Just signal."
        para3="Development is 100% community-driven and fully open-source."
        
        closing_text="🔒 No paywalls. No locked features."

        self.post_text_area.insert(tk.END, title+"\n", "welcome_title_tag");
        self.post_text_area.insert(tk.END, para1+"\n\n", "welcome_text_tag")
        self.post_text_area.insert(tk.END, para2+"\n\n", "welcome_text_tag")
        self.post_text_area.insert(tk.END, para3+"\n\n", ("welcome_text_tag", "welcome_emphasis_tag"))
        
        self.post_text_area.insert(tk.END, "\n\n", "welcome_text_tag")
        self.post_text_area.insert(tk.END, closing_text+"\n", "welcome_closing_tag")
        
# self.post_text_area.config(state=tk.DISABLED) # Keep commented out for now
        
        if hasattr(self,'show_links_button'): self.show_links_button.config(state=tk.DISABLED)
        if hasattr(self,'view_article_button'): self.view_article_button.config(text="Article Not Saved", state=tk.DISABLED, command=lambda: None)
        self.update_post_number_label(is_welcome=True); self.update_bookmark_button_status(is_welcome=True)
        if hasattr(self,'view_edit_note_button'): self.view_edit_note_button.config(state=tk.DISABLED)

# --- END SHOW_WELCOME_MESSAGE ---

# --- START JUMP_TO_POST_FROM_REF ---

    def jump_to_post_number_from_ref(self, post_number):
        if post_number is None:
             messagebox.showinfo("Navigation Error", "Invalid post number reference (None).", parent=self.root); return
        if self.df_all_posts is None or self.df_all_posts.empty: 
            messagebox.showwarning("Data Error", "No post data loaded.", parent=self.root); return
        try: target_post_num_int = int(post_number)
        except (ValueError, TypeError): messagebox.showinfo("Navigation Error", f"Invalid post number format for jump: {post_number}.", parent=self.root); return
        matching_posts = self.df_all_posts[self.df_all_posts['Post Number'] == target_post_num_int]
        if not matching_posts.empty:
            original_df_idx_to_jump_to = matching_posts.index[0]
# When jumping from a reference, we always want to show all posts initially
# to make sure the target post is in the df_displayed.
            if self.current_search_active:
                self.clear_search_and_show_all()
# Ensure UI updates before selection. This is handled by clear_search_and_show_all itself.
                self.root.update_idletasks() # Let the UI refresh after clearing search

# Now, select the item in the treeview.
# We need to find its positional index within the *current* df_displayed.
            if self.df_displayed is not None and original_df_idx_to_jump_to in self.df_displayed.index: 
                display_idx = self.df_displayed.index.get_loc(original_df_idx_to_jump_to)
                self.current_display_idx = display_idx
                self.select_tree_item_by_idx(self.current_display_idx)
            else:
                messagebox.showinfo("Not Found", f"Post # {target_post_num_int} could not be found in the current display view.", parent=self.root)
        else: messagebox.showinfo("Not Found", f"Post # {target_post_num_int} not found in dataset.", parent=self.root)

# --- END JUMP_TO_POST_FROM_REF ---

# --- START DATE_NAVIGATION_METHODS ---

    def _navigate_by_day(self, delta_days):
        if self.df_all_posts is None or self.df_all_posts.empty:
            messagebox.showwarning("Navigation", "No post data loaded to navigate by date.", parent=self.root)
            return

        current_date = None
# Try to get the date of the currently displayed post
        if self.df_displayed is not None and not self.df_displayed.empty and 0 <= self.current_display_idx < len(self.df_displayed):
            current_post = self.df_displayed.iloc[self.current_display_idx]
            dt_val = current_post.get('Datetime_UTC')
            if pd.notna(dt_val):
                current_date = dt_val.date()
        
# If no current date, default to today
        if current_date is None:
            current_date = datetime.date.today()

        target_date = current_date + datetime.timedelta(days=delta_days)

# Clear any active search to search the full dataset
        if self.current_search_active:
            self.clear_search_and_show_all()
            self.root.update_idletasks() # Ensure UI updates before proceeding

# Find posts for the target date
        results = self.df_all_posts[self.df_all_posts['Datetime_UTC'].dt.date == target_date]
        
        if not results.empty:
# Re-sort results by post number to ensure consistent navigation
            results = results.sort_values(by='Post Number').reset_index(drop=True)
            self._handle_search_results(results, f"Posts from {target_date.strftime('%Y-%m-%d')}")
        else:
            messagebox.showinfo("No Posts Found", f"No posts found for {target_date.strftime('%Y-%m-%d')}.", parent=self.root)
# If no posts found for the target date, we should still clear existing selection
# or show a neutral state. Calling update_display with -1 current_display_idx handles this.
            self.df_displayed = pd.DataFrame(columns=self.df_all_posts.columns if self.df_all_posts is not None else [])
            self.current_search_active = True # Treat as a search result
            self.clear_search_button.config(state=tk.NORMAL)
            self.current_display_idx = -1
            self.repopulate_treeview(self.df_displayed, select_first_item=False)
            self.show_welcome_message() # Show welcome on no results

    def prev_day_post(self):
        self._navigate_by_day(-1)

    def next_day_post(self):
        self._navigate_by_day(1)

# --- END DATE_NAVIGATION_METHODS ---

# --- START CONTEXT_MENU_METHODS ---

    def _search_selection_with(self, search_engine):
        try:
            selected_text = self.post_text_area.get(tk.SEL_FIRST, tk.SEL_LAST).strip()
            if not selected_text:
                return
            
            encoded_text = urllib.parse.quote_plus(selected_text)
            
            if search_engine == 'google_books':
                url = f"https://www.google.com/search?tbm=bks&q=%22{encoded_text}%22"
            elif search_engine == 'internet_archive':
                url = f"https://archive.org/search?query=%22{encoded_text}%22"
            elif search_engine == 'gematrix':
                url = f"https://www.gematrix.org/?word={encoded_text}"
            else:
                return
            
            utils.open_link_with_preference(url, self.app_settings)

        except tk.TclError:
            pass

    def _add_context_menu_options(self):
        self.context_menu.delete(0, tk.END)
        
        try:
            selected_text = self.post_text_area.get(tk.SEL_FIRST, tk.SEL_LAST).strip()
            state = tk.NORMAL if selected_text else tk.DISABLED
        except tk.TclError:
            state = tk.DISABLED

        abbreviation_meaning_displayed = False
        if selected_text:
            abbreviation_for_lookup = None
            if selected_text in config.Q_ABBREVIATIONS:
                abbreviation_for_lookup = selected_text
            elif selected_text.startswith('[') and selected_text.endswith(']'):
                inner_text = selected_text[1:-1]
                if inner_text in config.Q_ABBREVIATIONS:
                    abbreviation_for_lookup = inner_text

            if abbreviation_for_lookup:
                full_meaning = config.Q_ABBREVIATIONS.get(abbreviation_for_lookup, "Unknown")
                if " also " in full_meaning:
                    meanings = full_meaning.split(" also ")
                    display_meaning = " / ".join(m.strip() for m in meanings)
                else:
                    display_meaning = full_meaning
                
                self.context_menu.add_command(label=f"{abbreviation_for_lookup}: {display_meaning}?", state=tk.DISABLED)
                self.context_menu.add_separator()
                abbreviation_meaning_displayed = True

        self.context_menu.add_command(label="Copy", command=self._copy_selection_to_clipboard, state=state)
        self.context_menu.add_separator()
        self.context_menu.add_command(
            label="Filter post list for selection",
            command=self._filter_for_selection,
            state=state
        )
        self.context_menu.add_separator()
        self.context_menu.add_command(
            label="Search Google Books for selection",
            command=lambda: self._search_selection_with('google_books'),
            state=state
        )
        self.context_menu.add_command(
            label="Search Internet Archive for selection",
            command=lambda: self._search_selection_with('internet_archive'),
            state=state
        )
        self.context_menu.add_command(
            label="Search on Gematrix.org for selection",
            command=lambda: self._search_selection_with('gematrix'),
            state=state
        )
        self.context_menu.add_separator()
        self.context_menu.add_command(
            label="Calculate Gematria of selection",
            command=lambda: self.show_gematria_calculator_window(self.post_text_area.get(tk.SEL_FIRST, tk.SEL_LAST).strip()),
            state=state
        )


    def _show_context_menu(self, event):
        # Prioritize existing selection if it exists
        try:
            # Check if there's an active selection before processing event coordinates
            if not self.post_text_area.tag_ranges(tk.SEL):
                # No active selection, try to select word or bracketed text under mouse
                index_at_mouse = self.post_text_area.index(f"@{event.x},{event.y}")
                word_start = self.post_text_area.index(f"{index_at_mouse} wordstart")
                word_end = self.post_text_area.index(f"{index_at_mouse} wordend")
                
                if word_start == word_end:
                    # Check if it's within a bracketed abbreviation like [ROTH]
                    line_content = self.post_text_area.get(f"{index_at_mouse} linestart", f"{index_at_mouse} lineend")
                    char_in_line = int(index_at_mouse.split('.')[-1])
                    
                    bracketed_match = re.search(r'\[([A-Z0-9/\-, ]+)\]', line_content)
                    if bracketed_match:
                        start_char_idx = bracketed_match.start(0)
                        end_char_idx = bracketed_match.end(0)
                        
                        if start_char_idx <= char_in_line <= end_char_idx:
                            line_num = index_at_mouse.split('.')[0]
                            word_start = f"{line_num}.{start_char_idx}"
                            word_end = f"{line_num}.{end_char_idx}"
                            self.post_text_area.tag_add(tk.SEL, word_start, word_end)
                else:
                    self.post_text_area.tag_add(tk.SEL, word_start, word_end)

            self._add_context_menu_options() # Populate menu based on selection
            self.context_menu.tk_popup(event.x_root, event.y_root)

        except tk.TclError:
            # If selection handling fails (e.g., no text under cursor), just show the menu
            self._add_context_menu_options()
            self.context_menu.tk_popup(event.x_root, event.y_root)

    def _copy_selection_to_clipboard(self):
        try:
            selected_text = self.post_text_area.get(tk.SEL_FIRST, tk.SEL_LAST)
            self.root.clipboard_clear()
            self.root.clipboard_append(selected_text)
        except tk.TclError:
            pass

    def _filter_for_selection(self):
        try:
            selected_text = self.post_text_area.get(tk.SEL_FIRST, tk.SEL_LAST).strip()
            if not selected_text:
                return
            self.keyword_entry.delete(0, tk.END)
            self.keyword_entry.insert(0, selected_text)
            self.search_by_keyword()
        except tk.TclError:
            pass
            
# --- END CONTEXT_MENU_METHODS ---

# --- START ON_CLOSING ---

    def on_closing(self):
        utils.save_bookmarks_to_file(self.bookmarked_posts, config.BOOKMARKS_FILE_PATH)
        utils.save_user_notes(self.user_notes, config.USER_NOTES_FILE_PATH)
        self.root.destroy()

# --- END ON_CLOSING ---

# --- START SEARCH_POST_BY_NUMBER ---

    def search_post_by_number(self):
        entry_widget = self.post_entry
        placeholder = config.PLACEHOLDER_POST_NUM
        search_input = entry_widget.get()

        if search_input == placeholder or not search_input.strip():
            messagebox.showwarning("Input", "Please enter a post number, range (e.g., 10-15), or list (e.g., 10,12,15).", parent=self.root)
            if not search_input.strip(): # If truly empty
                self.restore_placeholder(None, placeholder, entry_widget)
            return

        target_post_numbers = []
        search_term_str = f"Post(s) = '{search_input}'"
        is_jump_to_single = False

        try:
            if ',' in search_input:
                target_post_numbers = [int(p.strip()) for p in search_input.split(',')]
            elif '-' in search_input:
                parts = search_input.split('-')
                if len(parts) == 2:
                    start_num_str = parts[0].strip()
                    end_num_str = parts[1].strip()
                    if not start_num_str or not end_num_str: 
                        raise ValueError("Invalid range format - empty start or end.")
                    start_num, end_num = int(start_num_str), int(end_num_str)
                    if start_num <= end_num:
                        target_post_numbers = list(range(start_num, end_num + 1))
                    else:
                        messagebox.showerror("Input Error", "Start of range must be less than or equal to end.", parent=self.root)
# Clear entry and restore placeholder before returning if input was bad
                        if entry_widget.get() != placeholder:
                            entry_widget.delete(0, tk.END)
                            self.restore_placeholder(None, placeholder, entry_widget)
                        return
                else:
                    raise ValueError("Invalid range format - not two parts.")
            else:
                target_post_numbers = [int(search_input.strip())]
                is_jump_to_single = True

            if not target_post_numbers: # Safeguard
                messagebox.showerror("Input Error", "No valid post numbers to search.", parent=self.root)
                if entry_widget.get() != placeholder:
                    entry_widget.delete(0, tk.END)
                    self.restore_placeholder(None, placeholder, entry_widget)
                return

            if is_jump_to_single:
                post_to_find = target_post_numbers[0] #

                if self.current_search_active:
                    self.current_display_idx = -1 
                    self.df_displayed = self.df_all_posts.copy() #
                    self.current_search_active = False #
                    self.clear_search_button.config(state=tk.DISABLED) #
                    self.repopulate_treeview(self.df_displayed, select_first_item=True) #
                    self.root.update_idletasks() # Allow UI to update

                matching_posts = self.df_all_posts[self.df_all_posts['Post Number'] == post_to_find] #
                if not matching_posts.empty: #
                    original_df_idx_of_target = matching_posts.index[0]

                    if self.df_displayed is not None and original_df_idx_of_target in self.df_displayed.index:
                        target_display_idx_in_current_df = self.df_displayed.index.get_loc(original_df_idx_of_target)

                        self.current_display_idx = -1
                        
                        self.select_tree_item_by_idx(target_display_idx_in_current_df) #
                    else:
# This case would be unusual if df_displayed is correctly set to df_all_posts
                         messagebox.showinfo("Not Found", f"Post # {post_to_find} (Original Index {original_df_idx_of_target}) not found in current display view.", parent=self.root) #
                else:
                    messagebox.showinfo("Not Found", f"Post # {post_to_find} not found in all posts.", parent=self.root) #
            else: 
# This is for range or list search (e.g., "10-15" or "10,12,15")
                results = self.df_all_posts[self.df_all_posts['Post Number'].isin(target_post_numbers)]
# The fix for this path (setting self.current_display_idx = -1)
# should already be in your _handle_search_results method from my previous response.
                self._handle_search_results(results, search_term_str) #

        except ValueError: # Catches int conversion errors or custom ValueErrors
            messagebox.showerror("Input Error", "Invalid input. Please enter a number, a range (e.g., 10-15), or a comma-separated list. Ensure range parts are not empty.", parent=self.root)
        finally:
            current_entry_text = entry_widget.get()
            if current_entry_text != placeholder and current_entry_text.strip() != "":
                entry_widget.delete(0, tk.END)
                self.restore_placeholder(None, placeholder, entry_widget)
            elif not current_entry_text.strip() and current_entry_text != placeholder :
                self.restore_placeholder(None, placeholder, entry_widget)

# --- END SEARCH_POST_BY_NUMBER ---

# --- START KEYWORD_SEARCH_LOGIC ---

    def search_by_keyword(self):
        entry_widget = self.keyword_entry
        placeholder = config.PLACEHOLDER_KEYWORD
        keyword = entry_widget.get().strip()

        if not keyword or keyword == placeholder:
            messagebox.showwarning("Input",
                                   "Please enter a keyword or phrase to search.",
                                   parent=self.root)
            if not keyword: 
# If truly empty, restore placeholder
                self.restore_placeholder(None, placeholder, entry_widget)
            return

        keyword_lower = keyword.lower()
        
# Ensure df_all_posts is not None before trying to search
        if self.df_all_posts is None:
            messagebox.showerror("Data Error", "Post data is not loaded.", parent=self.root)
            return

        results = self.df_all_posts[
            (self.df_all_posts['Text'].str.lower().str.contains(keyword_lower, na=False, regex=False)) |
            (self.df_all_posts['Tripcode'].str.lower().str.contains(keyword_lower, na=False, regex=False)) # Themes search removed from here
        ]
        
        self._handle_search_results(results, f"Search = '{keyword}'") # Updated search term string
        
# Clear the entry and restore placeholder after search attempt
        entry_widget.delete(0, tk.END)
        self.restore_placeholder(None, placeholder, entry_widget)

# --- END KEYWORD_SEARCH_LOGIC ---

# --- START DATE_SEARCH_LOGIC ---

    def show_calendar(self):
        try:
            dialog_bg = self.style.lookup("TFrame", "background")
        except tk.TclError: # Fallback if style lookup fails
            dialog_bg = "#2b2b2b" if self.current_theme == "dark" else "#f0f0f0"

        top = tk.Toplevel(self.root)
        top.title("Select Date")
        top.configure(bg=dialog_bg)
        top.transient(self.root)
        top.grab_set()

        now = datetime.datetime.now()
        cal_y, cal_m, cal_d = now.year, now.month, now.day

        if self.df_displayed is not None and not self.df_displayed.empty and 0 <= self.current_display_idx < len(self.df_displayed): # Check df_displayed
            cur_post_dt = self.df_displayed.iloc[self.current_display_idx].get('Datetime_UTC')
            if pd.notna(cur_post_dt):
                cal_y, cal_m, cal_d = cur_post_dt.year, cur_post_dt.month, cur_post_dt.day
        
# Define calendar colors based on theme
        cal_fg = "#000000" if self.current_theme == "light" else "#e0e0e0"
        cal_bg = "#ffffff" if self.current_theme == "light" else "#3c3f41"
        cal_sel_bg = "#0078D7"  # Selection background can be consistent
        cal_sel_fg = "#ffffff"  # Selection foreground
        cal_hdr_bg = "#e1e1e1" if self.current_theme == "light" else "#4a4a4a" # Header/border
        cal_dis_bg = "#f0f0f0" if self.current_theme == "light" else "#2b2b2b" # Disabled days background
        cal_dis_fg = "grey" # Disabled days foreground

        cal = Calendar(top, selectmode="day", year=cal_y, month=cal_m, day=cal_d,
                       date_pattern='m/d/yy', font="Arial 9",
                       background=cal_hdr_bg, foreground=cal_fg, 
                       headersbackground=cal_hdr_bg, headersforeground=cal_fg, 
                       normalbackground=cal_bg, weekendbackground=cal_bg, 
                       normalforeground=cal_fg, weekendforeground=cal_fg, 
                       othermonthbackground=cal_dis_bg, othermonthwebackground=cal_dis_bg, 
                       othermonthforeground=cal_dis_fg, othermonthweforeground=cal_dis_fg,
                       selectbackground=cal_sel_bg, selectforeground=cal_sel_fg, 
                       bordercolor=cal_hdr_bg)
        cal.pack(padx=10, pady=10)

        def on_date_selected_from_calendar():
            selected_date_str = cal.get_date()
            top.destroy() # Close the calendar window
            self._search_by_date_str(selected_date_str) # Process the selected date

        ttk.Button(top, text="Select Date", command=on_date_selected_from_calendar).pack(pady=5)

    def _search_by_date_str(self, date_str_from_cal):
        try:
            target_date = pd.to_datetime(date_str_from_cal, format='%m/%d/%y').date()
            if self.df_all_posts is None: # Ensure df_all_posts is loaded
                messagebox.showerror("Error", "Post data not loaded.", parent=self.root)
                return
            results = self.df_all_posts[self.df_all_posts['Datetime_UTC'].dt.date == target_date]
            self._handle_search_results(results, f"Date = {target_date.strftime('%Y-%m-%d')}")
        except Exception as e:
            messagebox.showerror("Error", f"Date selection error: {e}", parent=self.root)

# --- END DATE_SEARCH_LOGIC ---


# --- START DELTA_SEARCH_LOGIC ---

    def show_day_delta_dialog(self):
        try:
            dialog_bg = self.style.lookup("TFrame", "background")
        except tk.TclError: 
            dialog_bg = "#2b2b2b" if self.current_theme == "dark" else "#f0f0f0"

        top = tk.Toplevel(self.root)
        top.title("Select Month and Day for Delta Search")
        top.configure(bg=dialog_bg)
        top.transient(self.root)
        top.grab_set()

        dialog_width = 250
        dialog_height = 160 
        root_x = self.root.winfo_x()
        root_y = self.root.winfo_y()
        root_width = self.root.winfo_width()
        root_height = self.root.winfo_height()
        x = root_x + (root_width // 2) - (dialog_width // 2)
        y = root_y + (root_height // 2) - (dialog_height // 2)
        top.geometry(f'{dialog_width}x{dialog_height}+{x}+{y}')

        ttk.Label(top, text="Month:").pack(pady=(10,2))
        month_var = tk.StringVar()
        months = ["January", "February", "March", "April", "May", "June", 
                  "July", "August", "September", "October", "November", "December"]
        month_cb = ttk.Combobox(top, textvariable=month_var, values=months, state="readonly", width=18)
        month_cb.pack()
        month_cb.set(datetime.datetime.now().strftime("%B")) 

        ttk.Label(top, text="Day:").pack(pady=(5,2))
        day_var = tk.StringVar()
        days = [str(d) for d in range(1, 32)]
        day_cb = ttk.Combobox(top, textvariable=day_var, values=days, state="readonly", width=5)
        day_cb.pack()
        day_cb.set(str(datetime.datetime.now().day)) 

        def on_search():
            try:
                month_num = months.index(month_var.get()) + 1
                day_num = int(day_var.get())
                
                if month_num == 2 and day_num > 29: 
                    messagebox.showerror("Invalid Date", "February cannot have more than 29 days for this search.", parent=top)
                    return
                elif month_num in [4, 6, 9, 11] and day_num > 30:
                    messagebox.showerror("Invalid Date", f"{month_var.get()} cannot have more than 30 days.", parent=top)
                    return
                elif day_num > 31 or day_num < 1 : 
                     messagebox.showerror("Invalid Date", "Day must be between 1 and 31.", parent=top)
                     return

                top.destroy()
                self._search_by_month_day(month_num, day_num)
            except ValueError:
                messagebox.showerror("Input Error", "Please select a valid month and day.", parent=top)
            except Exception as e:
                messagebox.showerror("Error", f"An error occurred: {e}", parent=top)

        search_button = ttk.Button(top, text="Search Deltas", command=on_search)
        search_button.pack(pady=10)

    def _search_by_month_day(self, month, day):
        if self.df_all_posts is None or 'Datetime_UTC' not in self.df_all_posts.columns:
            messagebox.showerror("Error", "Post data or 'Datetime_UTC' column not available.", parent=self.root)
            return
        
        if not pd.api.types.is_datetime64_any_dtype(self.df_all_posts['Datetime_UTC']):
             self.df_all_posts['Datetime_UTC'] = pd.to_datetime(self.df_all_posts['Datetime_UTC'], errors='coerce')
             if self.df_all_posts['Datetime_UTC'].isna().any(): 
                 messagebox.showwarning("Data Warning", "Some dates could not be parsed. Results might be incomplete.", parent=self.root)

        try:
            valid_dates_df = self.df_all_posts.dropna(subset=['Datetime_UTC'])
            results = valid_dates_df[
                (valid_dates_df['Datetime_UTC'].dt.month == month) &
                (valid_dates_df['Datetime_UTC'].dt.day == day)
            ]
            month_name = datetime.date(1900, month, 1).strftime('%B')
            self._handle_search_results(results, f"Posts from {month_name} {day} (All Years)")
        except Exception as e:
            messagebox.showerror("Search Error", f"An error occurred during delta search: {e}", parent=self.root)

    def search_today_deltas(self):
        today = datetime.datetime.now()
        self._search_by_month_day(today.month, today.day)

# --- END DELTA_SEARCH_LOGIC ---

# --- START THEME_SEARCH_LOGIC ---

    def show_theme_selection_dialog(self):
        if self.df_all_posts is None or self.df_all_posts.empty:
            messagebox.showwarning("No Data", "No post data loaded to search themes.", parent=self.root)
            return

        try:
            dialog_bg = self.style.lookup("TFrame", "background")
            listbox_bg = self.style.lookup("Treeview", "fieldbackground")
            listbox_fg = self.style.lookup("Treeview", "foreground")
            select_bg = self.style.lookup("Treeview", "selectbackground")
            select_fg = self.style.lookup("Treeview", "selectforeground")
        except tk.TclError: # Fallback colors
            dialog_bg = "#2b2b2b" if self.current_theme == "dark" else "#f0f0f0"
            listbox_bg = "#3c3f41" if self.current_theme == "dark" else "#ffffff"
            listbox_fg = "#e0e0e0" if self.current_theme == "dark" else "#000000"
            select_bg = "#0078D7"
            select_fg = "#ffffff"

        theme_dialog = tk.Toplevel(self.root)
        theme_dialog.title("Select Themes to Search")
        theme_dialog.configure(bg=dialog_bg)
        theme_dialog.geometry("400x450")
        theme_dialog.transient(self.root)
        theme_dialog.grab_set()

        main_frame = ttk.Frame(theme_dialog, padding="10")
        main_frame.pack(expand=True, fill=tk.BOTH)

        # Instructions Label
        ttk.Label(main_frame, text="Select one or more themes:", wraplength=350).pack(pady=(0, 5), anchor="w")

        # Listbox for themes
        listbox_frame = ttk.Frame(main_frame)
        listbox_frame.pack(expand=True, fill=tk.BOTH, pady=(5, 10))

        theme_listbox = tk.Listbox(listbox_frame, selectmode=tk.MULTIPLE,
                                   bg=listbox_bg, fg=listbox_fg,
                                   selectbackground=select_bg, selectforeground=select_fg,
                                   exportselection=False, # Important for multiple listboxes
                                   font=('Arial', 10), relief=tk.SOLID, borderwidth=1)
        
        listbox_scrollbar = ttk.Scrollbar(listbox_frame, orient="vertical", command=theme_listbox.yview)
        theme_listbox.config(yscrollcommand=listbox_scrollbar.set)
        
        theme_listbox.pack(side="left", fill="both", expand=True)
        listbox_scrollbar.pack(side="right", fill="y")

        # Populate listbox with human-readable theme names
        # Sort them alphabetically for consistent display
        display_theme_names = sorted([
            " ".join(word.capitalize() for word in theme_key.split('_'))
            for theme_key in config.THEMES.keys()
        ])
        for theme_name in display_theme_names:
            theme_listbox.insert(tk.END, theme_name)

        def perform_theme_search():
            selected_display_indices = theme_listbox.curselection()
            selected_themes_display = [theme_listbox.get(i) for i in selected_display_indices]
            
            if not selected_themes_display:
                messagebox.showwarning("No Selection", "Please select at least one theme.", parent=theme_dialog)
                return

            # Convert display names back to original theme keys for searching
            selected_theme_keys = []
            for display_name in selected_themes_display:
                # Find the original key by reversing the capitalization process
                original_key = "_".join(word.lower() for word in display_name.split(' '))
                if original_key in config.THEMES: # Sanity check
                    selected_theme_keys.append(original_key)
            
            if not selected_theme_keys:
                messagebox.showerror("Error", "Could not map selected themes to internal keys.", parent=theme_dialog)
                return

            theme_dialog.destroy() # Close the selection dialog

            # Perform the actual search in the DataFrame
            # Filter posts where the 'Themes' list contains ANY of the selected theme keys
            results = self.df_all_posts[
                self.df_all_posts['Themes'].apply(
                    lambda themes: any(t_key in themes for t_key in selected_theme_keys) if isinstance(themes, list) else False
                )
            ]
            
            search_term_str = f"Themes = '{', '.join(selected_themes_display)}'"
            self._handle_search_results(results, search_term_str)

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))

        ttk.Button(button_frame, text="Search", command=perform_theme_search).pack(side=tk.LEFT, expand=True, padx=(0, 5))
        ttk.Button(button_frame, text="Cancel", command=theme_dialog.destroy).pack(side=tk.LEFT, expand=True)

# --- END THEME_SEARCH_LOGIC ---

# --- START CLEAR_SEARCH_AND_SHOW_ALL ---

    def clear_search_and_show_all(self):
        if self.df_all_posts is None or self.df_all_posts.empty:
            self.show_welcome_message() # Handles empty df_all_posts
            return

        self.df_displayed = self.df_all_posts.copy()
        self.current_search_active = False
        self.clear_search_button.config(state=tk.DISABLED)
        self.current_display_idx = -1
        self.repopulate_treeview(self.df_displayed, select_first_item=True) # Select first post
        
# update_display is called via on_tree_select if selection happens in repopulate_treeview
        if self.df_displayed.empty: 
# Should not happen if df_all_posts is not empty
             self.show_welcome_message()
# If no item was selected for some reason (e.g. tree is empty after repopulation), ensure correct state:
        elif self.post_tree.selection() == (): 
# If nothing ended up selected after repopulate
             self.show_welcome_message()
# Else, if a selection was made by repopulate_treeview, update_display would have been called.
# If current_display_idx is somehow valid but no selection, explicitly update.
        elif self.df_displayed is not None and not self.df_displayed.empty and \
             0 <= self.current_display_idx < len(self.df_displayed) and not self.post_tree.selection():
             self.update_display()

# --- END CLEAR_SEARCH_AND_SHOW_ALL ---

# --- START PREV_POST ---

    def prev_post(self):
        if self.df_displayed is None or self.df_displayed.empty: return
        num_items = len(self.df_displayed)
        if num_items == 0: return
        if num_items == 1 and self.current_display_idx == 0: return 

        target_display_idx = self.current_display_idx 
        if target_display_idx == -1 : 
            target_display_idx = num_items - 1 
        else:
            target_display_idx = (self.current_display_idx - 1 + num_items) % num_items
        
        self.select_tree_item_by_idx(target_display_idx)

# --- END PREV_POST ---

# --- START NEXT_POST ---

    def next_post(self):
        if self.df_displayed is None or self.df_displayed.empty: return
        num_items = len(self.df_displayed)
        if num_items == 0: return
        if num_items == 1 and self.current_display_idx == 0: return

        target_display_idx = self.current_display_idx
        if target_display_idx == -1 : 
            target_display_idx = 0 
        else:
            target_display_idx = (self.current_display_idx + 1) % num_items
            
        self.select_tree_item_by_idx(target_display_idx)

# --- END NEXT_POST ---

# --- START SHOW_POST_LINKS_WINDOW_EXTERNAL ---

    def show_post_links_window_external(self):
        if not self.current_post_urls:
            messagebox.showinfo("Links", "No URLs found in the current post.", parent=self.root)
            return

        display_urls = self.current_post_urls # No more filtering

        try:
            popup_bg = self.style.lookup("TFrame", "background")
            canvas_bg = self.style.lookup("Treeview", "fieldbackground")
            link_label_fg = self.link_label_fg_dark if self.current_theme == "dark" else self.link_label_fg_light
        except tk.TclError:
            popup_bg = "#2b2b2b" if self.current_theme == "dark" else "#f0f0f0"
            canvas_bg = "#3c3f41" if self.current_theme == "dark" else "#ffffff"
            link_label_fg = self.link_label_fg_dark if self.current_theme == "dark" else self.link_label_fg_light

        link_window = tk.Toplevel(self.root)
        link_window.title("Post URLs")
        link_window.configure(bg=popup_bg)
        link_window.geometry("600x400")
        link_window.transient(self.root)
        link_window.grab_set()

        canvas = tk.Canvas(link_window, bg=canvas_bg, highlightthickness=0)
        scrollbar = ttk.Scrollbar(link_window, orient="vertical", command=canvas.yview)

        scrollable_frame = ttk.Frame(canvas, style="TFrame")

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(
                scrollregion=canvas.bbox("all")
            )
        )
        canvas_window = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        scrollbar.pack(side="right", fill="y")

        for url in display_urls:
            def open_url_action_factory(u=url): # Factory to capture current 'u'
                return lambda e: utils.open_link_with_preference(u, self.app_settings)

            link_label = ttk.Label(scrollable_frame, text=url, cursor="hand2", style="TLabel")
            link_label.configure(font=("TkDefaultFont", 10, "underline"), foreground=link_label_fg)
            link_label.pack(anchor="w", padx=10, pady=3)
            link_label.bind("<Button-1>", open_url_action_factory(url))

        def frame_width(event): # Make canvas window resizable with the canvas itself
            canvas_width = event.width
            canvas.itemconfig(canvas_window, width = canvas_width)
        canvas.bind("<Configure>", frame_width)

# --- END SHOW_POST_LINKS_WINDOW_EXTERNAL ---

# --- START BOOKMARKING_LOGIC ---

    def toggle_current_post_bookmark(self):
        if self.df_displayed is None or self.df_displayed.empty or self.current_display_idx < 0: 
            messagebox.showwarning("Bookmark", "No post selected to bookmark/unbookmark.", parent=self.root) 
            return
        
# Get the original DataFrame index of the currently displayed post
        original_df_index_of_current_post = self.df_displayed.index[self.current_display_idx] 

        post_series = self.df_all_posts.loc[original_df_index_of_current_post] 
        post_num_df = post_series.get('Post Number', original_df_index_of_current_post) 
        post_id_str = f"#{post_num_df}" if pd.notna(post_num_df) else f"(Index: {original_df_index_of_current_post})" #
        
        if original_df_index_of_current_post in self.bookmarked_posts: 
            self.bookmarked_posts.remove(original_df_index_of_current_post) 
            messagebox.showinfo("Bookmark", f"Q Drop {post_id_str} unbookmarked.", parent=self.root) 
        else:
            self.bookmarked_posts.add(original_df_index_of_current_post) 
            messagebox.showinfo("Bookmark", f"Q Drop {post_id_str} bookmarked!", parent=self.root) 
        
        self.update_bookmark_button_status() # Updates button text
        
        self.update_display() 

# Repopulate tree to update the '★' column, but DO NOT auto-select the first item.
        self.repopulate_treeview(self.df_displayed, select_first_item=False) 
        
# Re-select the item that was just bookmarked/unbookmarked.
# Its positional index (self.current_display_idx) within self.df_displayed has not changed.
# The iid for the treeview is the original_df_index_of_current_post.
        iid_to_reselect = str(original_df_index_of_current_post)
        if self.post_tree.exists(iid_to_reselect): 
            self.post_tree.selection_set(iid_to_reselect) 
            self.post_tree.focus(iid_to_reselect) 
            self.post_tree.see(iid_to_reselect) 
# Note: self.post_tree.selection_set() will trigger on_tree_select.
# Since new_display_idx will equal self.current_display_idx, and welcome_was_showing is false,
# on_tree_select will NOT call update_display() again, which is correct as we just called it.
        
        self.view_bookmarks_button.config(text=f"View Bookmarks ({len(self.bookmarked_posts)})") 

    def update_bookmark_button_status(self, is_welcome=False): # Added is_welcome
        if is_welcome or self.df_displayed is None or self.df_displayed.empty or self.current_display_idx < 0:
            self.bookmark_button.config(text="Bookmark Post", state=tk.DISABLED)
            return
        self.bookmark_button.config(state=tk.NORMAL)
        original_df_index = self.df_displayed.index[self.current_display_idx]
        self.bookmark_button.config(text="Unbookmark This Post" if original_df_index in self.bookmarked_posts else "Bookmark This Post")


    # --- START UPDATE_CONTEXT_BUTTON_STATE ---
    def _update_context_button_state(self):
        if hasattr(self, 'view_context_button'):
            if self.df_displayed is not None and not self.df_displayed.empty and 0 <= self.current_display_idx < len(self.df_displayed):
                original_df_index = self.df_displayed.index[self.current_display_idx]
                current_post_num = self.df_all_posts.loc[original_df_index].get('Post Number')
                if pd.notna(current_post_num):
                    self.view_context_button.config(state=tk.NORMAL)
                else:
                    self.view_context_button.config(state=tk.DISABLED)
            else:
                self.view_context_button.config(state=tk.DISABLED)
    # --- END UPDATE_CONTEXT_BUTTON_STATE ---

    def view_bookmarked_gui_posts(self):
        if not self.bookmarked_posts:
            messagebox.showinfo("Bookmarks", "No posts bookmarked yet.", parent=self.root)
            return
        valid_bookmarked_indices = [idx for idx in self.bookmarked_posts if idx in self.df_all_posts.index]
        if not valid_bookmarked_indices:
            messagebox.showwarning("Bookmarks", "Bookmarked posts not found in current data.", parent=self.root)
            self.df_displayed = pd.DataFrame(columns=self.df_all_posts.columns if self.df_all_posts is not None else [])
            self.repopulate_treeview(self.df_displayed, select_first_item=False)
            self.show_welcome_message()
            return
        
        results_df = self.df_all_posts.loc[list(valid_bookmarked_indices)].copy()
        if 'Datetime_UTC' in results_df.columns:
            results_df.sort_values(by='Datetime_UTC', inplace=True) 
        self._handle_search_results(results_df, "Bookmarked Posts")

# --- END BOOKMARKING_LOGIC ---

# --- START USER_NOTES_METHODS ---

    def show_note_popup(self):
        if self.df_displayed is None or self.df_displayed.empty or not (0 <= self.current_display_idx < len(self.df_displayed)):
            messagebox.showwarning("No Post Selected", "Please select a post to view or edit its note.", parent=self.root)
            return

        original_df_index = str(self.df_displayed.index[self.current_display_idx])
        
        # Retrieve current note content and show_tooltip preference
        note_data = self.user_notes.get(original_df_index, {"content": "", "show_tooltip": True})
        current_note_content = note_data["content"]
        current_show_tooltip = note_data["show_tooltip"]

        note_popup = tk.Toplevel(self.root)
        note_popup.title(f"Note for Post (Index: {original_df_index})")
        note_popup.geometry("500x400")
        note_popup.transient(self.root)
        note_popup.grab_set()

        try:
            dialog_bg = self.style.lookup("TFrame", "background")
            text_bg = self.style.lookup("TEntry", "fieldbackground")
            text_fg = self.style.lookup("TEntry", "foreground")
        except tk.TclError: # Fallback colors
            dialog_bg = "#f0f0f0" if self.current_theme == "light" else "#2b2b2b"
            text_bg = "#ffffff" if self.current_theme == "light" else "#3c3f41"
            text_fg = "#000000" if self.current_theme == "light" else "#e0e0e0"
        
        note_popup.configure(bg=dialog_bg)

        popup_main_frame = ttk.Frame(note_popup, padding=10)
        popup_main_frame.pack(expand=True, fill=tk.BOTH)

        note_text_widget = tk.Text(popup_main_frame, wrap=tk.WORD, height=15, font=("TkDefaultFont", 10), relief=tk.SOLID, borderwidth=1, padx=5, pady=5)
        note_text_widget.configure(bg=text_bg, fg=text_fg, insertbackground=text_fg)
        note_text_widget.pack(expand=True, fill=tk.BOTH, pady=(0,10))
        note_text_widget.insert(tk.END, current_note_content)
        note_text_widget.focus_set()

        # Enable standard Tkinter text widget context menu (cut/copy/paste)
        # This makes the default right-click menu available.
        note_text_widget.bind("<Button-3>", utils._show_text_widget_context_menu) # Changed bind_class to bind
        note_text_widget.bind("<Control-v>", lambda e: note_text_widget.event_generate("<<Paste>>"))


        # Checkbox for Tooltip
        show_tooltip_var = tk.BooleanVar(value=current_show_tooltip)
        ttk.Checkbutton(popup_main_frame, text="Show this note as a tooltip in Treeview", variable=show_tooltip_var).pack(anchor="w", pady=(0, 5))

        button_frame = ttk.Frame(popup_main_frame)
        button_frame.pack(fill=tk.X)

        def save_and_close():
            note_content = note_text_widget.get(1.0, tk.END).strip()
            tooltip_enabled = show_tooltip_var.get()
            
            if note_content:
                self.user_notes[original_df_index] = {"content": note_content, "show_tooltip": tooltip_enabled}
            elif original_df_index in self.user_notes: # If content is empty, remove note
                del self.user_notes[original_df_index]
            
            utils.save_user_notes(self.user_notes, config.USER_NOTES_FILE_PATH) # Save immediately
            print(f"Note for post index {original_df_index} saved. Tooltip enabled: {tooltip_enabled}")
            
            # Refresh treeview to update '♪' icon and potentially tooltips
            self.repopulate_treeview(self.df_displayed, select_first_item=False) 
            self.select_tree_item_by_idx(self.current_display_idx) # Reselect current post
            note_popup.destroy()

        def cancel_and_close():
            note_popup.destroy()

        save_button = ttk.Button(button_frame, text="Save Note", command=save_and_close)
        save_button.pack(side=tk.RIGHT, padx=5)
        cancel_button = ttk.Button(button_frame, text="Cancel", command=cancel_and_close)
        cancel_button.pack(side=tk.RIGHT)

        note_popup.protocol("WM_DELETE_WINDOW", cancel_and_close)

# --- END USER_NOTES_METHODS ---

# --- START TREEVIEW_MOTION_LEAVE_FOR_TOOLTIP ---

    def _on_treeview_motion_for_tooltip(self, event):
        """Handle mouse motion over treeview to show/hide note tooltips."""
        # Hide any existing tooltip first
        self.treeview_note_tooltip.hidetip()

        # Get the item (row) under the mouse
        item = self.post_tree.identify_row(event.y)

        # Check if an item (row) is identified
        if item:
            original_df_index = item # Treeview iid is the original DataFrame index
            note_data = self.user_notes.get(original_df_index)

            # Check if there's note data, if tooltip is enabled, and if content exists
            if note_data and note_data.get("show_tooltip", True) and note_data.get("content", "").strip():
                # Store enough info to retrieve the content later
                self.treeview_note_tooltip.text_generator = \
                    lambda idx=original_df_index: self.user_notes.get(idx, {}).get("content", "").strip()
                self.treeview_note_tooltip.schedule() # Show tooltip
            else:
                self.treeview_note_tooltip.unschedule() # Hide if no valid note/tooltip disabled
        else:
            self.treeview_note_tooltip.unschedule() # Not over any item

    def _on_treeview_leave_for_tooltip(self, event):
        """Handle mouse leaving treeview to hide note tooltips."""
        self.treeview_note_tooltip.unschedule()
        self.treeview_note_tooltip.hidetip()

    def _get_note_tooltip_text(self):
        # This is a placeholder; the text_generator is updated in _on_treeview_motion_for_tooltip
        # when a specific item is identified.
        return "" 
# --- END TREEVIEW_MOTION_LEAVE_FOR_TOOLTIP ---

# --- START TREEVIEW_MOTION_LEAVE_FOR_TOOLTIP ---

    def _on_treeview_motion_for_tooltip(self, event):
        """Handle mouse motion over treeview to show/hide note tooltips."""
        # Hide any existing tooltip first
        self.treeview_note_tooltip.hidetip()

        # Get the item (row) under the mouse
        item = self.post_tree.identify_row(event.y)

        # Check if an item (row) is identified
        if item:
            original_df_index = item # Treeview iid is the original DataFrame index
            note_data = self.user_notes.get(original_df_index)

            # Check if there's note data, if tooltip is enabled, and if content exists
            if note_data and note_data.get("show_tooltip", True) and note_data.get("content", "").strip():
                # Store enough info to retrieve the content later
                self.treeview_note_tooltip.text_generator = \
                    lambda idx=original_df_index: self.user_notes.get(idx, {}).get("content", "").strip()
                self.treeview_note_tooltip.schedule() # Show tooltip
            else:
                self.treeview_note_tooltip.unschedule() # Hide if no valid note/tooltip disabled
        else:
            self.treeview_note_tooltip.unschedule() # Not over any item

    def _on_treeview_leave_for_tooltip(self, event):
        """Handle mouse leaving treeview to hide note tooltips."""
        self.treeview_note_tooltip.unschedule()
        self.treeview_note_tooltip.hidetip()

    def _get_note_tooltip_text(self):
        # This is a placeholder; the text_generator is updated in _on_treeview_motion_for_tooltip
        # when a specific item is identified.
        return "" 
# --- END TREEVIEW_MOTION_LEAVE_FOR_TOOLTIP ---

# --- START EXPORT_DISPLAYED_LIST ---

    def export_displayed_list(self, file_format=""): # file_format arg added
        if self.df_displayed is None or self.df_displayed.empty:
            messagebox.showwarning("Export", "No posts to export.", parent=self.root)
            return
        
# --- MODIFIED: Use file_format from menu, or prompt if called directly without format ---
        if not file_format: 
# If called without a specific format (e.g., old direct call)
# This path should ideally not be hit with the new menu button
            export_format = self.export_var.get() 
# Fallback to old OptionMenu var
        else:
            export_format = file_format
        
        default_fname = f"q_export_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        if export_format == "HTML":
            file_types = [("HTML files", "*.html"), ("All files", "*.*")]
            initial_ext = ".html"
        elif export_format == "CSV":
            file_types = [("CSV files", "*.csv"), ("All files", "*.*")]
            initial_ext = ".csv"
        else: # Should not happen with the menu
            messagebox.showerror("Export Error", "Invalid export format selected.", parent=self.root)
            return

        final_filename = filedialog.asksaveasfilename(
            parent=self.root,
            initialdir=os.getcwd(), # Or config.USER_DATA_ROOT for a default save location
            title=f"Save {export_format}",
            defaultextension=initial_ext,
            filetypes=file_types,
            initialfile=default_fname
        )

        if not final_filename:  # User cancelled
            return
        
# Ensure df_displayed is used, not df_all_posts by mistake
        df_exp = self.df_displayed.copy()
        
# Use only the columns defined in config.EXPORT_COLUMNS that exist in df_exp
        cols_to_use = [c for c in config.EXPORT_COLUMNS if c in df_exp.columns]
        if not cols_to_use:
            messagebox.showerror("Export Error", "No valid columns found for export. Check EXPORT_COLUMNS in config.", parent=self.root)
            return
        
        df_for_export = df_exp[cols_to_use]

        try:
            if final_filename.endswith(".csv"):
                df_csv = df_for_export.copy()
# Convert list columns to strings for CSV
                if 'Themes' in df_csv.columns:
                    df_csv['Themes'] = df_csv['Themes'].apply(lambda x: ', '.join(x) if isinstance(x, list) else str(x))
                if 'ImagesJSON' in df_csv.columns: # Example if you export complex data
                    df_csv['ImagesJSON'] = df_csv['ImagesJSON'].apply(lambda x: str(x) if isinstance(x, list) else "")
# Ensure Referenced Posts Display is string
                if 'Referenced Posts Display' in df_csv.columns:
                    df_csv['Referenced Posts Display'] = df_csv['Referenced Posts Display'].astype(str)

                df_csv.to_csv(final_filename, index=False, encoding='utf-8-sig')
                messagebox.showinfo("Success", f"Exported {len(df_for_export)} posts to {final_filename}", parent=self.root)
            
            elif final_filename.endswith(".html"):
                import html # Ensure html module is available
                df_html = df_for_export.copy()
                
# Apply HTML formatting for specific columns
                if 'Link' in df_html.columns:
                    df_html['Link'] = df_html['Link'].apply(
                        lambda x: f'<a href="{html.escape(x, quote=True)}" target="_blank">{html.escape(x)}</a>' if pd.notna(x) and x else ""
                    )
                if 'Text' in df_html.columns:
                    df_html['Text'] = df_html['Text'].apply(utils.format_cell_text_for_gui_html) # Assumes this util handles HTML line breaks
                
                if 'Themes' in df_html.columns:
                    df_html['Themes'] = df_html['Themes'].apply(
                        lambda x: html.escape(', '.join(x)) if isinstance(x, list) else html.escape(str(x))
                    )
                if 'Referenced Posts Display' in df_html.columns:
                     df_html['Referenced Posts Display'] = df_html['Referenced Posts Display'].astype(str).apply(lambda x: x.replace('\n', '<br />\n'))
                
                if 'Datetime_UTC' in df_html.columns and pd.api.types.is_datetime64_any_dtype(df_html['Datetime_UTC']):
                    df_html['Datetime_UTC'] = df_html['Datetime_UTC'].dt.strftime('%Y-%m-%d %H:%M:%S %Z')
                
                if 'ImagesJSON' in df_html.columns: # Example if you export complex data
                     df_html['ImagesJSON'] = df_html['ImagesJSON'].apply(lambda x: html.escape(str(x)) if isinstance(x, list) else "")

                html_table = df_html.to_html(escape=False, index=False, border=0, classes='qposts_table', na_rep="")
                css = """<style>body{font-family:Arial,sans-serif;margin:20px;background-color:#f4f4f4;color:#333}h1{color:#333;text-align:center}.qposts_table{border-collapse:collapse;width:95%;margin:20px auto;background-color:#fff;box-shadow:0 0 10px rgba(0,0,0,.1)}.qposts_table th,.qposts_table td{border:1px solid #ddd;padding:10px;text-align:left;vertical-align:top}.qposts_table th{background-color:#4CAF50;color:#fff}.qposts_table tr:nth-child(even){background-color:#f9f9f9}.qposts_table tr:hover{background-color:#e2f0e8}.qposts_table td a{color:#007bff;text-decoration:none}.qposts_table td a:hover{text-decoration:underline}.qposts_table td{word-wrap:break-word;max-width:600px;min-width:100px;}</style>"""
                html_full = f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><title>Q Posts GUI Export</title>{css}</head><body><h1>Q Posts Export</h1>{html_table}</body></html>""" # Changed html_full_table to html_table

                with open(final_filename, 'w', encoding='utf-8') as f:
                    f.write(html_full)
                messagebox.showinfo("Success", f"Exported {len(df_for_export)} posts to {final_filename}", parent=self.root)
                
                try: # Try to open the exported HTML file
                    webbrowser.open_new_tab(f"file://{os.path.realpath(final_filename)}")
                except Exception as e:
                    print(f"Could not auto-open HTML: {e}")
            else:
                messagebox.showerror("Error", "Unsupported file extension. Please use .csv or .html.", parent=self.root)
        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to export: {e}", parent=self.root)
            import traceback
            traceback.print_exc()

# --- END EXPORT_DISPLAYED_LIST ---

# --- START DOWNLOAD_WINDOW_AND_THREADING ---

    def show_download_window(self):
        if hasattr(self, 'download_win') and self.download_win is not None and self.download_win.winfo_exists():
            self.download_win.lift()
            self.download_win.focus_set()
            return

        self.download_win = tk.Toplevel(self.root)
        self.download_win.title("Download Offline Content")

        try: 
            dialog_bg = self.style.lookup("TFrame", "background")
        except tk.TclError: 
            dialog_bg = "#2b2b2b" if self.current_theme == "dark" else "#f0f0f0"
        self.download_win.configure(bg=dialog_bg)

        self.download_win.geometry("450x560") # Increased height to fit all 3 sections
        self.download_win.transient(self.root)
        self.download_win.grab_set()
# RESIZABLE Download Window
        self.download_win.resizable(False, False)

        main_frame = ttk.Frame(self.download_win, padding="15")
        main_frame.pack(expand=True, fill=tk.BOTH)

# --- Main Images Section ---
        img_frame = ttk.Labelframe(main_frame, text="Main Post Images", padding="10")
        img_frame.pack(fill="x", pady=5)
        ttk.Label(img_frame, text="Downloads all primary image attachments.", wraplength=380, justify=tk.LEFT).pack(anchor='w', padx=5, pady=(0, 5))
        self.download_images_button = ttk.Button(img_frame, text="Start Main Image Download", command=lambda: self._start_download_thread("images"))
        self.download_images_button.pack(pady=(5, 5), fill='x')
        self.main_images_progress = ttk.Progressbar(img_frame, orient='horizontal', mode='determinate', length=380, style="Contrasting.Horizontal.TProgressbar")
        self.main_images_progress.pack(pady=(0, 5), fill='x', expand=True)

# --- Quoted Images Section ---
        quoted_img_frame = ttk.Labelframe(main_frame, text="Quoted Post Images", padding="10")
        quoted_img_frame.pack(fill="x", pady=5)
        ttk.Label(quoted_img_frame, text="Downloads images found within quoted content.", wraplength=380, justify=tk.LEFT).pack(anchor='w', padx=5, pady=(0, 5))
        self.download_quoted_images_button = ttk.Button(quoted_img_frame, text="Start Quoted Image Download", command=lambda: self._start_download_thread("quoted_images"))
        self.download_quoted_images_button.pack(pady=(5, 5), fill='x')
        self.quoted_images_progress = ttk.Progressbar(quoted_img_frame, orient='horizontal', mode='determinate', length=380, style="Contrasting.Horizontal.TProgressbar")
        self.quoted_images_progress.pack(pady=(0, 5), fill='x', expand=True)
        
# --- Articles Section ---
        articles_frame = ttk.Labelframe(main_frame, text="Linked Articles", padding="10")
        articles_frame.pack(fill="x", pady=5)
        ttk.Label(articles_frame, text="Downloads HTML from external links in posts.", wraplength=380, justify=tk.LEFT).pack(anchor='w', padx=5, pady=(0, 5))
        self.download_articles_button = ttk.Button(articles_frame, text="Start Article Download", command=lambda: self._start_download_thread("articles"))
        self.download_articles_button.pack(pady=(5, 5), fill='x')
        self.articles_progress = ttk.Progressbar(articles_frame, orient='horizontal', mode='determinate', length=380, style="Contrasting.Horizontal.TProgressbar")
        self.articles_progress.pack(pady=(0, 5), fill='x', expand=True)

# --- General Status and Close Button ---
        self.download_status_label = ttk.Label(main_frame, text="Idle.", wraplength=380, justify=tk.LEFT)
        self.download_status_label.pack(pady=(10,5), anchor='w')
        ttk.Button(main_frame, text="Close", command=self.download_win.destroy).pack(side="bottom", pady=10)

    def _update_download_status(self, message):
        if hasattr(self, 'download_status_label') and self.download_status_label.winfo_exists():
            self.download_status_label.config(text=message)
        else:
            print(f"Download Status: {message}")

    def _update_download_progress(self, bar_widget, current_value, total_value):
        """Updates the specified download progress bar."""
        if bar_widget and bar_widget.winfo_exists():
            if total_value > 0:
                percent = (current_value / total_value) * 100
                bar_widget['value'] = percent
                self.download_win.update_idletasks()
            else:
                bar_widget['value'] = 0
    
    def _execute_download_task(self, task_name):
        buttons_to_disable = []
        if hasattr(self, 'download_win') and self.download_win.winfo_exists():
            if hasattr(self, 'download_images_button'): buttons_to_disable.append(self.download_images_button)
            if hasattr(self, 'download_articles_button'): buttons_to_disable.append(self.download_articles_button)
            if hasattr(self, 'download_quoted_images_button'): buttons_to_disable.append(self.download_quoted_images_button)

        try:
            for btn in buttons_to_disable:
                self.root.after(0, lambda b=btn: b.config(state=tk.DISABLED))

            progress_bar_widget = None
            if task_name == "images":
                progress_bar_widget = self.main_images_progress
            elif task_name == "quoted_images":
                progress_bar_widget = self.quoted_images_progress
            elif task_name == "articles":
                progress_bar_widget = self.articles_progress
            
            if progress_bar_widget:
                self.root.after(0, lambda: self._update_download_progress(progress_bar_widget, 0, 1))

            status_cb = lambda msg: self.root.after(0, lambda m=msg: self._update_download_status(m))
            progress_cb = lambda cur, tot, bar=progress_bar_widget: self.root.after(0, lambda c=cur, t=tot, b=bar: self._update_download_progress(b, c, t))

            if task_name == "images":
                utils.download_all_post_images_util(self.df_all_posts, status_callback=status_cb, progress_callback=progress_cb)
            elif task_name == "articles":
                utils.scan_and_download_all_articles_util(self.df_all_posts, status_callback=status_cb, progress_callback=progress_cb)
            elif task_name == "quoted_images":
                utils.download_all_quoted_images_util(self.df_all_posts, status_callback=status_cb, progress_callback=progress_cb)
            
            if progress_bar_widget:
                self.root.after(0, lambda: self._update_download_progress(progress_bar_widget, 1, 1))

        except Exception as e:
            error_msg = f"Error during {task_name} download: {e}"
            print(error_msg)
            self.root.after(0, lambda: self._update_download_status(error_msg))
        finally:
            for btn in buttons_to_disable:
                if btn.winfo_exists():
                    self.root.after(0, lambda b=btn: b.config(state=tk.NORMAL))
            if hasattr(self, 'download_status_label') and self.download_status_label.winfo_exists():
                self.root.after(5000, lambda: self._update_download_status("Idle." if self.download_status_label.winfo_exists() else ""))

    def _start_download_thread(self, task_name):
        parent_window = self.download_win if hasattr(self, 'download_win') and self.download_win.winfo_exists() else self.root
        
        if self.df_all_posts is None or self.df_all_posts.empty:
            messagebox.showinfo("No Data", "No posts loaded to download content from.", parent=parent_window)
            return

        confirm_msg = ""
        title = "Confirm Download"
        if task_name == "images":
            confirm_msg = "This will download all available main Q post images.\n\nThis can take a while. Continue?"
        elif task_name == "articles":
            confirm_msg = "This will download linked web articles.\n\nThis can take a *very* long time and consume significant disk space. Continue?"
        elif task_name == "quoted_images":
            confirm_msg = "This will attempt to download images found within quoted content.\nThis may take some time. Continue?"
        else:
            messagebox.showerror("Error", f"Unknown download task: {task_name}", parent=parent_window)
            return

        if not messagebox.askyesno(title, confirm_msg, parent=parent_window):
            return
        
        buttons_to_check = []
        if hasattr(self, 'download_images_button'): buttons_to_check.append(self.download_images_button)
        if hasattr(self, 'download_articles_button'): buttons_to_check.append(self.download_articles_button)
        if hasattr(self, 'download_quoted_images_button'): buttons_to_check.append(self.download_quoted_images_button)

        for btn in buttons_to_check:
            if btn.cget('state') == tk.DISABLED:
                messagebox.showinfo("In Progress", "A download operation is already in progress. Please wait.", parent=parent_window)
                return

        thread = threading.Thread(target=self._execute_download_task, args=(task_name,), daemon=True)
        thread.start()

# --- END DOWNLOAD_WINDOW_AND_THREADING ---

# --- START SHOW_SETTINGS_WINDOW ---

    def show_settings_window(self):
        if hasattr(self, 'settings_win') and self.settings_win is not None and self.settings_win.winfo_exists():
            self.settings_win.lift()
            self.settings_win.focus_set()
            return

        self.settings_win = tk.Toplevel(self.root)
        self.settings_win.title("QView Settings")

        try:
            dialog_bg = self.style.lookup("TFrame", "background")
        except tk.TclError:
            dialog_bg = "#2b2b2b" if self.current_theme == "dark" else "#f0f0f0"
        self.settings_win.configure(bg=dialog_bg)

        self.settings_win.geometry("400x250") # Adjusted height as abbrev. highlight is removed
        self.settings_win.transient(self.root)
        self.settings_win.grab_set()
        self.settings_win.resizable(False, False)
        self.settings_win.protocol("WM_DELETE_WINDOW", self.on_settings_window_close)

        main_frame = ttk.Frame(self.settings_win, padding="10")
        main_frame.pack(expand=True, fill=tk.BOTH)

# --- Theme Setting ---
        theme_frame = ttk.Labelframe(main_frame, text="Display Theme", padding="10")
        theme_frame.pack(fill="x", pady=5)
        self.settings_theme_var = tk.StringVar(value=self.app_settings.get("theme", settings.DEFAULT_SETTINGS.get("theme")))
        
# We now use the main _set_theme method directly from the radio buttons
        ttk.Radiobutton(theme_frame, text="Dark", variable=self.settings_theme_var, value="dark", command=self.on_setting_change).pack(side="left", padx=5, expand=True)
        ttk.Radiobutton(theme_frame, text="Light", variable=self.settings_theme_var, value="light", command=self.on_setting_change).pack(side="left", padx=5, expand=True)
        ttk.Radiobutton(theme_frame, text="RWB", variable=self.settings_theme_var, value="rwb", command=self.on_setting_change).pack(side="left", padx=5, expand=True)

# --- Link Opening Preference ---
        link_pref_frame = ttk.Labelframe(main_frame, text="Link Opening Preference", padding="10")
        link_pref_frame.pack(fill="x", pady=5)
        self.settings_link_pref_var = tk.StringVar(value=self.app_settings.get("link_opening_preference", settings.DEFAULT_SETTINGS.get("link_opening_preference", "default")))
        
        rb_default = ttk.Radiobutton(link_pref_frame, text="System Default Browser", variable=self.settings_link_pref_var, value="default", command=self.on_setting_change)
        rb_default.pack(anchor="w", padx=5)
        rb_chrome_incognito = ttk.Radiobutton(link_pref_frame, text="Google Chrome (Incognito, if available)", variable=self.settings_link_pref_var, value="chrome_incognito", command=self.on_setting_change)
        rb_chrome_incognito.pack(anchor="w", padx=5)


# --- Close Button ---
        close_button_frame = ttk.Frame(main_frame)
        close_button_frame.pack(side="bottom", fill="x", pady=(10,0))
        ttk.Button(close_button_frame, text="Close", command=self.on_settings_window_close).pack(pady=5)

    def on_setting_change(self, event=None):
        """Handles changes from the Settings window."""
        # Theme
        new_theme = self.settings_theme_var.get()
        if self.current_theme != new_theme:
            self._set_theme(new_theme) # Call the central handler which also saves

# Link Opening Preference
        new_link_pref = self.settings_link_pref_var.get()
        if self.app_settings.get("link_opening_preference") != new_link_pref:
            self.app_settings["link_opening_preference"] = new_link_pref
            settings.save_settings(self.app_settings) # Save immediately
            print(f"Link preference saved: '{new_link_pref}'")
        
    def on_settings_window_close(self):
        if hasattr(self, 'settings_win') and self.settings_win:
            self.settings_win.destroy()
            self.settings_win = None

# --- END SHOW_SETTINGS_WINDOW ---

# --- START SHOW_HELP_WINDOW ---

    def show_help_window(self):
        import webbrowser # Keep import local to method if only used here
        try: 
            dialog_bg = self.style.lookup("TFrame", "background")
            bold_font = ('Arial', 12, 'bold', 'underline')
            normal_font = ('Arial', 10)
            link_fg = self.link_label_fg_dark if self.current_theme == "dark" else self.link_label_fg_light
        except tk.TclError: # Fallback if style lookup fails
            dialog_bg = "#2b2b2b" if self.current_theme == "dark" else "#f0f0f0"
            bold_font = ('Arial', 12, 'bold', 'underline')
            normal_font = ('Arial', 10)
            link_fg = "#6DAEFF" if self.current_theme == "dark" else "#0056b3"

        help_win = tk.Toplevel(self.root)
        help_win.title("QView - Help/Tips") 
        help_win.configure(bg=dialog_bg)
        help_win.geometry("550x500") # Adjusted height
        help_win.transient(self.root)
        help_win.grab_set()

        main_help_frame = ttk.Frame(help_win, padding="15", style="TFrame")
        main_help_frame.pack(expand=True, fill=tk.BOTH)
        
# --- MODIFICATION FOR BUTTON PLACEMENT ---

# Frame for the Close button, packed at the bottom
        bottom_button_frame = ttk.Frame(main_help_frame, style="TFrame") # Use style="TFrame" for consistency
        bottom_button_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(10, 0)) # Pack at bottom, add some top padding
        ttk.Button(bottom_button_frame, text="Close", command=help_win.destroy).pack(pady=5) # Add padding around button

# Container for canvas and scrollbar, will fill space above the button
        canvas_container = ttk.Frame(main_help_frame, style="TFrame")
        canvas_container.pack(side=tk.TOP, fill=tk.BOTH, expand=True) # Fill remaining space

        canvas = tk.Canvas(canvas_container, bg=dialog_bg, highlightthickness=0) # Canvas inside new container
        scrollbar = ttk.Scrollbar(canvas_container, orient="vertical", command=canvas.yview) # Scrollbar inside new container
        scrollable_content_frame = ttk.Frame(canvas, style="TFrame")  #

# --- END MODIFICATION FOR BUTTON PLACEMENT --- 

        scrollable_content_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(
                scrollregion=canvas.bbox("all")
            )
        )

        canvas.create_window((0, 0), window=scrollable_content_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        ttk.Label(scrollable_content_frame, text="Help & Tips", font=bold_font).pack(pady=(0, 10), anchor='w')
        tips = [
            "- Use the Treeview (left) to navigate posts. Click a post to view it.",
            "- Click Treeview headers to sort by Post # or Date.",
            "- Use 'Post #' entry to jump directly (e.g., 123, 10-15, 1,5,10).",
            "- 'Keyword/Theme' searches post text and assigned themes.",
            "- 'Search by Date' uses a calendar for specific day lookups.",
            "- 'Delta Search' finds posts on the same Month/Day across all years.",
            "- 'Today's Deltas' shows posts from the current Month/Day (hover for specific date).",
            "- Bookmark posts using the 'Bookmark' button and view them via 'View Bookmarks'.",
            "- Add personal annotations to posts using the 'View/Edit Note' button.",
            "- Use 'Content Sync' to download images or linked articles for offline access.",
            "- Export the current list of displayed posts to HTML or CSV.",
            "- Toggle 'Dark to Light' / 'Into the Dark' for theme.",
            "- Clickable links appear in post text, quotes, and the 'Show Links' window.",
            "- Quoted post IDs (e.g., >>12345) are clickable to jump to that post.",
            "- Small thumbnails of images from quoted posts may appear directly within the quote.",
            "- Use 'Settings' to change the application theme and link opening preferences."
        ]
        for tip in tips:
            ttk.Label(scrollable_content_frame, text=tip, wraplength=460, justify=tk.LEFT, font=normal_font).pack(anchor='w', padx=5, pady=1)

        ttk.Label(scrollable_content_frame, text="Resources", font=bold_font).pack(pady=(20, 10), anchor='w')
        resources = {
            "QAnon.pub": "https://qanon.pub/",
            "Q Agg (qagg.news)": "https://qagg.news/",
            "Gematrix.org": "https://www.gematrix.org/",
            "Operation Q (giveit.link)": "https://giveit.link/OperationQ"
        }
        for text, url in resources.items():
            label = ttk.Label(scrollable_content_frame, text=text, cursor="hand2", style="TLabel")
            label.configure(font=(normal_font[0], normal_font[1], "underline"), foreground=link_fg)
            label.pack(anchor='w', padx=5, pady=2)
            label.bind("<Button-1>", lambda e, link=url: utils.open_link_with_preference(link, self.app_settings))
        
# --- Support & Feedback Section ---

        ttk.Label(scrollable_content_frame, text="Support & Feedback", font=bold_font).pack(pady=(20, 10), anchor='w')
        support_text = "If you find QView helpful, you can show your support and help keep the coffee flowing!"
        ttk.Label(scrollable_content_frame, text=support_text, wraplength=460, justify=tk.LEFT, font=normal_font).pack(anchor='w', padx=5, pady=1)

        donation_link_text = "Buy me a coffee ☕" 
        donation_url = "https://www.buymeacoffee.com/qview1776" 

        donation_label = ttk.Label(scrollable_content_frame, text=donation_link_text, cursor="hand2", style="TLabel")
        donation_label.configure(font=(normal_font[0], normal_font[1], "underline"), foreground=link_fg)
        donation_label.pack(anchor='w', padx=5, pady=2)
        donation_label.bind("<Button-1>", lambda e, link=donation_url: utils.open_link_with_preference(link, self.app_settings))

        feedback_email_text = "Feedback/Suggestions: qview1776@gmail.com"
        feedback_label = ttk.Label(scrollable_content_frame, text=feedback_email_text, style="TLabel")
        feedback_label.configure(font=normal_font) 
        feedback_label.pack(anchor='w', padx=5, pady=(5,2))
# --- End Support & Feedback Section --- 

        widgets_to_bind_scroll = [canvas, scrollable_content_frame] + list(scrollable_content_frame.winfo_children())
        for widget in widgets_to_bind_scroll:
            widget.bind("<MouseWheel>", lambda e, cw=canvas: self._on_mousewheel(e, cw), add="+")
            widget.bind("<Button-4>", lambda e, cw=canvas: self._on_scroll_up(e, cw), add="+")
            widget.bind("<Button-5>", lambda e, cw=canvas: self._on_scroll_down(e, cw), add="+")

# --- END SHOW_HELP_WINDOW ---

# --- START SHOW_CONTEXT_CHAIN_VIEWER_WINDOW ---

    def show_context_chain_viewer_window(self):
        if self.df_displayed is None or self.df_displayed.empty or not (0 <= self.current_display_idx < len(self.df_displayed)):
            messagebox.showwarning("Context Chain", "Please select a post to view its context chain.", parent=self.root)
            return

        original_df_index = self.df_displayed.index[self.current_display_idx]
        current_post = self.df_all_posts.loc[original_df_index]
        current_post_num = current_post.get('Post Number')

        if not current_post_num:
            messagebox.showinfo("Context Chain", "Selected post has no valid Post Number for context tracing.", parent=self.root)
            return

        # Ensure only one instance of the context window
        if hasattr(self, 'context_chain_win') and self.context_chain_win is not None and self.context_chain_win.winfo_exists():
            self.context_chain_win.lift()
            self.context_chain_win.focus_set()
        else:
            self.context_chain_win = tk.Toplevel(self.root)
            self.context_chain_win.title("Context Chain Viewer")
            try:
                dialog_bg = self.style.lookup("TFrame", "background")
                text_bg = self.style.lookup("TEntry", "fieldbackground")
                text_fg = self.style.lookup("TEntry", "foreground")
                link_fg = self.link_label_fg_dark if self.current_theme == "dark" else self.link_label_fg_light
            except tk.TclError:
                dialog_bg = "#2b2b2b" if self.current_theme == "dark" else "#f0f0f0"
                text_bg = "#3c3f41" if self.current_theme == "dark" else "#ffffff"
                text_fg = "#e0e0e0" if self.current_theme == "dark" else "#000000"
                link_fg = "#6DAEFF" if self.current_theme == "dark" else "#0056b3"
                
            self.context_chain_win.configure(bg=dialog_bg)
            self.context_chain_win.geometry("500x700")
            
            main_frame = ttk.Frame(self.context_chain_win, padding="10")
            main_frame.pack(expand=True, fill=tk.BOTH)

            # --- Create all widgets first ---
            self.context_text_area = tk.Text(main_frame, wrap=tk.WORD,
                                   relief=tk.FLAT, borderwidth=1, font=("TkDefaultFont", 10),
                                   padx=10, pady=10)
            self.context_text_area.configure(bg=text_bg, fg=text_fg, insertbackground=text_fg, selectbackground=self.style.lookup("Treeview", "selectbackground"))
            
            context_text_scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=self.context_text_area.yview)
            self.context_text_area.configure(yscrollcommand=context_text_scrollbar.set)
            
            button_frame = ttk.Frame(main_frame)
            self.context_back_button = ttk.Button(button_frame, text="< Back", command=self.navigate_context_back, state=tk.DISABLED)
            close_button = ttk.Button(button_frame, text="Close", command=self.context_chain_win.destroy)

            # --- Correctly pack all widgets in order ---
            button_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(10, 0))
            self.context_back_button.pack(side=tk.LEFT, padx=(0, 5), expand=True, fill=tk.X)
            close_button.pack(side=tk.LEFT, padx=(5, 0), expand=True, fill=tk.X)
            
            context_text_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            self.context_text_area.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            
            # Configure tags
            self.context_text_area.tag_configure("clickable_context_link", foreground=link_fg, underline=True)
            def show_hand_cursor(event): self.context_text_area.config(cursor="hand2")
            def show_arrow_cursor(event): self.context_text_area.config(cursor="arrow")
            self.context_text_area.tag_bind("clickable_context_link", "<Enter>", show_hand_cursor)
            self.context_text_area.tag_bind("clickable_context_link", "<Leave>", show_arrow_cursor)
            self.context_text_area.tag_configure("bold", font=("TkDefaultFont", 10, "bold"))

        # Clear history to start a new trace
        self.context_history.clear()
        self._is_navigating_context_back = False

        self._update_context_chain_content()
        
# --- END SHOW_CONTEXT_CHAIN_VIEWER_WINDOW ---
       
# --- START UPDATE_CONTEXT_CHAIN_CONTENT ---
    def _update_context_chain_content(self):
        if not (hasattr(self, 'context_chain_win') and self.context_chain_win is not None and self.context_chain_win.winfo_exists()):
            return

        self.context_text_area.config(state=tk.NORMAL)
        self.context_text_area.delete(1.0, tk.END)
        
        for tag in self.context_text_area.tag_names():
            if "link" in tag:
                self.context_text_area.tag_delete(tag)
        
        if hasattr(self, '_context_tag_refs'):
            for ttip in self._context_tag_refs:
                ttip.hidetip(); ttip.unschedule()
            self._context_tag_refs = []
        else:
            self._context_tag_refs = []

        # Helper function to display a section of related posts
        def display_section(title, post_list_raw):
            post_list = sorted(post_list_raw)
            self.context_text_area.insert(tk.END, f"{title}:\n", "bold")

            if post_list:
                for i, p_num in enumerate(post_list):
                    tag_base = f"{title.replace(' ', '_').replace(':', '').replace('/', '_').replace('.', '_')}_link_{p_num}_{i}"
                    self.context_text_area.insert(tk.END, f"  [>>{p_num}]", ("clickable_context_link", tag_base))
                    self.context_text_area.tag_bind(tag_base, "<Button-1>", lambda e, pn=p_num: self.jump_to_post_number_from_ref(pn))
                    
                    tooltip_instance = Tooltip(self.context_text_area, 
                                                 lambda pn=p_num: self._get_post_text_snippet(pn), 
                                                 delay=500, follow=False, bind_widget_events=False)
                    self._context_tag_refs.append(tooltip_instance)
                    self.context_text_area.tag_bind(tag_base, "<Enter>", tooltip_instance.enter)
                    self.context_text_area.tag_bind(tag_base, "<Leave>", tooltip_instance.leave)

                    if i < len(post_list) - 1: self.context_text_area.insert(tk.END, ",")
                self.context_text_area.insert(tk.END, "\n")
            else:
                self.context_text_area.insert(tk.END, "  None\n")
            self.context_text_area.insert(tk.END, "\n")
            
        if self.df_displayed is None or self.df_displayed.empty or not (0 <= self.current_display_idx < len(self.df_displayed)):
            return

        original_df_index = self.df_displayed.index[self.current_display_idx]
        current_post = self.df_all_posts.loc[original_df_index]
        current_post_num = current_post.get('Post Number')

        if not pd.notna(current_post_num): return

        if hasattr(self, '_is_navigating_context_back') and self._is_navigating_context_back:
            self._is_navigating_context_back = False
        else:
            if not self.context_history or self.context_history[-1] != current_post_num:
                self.context_history.append(current_post_num)
        
        if hasattr(self, 'context_back_button') and self.context_back_button.winfo_exists():
            self.context_back_button.config(state=tk.NORMAL if len(self.context_history) > 1 else tk.DISABLED)

        self.context_chain_win.title(f"Context Chain for Post #{int(current_post_num)}")
        self.context_text_area.insert(tk.END, f"Context for Post #{int(current_post_num)}\n\n", "bold")

        # --- Standard Context Sections ---
        quoted_by_this_post = app_data.post_quotes_map.get(current_post_num, [])
        display_section("Posts Quoted by This Post", quoted_by_this_post)
        posts_quoting_this = app_data.post_quoted_by_map.get(current_post_num, [])
        display_section("Posts Quoting This Post", posts_quoting_this)
        
        current_date = current_post.get('Datetime_UTC')
        if pd.notna(current_date):
            time_hhmm = current_date.strftime("%H:%M")
            delta_matches = app_data.post_time_hhmm_map.get(time_hhmm, [])
            filtered_delta_matches = sorted(list(set(delta_matches) - {current_post_num} - set(quoted_by_this_post) - set(posts_quoting_this)))
            display_section(f"Time/Delta Matches ({time_hhmm})", filtered_delta_matches)

        current_themes = current_post.get('Themes', [])
        if current_themes:
            all_shared_theme_posts = [p for t in current_themes for p in app_data.theme_posts_map.get(t, [])]
            filtered_theme_posts = sorted(list(set(all_shared_theme_posts) - {current_post_num} - set(quoted_by_this_post) - set(posts_quoting_this)))
            display_section("Shared Themes", filtered_theme_posts)

        text_content = current_post.get('Text', '')
        if isinstance(text_content, str) and (markers := re.findall(r'\[([^\]]+)\]', text_content)):
            all_shared_marker_posts = [p for m in markers for p in app_data.post_markers_map.get(m.strip(), []) if m.strip()]
            filtered_marker_posts = sorted(list(set(all_shared_marker_posts) - {current_post_num} - set(quoted_by_this_post) - set(posts_quoting_this)))
            display_section("Shared [Markers]", filtered_marker_posts)

        # --- NEW: Mirrored Matches Section ---
        self.context_text_area.insert(tk.END, "🔹 Mirrored Matches:\n", "bold")
        found_any_mirror = False

        # 1. Mirrored Date
        if pd.notna(current_date):
            mirrored_md, posts = self._get_mirrored_date_posts(current_date)
            if mirrored_md and posts:
                found_any_mirror = True
                self.context_text_area.insert(tk.END, f"  → Mirrored Delta: {mirrored_md.replace('-', '/')} →")
                for i, p_num in enumerate(posts):
                    self.context_text_area.insert(tk.END, f" [>>{p_num}]", ("clickable_context_link", f"md_link_{p_num}"))
                    self.context_text_area.tag_bind(f"md_link_{p_num}", "<Button-1>", lambda e, pn=p_num: self.jump_to_post_number_from_ref(pn))
                self.context_text_area.insert(tk.END, "\n")

        # 2. Mirrored Post Number
        reversed_post_num = self._get_mirrored_post_number(current_post_num)
        if reversed_post_num:
            found_any_mirror = True
            self.context_text_area.insert(tk.END, f"  → Reversed Post Number: [>>{reversed_post_num}]", ("clickable_context_link", f"rpn_link_{reversed_post_num}"))
            self.context_text_area.tag_bind(f"rpn_link_{reversed_post_num}", "<Button-1>", lambda e, pn=reversed_post_num: self.jump_to_post_number_from_ref(pn))
            self.context_text_area.insert(tk.END, "\n")

        # 3. Mirrored Timestamp
        if pd.notna(current_date):
            mirrored_time_str, posts = self._get_mirrored_time_posts(current_date)
            posts = sorted(list(set(posts) - {current_post_num})) # Filter self
            if posts:
                found_any_mirror = True
                self.context_text_area.insert(tk.END, f"  → Time Mirror: {mirrored_time_str} →")
                for i, p_num in enumerate(posts):
                    self.context_text_area.insert(tk.END, f" [>>{p_num}]", ("clickable_context_link", f"mt_link_{p_num}"))
                    self.context_text_area.tag_bind(f"mt_link_{p_num}", "<Button-1>", lambda e, pn=p_num: self.jump_to_post_number_from_ref(pn))
                self.context_text_area.insert(tk.END, "\n")
        
        if not found_any_mirror:
            self.context_text_area.insert(tk.END, "  None\n")

        self.context_text_area.config(state=tk.DISABLED)
# --- END UPDATE_CONTEXT_CHAIN_CONTENT ---


# --- START GET_POST_TEXT_SNIPPET ---
    def _get_post_text_snippet(self, post_number, max_length=150):
        """Retrieves a text snippet for a given post number for use in tooltips."""
        if not pd.isna(post_number):
            matching_posts = self.df_all_posts[self.df_all_posts['Post Number'] == post_number]
            if not matching_posts.empty:
                text_content = matching_posts.iloc[0].get('Text', '')
                if isinstance(text_content, str):
                    snippet = text_content.strip()
                    if len(snippet) > max_length:
                        snippet = snippet[:max_length].rsplit(' ', 1)[0] + '...' # Truncate at whole word
                    return f"Post #{post_number}:\n\n{snippet}"
        return f"Post #{post_number}: [Text not found]"
# --- END GET_POST_TEXT_SNIPPET ---
            
    
    def show_gematria_calculator_window(self, initial_text=""):
        """Creates and shows a standalone window for Gematria calculations."""
        if hasattr(self, 'gematria_win') and self.gematria_win.winfo_exists():
            self.gematria_win.lift()
            self.gematria_win.focus_set()
            if initial_text and hasattr(self, 'gematria_input_entry'):
                 self.gematria_input_entry.delete(0, tk.END)
                 self.gematria_input_entry.insert(0, initial_text)
                 self.gematria_input_entry.focus_set()
# Automatically calculate when opened from context menu
                 self._calculate_and_display_gematria_in_window(initial_text)
            return

        self.gematria_win = tk.Toplevel(self.root)
        self.gematria_win.title("Gematria Calculator")
        try:
            dialog_bg = self.style.lookup("TFrame", "background")
            text_fg = self.style.lookup("TEntry", "foreground")
        except tk.TclError:
            dialog_bg = "#2b2b2b" if self.current_theme == "dark" else "#f0f0f0"
            text_fg = "#e0e0e0" if self.current_theme == "dark" else "#000000"
        
        self.gematria_win.configure(bg=dialog_bg)
        self.gematria_win.geometry("350x250")
        self.gematria_win.transient(self.root)
        
        main_frame = ttk.Frame(self.gematria_win, padding="10")
        main_frame.pack(expand=True, fill=tk.BOTH)
        
        input_frame = ttk.Frame(main_frame)
        input_frame.pack(fill=tk.X)
        
        ttk.Label(input_frame, text="Text:").pack(side=tk.LEFT, padx=(0, 5))
        self.gematria_input_entry = ttk.Entry(input_frame, font=('Arial', 10))
        self.gematria_input_entry.pack(side=tk.LEFT, expand=True, fill=tk.X)
        self.gematria_input_entry.insert(0, initial_text)
        
        results_frame = ttk.Labelframe(main_frame, text="Results", padding="10")
        results_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        self.gematria_simple_var = tk.StringVar(value="Simple / Ordinal: 0")
        self.gematria_reverse_var = tk.StringVar(value="Reverse Ordinal: 0")
        self.gematria_hebrew_var = tk.StringVar(value="Hebrew / Jewish: 0")
        self.gematria_english_var = tk.StringVar(value="English (Agrippa): 0")
        
        ttk.Label(results_frame, textvariable=self.gematria_simple_var, font=('Arial', 10, 'bold')).pack(anchor="w")
        ttk.Label(results_frame, textvariable=self.gematria_reverse_var, font=('Arial', 10, 'bold')).pack(anchor="w")
        ttk.Label(results_frame, textvariable=self.gematria_hebrew_var, font=('Arial', 10, 'bold')).pack(anchor="w")
        ttk.Label(results_frame, textvariable=self.gematria_english_var, font=('Arial', 10, 'bold')).pack(anchor="w")
        
        def _calculate_and_display():
            text_to_calc = self.gematria_input_entry.get()
            if text_to_calc:
                results = utils.calculate_gematria(text_to_calc)
                self.gematria_simple_var.set(f"Simple / Ordinal: {results.get('simple', 0)}")
                self.gematria_reverse_var.set(f"Reverse Ordinal: {results.get('reverse', 0)}")
                self.gematria_hebrew_var.set(f"Hebrew / Jewish: {results.get('hebrew', 0)}")
                self.gematria_english_var.set(f"English (Agrippa): {results.get('english', 0)}")
        
        self.gematria_input_entry.bind("<Return>", lambda e: _calculate_and_display())

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, side=tk.BOTTOM)
        ttk.Button(button_frame, text="Calculate", command=_calculate_and_display).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 5))
        ttk.Button(button_frame, text="Close", command=self.gematria_win.destroy).pack(side=tk.LEFT, expand=True, fill=tk.X)
        
        if initial_text:
            _calculate_and_display()

# --- START CONTEXT BACK NAVIGATION ---

    def navigate_context_back(self):
        """Navigates to the previous post in the context window's history."""
        if len(self.context_history) > 1:
            self.context_history.pop()  # Remove the current post from history
            target_post_num = self.context_history[-1]  # Get the previous post

            # Set a flag to prevent the history from being modified during the jump
            self._is_navigating_context_back = True
            self.jump_to_post_number_from_ref(target_post_num)

# --- END CONTEXT BACK NAVIGATION ---

# --- START MIRRORING LOGIC HELPERS ---

    def _get_mirrored_date_posts(self, date_obj):
        """Looks up posts from a mirrored calendar date."""
        mirrored_date_pairs = {
            "04-15": "10-17", "10-17": "04-15", "01-28": "07-31",
            "07-31": "01-28", "03-11": "09-12", "09-12": "03-11",
            "02-05": "08-08", "08-08": "02-05", "06-10": "12-11",
            "12-11": "06-10"
        }
        month_day_str = date_obj.strftime("%m-%d")
        mirrored_md = mirrored_date_pairs.get(month_day_str)
        
        if not mirrored_md:
            return None, []
            
        # Find all posts matching the mirrored month and day
        matching_posts_df = self.df_all_posts[
            self.df_all_posts['Datetime_UTC'].dt.strftime('%m-%d') == mirrored_md
        ]
        return mirrored_md, list(matching_posts_df['Post Number'].dropna().astype(int))

    def _get_mirrored_post_number(self, post_num):
        """Returns the reversed post number if it exists in the data."""
        if not post_num or not isinstance(post_num, (int, float)):
            return None
        reversed_num = int(str(int(post_num))[::-1])
        
        # Check if a post with this reversed number actually exists
        if not self.df_all_posts[self.df_all_posts['Post Number'] == reversed_num].empty:
            return reversed_num
        return None

    def _get_mirrored_time_posts(self, time_obj):
        """Finds posts at the 'reversed' time (23:59:59 - current time)."""
        mirrored_hr = 23 - time_obj.hour
        mirrored_min = 59 - time_obj.minute
        mirrored_sec = 59 - time_obj.second
        
        # Create a new time string to look up in the index
        mirrored_time_str = f"{mirrored_hr:02}:{mirrored_min:02}:{mirrored_sec:02}"
        matching_posts = app_data.post_time_hhmms_map.get(mirrored_time_str, [])
        return mirrored_time_str, matching_posts

# --- END MIRRORING LOGIC HELPERS ---

# --- START SHOW_ABOUT_DIALOG ---

    def show_about_dialog(self):
        messagebox.showinfo("About QView", 
                            "QView - Q Post Explorer\n\n"
                            "Version: 1.1 (Research & UI Update)\n\n"
                            "Developed for independent research and analysis of Q posts.\n"
                            "QView allows local exploration, searching, and annotation of the dataset.\n\n"
                            "Data processing in QView is based on the 'JSON-QAnon' dataset compilation by Jack Kingsman "
                            "(github.com/jkingsman/JSON-QAnon).\n\n"
                            "This application does not endorse any specific viewpoints but aims to provide a robust tool for study.\n\n"
                            "Happy digging!",
                            parent=self.root)

# --- END SHOW_ABOUT_DIALOG ---

# --- START PLACEHOLDER_HANDLING ---

    def clear_placeholder(self, event, placeholder_text, widget=None):
        if widget is None and event: 
            widget = event.widget
        elif widget is None and not event: 
            if placeholder_text == config.PLACEHOLDER_POST_NUM: 
                widget = self.post_entry
            elif placeholder_text == config.PLACEHOLDER_KEYWORD: 
                widget = self.keyword_entry
            else: 
                return
        
        if widget and hasattr(widget, 'get') and widget.get() == placeholder_text:
            widget.delete(0, tk.END)
# Use the style's foreground for normal text color
            try:
                normal_fg = self.style.lookup("TEntry", "foreground")
                widget.config(foreground=normal_fg)
            except tk.TclError: 
# Fallback if style lookup fails
                widget.config(foreground=self.link_label_fg_light if self.current_theme == "light" else self.link_label_fg_dark)


    def restore_placeholder(self, event, placeholder_text, widget=None):
        if widget is None and event: 
            widget = event.widget
        elif widget is None and not event: 
            if placeholder_text == config.PLACEHOLDER_POST_NUM: 
                widget = self.post_entry
            elif placeholder_text == config.PLACEHOLDER_KEYWORD: 
                widget = self.keyword_entry
            else: 
                return

        if widget and hasattr(widget, 'get') and not widget.get(): # Only restore if field is empty
            widget.insert(0, placeholder_text)
            placeholder_color = self.placeholder_fg_color_light if self.current_theme == "light" else self.placeholder_fg_color_dark
            widget.config(foreground=placeholder_color)

# --- END PLACEHOLDER_HANDLING ---

# --- START ON_TREE_SELECT ---

    def on_tree_select(self, event):
        selected_items = self.post_tree.selection()
        if selected_items:
            selected_iid_str = selected_items[0]
            try:
                original_df_index = int(selected_iid_str)
                if self.df_displayed is not None and original_df_index in self.df_displayed.index:
                    new_display_idx = self.df_displayed.index.get_loc(original_df_index)
                    
                    welcome_was_showing = (hasattr(self, 'post_number_label') and 
                                           self.post_number_label.cget("text") == "Welcome to QView!")
                                           
                    if (not hasattr(self, '_init_complete') or not self._init_complete or \
                       new_display_idx != self.current_display_idx or welcome_was_showing):
                        self.current_display_idx = new_display_idx # Update current index HERE
                        self.update_display()
                        self._update_context_chain_content() # NEW: Update context window content
            except ValueError: 
                print(f"Error: Tree iid '{selected_iid_str}' not a valid integer for index.")
            except Exception as e: 
                print(f"Error in on_tree_select: {e}")
        else: 
# No items selected in tree
            self.current_display_idx = -1 # Reflect that no item is selected
            if hasattr(self, '_init_complete') and self._init_complete:
# If fully initialized and selection is cleared, usually means list is empty
# or we want to show a default state like the welcome message.
# update_display (if current_display_idx becomes -1) will call show_welcome_message.
                self.update_display() # Call update_display to handle the "no selection" state

# --- END ON_TREE_SELECT ---

# --- START ON_TREE_ARROW_NAV ---

    def on_tree_arrow_nav(self, event):
        if self.df_displayed is None or self.df_displayed.empty: return "break"
        all_tree_iids_str = list(self.post_tree.get_children(''))
        num_items_in_tree = len(all_tree_iids_str)
        if num_items_in_tree == 0: return "break"
        
        current_focus_iid_str = self.post_tree.focus()
        current_logical_idx_in_tree = -1
        
        if current_focus_iid_str and current_focus_iid_str in all_tree_iids_str:
            current_logical_idx_in_tree = all_tree_iids_str.index(current_focus_iid_str)
        elif num_items_in_tree > 0 : # If no focus, but items exist, determine start based on key
            current_logical_idx_in_tree = 0 if event.keysym == "Down" else num_items_in_tree - 1
            
        if current_logical_idx_in_tree == -1 : return "break" # Should not happen if num_items > 0
            
        target_logical_idx_in_tree = -1
        if event.keysym == "Down":
            target_logical_idx_in_tree = current_logical_idx_in_tree + 1
            if target_logical_idx_in_tree >= num_items_in_tree:
                target_logical_idx_in_tree = num_items_in_tree - 1 # Stay on last item
        elif event.keysym == "Up":
            target_logical_idx_in_tree = current_logical_idx_in_tree - 1
            if target_logical_idx_in_tree < 0:
                target_logical_idx_in_tree = 0 # Stay on first item
        else:
            return # Should not happen if bound to Up/Down keys only
            
        if 0 <= target_logical_idx_in_tree < num_items_in_tree:
            target_iid_str = all_tree_iids_str[target_logical_idx_in_tree]
            self.post_tree.selection_set(target_iid_str) # This will trigger on_tree_select
            self.post_tree.focus(target_iid_str)
            self.post_tree.see(target_iid_str)
            
        return "break" # Prevent default Treeview handling of arrow keys if we've handled it

# --- END ON_TREE_ARROW_NAV ---

# --- START REPOPULATE_TREEVIEW ---

    def repopulate_treeview(self, dataframe_to_show, select_first_item=True): # Added select_first_item
        self.post_tree.delete(*self.post_tree.get_children())
        if dataframe_to_show is not None:
            for original_df_index, row in dataframe_to_show.iterrows():
                date_val_real = row.get('Datetime_UTC')
                date_str = date_val_real.strftime('%Y-%m-%d') if pd.notna(date_val_real) else "No Date"
                post_num_real = row.get('Post Number')
                iid_original_index_str = str(row.name)
                post_num_display = f"#{post_num_real}" if pd.notna(post_num_real) else f"Idx:{iid_original_index_str}"
                is_bookmarked_char = "★" if row.name in self.bookmarked_posts else ""
# NEW: Check for notes and add indicator
# In gui.py, inside repopulate_treeview, replace the has_note_char line:
# NEW: Check for notes and add indicator
                has_note_char = "♪" if iid_original_index_str in self.user_notes and self.user_notes.get(iid_original_index_str, {}).get("content", "").strip() else ""
                self.post_tree.insert("", "end", iid=iid_original_index_str, values=(post_num_display, date_str, has_note_char, is_bookmarked_char)) # Added has_note_char

        if dataframe_to_show is not None and not dataframe_to_show.empty:
            if select_first_item:
# For new views (searches, clear search), we always select the first item (index 0)
# of the 'dataframe_to_show'. We do not modify self.current_display_idx here.
# The on_tree_select event will handle updating self.current_display_idx.
                idx_to_select_in_df = 0 
                                
                if 0 <= idx_to_select_in_df < len(dataframe_to_show.index): 
                    iid_to_select_original_index_str = str(dataframe_to_show.index[idx_to_select_in_df])
                    if self.post_tree.exists(iid_to_select_original_index_str):
                        self.post_tree.selection_set(iid_to_select_original_index_str)
                        self.post_tree.focus(iid_to_select_original_index_str)
                        self.post_tree.see(iid_to_select_original_index_str)
# If select_first_item is False (e.g., initial load with welcome message showing),
# no item is programmatically selected here. self.current_display_idx remains as is
# (likely -1, set by show_welcome_message or __init__).
        else: # dataframe_to_show is empty or None
# current_display_idx will be set to -1 by on_tree_select if selection is cleared,
# or by show_welcome_message if that's called by the search logic.
            if hasattr(self, '_init_complete') and self._init_complete:
# If the app is running and the displayed list becomes empty (e.g. no search results),
# show the welcome message. on_tree_select will also likely have cleared selection.
                self.show_welcome_message()
            elif not (hasattr(self, '_init_complete') and self._init_complete):
# This case is for during __init__ if the initial df_all_posts is empty.
# __init__ itself calls show_welcome_message.
# Setting labels here is just a fallback for a very specific init state.
                 self.update_post_number_label(is_welcome=True)
                 self.update_bookmark_button_status(is_welcome=True)
                 if hasattr(self, 'view_edit_note_button') and self.view_edit_note_button.winfo_exists():
                     self.view_edit_note_button.config(state=tk.DISABLED)
        
        if not hasattr(self, '_init_complete'): # Should already exist from __init__
             self._init_complete = False

# --- END REPOPULATE_TREEVIEW ---

# --- START UPDATE_POST_NUMBER_LABEL ---

    def update_post_number_label(self, is_welcome=False): # Added is_welcome
        if is_welcome:
            self.post_number_label.config(text="Welcome to QView!")
            return
        
        if self.df_displayed is None or self.df_displayed.empty or self.current_display_idx < 0 :
            self.post_number_label.config(text="No Posts Displayed")
            return
        
        if not (0 <= self.current_display_idx < len(self.df_displayed)):
            self.post_number_label.config(text="Invalid Index")
            return
            
        post_series = self.df_displayed.iloc[self.current_display_idx]
        post_num_df = post_series.get('Post Number')
        original_df_idx = self.df_displayed.index[self.current_display_idx] 
        
        post_num_display = f"#{post_num_df}" if pd.notna(post_num_df) else f"(Original Idx:{original_df_idx})"
        total_in_view = len(self.df_displayed)
        current_pos_in_view = self.current_display_idx + 1
        
        label_text_parts = []
        if self.current_search_active:
            label_text_parts.append(f"Result {current_pos_in_view}/{total_in_view}")
        else:
            label_text_parts.append(f"Post {current_pos_in_view}/{total_in_view}")
        
        label_text_parts.append(f"(Q {post_num_display})")
        
        self.post_number_label.config(text=" ".join(label_text_parts))

# --- END UPDATE_POST_NUMBER_LABEL ---

# --- START _HANDLE_SEARCH_RESULTS ---

    def _handle_search_results(self, results_df, search_term_str):
        if not results_df.empty:
            self.df_displayed = results_df.copy()
            self.current_search_active = True
            self.clear_search_button.config(state=tk.NORMAL)
            self.current_display_idx = -1
            self.repopulate_treeview(self.df_displayed, select_first_item=True) # select_first_item=True to show first result
            
# After repopulating, if df_displayed is still not empty and no tree selection was made
# (which repopulate_treeview with select_first_item=True should handle),
# ensure the first item is selected and display is updated.
# The on_tree_select event triggered by repopulate_treeview should call update_display.
            if not self.df_displayed.empty and not self.post_tree.selection():
                if 0 <= self.current_display_idx < len(self.df_displayed) : # If current_display_idx is somehow valid
                    self.select_tree_item_by_idx(self.current_display_idx)
                elif len(self.df_displayed) > 0: # Default to first item if display_idx was bad
                    self.current_display_idx = 0
                    self.select_tree_item_by_idx(0)
                else: # No results to select (should not happen if results_df was not empty)
                    self.show_welcome_message()
            elif self.df_displayed.empty: # If results_df was not empty but df_displayed somehow became empty
                 self.show_welcome_message()
# If a selection was made by repopulate_treeview, update_display would have been called via on_tree_select.

        else: 
# No results found
            messagebox.showinfo("Search Results", 
                                f"No posts found for: {search_term_str}", 
                                parent=self.root)
# Ensure df_all_posts exists before trying to get its columns
# ---- PROPOSED CHANGE for consistency ----
            self.current_display_idx = -1 # Also invalidate here
# ---- END PROPOSED CHANGE ----
            columns_to_use = self.df_all_posts.columns if self.df_all_posts is not None else []
            self.df_displayed = pd.DataFrame(columns=columns_to_use) 
            self.current_search_active = True 
            self.clear_search_button.config(state=tk.NORMAL) 
            self.repopulate_treeview(self.df_displayed, select_first_item=False) 
            self.show_welcome_message() # Show welcome on no results

# --- END _HANDLE_SEARCH_RESULTS ---

# --- START SELECT_TREE_ITEM_BY_IDX ---

    def select_tree_item_by_idx(self, display_idx_in_current_df):
        if self.df_displayed is not None and \
           0 <= display_idx_in_current_df < len(self.df_displayed): # Check df_displayed
            # Ensure the index exists in the current df_displayed's index
            if display_idx_in_current_df < len(self.df_displayed.index):
                original_df_idx_to_select = self.df_displayed.index[display_idx_in_current_df]
                iid_to_select = str(original_df_idx_to_select)
                if self.post_tree.exists(iid_to_select):
                    self.post_tree.selection_set(iid_to_select)
                    self.post_tree.focus(iid_to_select)
                    self.post_tree.see(iid_to_select)
                # else:
                #     print(f"Warning: IID {iid_to_select} not found in tree, though index was valid.")
            # else:
            #     print(f"Warning: display_idx_in_current_df {display_idx_in_current_df} out of range for df_displayed.index.")

        elif self.post_tree.selection(): # If no valid selection can be made, clear existing selection
            self.post_tree.selection_remove(self.post_tree.selection())

# --- END SELECT_TREE_ITEM_BY_IDX ---

# === START::THEME_TOGGLE ===

    def apply_dark_theme(self):
        self.current_theme = "dark"; self.style.theme_use('clam')
        bg="#2b2b2b"; fg="#e0e0e0"; entry_bg="#3c3f41"; btn_bg="#4f4f4f"; btn_active="#6a6a6a"
        tree_bg="#3c3f41"; tree_sel_bg="#0078D7"; tree_sel_fg="#ffffff"; heading_bg="#4f4f4f"
        progress_trough = '#3c3f41'; progress_bar_color = '#0078D7'
        accent_yellow = "#FFCB6B" # Define the yellow color for reuse
        
        self.root.configure(bg=bg); self.style.configure(".", background=bg, foreground=fg, font=('Arial',10))
        self.style.configure("TFrame", background=bg); self.style.configure("TLabel", background=bg, foreground=fg, padding=3)
        self.style.configure("TButton", background=btn_bg, foreground=fg, padding=5, font=('Arial',9,'bold'), borderwidth=1, relief=tk.RAISED)
        self.style.map("TButton", background=[("active",btn_active),("pressed","#5a5a5a")], relief=[("pressed",tk.SUNKEN)])
        self.style.configure("Treeview", background=tree_bg, foreground=fg, fieldbackground=tree_bg, borderwidth=1, relief=tk.FLAT)
        self.style.map("Treeview", background=[("selected",tree_sel_bg)], foreground=[("selected",tree_sel_fg)])
        self.style.configure("Treeview.Heading", background=heading_bg, foreground=fg, font=('Arial',10,'bold'), relief=tk.FLAT, padding=3)
        self.style.configure("TEntry", fieldbackground=entry_bg, foreground=fg, insertbackground=fg, relief=tk.SUNKEN, borderwidth=1)
        self.style.configure("TLabelframe", background=bg, foreground=fg, relief=tk.GROOVE, borderwidth=1, padding=5)
        self.style.configure("TLabelframe.Label", background=bg, foreground=fg, font=('Arial',10,'bold'))
        self.style.configure("TCombobox", fieldbackground=entry_bg, background=btn_bg, foreground=fg, arrowcolor=fg, selectbackground=entry_bg, selectforeground=fg)
        
        self.style.configure("Contrasting.Horizontal.TProgressbar", troughcolor=progress_trough, background=progress_bar_color, thickness=20)

        self.post_text_area.configure(bg=entry_bg, fg=fg, insertbackground=fg, selectbackground=tree_sel_bg)
        if hasattr(self,'image_display_frame'): self.image_display_frame.configure(style="TFrame")

# --- MODIFICATION: Set all metadata labels to yellow for contrast ---
        self.post_text_area.tag_configure("bold_label", foreground=accent_yellow)
        self.post_text_area.tag_configure("post_number_val", foreground=accent_yellow)
# --- MODIFIED: Abbreviation tag to use background instead of foreground for highlighting ---
        self.post_text_area.tag_configure("abbreviation_tag", background=config.ABBREVIATION_HIGHLIGHT_COLOR, foreground="white") # Text will be white on red
# --- END MODIFIED ---

# --- Configure remaining tags for theme consistency ---
        self.post_text_area.tag_configure("date_val",foreground="#A5C25C")
        self.post_text_area.tag_configure("author_val",foreground="#B0B0B0")
        self.post_text_area.tag_configure("themes_val",foreground="#C39AC9")
        self.post_text_area.tag_configure("image_val",foreground="#589DF6")
        self.post_text_area.tag_configure("clickable_link_style",foreground=self.link_label_fg_dark)
        self.post_text_area.tag_configure("bookmarked_header",foreground="#FFD700")
        self.post_text_area.tag_configure("quoted_ref_header",foreground="#ABBFD0")
        self.post_text_area.tag_configure("quoted_ref_text_body",foreground="#FFEE77")
        self.post_text_area.tag_configure("welcome_title_tag", foreground="#FFCB6B")
        self.post_text_area.tag_configure("welcome_text_tag", foreground="#e0e0e0")
        self.post_text_area.tag_configure("welcome_emphasis_tag", foreground="#A5C25C")
        self.post_text_area.tag_configure("welcome_closing_tag", foreground="#FFD700")

    def apply_light_theme(self):
        self.current_theme = "light"; self.style.theme_use('clam')
        bg_color="#f0f0f0"; fg_color="#000000"; entry_bg="#ffffff"; button_bg="#e1e1e1"; button_active_bg="#d1d1d1"
        tree_bg="#ffffff"; tree_sel_bg="#0078D7"; tree_sel_fg="#ffffff"; heading_bg="#e1e1e1"
        progress_trough = '#dcdcdc'; progress_bar_color = '#4CAF50'
        
        self.root.configure(bg=bg_color); self.style.configure(".", background=bg_color, foreground=fg_color, font=('Arial',10))
        self.style.configure("TFrame", background=bg_color); self.style.configure("TLabel", background=bg_color, foreground=fg_color, padding=3)
        self.style.configure("TButton", background=button_bg, foreground=fg_color, padding=5, font=('Arial',9,'bold'), borderwidth=1, relief=tk.RAISED)
        self.style.map("TButton", background=[("active",button_active_bg),("pressed","#c1c1c1")], relief=[("pressed",tk.SUNKEN)])
        self.style.configure("Treeview", background=tree_bg, foreground=fg_color, fieldbackground=tree_bg, borderwidth=1, relief=tk.FLAT)
        self.style.map("Treeview", background=[("selected",tree_sel_bg)], foreground=[("selected",tree_sel_fg)])
        self.style.configure("Treeview.Heading", background=heading_bg, foreground=fg_color, font=('Arial',10,'bold'), relief=tk.FLAT, padding=3)
        self.style.configure("TEntry", fieldbackground=entry_bg, foreground=fg_color, insertbackground=fg_color, relief=tk.SUNKEN, borderwidth=1)
        self.style.configure("TLabelframe", background=bg_color, foreground=fg_color, relief=tk.GROOVE, borderwidth=1, padding=5)
        self.style.configure("TLabelframe.Label", background=bg_color, foreground=fg_color, font=('Arial',10,'bold'))
        
        self.style.configure("Contrasting.Horizontal.TProgressbar", troughcolor=progress_trough, background=progress_bar_color, thickness=20)

        self.post_text_area.configure(bg=entry_bg, fg=fg_color, insertbackground=fg_color, selectbackground=tree_sel_bg)
        if hasattr(self,'image_display_frame'): self.image_display_frame.configure(style="TFrame")
        self.post_text_area.tag_configure("bold_label", foreground="#333333"); self.post_text_area.tag_configure("post_number_val", foreground="#D9534F")
        # --- MODIFIED: Abbreviation tag to use background instead of foreground for highlighting ---
        self.post_text_area.tag_configure("abbreviation_tag", background=config.ABBREVIATION_HIGHLIGHT_COLOR, foreground="white") # Text will be white on red
        # --- END MODIFIED ---
        self.post_text_area.tag_configure("date_val", foreground="#5CB85C"); self.post_text_area.tag_configure("author_val", foreground="#555555")
        self.post_text_area.tag_configure("themes_val", foreground="#8E44AD"); self.post_text_area.tag_configure("image_val", foreground="#337AB7")
        self.post_text_area.tag_configure("clickable_link_style", foreground=self.link_label_fg_light); self.post_text_area.tag_configure("bookmarked_header", foreground="#F0AD4E")
        self.post_text_area.tag_configure("quoted_ref_header", foreground="#4A4A4A"); self.post_text_area.tag_configure("quoted_ref_text_body", foreground="#B8860B")
        self.post_text_area.tag_configure("welcome_title_tag", foreground="#D9534F"); self.post_text_area.tag_configure("welcome_text_tag", foreground="#000000")
        self.post_text_area.tag_configure("welcome_emphasis_tag", foreground="#8E44AD"); self.post_text_area.tag_configure("welcome_closing_tag", foreground="#5CB85C")

    def apply_rwb_theme(self):
        """Applies a Red, White, and Blue theme."""
        self.current_theme = "rwb"; self.style.theme_use('clam')
        # Official US Flag Colors: Old Glory Blue, Old Glory Red, White
        bg = "#002868"; fg = "#FFFFFF"; entry_bg = "#1d3461"; btn_bg = "#4A6572"; btn_active = "#5E8294"
        tree_bg = "#1d3461"; tree_sel_bg = "#BF0A30"; tree_sel_fg = "#FFFFFF"; heading_bg = "#4A6572"
        progress_trough = entry_bg; progress_bar_color = "#BF0A30"
        link_color = "#87CEEB" # A bright, patriotic blue
        accent_gold = "#FFD700"
        accent_red = "#BF0A30"
        subtle_text_color = "#CCCCCC"

        self.root.configure(bg=bg); self.style.configure(".", background=bg, foreground=fg, font=('Arial',10))
        self.style.configure("TFrame", background=bg); self.style.configure("TLabel", background=bg, foreground=fg, padding=3)
        self.style.configure("TButton", background=btn_bg, foreground=fg, padding=5, font=('Arial',9,'bold'), borderwidth=1, relief=tk.RAISED)
        self.style.map("TButton", background=[("active",btn_active),("pressed","#5E8294")], relief=[("pressed",tk.SUNKEN)])
        self.style.configure("Treeview", background=tree_bg, foreground=fg, fieldbackground=tree_bg, borderwidth=1, relief=tk.FLAT)
        self.style.map("Treeview", background=[("selected",tree_sel_bg)], foreground=[("selected",tree_sel_fg)])
        self.style.configure("Treeview.Heading", background=heading_bg, foreground=fg, font=('Arial',10,'bold'), relief=tk.FLAT, padding=3)
        self.style.configure("TEntry", fieldbackground=entry_bg, foreground=fg, insertbackground=fg, relief=tk.SUNKEN, borderwidth=1)
        self.style.configure("TLabelframe", background=bg, foreground=fg, relief=tk.GROOVE, borderwidth=1, padding=5)
        self.style.configure("TLabelframe.Label", background=bg, foreground=fg, font=('Arial',10,'bold'))
        self.style.configure("Contrasting.Horizontal.TProgressbar", troughcolor=progress_trough, background=progress_bar_color, thickness=20)
        
        self.post_text_area.configure(bg=entry_bg, fg=fg, insertbackground=fg, selectbackground=tree_sel_bg)
        if hasattr(self,'image_display_frame'): self.image_display_frame.configure(style="TFrame")
        
# --- MODIFICATION: Set all metadata labels to gold/yellow for contrast ---
        self.post_text_area.tag_configure("bold_label", foreground=accent_gold)
        self.post_text_area.tag_configure("post_number_val", foreground=accent_gold)
        self.post_text_area.tag_configure("bookmarked_header", foreground=accent_red)
# --- MODIFIED: Abbreviation tag to use background instead of foreground for highlighting ---
        self.post_text_area.tag_configure("abbreviation_tag", background=config.ABBREVIATION_HIGHLIGHT_COLOR, foreground="white") # Text will be white on red
# --- END MODIFIED ---

# --- Configure remaining tags for theme consistency ---
        self.post_text_area.tag_configure("date_val", foreground=subtle_text_color)
        self.post_text_area.tag_configure("author_val", foreground=subtle_text_color)
        self.post_text_area.tag_configure("themes_val", foreground=link_color)
        self.post_text_area.tag_configure("image_val", foreground=link_color)
        self.post_text_area.tag_configure("clickable_link_style", foreground=link_color)
        self.post_text_area.tag_configure("quoted_ref_header", foreground=accent_gold)
        self.post_text_area.tag_configure("quoted_ref_text_body", foreground=fg)
        self.post_text_area.tag_configure("welcome_title_tag", foreground=accent_red)
        self.post_text_area.tag_configure("welcome_text_tag", foreground=fg)
        self.post_text_area.tag_configure("welcome_emphasis_tag", foreground=accent_gold)
        self.post_text_area.tag_configure("welcome_closing_tag", foreground=accent_red)
        
        self.restore_placeholder(None, config.PLACEHOLDER_POST_NUM, self.post_entry)
        self.restore_placeholder(None, config.PLACEHOLDER_KEYWORD, self.keyword_entry)

    def _set_theme(self, theme_name):
        """Sets the application theme and saves the setting."""
        if self.current_theme == theme_name:
            return

        if theme_name == "dark":
            self.apply_dark_theme()
        elif theme_name == "light":
            self.apply_light_theme()
        elif theme_name == "rwb":
            self.apply_rwb_theme()
        
        self.app_settings["theme"] = theme_name
        self.theme_var.set(theme_name)
        settings.save_settings(self.app_settings)
        print(f"Theme changed and saved: '{theme_name}'")

        if self.current_display_idx != -1 and self.df_displayed is not None and not self.df_displayed.empty: 
            self.update_display()
        else: 
            self.show_welcome_message()

# --- NEW: Handler for abbreviation highlight toggle ---
    def on_highlight_abbreviations_toggle(self):
        new_state = self.highlight_abbreviations_var.get()
        self.app_settings["highlight_abbreviations"] = new_state
        settings.save_settings(self.app_settings)
        print(f"Abbreviation highlighting set to: {new_state}")
# Re-render the current post to apply/remove highlighting
        if self.current_display_idx != -1 and self.df_displayed is not None and not self.df_displayed.empty:
            self.update_display()
        else:
            self.show_welcome_message() # Even for welcome, ensure tags are reset

# === END::THEME_TOGGLE ===

# --- START CONFIGURE_TEXT_TAGS ---

    def configure_text_tags(self):
        default_font_name = "TkDefaultFont"
        self.post_text_area.tag_configure("bold_label", font=(default_font_name, 11, "bold"))
        self.post_text_area.tag_configure("post_number_val", font=(default_font_name, 11, "bold"))
        self.post_text_area.tag_configure("date_val", font=(default_font_name, 10))
        self.post_text_area.tag_configure("author_val", font=(default_font_name, 10))
        self.post_text_area.tag_configure("themes_val", font=(default_font_name, 10, "italic"))
        self.post_text_area.tag_configure("image_val", font=(default_font_name, 10))
        
        self.post_text_area.tag_configure("abbreviation_tag", underline=False) # Theme methods set actual colors
        self.post_text_area.tag_configure("search_highlight_tag", background="#FFFF00", foreground="black")

        self.post_text_area.tag_configure("clickable_link_style", underline=True)
        def show_hand_cursor(event): event.widget.config(cursor="hand2")
        def show_arrow_cursor(event): event.widget.config(cursor=self.default_text_area_cursor)
        

        self.post_text_area.tag_bind("clickable_link_style", "<Enter>", show_hand_cursor)
        self.post_text_area.tag_bind("clickable_link_style", "<Leave>", show_arrow_cursor)
        self.post_text_area.tag_configure("bookmarked_header", font=(default_font_name, 11, "bold"))
        self.post_text_area.tag_configure("quoted_ref_header", font=(default_font_name, 10, "italic", "bold"), lmargin1=20, lmargin2=20, spacing1=5)
        self.post_text_area.tag_configure("quoted_ref_text_body", font=(default_font_name, 10, "italic"), lmargin1=25, lmargin2=25, spacing3=5)
        self.post_text_area.tag_configure("welcome_title_tag", font=(default_font_name, 14, "bold"), justify=tk.CENTER, spacing1=5, spacing3=10)
        self.post_text_area.tag_configure("welcome_text_tag", font=(default_font_name, 10), lmargin1=15, lmargin2=15, spacing1=3, spacing3=3, wrap=tk.WORD)
        self.post_text_area.tag_configure("welcome_emphasis_tag", font=(default_font_name, 10, "italic"))
        self.post_text_area.tag_configure("welcome_closing_tag", font=(default_font_name, 10, "bold"), justify=tk.CENTER, spacing1=10)

# --- END CONFIGURE_TEXT_TAGS ---



# --- START UPDATE_DISPLAY ---

    def update_display(self):
        for widget in self.image_display_frame.winfo_children(): widget.destroy()
        self.displayed_images_references = []; self._quote_image_references = []; self.current_post_urls = []; self.current_post_downloaded_article_path = None
        self.post_text_area.config(state=tk.NORMAL); 
        self.post_text_area.delete(1.0, tk.END)
        self.post_text_area.tag_remove("search_highlight_tag", "1.0", tk.END)
        
        show_images = True
        if self.df_displayed is None or self.df_displayed.empty or not (0 <= self.current_display_idx < len(self.df_displayed)):
            self.show_welcome_message(); return
        
        original_df_index = self.df_displayed.index[self.current_display_idx]
        post = self.df_all_posts.loc[original_df_index]
        post_number_val = post.get('Post Number'); safe_filename_post_id = utils.sanitize_filename_component(str(post_number_val if pd.notna(post_number_val) else original_df_index))
        pn_display_raw = post.get('Post Number', original_df_index); pn_str = f"#{pn_display_raw}" if pd.notna(pn_display_raw) else f"(Idx:{original_df_index})"
        is_bookmarked = original_df_index in self.bookmarked_posts; bookmark_indicator_text_raw = "[BOOKMARKED]" if is_bookmarked else ""
        
        self.post_text_area.insert(tk.END, utils.sanitize_text_for_tkinter(f"QView Post {pn_str} "), "post_number_val")
        if is_bookmarked: self.post_text_area.insert(tk.END, utils.sanitize_text_for_tkinter(bookmark_indicator_text_raw) + "\n", "bookmarked_header")
        else: self.post_text_area.insert(tk.END, "\n")
        
        dt_val = post.get('Datetime_UTC')
        if pd.notna(dt_val):
            dt_utc = dt_val.tz_localize('UTC') if dt_val.tzinfo is None else dt_val; dt_local = dt_utc.tz_convert(None)
            date_local_str=f"{dt_local.strftime('%Y-%m-%d %H:%M:%S %Z')} (Local)\n"; date_utc_str=f"{dt_utc.strftime('%Y-%m-%d %H:%M:%S %Z')} (UTC)\n"
            self.post_text_area.insert(tk.END, "Date: ", "bold_label"); self.post_text_area.insert(tk.END, date_local_str, "date_val"); self.post_text_area.insert(tk.END, "      ", "bold_label"); self.post_text_area.insert(tk.END, date_utc_str, "date_val")
        else: self.post_text_area.insert(tk.END, "Date: No Date\n", "bold_label")
        
        author_text_raw=post.get('Author',''); tripcode_text_raw=post.get('Tripcode',''); author_text=utils.sanitize_text_for_tkinter(author_text_raw); tripcode_text=utils.sanitize_text_for_tkinter(tripcode_text_raw)
        if author_text and pd.notna(author_text_raw): self.post_text_area.insert(tk.END, "Author: ", "bold_label"); self.post_text_area.insert(tk.END, f"{author_text}\n", "author_val")
        if tripcode_text and pd.notna(tripcode_text_raw): self.post_text_area.insert(tk.END, "Tripcode: ", "bold_label"); self.post_text_area.insert(tk.END, f"{tripcode_text}\n", "author_val")
        
        themes_list = post.get('Themes', [])
        if themes_list and isinstance(themes_list, list) and len(themes_list) > 0: themes_str = utils.sanitize_text_for_tkinter(f"{', '.join(themes_list)}\n"); self.post_text_area.insert(tk.END, "Themes: ", "bold_label"); self.post_text_area.insert(tk.END, themes_str, "themes_val")
        
        referenced_posts_raw_data = post.get('Referenced Posts Raw')
        if isinstance(referenced_posts_raw_data, list) and referenced_posts_raw_data:
            self.post_text_area.insert(tk.END, "\nReferenced Content:\n", ("bold_label"))
            for ref_idx, ref_post_data in enumerate(referenced_posts_raw_data):
                if not isinstance(ref_post_data, dict): continue
                ref_num_raw = ref_post_data.get('reference', ''); ref_author_id_raw = ref_post_data.get('author_id'); ref_text_content_raw = ref_post_data.get('text', '[No text in reference]')
                ref_num_san = utils.sanitize_text_for_tkinter(str(ref_num_raw)); ref_auth_id_san = utils.sanitize_text_for_tkinter(str(ref_author_id_raw))
                
                self.post_text_area.insert(tk.END, "↪ Quoting ", ("quoted_ref_header"))
                clickable_ref_id_tag = f"clickable_ref_id_{original_df_index}_{ref_idx}_{ref_num_raw}"
                target_post_num_for_ref = None 
                if ref_num_san: 
                    self.post_text_area.insert(tk.END, f"{ref_num_san} ", ("quoted_ref_header", "clickable_link_style", clickable_ref_id_tag))
                    try: 
                        actual_post_num_match = re.search(r'\d+', ref_num_raw)
                        if actual_post_num_match: 
                            target_post_num_for_ref = int(actual_post_num_match.group(0))
                            self.post_text_area.tag_bind(clickable_ref_id_tag, "<Button-1>", lambda e, pn=target_post_num_for_ref: self.jump_to_post_number_from_ref(pn))
                    except ValueError: pass 
                
                if ref_auth_id_san and str(ref_auth_id_san).strip(): self.post_text_area.insert(tk.END, f"(by {ref_auth_id_san})", ("quoted_ref_header"))
                self.post_text_area.insert(tk.END, ":\n", ("quoted_ref_header"))
                
                quoted_images_list = ref_post_data.get('images', [])
                if quoted_images_list and isinstance(quoted_images_list, list):
                    self.post_text_area.insert(tk.END, "    ", ("quoted_ref_text_body"))

                    for q_img_idx, quote_img_data in enumerate(quoted_images_list):
                        img_filename_from_quote = quote_img_data.get('file')
                        if img_filename_from_quote:
                            local_image_path_from_quote = os.path.join(config.IMAGE_DIR, utils.sanitize_filename_component(os.path.basename(img_filename_from_quote)))
                            
                            if os.path.exists(local_image_path_from_quote):
                                try:
                                    img_pil_quote = Image.open(local_image_path_from_quote)
                                    img_pil_quote.thumbnail((75, 75))
                                    photo_quote = ImageTk.PhotoImage(img_pil_quote)
                                    self._quote_image_references.append(photo_quote)
                                    
                                    clickable_quote_img_tag = f"quote_img_open_{original_df_index}_{ref_idx}_{q_img_idx}"
                                    
# Insert the thumbnail image
                                    self.post_text_area.image_create(tk.END, image=photo_quote)
# Insert a clickable link icon (chain) next to it
                                    self.post_text_area.insert(tk.END, " 🔗", ('clickable_link_style', clickable_quote_img_tag))
# Bind the click event to open the full image
                                    self.post_text_area.tag_bind(
                                        clickable_quote_img_tag, 
                                        "<Button-1>", 
                                        lambda e, p=local_image_path_from_quote: utils.open_image_external(p, self.root)
                                    )
                                    if q_img_idx < len(quoted_images_list) - 1:
                                        self.post_text_area.insert(tk.END, "  ")
                                except Exception as e_quote_img:
                                    print(f"Error displaying inline quote img {img_filename_from_quote}: {e_quote_img}")
                                    self.post_text_area.insert(tk.END, f"[ErrImg]", ("quoted_ref_text_body", "image_val"))
                                    if q_img_idx < len(quoted_images_list) - 1:
                                        self.post_text_area.insert(tk.END, " ")
                            else: 
                                self.post_text_area.insert(tk.END, f"[ImgN/F]", ("quoted_ref_text_body", "image_val"))
                                if q_img_idx < len(quoted_images_list) - 1:
                                    self.post_text_area.insert(tk.END, " ")
                    
                    self.post_text_area.insert(tk.END, "\n", ("quoted_ref_text_body"))

# --- MODIFIED: Use the new helper to insert text with abbreviations and URLs ---
                self._insert_text_with_abbreviations_and_urls(self.post_text_area, ref_text_content_raw, ("quoted_ref_text_body",), f"qref_{original_df_index}_{ref_idx}")
                
                self.post_text_area.insert(tk.END, "\n")
            self.post_text_area.insert(tk.END, "\n")
        
# --- MODIFIED: Use the new helper to insert main text with abbreviations and URLs ---
        main_text_content_raw = post.get('Text', '')
        self.post_text_area.insert(tk.END, "Post Text:\n", ("bold_label"))
        self._insert_text_with_abbreviations_and_urls(self.post_text_area, main_text_content_raw, (), f"main_{original_df_index}")
        if self.current_search_active:
            search_keyword = self.keyword_entry.get().strip().lower()
            # Ensure the placeholder text is not treated as a search term
            if search_keyword and search_keyword != config.PLACEHOLDER_KEYWORD.lower():
                # Iterate through the entire text area content to find matches
                start_pos = "1.0"
                while True:
                    start_pos = self.post_text_area.search(search_keyword, start_pos, stopindex=tk.END, nocase=True)
                    if not start_pos:
                        break
                    end_pos = f"{start_pos}+{len(search_keyword)}c"
                    self.post_text_area.tag_add("search_highlight_tag", start_pos, end_pos)
                    start_pos = end_pos
        if show_images:
            images_json_data = post.get('ImagesJSON', [])
            if images_json_data and isinstance(images_json_data, list) and len(images_json_data) > 0:
                self.post_text_area.insert(tk.END, f"\n\n--- Images ({len(images_json_data)}) ---\n", "bold_label")
                for img_data in images_json_data:
                    img_filename = img_data.get('file')
                    if img_filename:
                        local_image_path = os.path.join(config.IMAGE_DIR, utils.sanitize_filename_component(os.path.basename(img_filename)))

                        if os.path.exists(local_image_path):
                            try:                              
                                img_pil = Image.open(local_image_path)
                                img_pil.thumbnail((300, 300))
                                photo = ImageTk.PhotoImage(img_pil)
                                img_label = ttk.Label(self.image_display_frame, image=photo, cursor="hand2")
                                img_label.image = photo
                                img_label.pack(pady=2, anchor='nw')
                                img_label.bind("<Button-1>", lambda e, p=local_image_path: utils.open_image_external(p, self.root))
                                self.displayed_images_references.append(photo)
                            except Exception as e:            
                                print(f"Err display img {local_image_path}: {e}")
                                self.post_text_area.insert(tk.END, f"[Err display img: {img_filename}]\n", "image_val")
                        else:                             
                            self.post_text_area.insert(tk.END, f"[Img not found: {img_filename}]\n", "image_val")
            else: 
                img_count_from_data = post.get('Image Count', 0)
                if img_count_from_data == 0 : 
                    self.post_text_area.insert(tk.END, "\n\nImage Count: 0\n", "image_val")
                else: 
                    self.post_text_area.insert(tk.END, f"\n\n--- Images ({img_count_from_data}) - metadata mismatch or files not found ---\n", "image_val")
            
            metadata_link_raw = post.get('Link')
            if metadata_link_raw and pd.notna(metadata_link_raw) and len(str(metadata_link_raw).strip()) > 0 :
                actual_metadata_link_str = utils.sanitize_text_for_tkinter(str(metadata_link_raw).strip())
                # --- MODIFIED: Use the new helper for source link too ---
                self.post_text_area.insert(tk.END, "\nSource Link: ", "bold_label")
                self._insert_text_with_abbreviations_and_urls(self.post_text_area, actual_metadata_link_str, ("clickable_link_style",) , f"metalink_{original_df_index}")
                self.post_text_area.insert(tk.END, "\n")
            elif post.get('Site') and post.get('Board'): site_text=utils.sanitize_text_for_tkinter(post.get('Site','')); board_text=utils.sanitize_text_for_tkinter(post.get('Board','')); self.post_text_area.insert(tk.END, "\nSource: ", "bold_label"); self.post_text_area.insert(tk.END, f"{site_text}/{board_text}\n", "author_val")
        
        article_found_path = None; urls_to_scan_for_articles = []
        if metadata_link_raw and isinstance(metadata_link_raw, str) and metadata_link_raw.strip(): urls_to_scan_for_articles.append(metadata_link_raw.strip())
        if main_text_content_raw: urls_to_scan_for_articles.extend(utils._extract_urls_from_text(main_text_content_raw))
        unique_urls_for_article_check = list(dict.fromkeys(urls_to_scan_for_articles))
        for url in unique_urls_for_article_check:
            if not url or not isinstance(url,str) or not url.startswith(('http://','https://')): continue
            if utils.is_excluded_domain(url, config.EXCLUDED_LINK_DOMAINS): continue
            exists, filepath = utils.check_article_exists_util(safe_filename_post_id, url)
            if exists: article_found_path = filepath; break
        
        if hasattr(self,'view_article_button'):
            if article_found_path: self.view_article_button.config(text="View Saved Article", state=tk.NORMAL, command=lambda p=article_found_path: self.open_downloaded_article(p))
            else: self.view_article_button.config(text="Article Not Saved", state=tk.DISABLED, command=lambda: None)
        if hasattr(self,'show_links_button'):
            if self.current_post_urls: self.show_links_button.config(state=tk.NORMAL)
            else: self.show_links_button.config(state=tk.DISABLED)
        if hasattr(self,'view_edit_note_button'):
            if self.df_displayed is not None and not self.df_displayed.empty and 0 <= self.current_display_idx < len(self.df_displayed): self.view_edit_note_button.config(state=tk.NORMAL)
            else: self.view_edit_note_button.config(state=tk.DISABLED)
        self._update_context_button_state()    
        
        if not self.image_display_frame.winfo_children():
            self.details_outer_frame.grid_columnconfigure(1, weight=0)
        else:
            self.details_outer_frame.grid_columnconfigure(1, weight=1)
        
        self.post_text_area.config(state=tk.DISABLED)
        self.update_post_number_label(); self.update_bookmark_button_status()
        self.root.update_idletasks()

# --- END UPDATE_DISPLAY ---

# --- START SHOW_WELCOME_MESSAGE ---

    def show_welcome_message(self):
        self.post_text_area.config(state=tk.NORMAL); self.post_text_area.delete(1.0, tk.END)
        for widget in self.image_display_frame.winfo_children(): widget.destroy()
        self.displayed_images_references = []; self._quote_image_references = []; self.current_post_urls = []
        
# --- Conditionally display the RWB logo ---
#if self.current_theme == "rwb" and self.rwb_logo_image:
# logo_label = ttk.Label(self.image_display_frame, image=self.rwb_logo_image)
# logo_label.pack(pady=20, padx=20, anchor='center')

        title="QView – Offline Q Post Explorer\n";
        para1="QView is a standalone desktop application designed for serious research into the full Q post archive. Built from the ground up for speed, clarity, and privacy, QView lets you search, explore, and annotate thousands of drops without needing an internet connection."
        para2="Unlike web-based tools that can disappear or go dark, QView gives you complete control—local images, saved article archives, powerful search tools, and customizable settings wrapped in a clean, user-friendly interface. No tracking. No fluff. Just signal."
        para3="Development is 100% community-driven and fully open-source."
        
        closing_text="🔒 No paywalls. No locked features."

        self.post_text_area.insert(tk.END, title+"\n", "welcome_title_tag");
        self.post_text_area.insert(tk.END, para1+"\n\n", "welcome_text_tag")
        self.post_text_area.insert(tk.END, para2+"\n\n", "welcome_text_tag")
        self.post_text_area.insert(tk.END, para3+"\n\n", ("welcome_text_tag", "welcome_emphasis_tag"))
        
        self.post_text_area.insert(tk.END, "\n\n", "welcome_text_tag")
        self.post_text_area.insert(tk.END, closing_text+"\n", "welcome_closing_tag")
        
# self.post_text_area.config(state=tk.DISABLED) Keep commented out for now
        
        if hasattr(self,'show_links_button'): self.show_links_button.config(state=tk.DISABLED)
        if hasattr(self,'view_article_button'): self.view_article_button.config(text="Article Not Saved", state=tk.DISABLED, command=lambda: None)
        self.update_post_number_label(is_welcome=True); self.update_bookmark_button_status(is_welcome=True)
        if hasattr(self,'view_edit_note_button'): self.view_edit_note_button.config(state=tk.DISABLED)

# --- END SHOW_WELCOME_MESSAGE ---

# --- START JUMP_TO_POST_FROM_REF ---

    def jump_to_post_number_from_ref(self, post_number):
        if post_number is None:
             messagebox.showinfo("Navigation Error", "Invalid post number reference (None).", parent=self.root); return
        if self.df_all_posts is None or self.df_all_posts.empty: 
            messagebox.showwarning("Data Error", "No post data loaded.", parent=self.root); return
        try: target_post_num_int = int(post_number)
        except (ValueError, TypeError): messagebox.showinfo("Navigation Error", f"Invalid post number format for jump: {post_number}.", parent=self.root); return
        
        matching_posts = self.df_all_posts[self.df_all_posts['Post Number'] == target_post_num_int]
        
        if not matching_posts.empty:
            original_df_idx_to_jump_to = matching_posts.index[0]
            
            if self.current_search_active:
                self.clear_search_and_show_all()
                self.root.update_idletasks() # Let the UI refresh after clearing search

            if self.df_displayed is not None and original_df_idx_to_jump_to in self.df_displayed.index: 
                # Find the position of the target post in the currently displayed list
                display_idx = self.df_displayed.index.get_loc(original_df_idx_to_jump_to)
                # Select the item in the tree. This will trigger the on_tree_select event,
                # which is the single correct place to update self.current_display_idx and the view.
                self.select_tree_item_by_idx(display_idx)
            else:
                messagebox.showinfo("Not Found", f"Post # {target_post_num_int} could not be found in the current display view.", parent=self.root)
        else: messagebox.showinfo("Not Found", f"Post # {target_post_num_int} not found in dataset.", parent=self.root)

# --- END JUMP_TO_POST_FROM_REF ---

# --- END QPOSTVIEWER_CLASS_DEFINITION ---