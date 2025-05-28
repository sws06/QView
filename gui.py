# --- START GUI_PY_HEADER ---
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from tkcalendar import Calendar
from PIL import Image, ImageTk
import pandas as pd
import datetime
import os # For os.path.join, os.path.abspath, os.getcwd
import webbrowser # For help links and fallback URL opening
import threading # For non-blocking article download

import config
import utils
import data as app_data
import settings # Import the new settings module
# --- END GUI_PY_HEADER ---

# --- START TOOLTIP_CLASS ---
class Tooltip:
    """
    Creates a tooltip for a given widget.
    """
    def __init__(self, widget, text_generator, delay=700, follow=True):
        self.widget = widget
        self.text_generator = text_generator # A function that returns the text to display
        self.delay = delay  # Milliseconds
        self.follow = follow # Tooltip follows mouse motion
        self.tip_window = None
        self.id = None
        self.widget.bind("<Enter>", self.enter)
        self.widget.bind("<Leave>", self.leave)
        self.widget.bind("<ButtonPress>", self.leave) # Hide on click too

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

        # Position the tooltip
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 1

        self.tip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")

        label = tk.Label(tw, text=text_to_show, justify=tk.LEFT,
                         background="#FFFFE0",
                         foreground="#000000",
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

        # === START::WINDOW_POSITIONING ===
        window_width = 1024
        window_height = 720
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        center_x = int(screen_width/2 - window_width / 2)
        center_y = int(screen_height/2 - window_height / 2)
        if center_y + window_height > screen_height - 40:
             center_y = screen_height - 40 - window_height
        if center_y < 0:
            center_y = 0
        self.root.geometry(f'{window_width}x{window_height}+{center_x}+{center_y}')
        self.root.minsize(800, 600)
        # === END::WINDOW_POSITIONING ===

        self.displayed_images_references = []
        self.current_post_urls = []
        self.current_post_downloaded_article_path = None

        self.app_settings = settings.load_settings()

        self.bookmarked_posts = utils.load_bookmarks_from_file(config.BOOKMARKS_FILE_PATH)
        self.user_notes = utils.load_user_notes(config.USER_NOTES_FILE_PATH)

        self.df_all_posts = app_data.load_or_parse_data()
        # self.df_all_posts is checked after welcome message now

        # Initialize df_displayed and current_display_idx, might be updated after welcome
        self.df_displayed = pd.DataFrame()
        self.current_display_idx = -1
        self.current_search_active = False


        self.current_theme = self.app_settings.get("theme", settings.DEFAULT_SETTINGS["theme"])
        self.placeholder_fg_color_dark = "grey"
        self.placeholder_fg_color_light = "#757575"
        self.link_label_fg_dark = "#6DAEFF"
        self.link_label_fg_light = "#0056b3"

        self.style = ttk.Style()

        self.tree_frame = ttk.Frame(root)
        self.tree_frame.grid(row=0, column=0, padx=10, pady=(10,0), sticky="nswe")
        root.grid_rowconfigure(0, weight=1)
        root.grid_columnconfigure(0, weight=1, minsize=280)
        # ====> PASTE THIS MISSING BLOCK HERE <====
        self.post_tree = ttk.Treeview(self.tree_frame, columns=("Post #", "Date", "Bookmarked"), show="headings")
        self.scrollbar_y = ttk.Scrollbar(self.tree_frame, orient="vertical", command=self.post_tree.yview)
        self.post_tree.configure(yscrollcommand=self.scrollbar_y.set)
        self.post_tree.heading("Post #", text="Post #", anchor='w')
        self.post_tree.heading("Date", text="Date", anchor='w')
        self.post_tree.heading("Bookmarked", text="★", anchor='center')
        self.post_tree.column("Post #", width=70, stretch=tk.NO, anchor='w')
        self.post_tree.column("Date", width=110, stretch=tk.YES, anchor='w')
        self.post_tree.column("Bookmarked", width=30, stretch=tk.NO, anchor='center')
        self.post_tree.grid(row=0, column=0, sticky="nswe")
        self.scrollbar_y.grid(row=0, column=1, sticky="ns")
        self.tree_frame.grid_rowconfigure(0, weight=1)
        self.tree_frame.grid_columnconfigure(0, weight=1)
        # ====> END OF MISSING BLOCK <====
        self.details_outer_frame = ttk.Frame(root)
        self.details_outer_frame.grid(row=0, column=1, padx=(0,10), pady=(10,0), sticky="nswe")
        root.grid_columnconfigure(1, weight=3)
        self.details_outer_frame.grid_rowconfigure(0, weight=2) # Post text area
        self.details_outer_frame.grid_rowconfigure(1, weight=1) # Image display
        # Note section is now a popup, row 2 configuration might not be needed or set to weight 0
        self.details_outer_frame.grid_rowconfigure(2, weight=0)
        # ====> START OF BLOCK TO PASTE <====
        self.text_area_frame = ttk.Frame(self.details_outer_frame)
        self.text_area_frame.grid(row=0, column=0, sticky="nswe")
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

        self.image_display_frame = ttk.Frame(self.details_outer_frame)
        self.image_display_frame.grid(row=1, column=0, sticky="nswe", pady=(5,0))
        self.image_display_frame.grid_columnconfigure(0, weight=1)
        # ====> END OF BLOCK TO PASTE <====
        self.post_text_area.bind("<KeyPress>", self._prevent_text_edit)
        self.configure_text_tags()

        controls_main_frame = ttk.Frame(root)
        controls_main_frame.grid(row=1, column=0, columnspan=2, padx=10, pady=(5,10), sticky="ew")
        
        nav_frame = ttk.Frame(controls_main_frame)
        nav_frame.pack(pady=(0,5), fill=tk.X)
        self.prev_button = ttk.Button(nav_frame, text="<< Prev", command=self.prev_post, width=8)
        self.prev_button.pack(side="left", padx=2)
        self.post_number_label = ttk.Label(nav_frame, text="", width=35, anchor="center", font=('Arial', 11, 'bold'))
        self.post_number_label.pack(side="left", padx=5, expand=True, fill=tk.X)
        self.next_button = ttk.Button(nav_frame, text="Next >>", command=self.next_post, width=8)
        self.next_button.pack(side="left", padx=2)

        actions_frame = ttk.Labelframe(controls_main_frame, text="Search & Actions", padding=(10,5))
        actions_frame.pack(pady=5, fill=tk.X, expand=True)

        search_fields_frame = ttk.Frame(actions_frame)
        search_fields_frame.pack(fill=tk.X, pady=2)
        self.post_entry = ttk.Entry(search_fields_frame, width=12, font=('Arial', 10))
        self.post_entry.pack(side=tk.LEFT, padx=(0,2), expand=True, fill=tk.X)
        ttk.Button(search_fields_frame, text="Go", command=self.search_post_by_number, width=4).pack(side=tk.LEFT, padx=(0,10))
        self.post_entry.bind("<FocusIn>", lambda e, p=config.PLACEHOLDER_POST_NUM: self.clear_placeholder(e, p, self.post_entry))
        self.post_entry.bind("<FocusOut>", lambda e, p=config.PLACEHOLDER_POST_NUM: self.restore_placeholder(e, p, self.post_entry))
        self.post_entry.bind("<Return>", lambda event: self.search_post_by_number())

        self.keyword_entry = ttk.Entry(search_fields_frame, width=20, font=('Arial', 10))
        self.keyword_entry.pack(side=tk.LEFT, padx=(0,2), expand=True, fill=tk.X)
        ttk.Button(search_fields_frame, text="Go", command=self.search_by_keyword, width=4).pack(side=tk.LEFT)
        self.keyword_entry.bind("<FocusIn>", lambda e, p=config.PLACEHOLDER_KEYWORD: self.clear_placeholder(e, p, self.keyword_entry))
        self.keyword_entry.bind("<FocusOut>", lambda e, p=config.PLACEHOLDER_KEYWORD: self.restore_placeholder(e, p, self.keyword_entry))
        self.keyword_entry.bind("<Return>", lambda event: self.search_by_keyword())

        buttons_frame1 = ttk.Frame(actions_frame)
        buttons_frame1.pack(fill=tk.X, pady=(5,2))
        ttk.Button(buttons_frame1, text="Search by Date", command=self.show_calendar).pack(side=tk.LEFT, padx=2, expand=True, fill=tk.X)
        ttk.Button(buttons_frame1, text="Delta Search", command=self.show_day_delta_dialog).pack(side=tk.LEFT, padx=2, expand=True, fill=tk.X)

        self.todays_deltas_button = ttk.Button(buttons_frame1, text="Today's Deltas", command=self.search_today_deltas)
        self.todays_deltas_button.pack(side=tk.LEFT, padx=2, expand=True, fill=tk.X)

        def get_todays_deltas_tooltip_text():
            return f"Posts from {datetime.datetime.now().strftime('%m/%d')} (all years)"
        Tooltip(self.todays_deltas_button, get_todays_deltas_tooltip_text)

        buttons_frame2 = ttk.Frame(actions_frame)
        buttons_frame2.pack(fill=tk.X, pady=2)
        self.clear_search_button = ttk.Button(buttons_frame2, text="Show All Posts", command=self.clear_search_and_show_all)
        self.clear_search_button.pack(side=tk.LEFT, padx=2, expand=True, fill=tk.X)
        self.clear_search_button.config(state=tk.DISABLED)

        self.show_links_button = ttk.Button(buttons_frame2, text="Show Links", command=self.show_post_links_window_external, state=tk.DISABLED)
        self.show_links_button.pack(side=tk.LEFT, padx=2, expand=True, fill=tk.X)

        self.view_article_button = ttk.Button(buttons_frame2, text="Article Not Saved", command=lambda: None, state=tk.DISABLED)
        self.view_article_button.pack(side=tk.LEFT, padx=2, expand=True, fill=tk.X)

        buttons_frame3 = ttk.Frame(actions_frame)
        buttons_frame3.pack(fill=tk.X, pady=2)
        self.bookmark_button = ttk.Button(buttons_frame3, text="Bookmark This Post", command=self.toggle_current_post_bookmark)
        self.bookmark_button.pack(side=tk.LEFT, padx=2, expand=True, fill=tk.X)
        self.bookmark_button.config(state=tk.DISABLED)
        self.view_bookmarks_button = ttk.Button(buttons_frame3, text=f"View Bookmarks ({len(self.bookmarked_posts)})", command=self.view_bookmarked_gui_posts)
        self.view_bookmarks_button.pack(side=tk.LEFT, padx=2, expand=True, fill=tk.X)

        self.view_edit_note_button = ttk.Button(buttons_frame3, text="View/Edit Note", command=self.show_note_popup, state=tk.DISABLED)
        self.view_edit_note_button.pack(side=tk.LEFT, padx=2, expand=True, fill=tk.X)

        bottom_buttons_frame = ttk.Frame(controls_main_frame)
        bottom_buttons_frame.pack(pady=(10,0), fill=tk.X, expand=True)
        self.export_var = tk.StringVar(value="HTML")
        ttk.OptionMenu(bottom_buttons_frame, self.export_var, "HTML", "HTML", "CSV").pack(side=tk.LEFT, padx=(0,5), fill=tk.X)
        ttk.Button(bottom_buttons_frame, text="Export Displayed List", command=self.export_displayed_list).pack(side=tk.LEFT, expand=True, fill=tk.X)

        self.content_sync_button = ttk.Button(bottom_buttons_frame, text="Content Sync", command=self.show_download_window)
        self.content_sync_button.pack(side=tk.LEFT, padx=5, fill=tk.X)

        self.settings_button = ttk.Button(bottom_buttons_frame, text="Settings", command=self.show_settings_window)
        self.settings_button.pack(side=tk.LEFT, padx=5, fill=tk.X)

        self.theme_toggle_button = ttk.Button(bottom_buttons_frame, text="Dark to Light", command=self.toggle_theme)
        self.theme_toggle_button.pack(side=tk.LEFT, padx=5, fill=tk.X)

        self.help_button = ttk.Button(bottom_buttons_frame, text="Help & Info", command=self.show_help_window)
        self.help_button.pack(side=tk.LEFT, padx=5, fill=tk.X)

        self.about_button = ttk.Button(bottom_buttons_frame, text="About", command=self.show_about_dialog)
        self.about_button.pack(side=tk.LEFT, padx=5, fill=tk.X)

        ttk.Button(bottom_buttons_frame, text="Quit App", command=self.on_closing).pack(side=tk.LEFT, padx=5, fill=tk.X)

        if self.current_theme == "light":
            self.apply_light_theme()
        else:
            self.apply_dark_theme()

        self.restore_placeholder(None, config.PLACEHOLDER_POST_NUM, self.post_entry)
        self.restore_placeholder(None, config.PLACEHOLDER_KEYWORD, self.keyword_entry)

        self.post_tree.bind("<<TreeviewSelect>>", self.on_tree_select)
        self.post_tree.bind("<Up>", self.on_tree_arrow_nav)
        self.post_tree.bind("<Down>", self.on_tree_arrow_nav)
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        self._init_complete = False

        # Initial data loading and tree population
        if self.df_all_posts is not None and not self.df_all_posts.empty:
            self.df_all_posts = self.df_all_posts.reset_index(drop=True)
            self.df_displayed = self.df_all_posts.copy()
            # Populate the tree, but DO NOT select the first item yet to let welcome message show
            self.repopulate_treeview(self.df_displayed, select_first_item=False)
        elif self.df_all_posts is None: # Critical load failure from data.py
            messagebox.showerror("Critical Error", "Failed to load any post data. Application cannot continue.")
            self.root.destroy()
            return # Stop __init__

        # Show the welcome message in the text area AFTER tree might be populated
        self.show_welcome_message()

        self._init_complete = True
    # --- END __INIT__ ---
    # --- END __INIT__ ---

    # --- START ON_CLOSING ---
    def on_closing(self):
        utils.save_bookmarks_to_file(self.bookmarked_posts, config.BOOKMARKS_FILE_PATH)
        utils.save_user_notes(self.user_notes, config.USER_NOTES_FILE_PATH) # Save user notes
        self.root.destroy()
    # --- END ON_CLOSING ---

    # === START::THEME_TOGGLE ===
    # --- START APPLY_DARK_THEME ---
    def apply_dark_theme(self):
        self.current_theme = "dark"
        self.style.theme_use('clam')

        bg_color = "#2b2b2b"; fg_color = "#e0e0e0"; entry_bg = "#3c3f41"
        button_bg = "#4f4f4f"; button_active_bg = "#6a6a6a"; tree_bg = "#3c3f41"
        tree_sel_bg = "#0078D7"; tree_sel_fg = "#ffffff"; heading_bg = "#4f4f4f"
        scrollbar_bg = '#4f4f4f'; scrollbar_trough = '#3c3f41'; scrollbar_arrow = '#e0e0e0'

        self.root.configure(bg=bg_color)
        self.style.configure(".", background=bg_color, foreground=fg_color, font=('Arial', 10))
        self.style.configure("TFrame", background=bg_color)
        self.style.configure("TLabel", background=bg_color, foreground=fg_color, padding=3)
        self.style.configure("TButton", background=button_bg, foreground=fg_color, padding=5, font=('Arial', 9, 'bold'), borderwidth=1, relief=tk.RAISED)
        self.style.map("TButton", background=[("active", button_active_bg), ("pressed", "#5a5a5a")], relief=[("pressed", tk.SUNKEN)])
        self.style.configure("Treeview", background=tree_bg, foreground=fg_color, fieldbackground=tree_bg, borderwidth=1, relief=tk.FLAT)
        self.style.map("Treeview", background=[("selected", tree_sel_bg)], foreground=[("selected", tree_sel_fg)])
        self.style.configure("Treeview.Heading", background=heading_bg, foreground=fg_color, font=('Arial', 10, 'bold'), relief=tk.FLAT, padding=3)
        self.style.configure("TEntry", fieldbackground=entry_bg, foreground=fg_color, insertbackground=fg_color, relief=tk.SUNKEN, borderwidth=1)
        self.style.configure("TLabelframe", background=bg_color, foreground=fg_color, relief=tk.GROOVE, borderwidth=1, padding=5)
        self.style.configure("TLabelframe.Label", background=bg_color, foreground=fg_color, font=('Arial', 10, 'bold'))
        self.style.configure("Vertical.TScrollbar", background=scrollbar_bg, troughcolor=scrollbar_trough, arrowcolor=scrollbar_arrow, arrowsize=15, width=15)
        self.style.map('Vertical.TScrollbar', background=[('active', button_active_bg)])
        self.style.configure("TCombobox", fieldbackground=entry_bg, background=button_bg, foreground=fg_color, arrowcolor=fg_color, selectbackground=entry_bg, selectforeground=fg_color)
        self.style.map("TCombobox", fieldbackground=[("readonly", entry_bg)], background=[("readonly", button_bg)], foreground=[("readonly", fg_color)], lightcolor=[("readonly", button_bg)], darkcolor=[("readonly", button_bg)])

        self.post_text_area.configure(bg=entry_bg, fg=fg_color, insertbackground=fg_color, selectbackground=tree_sel_bg)
        # if hasattr(self, 'note_text_area'): self.note_text_area.configure(bg=entry_bg, fg=fg_color, insertbackground=fg_color, selectbackground=tree_sel_bg) # Old embedded notes
        if hasattr(self, 'image_display_frame'): self.image_display_frame.configure(style="TFrame")

        self.post_text_area.tag_configure("bold_label", foreground="#a9b7c6")
        self.post_text_area.tag_configure("post_number_val", foreground="#FFCB6B")
        self.post_text_area.tag_configure("date_val", foreground="#A5C25C")
        self.post_text_area.tag_configure("author_val", foreground="#B0B0B0")
        self.post_text_area.tag_configure("themes_val", foreground="#C39AC9")
        self.post_text_area.tag_configure("image_val", foreground="#589DF6")
        self.post_text_area.tag_configure("clickable_link_style", foreground=self.link_label_fg_dark)
        self.post_text_area.tag_configure("bookmarked_header", foreground="#FFD700")
        self.post_text_area.tag_configure("quoted_ref_header", foreground="#ABBFD0")
        self.post_text_area.tag_configure("quoted_ref_text_body", foreground="#cccccc")
        self.post_text_area.tag_configure("welcome_title_tag", foreground="#FFCB6B")
        self.post_text_area.tag_configure("welcome_text_tag", foreground="#e0e0e0")
        self.post_text_area.tag_configure("welcome_emphasis_tag", foreground="#A5C25C")
        self.post_text_area.tag_configure("welcome_closing_tag", foreground="#FFD700")


        if hasattr(self, 'theme_toggle_button'): self.theme_toggle_button.config(text="Dark to Light")
        if hasattr(self, 'post_entry') and self.post_entry.winfo_exists(): self.restore_placeholder(None, config.PLACEHOLDER_POST_NUM, self.post_entry)
        if hasattr(self, 'keyword_entry') and self.keyword_entry.winfo_exists(): self.restore_placeholder(None, config.PLACEHOLDER_KEYWORD, self.keyword_entry)
    # --- END APPLY_DARK_THEME ---

    # --- START APPLY_LIGHT_THEME ---
    def apply_light_theme(self):
        self.current_theme = "light"
        self.style.theme_use('clam')
        bg_color = "#f0f0f0"; fg_color = "#000000"; entry_bg = "#ffffff"; button_bg = "#e1e1e1"; button_active_bg = "#d1d1d1"; tree_bg = "#ffffff"; tree_sel_bg = "#0078D7"; tree_sel_fg = "#ffffff"; heading_bg = "#e1e1e1"; scrollbar_bg = '#c1c1c1'; scrollbar_trough = '#e1e1e1'; scrollbar_arrow = '#000000'

        self.root.configure(bg=bg_color)
        self.style.configure(".", background=bg_color, foreground=fg_color, font=('Arial', 10))
        self.style.configure("TFrame", background=bg_color)
        self.style.configure("TLabel", background=bg_color, foreground=fg_color, padding=3)
        self.style.configure("TButton", background=button_bg, foreground=fg_color, padding=5, font=('Arial', 9, 'bold'), borderwidth=1, relief=tk.RAISED)
        self.style.map("TButton", background=[("active", button_active_bg), ("pressed", "#c1c1c1")], relief=[("pressed", tk.SUNKEN)])
        self.style.configure("Treeview", background=tree_bg, foreground=fg_color, fieldbackground=tree_bg, borderwidth=1, relief=tk.FLAT)
        self.style.map("Treeview", background=[("selected", tree_sel_bg)], foreground=[("selected", tree_sel_fg)])
        self.style.configure("Treeview.Heading", background=heading_bg, foreground=fg_color, font=('Arial', 10, 'bold'), relief=tk.FLAT, padding=3)
        self.style.configure("TEntry", fieldbackground=entry_bg, foreground=fg_color, insertbackground=fg_color, relief=tk.SUNKEN, borderwidth=1)
        self.style.configure("TLabelframe", background=bg_color, foreground=fg_color, relief=tk.GROOVE, borderwidth=1, padding=5)
        self.style.configure("TLabelframe.Label", background=bg_color, foreground=fg_color, font=('Arial', 10, 'bold'))
        self.style.configure("Vertical.TScrollbar", background=scrollbar_bg, troughcolor=scrollbar_trough, arrowcolor=scrollbar_arrow, arrowsize=15, width=15)
        self.style.map('Vertical.TScrollbar', background=[('active', '#b1b1b1')])
        self.style.configure("TCombobox", fieldbackground=entry_bg, background=button_bg, foreground=fg_color, arrowcolor=fg_color, selectbackground=entry_bg, selectforeground=fg_color)
        self.style.map("TCombobox", fieldbackground=[("readonly", entry_bg)], background=[("readonly", button_bg)], foreground=[("readonly", fg_color)], lightcolor=[("readonly", button_bg)], darkcolor=[("readonly", button_bg)])
        self.post_text_area.configure(bg=entry_bg, fg=fg_color, insertbackground=fg_color, selectbackground=tree_sel_bg)
        # if hasattr(self, 'note_text_area'): self.note_text_area.configure(bg=entry_bg, fg=fg_color, insertbackground=fg_color, selectbackground=tree_sel_bg) # Old embedded notes
        if hasattr(self, 'image_display_frame'): self.image_display_frame.configure(style="TFrame")
        self.post_text_area.tag_configure("bold_label", foreground="#333333"); self.post_text_area.tag_configure("post_number_val", foreground="#D9534F"); self.post_text_area.tag_configure("date_val", foreground="#5CB85C"); self.post_text_area.tag_configure("author_val", foreground="#555555"); self.post_text_area.tag_configure("themes_val", foreground="#8E44AD"); self.post_text_area.tag_configure("image_val", foreground="#337AB7"); self.post_text_area.tag_configure("clickable_link_style", foreground=self.link_label_fg_light); self.post_text_area.tag_configure("bookmarked_header", foreground="#F0AD4E"); self.post_text_area.tag_configure("quoted_ref_header", foreground="#4A4A4A"); self.post_text_area.tag_configure("quoted_ref_text_body", foreground="#202020")
        self.post_text_area.tag_configure("welcome_title_tag", foreground="#D9534F")
        self.post_text_area.tag_configure("welcome_text_tag", foreground="#000000")
        self.post_text_area.tag_configure("welcome_emphasis_tag", foreground="#8E44AD")
        self.post_text_area.tag_configure("welcome_closing_tag", foreground="#5CB85C")

        if hasattr(self, 'theme_toggle_button'): self.theme_toggle_button.config(text="Into the Dark")
        if hasattr(self, 'post_entry') and self.post_entry.winfo_exists(): self.restore_placeholder(None, config.PLACEHOLDER_POST_NUM, self.post_entry)
        if hasattr(self, 'keyword_entry') and self.keyword_entry.winfo_exists(): self.restore_placeholder(None, config.PLACEHOLDER_KEYWORD, self.keyword_entry)
    # --- END APPLY_LIGHT_THEME ---

    # --- START TOGGLE_THEME ---
    def toggle_theme(self):
        if self.current_theme == "dark":
            self.apply_light_theme()
        else:
            self.apply_dark_theme()
        # Refresh display (either current post or welcome message) to apply new theme styles to text area
        if self.current_display_idx != -1 and not (self.df_displayed is None or self.df_displayed.empty):
             self.update_display()
        else:
             self.show_welcome_message()
    # --- END TOGGLE_THEME ---
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
        self.post_text_area.tag_configure("clickable_link_style", underline=True)

        def show_hand_cursor(event): event.widget.config(cursor="hand2")
        def show_arrow_cursor(event): event.widget.config(cursor=self.default_text_area_cursor)

        self.post_text_area.tag_bind("clickable_link_style", "<Enter>", show_hand_cursor)
        self.post_text_area.tag_bind("clickable_link_style", "<Leave>", show_arrow_cursor)

        self.post_text_area.tag_configure("bookmarked_header", font=(default_font_name, 11, "bold"))
        self.post_text_area.tag_configure("quoted_ref_header", font=(default_font_name, 10, "italic", "bold"), lmargin1=20, lmargin2=20, spacing1=5)
        self.post_text_area.tag_configure("quoted_ref_text_body", font=(default_font_name, 10, "italic"), lmargin1=25, lmargin2=25, spacing3=5)

        # Tags for Welcome Message
        self.post_text_area.tag_configure("welcome_title_tag", font=(default_font_name, 14, "bold"), justify=tk.CENTER, spacing1=5, spacing3=10)
        self.post_text_area.tag_configure("welcome_text_tag", font=(default_font_name, 10), lmargin1=15, lmargin2=15, spacing1=3, spacing3=3, wrap=tk.WORD)
        self.post_text_area.tag_configure("welcome_emphasis_tag", font=(default_font_name, 10, "italic"))
        self.post_text_area.tag_configure("welcome_closing_tag", font=(default_font_name, 10, "bold"), justify=tk.CENTER, spacing1=10)
    # --- END CONFIGURE_TEXT_TAGS ---

    # --- START _PREVENT_TEXT_EDIT ---
    def _prevent_text_edit(self, event):
        if event.state & 0x0004 and event.keysym.lower() == 'c': # Allow Ctrl+C
            return
        # Allow specific navigation and selection keys
        allowed_nav_keys = ["Left", "Right", "Up", "Down", "Prior", "Next", "Home", "End",
                            "Control_L", "Control_R", "Shift_L", "Shift_R", "Alt_L", "Alt_R",
                            "leftarrow", "rightarrow", "uparrow", "downarrow", "PageUp", "PageDown"] # adding keysyms
        if event.keysym in allowed_nav_keys or event.keysym.lower() in ["a"] and event.state & 0x0004: # Allow Ctrl+A
            return
        return "break" # Prevent modification
    # --- END _PREVENT_TEXT_EDIT ---

    # --- START _INSERT_TEXT_WITH_CLICKABLE_URLS ---
    def _insert_text_with_clickable_urls(self, text_content_raw, base_tags_tuple, main_post_original_df_index, link_event_tag_prefix):
        text_content = utils.sanitize_text_for_tkinter(text_content_raw)

        if not isinstance(text_content, str) or not text_content.strip():
            self.post_text_area.insert(tk.END, str(text_content) if pd.notna(text_content) else "", base_tags_tuple if base_tags_tuple else ())
            return

        urls_in_segment_all = utils._extract_urls_from_text(text_content)
        for url in urls_in_segment_all:
            if url not in self.current_post_urls:
                self.current_post_urls.append(url)

        last_end = 0
        for url_match in config.URL_REGEX.finditer(text_content):
            start, end = url_match.span()
            if start > last_end:
                self.post_text_area.insert(tk.END, text_content[last_end:start], base_tags_tuple if base_tags_tuple else ())

            url = url_match.group(0)
            clickable_tag_instance = f"{link_event_tag_prefix}_url_{url_match.start()}"
            current_tags = list(base_tags_tuple) if base_tags_tuple else []
            current_tags.extend(['clickable_link_style', clickable_tag_instance])
            self.post_text_area.insert(tk.END, url, tuple(current_tags))
            self.post_text_area.tag_bind(clickable_tag_instance, "<Button-1>", lambda e, u=url: utils.open_link_with_preference(u, self.app_settings))
            last_end = end

        if last_end < len(text_content):
            self.post_text_area.insert(tk.END, text_content[last_end:], base_tags_tuple if base_tags_tuple else ())
    # --- END _INSERT_TEXT_WITH_CLICKABLE_URLS ---

    # --- START UPDATE_DISPLAY ---
    def update_display(self):
        for widget in self.image_display_frame.winfo_children(): widget.destroy()
        self.displayed_images_references = []; self.current_post_urls = []; self.current_post_downloaded_article_path = None
        self.post_text_area.config(state=tk.NORMAL); self.post_text_area.delete(1.0, tk.END)

        show_images = True

        if self.df_displayed is None or self.df_displayed.empty or not (0 <= self.current_display_idx < len(self.df_displayed)):
            self.show_welcome_message()
            return

        original_df_index = self.df_displayed.index[self.current_display_idx]
        post = self.df_all_posts.loc[original_df_index]

        post_number_val = post.get('Post Number'); filename_post_id = str(post_number_val if pd.notna(post_number_val) else original_df_index)
        safe_filename_post_id = utils.sanitize_filename_component(filename_post_id)
        pn_display_raw = post.get('Post Number', original_df_index); pn_str = f"#{pn_display_raw}" if pd.notna(pn_display_raw) else f"(Idx:{original_df_index})"
        is_bookmarked = original_df_index in self.bookmarked_posts; bookmark_indicator_text_raw = "[BOOKMARKED]" if is_bookmarked else ""
        self.post_text_area.insert(tk.END, utils.sanitize_text_for_tkinter(f"QView Post {pn_str} "), "post_number_val")
        if is_bookmarked: self.post_text_area.insert(tk.END, utils.sanitize_text_for_tkinter(bookmark_indicator_text_raw) + "\n", "bookmarked_header")
        else: self.post_text_area.insert(tk.END, "\n")
        dt_val = post.get('Datetime_UTC')
        if pd.notna(dt_val):
            dt_utc = dt_val.tz_localize('UTC') if dt_val.tzinfo is None else dt_val; dt_local = dt_utc.tz_convert(None)
            date_local_str = utils.sanitize_text_for_tkinter(f"{dt_local.strftime('%Y-%m-%d %H:%M:%S %Z')} (Local)\n"); date_utc_str = utils.sanitize_text_for_tkinter(f"{dt_utc.strftime('%Y-%m-%d %H:%M:%S %Z')} (UTC)\n")
            self.post_text_area.insert(tk.END, utils.sanitize_text_for_tkinter("Date: "), "bold_label"); self.post_text_area.insert(tk.END, date_local_str, "date_val"); self.post_text_area.insert(tk.END, utils.sanitize_text_for_tkinter("      "), "bold_label"); self.post_text_area.insert(tk.END, date_utc_str, "date_val")
        else: self.post_text_area.insert(tk.END, utils.sanitize_text_for_tkinter("Date: No Date\n"), "bold_label")
        author_text_raw = post.get('Author', ''); tripcode_text_raw = post.get('Tripcode', ''); author_text = utils.sanitize_text_for_tkinter(author_text_raw); tripcode_text = utils.sanitize_text_for_tkinter(tripcode_text_raw)
        if author_text and pd.notna(author_text_raw): self.post_text_area.insert(tk.END, utils.sanitize_text_for_tkinter("Author: "), "bold_label"); self.post_text_area.insert(tk.END, f"{author_text}\n", "author_val")
        if tripcode_text and pd.notna(tripcode_text_raw): self.post_text_area.insert(tk.END, utils.sanitize_text_for_tkinter("Tripcode: "), "bold_label"); self.post_text_area.insert(tk.END, f"{tripcode_text}\n", "author_val")
        themes_list = post.get('Themes', [])
        if themes_list and isinstance(themes_list, list) and len(themes_list) > 0: themes_str = utils.sanitize_text_for_tkinter(f"{', '.join(themes_list)}\n"); self.post_text_area.insert(tk.END, utils.sanitize_text_for_tkinter("Themes: "), "bold_label"); self.post_text_area.insert(tk.END, themes_str, "themes_val")
        referenced_posts_raw_data = post.get('Referenced Posts Raw')
        if isinstance(referenced_posts_raw_data, list) and referenced_posts_raw_data:
            self.post_text_area.insert(tk.END, utils.sanitize_text_for_tkinter("\nReferenced Content:\n"), ("bold_label"))
            for ref_idx, ref_post_data in enumerate(referenced_posts_raw_data):
                if not isinstance(ref_post_data, dict): continue
                ref_num_raw = ref_post_data.get('reference', ''); ref_author_id_raw = ref_post_data.get('author_id'); ref_text_content_raw = ref_post_data.get('text', '[No text in reference]'); ref_num = utils.sanitize_text_for_tkinter(str(ref_num_raw)); ref_author_id = utils.sanitize_text_for_tkinter(str(ref_author_id_raw)); header_parts = ["↪ Quoting "];
                if ref_num: header_parts.append(f"{ref_num} ");
                if ref_author_id and str(ref_author_id).strip(): header_parts.append(f"(by {ref_author_id})")
                header_parts.append(":\n"); self.post_text_area.insert(tk.END, utils.sanitize_text_for_tkinter("".join(header_parts)), ("quoted_ref_header")); self._insert_text_with_clickable_urls(ref_text_content_raw, ("quoted_ref_text_body",), original_df_index, f"qref_{original_df_index}_{ref_idx}"); self.post_text_area.insert(tk.END, "\n")
            self.post_text_area.insert(tk.END, "\n")
        main_text_content_raw = post.get('Text', '');
        self.post_text_area.insert(tk.END, utils.sanitize_text_for_tkinter("Post Text:\n"), ("bold_label"));
        self._insert_text_with_clickable_urls(main_text_content_raw, (), original_df_index, f"main_{original_df_index}")

        if show_images:
            images_json_data = post.get('ImagesJSON', [])
            if images_json_data and isinstance(images_json_data, list) and len(images_json_data) > 0:
                self.post_text_area.insert(tk.END, utils.sanitize_text_for_tkinter(f"\n\n--- Images ({len(images_json_data)}) ---\n"), "bold_label")
                for img_data in images_json_data:
                    img_filename = img_data.get('file')
                    if img_filename:
                        local_image_path = os.path.join(config.IMAGE_DIR, utils.sanitize_filename_component(os.path.basename(img_filename)))
                        if os.path.exists(local_image_path):
                            try:
                                img_pil = Image.open(local_image_path); img_pil.thumbnail((300, 300)); photo = ImageTk.PhotoImage(img_pil)
                                img_label = ttk.Label(self.image_display_frame, image=photo, cursor="hand2"); img_label.image = photo; img_label.pack(pady=2, anchor='nw'); img_label.bind("<Button-1>", lambda e, path=local_image_path: utils.open_image_external(path, self.root)); self.displayed_images_references.append(photo)
                            except Exception as e: print(f"Error loading/displaying image {local_image_path}: {e}"); self.post_text_area.insert(tk.END, utils.sanitize_text_for_tkinter(f"[Error displaying image: {img_filename}]\n"), "image_val")
                        else: self.post_text_area.insert(tk.END, utils.sanitize_text_for_tkinter(f"[Image not found: {img_filename}]\n"), "image_val")
            else:
                img_count_from_data = post.get('Image Count', 0)
                if img_count_from_data == 0 : self.post_text_area.insert(tk.END, utils.sanitize_text_for_tkinter(f"\n\nImage Count: 0\n"), "image_val")
                else: self.post_text_area.insert(tk.END, utils.sanitize_text_for_tkinter(f"\n\n--- Images ({img_count_from_data}) - files not found ---\n"), "image_val")

        metadata_link_raw = post.get('Link')
        if metadata_link_raw and pd.notna(metadata_link_raw) and len(str(metadata_link_raw).strip()) > 0 :
            actual_metadata_link_str = utils.sanitize_text_for_tkinter(str(metadata_link_raw).strip())
            self.post_text_area.insert(tk.END, utils.sanitize_text_for_tkinter("\nSource Link: "), "bold_label"); self._insert_text_with_clickable_urls(actual_metadata_link_str, ("clickable_link_style",) , original_df_index, f"metalink_{original_df_index}"); self.post_text_area.insert(tk.END, "\n")
        elif post.get('Site') and post.get('Board'): site_text = utils.sanitize_text_for_tkinter(post.get('Site','')); board_text = utils.sanitize_text_for_tkinter(post.get('Board','')); self.post_text_area.insert(tk.END, utils.sanitize_text_for_tkinter("\nSource: "), "bold_label"); self.post_text_area.insert(tk.END, f"{site_text}/{board_text}\n", "author_val")

        article_found_path = None
        urls_to_scan_for_articles = []
        if metadata_link_raw and isinstance(metadata_link_raw, str) and metadata_link_raw.strip(): urls_to_scan_for_articles.append(metadata_link_raw.strip())
        if main_text_content_raw: urls_to_scan_for_articles.extend(utils._extract_urls_from_text(main_text_content_raw))
        unique_urls_for_article_check = list(dict.fromkeys(urls_to_scan_for_articles))

        for url in unique_urls_for_article_check:
            if not url or not isinstance(url, str) or not url.startswith(('http://', 'https://')): continue
            if utils.is_excluded_domain(url, config.EXCLUDED_LINK_DOMAINS): continue
            exists, filepath = utils.check_article_exists_util(safe_filename_post_id, url)
            if exists: article_found_path = filepath; break

        if hasattr(self, 'view_article_button'):
            if article_found_path:
                self.view_article_button.config(text="View Saved Article", state=tk.NORMAL, command=lambda p=article_found_path: self.open_downloaded_article(p))
            else:
                self.view_article_button.config(text="Article Not Saved", state=tk.DISABLED, command=lambda: None)

        if hasattr(self, 'show_links_button'):
            if self.current_post_urls: self.show_links_button.config(state=tk.NORMAL)
            else: self.show_links_button.config(state=tk.DISABLED)

        # --- Enable/Disable View/Edit Note button ---
        if hasattr(self, 'view_edit_note_button'):
            # This condition checks if a valid post is currently being displayed
            if self.df_displayed is not None and not self.df_displayed.empty and \
               0 <= self.current_display_idx < len(self.df_displayed):
                self.view_edit_note_button.config(state=tk.NORMAL)
            else:
                # This case should ideally be handled by show_welcome_message,
                # which already disables this button. But as a fallback:
                self.view_edit_note_button.config(state=tk.DISABLED)
        # --- End Enable/Disable ---


        self.post_text_area.config(state=tk.DISABLED); self.update_post_number_label(); self.update_bookmark_button_status()
    # --- END UPDATE_DISPLAY ---

    # --- START SHOW_WELCOME_MESSAGE ---
    def show_welcome_message(self):
        self.post_text_area.config(state=tk.NORMAL)
        self.post_text_area.delete(1.0, tk.END)

        for widget in self.image_display_frame.winfo_children(): widget.destroy()
        self.displayed_images_references = []
        self.current_post_urls = []

        title = "QView – Offline Q Post Explorer\n"
        para1 = "QView is a standalone desktop application designed for serious research into the full Q post archive. Built from the ground up for speed, clarity, and privacy, QView lets you search, explore, and annotate thousands of drops without needing an internet connection."
        para2 = "Unlike web-based tools that can disappear or go dark, QView gives you complete control—local images, saved article archives, powerful search tools, and customizable settings wrapped in a clean, user-friendly interface. No tracking. No fluff. Just signal."
        para3 = "Development is 100% community-driven and fully open-source."
        para4 = "If you’ve found QView useful in your research or decoding work, consider buying me a coffee. It helps keep the project alive and evolving."
        donation_text_display = "Buy me a coffee ☕"
        donation_url = "https://www.buymeacoffee.com/qview1776"
        feedback_text = "Feedback & Suggestions: qview1776@gmail.com"
        closing_text = "🔒 No paywalls. No locked features. Just a tip jar for the digital battlefield."

        self.post_text_area.insert(tk.END, title + "\n", "welcome_title_tag")
        self.post_text_area.insert(tk.END, para1 + "\n\n", "welcome_text_tag")
        self.post_text_area.insert(tk.END, para2 + "\n\n", "welcome_text_tag")
        self.post_text_area.insert(tk.END, para3 + "\n\n", ("welcome_text_tag", "welcome_emphasis_tag"))
        self.post_text_area.insert(tk.END, para4 + " ", "welcome_text_tag")

        clickable_donation_tag_welcome = "welcome_donation_link_main"
        self.post_text_area.insert(tk.END, donation_text_display, ("welcome_text_tag", "clickable_link_style", clickable_donation_tag_welcome))
        self.post_text_area.tag_bind(clickable_donation_tag_welcome, "<Button-1>", lambda e, url=donation_url: utils.open_link_with_preference(url, self.app_settings))
        self.post_text_area.insert(tk.END, "\n\n", "welcome_text_tag")

        self.post_text_area.insert(tk.END, feedback_text + "\n\n", "welcome_text_tag")
        self.post_text_area.insert(tk.END, closing_text + "\n", "welcome_closing_tag")

        self.post_text_area.config(state=tk.DISABLED)

        if hasattr(self, 'show_links_button'): self.show_links_button.config(state=tk.DISABLED)
        if hasattr(self, 'view_article_button'): self.view_article_button.config(text="Article Not Saved", state=tk.DISABLED, command=lambda: None)
        self.update_post_number_label(is_welcome=True)
        self.update_bookmark_button_status(is_welcome=True)
        if hasattr(self, 'view_edit_note_button'): self.view_edit_note_button.config(state=tk.DISABLED) # Changed from edit_save_note_button
        # No direct note_text_area in main UI anymore
    # --- END SHOW_WELCOME_MESSAGE ---

    # --- START UPDATE_POST_NUMBER_LABEL ---
    def update_post_number_label(self, is_welcome=False): # Added is_welcome
        if is_welcome:
            self.post_number_label.config(text="Welcome to QView!")
            return
        if self.df_displayed is None or self.df_displayed.empty or self.current_display_idx < 0 : self.post_number_label.config(text="No Posts Displayed"); return
        if not (0 <= self.current_display_idx < len(self.df_displayed)): self.post_number_label.config(text="Invalid Index"); return
        post_series = self.df_displayed.iloc[self.current_display_idx]; post_num_df = post_series.get('Post Number'); original_df_idx = self.df_displayed.index[self.current_display_idx]
        post_num_display = f"#{post_num_df}" if pd.notna(post_num_df) else f"(Original Idx:{original_df_idx})"; total_in_view = len(self.df_displayed); current_pos_in_view = self.current_display_idx + 1
        label_text = f"Result {current_pos_in_view}/{total_in_view} (Q {post_num_display})" if self.current_search_active else f"Post {current_pos_in_view}/{total_in_view} (Q {post_num_display})"; self.post_number_label.config(text=label_text)
    # --- END UPDATE_POST_NUMBER_LABEL ---

    # --- START ON_TREE_SELECT ---
    def on_tree_select(self, event):
        selected_items = self.post_tree.selection()
        if selected_items:
            selected_iid_str = selected_items[0]
            try:
                original_df_index = int(selected_iid_str)
                if self.df_displayed is not None and original_df_index in self.df_displayed.index: # Check df_displayed
                    new_display_idx = self.df_displayed.index.get_loc(original_df_index)
                    if not hasattr(self, '_init_complete') or not self._init_complete or new_display_idx != self.current_display_idx:
                        self.current_display_idx = new_display_idx
                        self.update_display()
                    elif new_display_idx == self.current_display_idx and hasattr(self, '_init_complete') and self._init_complete:
                        self.update_display() # Refresh even if same index
            except ValueError: print(f"Error: Tree iid '{selected_iid_str}' not a valid integer for index.")
            except Exception as e: print(f"Error in on_tree_select: {e}")
    # --- END ON_TREE_SELECT ---

    # --- START ON_TREE_ARROW_NAV ---
    def on_tree_arrow_nav(self, event):
        if self.df_displayed is None or self.df_displayed.empty: return "break"
        all_tree_iids_str = list(self.post_tree.get_children('')); num_items_in_tree = len(all_tree_iids_str)
        if num_items_in_tree == 0: return "break"
        current_focus_iid_str = self.post_tree.focus(); current_logical_idx_in_tree = -1
        if current_focus_iid_str and current_focus_iid_str in all_tree_iids_str: current_logical_idx_in_tree = all_tree_iids_str.index(current_focus_iid_str)
        elif num_items_in_tree > 0 : current_logical_idx_in_tree = 0 if event.keysym == "Down" else num_items_in_tree - 1
        if current_logical_idx_in_tree == -1 : return "break"
        target_logical_idx_in_tree = -1
        if event.keysym == "Down":
            target_logical_idx_in_tree = current_logical_idx_in_tree + 1
            if target_logical_idx_in_tree >= num_items_in_tree:
                target_logical_idx_in_tree = num_items_in_tree - 1
        elif event.keysym == "Up":
            target_logical_idx_in_tree = current_logical_idx_in_tree - 1
            if target_logical_idx_in_tree < 0:
                target_logical_idx_in_tree = 0
        else:
            return
        if 0 <= target_logical_idx_in_tree < num_items_in_tree:
            target_iid_str = all_tree_iids_str[target_logical_idx_in_tree]; self.post_tree.selection_set(target_iid_str); self.post_tree.focus(target_iid_str); self.post_tree.see(target_iid_str)
        return "break"
    # --- END ON_TREE_ARROW_NAV ---

    # --- START PREV_POST ---
    def prev_post(self):
        if self.df_displayed is None or self.df_displayed.empty or len(self.df_displayed) == 0: return
        if len(self.df_displayed) == 1 and self.current_display_idx == 0: return
        self.current_display_idx = (self.current_display_idx - 1 + len(self.df_displayed)) % len(self.df_displayed); self.select_tree_item_by_idx(self.current_display_idx)
    # --- END PREV_POST ---

    # --- START NEXT_POST ---
    def next_post(self):
        if self.df_displayed is None or self.df_displayed.empty or len(self.df_displayed) == 0: return
        if len(self.df_displayed) == 1 and self.current_display_idx == 0: return
        self.current_display_idx = (self.current_display_idx + 1) % len(self.df_displayed); self.select_tree_item_by_idx(self.current_display_idx)
    # --- END NEXT_POST ---

    # --- START SELECT_TREE_ITEM_BY_IDX ---
    def select_tree_item_by_idx(self, display_idx_in_current_df):
        if self.df_displayed is not None and 0 <= display_idx_in_current_df < len(self.df_displayed): # Check df_displayed
            original_df_idx_to_select = self.df_displayed.index[display_idx_in_current_df]; iid_to_select = str(original_df_idx_to_select)
            if self.post_tree.exists(iid_to_select): self.post_tree.selection_set(iid_to_select); self.post_tree.focus(iid_to_select); self.post_tree.see(iid_to_select)
        elif self.post_tree.selection(): self.post_tree.selection_remove(self.post_tree.selection())
    # --- END SELECT_TREE_ITEM_BY_IDX ---

    # --- START PLACEHOLDER_HANDLING ---
    def clear_placeholder(self, event, placeholder_text, widget=None):
        if widget is None and event: widget = event.widget
        elif widget is None and not event:
            if placeholder_text == config.PLACEHOLDER_POST_NUM: widget = self.post_entry
            elif placeholder_text == config.PLACEHOLDER_KEYWORD: widget = self.keyword_entry
            else: return
        if widget and hasattr(widget, 'get') and widget.get() == placeholder_text: widget.delete(0, tk.END); normal_fg = self.style.lookup("TEntry", "foreground"); widget.config(foreground=normal_fg)
    def restore_placeholder(self, event, placeholder_text, widget=None):
        if widget is None and event: widget = event.widget
        elif widget is None and not event:
            if placeholder_text == config.PLACEHOLDER_POST_NUM: widget = self.post_entry
            elif placeholder_text == config.PLACEHOLDER_KEYWORD: widget = self.keyword_entry
            else: return
        if widget and hasattr(widget, 'get') and not widget.get(): widget.insert(0, placeholder_text); placeholder_color = self.placeholder_fg_color_dark if self.current_theme == "dark" else self.placeholder_fg_color_light; widget.config(foreground=placeholder_color)
    # --- END PLACEHOLDER_HANDLING ---

    # --- START SEARCH_POST_BY_NUMBER ---
    def search_post_by_number(self):
        entry_widget = self.post_entry; placeholder = config.PLACEHOLDER_POST_NUM; search_input = entry_widget.get()
        if search_input == placeholder or not search_input.strip(): messagebox.showwarning("Input", "Please enter a post number, range (e.g., 10-15), or list (e.g., 10,12,15).", parent=self.root); return
        target_post_numbers = []; search_term_str = f"Post(s) = '{search_input}'"; is_jump_to_single = False
        try:
            if ',' in search_input: target_post_numbers = [int(p.strip()) for p in search_input.split(',')]
            elif '-' in search_input:
                parts = search_input.split('-');
                if len(parts) == 2: 
                    start_num_str = parts[0].strip() # Moved to new line and indented
                    end_num_str = parts[1].strip()   # Moved to new line and indented
                    
                    # This block is now correctly indented under 'if len(parts) == 2:'
                    if not start_num_str or not end_num_str: 
                        raise ValueError("Invalid range format - empty start or end.")
                    start_num, end_num = int(start_num_str), int(end_num_str)
                    if start_num <= end_num: 
                        target_post_numbers = list(range(start_num, end_num + 1))
                    else: 
                        messagebox.showerror("Input Error", "Start of range must be less than or equal to end.", parent=self.root)
                        return
                else: raise ValueError("Invalid range format - not two parts.")
            else: target_post_numbers = [int(search_input.strip())]; is_jump_to_single = True
            if not target_post_numbers: messagebox.showerror("Input Error", "No valid post numbers to search.", parent=self.root); return
            if is_jump_to_single:
                post_to_find = target_post_numbers[0]
                if self.current_search_active: self.df_displayed = self.df_all_posts.copy(); self.current_search_active = False; self.clear_search_button.config(state=tk.DISABLED); self.repopulate_treeview(self.df_displayed); self.root.update_idletasks()
                matching_posts = self.df_all_posts[self.df_all_posts['Post Number'] == post_to_find]
                if not matching_posts.empty:
                    original_df_idx = matching_posts.index[0]
                    if self.df_displayed is not None and original_df_idx in self.df_displayed.index: self.current_display_idx = self.df_displayed.index.get_loc(original_df_idx); self.select_tree_item_by_idx(self.current_display_idx)
                    else: messagebox.showinfo("Not Found", f"Post # {post_to_find} not found (internal error).", parent=self.root)
                else: messagebox.showinfo("Not Found", f"Post # {post_to_find} not found.", parent=self.root)
            else: results = self.df_all_posts[self.df_all_posts['Post Number'].isin(target_post_numbers)]; self._handle_search_results(results, search_term_str)
        except ValueError: messagebox.showerror("Input Error", "Invalid input. Please enter a number, a range (e.g., 10-15), or a comma-separated list.", parent=self.root)
        finally:
            current_entry_text = entry_widget.get()
            if current_entry_text != placeholder and current_entry_text.strip() != "": entry_widget.delete(0, tk.END); self.restore_placeholder(None, placeholder, entry_widget)
            elif not current_entry_text.strip() and current_entry_text != placeholder : self.restore_placeholder(None, placeholder, entry_widget)
    # --- END SEARCH_POST_BY_NUMBER ---

    # --- START DATE_SEARCH_LOGIC ---
    def show_calendar(self):
        try: dialog_bg = self.style.lookup("TFrame", "background")
        except tk.TclError: dialog_bg = "#2b2b2b" if self.current_theme == "dark" else "#f0f0f0"
        top = tk.Toplevel(self.root); top.title("Select Date"); top.configure(bg=dialog_bg); top.transient(self.root); top.grab_set()
        now = datetime.datetime.now(); cal_y, cal_m, cal_d = now.year, now.month, now.day
        if self.df_displayed is not None and not self.df_displayed.empty and 0 <= self.current_display_idx < len(self.df_displayed): # Check df_displayed
            cur_post_dt = self.df_displayed.iloc[self.current_display_idx].get('Datetime_UTC')
            if pd.notna(cur_post_dt): cal_y, cal_m, cal_d = cur_post_dt.year, cur_post_dt.month, cur_post_dt.day
        cal_fg = "#000000" if self.current_theme == "light" else "#e0e0e0"; cal_bg = "#ffffff" if self.current_theme == "light" else "#3c3f41"; cal_sel_bg = "#0078D7"; cal_sel_fg = "#ffffff"; cal_hdr_bg = "#e1e1e1" if self.current_theme == "light" else "#4a4a4a"; cal_dis_bg = "#f0f0f0" if self.current_theme == "light" else "#2b2b2b"; cal_dis_fg = "grey"
        cal = Calendar(top, selectmode="day", year=cal_y, month=cal_m, day=cal_d, date_pattern='m/d/yy', font="Arial 9", background=cal_hdr_bg, foreground=cal_fg, headersbackground=cal_hdr_bg, headersforeground=cal_fg, normalbackground=cal_bg, weekendbackground=cal_bg, normalforeground=cal_fg, weekendforeground=cal_fg, othermonthbackground=cal_dis_bg, othermonthwebackground=cal_dis_bg, othermonthforeground=cal_dis_fg, othermonthweforeground=cal_dis_fg, selectbackground=cal_sel_bg, selectforeground=cal_sel_fg, bordercolor=cal_hdr_bg)
        cal.pack(padx=10, pady=10)
        def on_date_selected_from_calendar(): selected_date_str = cal.get_date(); top.destroy(); self._search_by_date_str(selected_date_str)
        ttk.Button(top, text="Select Date", command=on_date_selected_from_calendar).pack(pady=5)
    def _search_by_date_str(self, date_str_from_cal):
        try:
            target_date = pd.to_datetime(date_str_from_cal, format='%m/%d/%y').date()
            results = self.df_all_posts[self.df_all_posts['Datetime_UTC'].dt.date == target_date]
            self._handle_search_results(results, f"Date = {target_date.strftime('%Y-%m-%d')}")
        except Exception as e: messagebox.showerror("Error", f"Date selection error: {e}", parent=self.root)
    # --- END DATE_SEARCH_LOGIC ---

    # --- START KEYWORD_SEARCH_LOGIC ---
    def search_by_keyword(self):
        entry_widget = self.keyword_entry; placeholder = config.PLACEHOLDER_KEYWORD; keyword = entry_widget.get().strip()
        if not keyword or keyword == placeholder: messagebox.showwarning("Input", "Please enter a keyword or theme to search.", parent=self.root); return
        keyword_lower = keyword.lower()
        results = self.df_all_posts[
            (self.df_all_posts['Text'].str.lower().str.contains(keyword_lower, na=False, regex=False)) |
            (self.df_all_posts['Themes'].apply(lambda x: isinstance(x, list) and any(keyword_lower in theme.lower() for theme in x)))
        ]
        self._handle_search_results(results, f"Keyword/Theme = '{keyword}'")
        entry_widget.delete(0, tk.END); self.restore_placeholder(None, placeholder, entry_widget)
    # --- END KEYWORD_SEARCH_LOGIC ---

    # --- START _HANDLE_SEARCH_RESULTS ---
    def _handle_search_results(self, results_df, search_term_str):
        if not results_df.empty:
            self.df_displayed = results_df.copy(); self.current_search_active = True; self.clear_search_button.config(state=tk.NORMAL)
            self.repopulate_treeview(self.df_displayed, select_first_item=True) # Select first result
            # update_display will be called via on_tree_select
        else:
            messagebox.showinfo("Search Results", f"No posts found for: {search_term_str}", parent=self.root)
            self.df_displayed = pd.DataFrame(columns=self.df_all_posts.columns if self.df_all_posts is not None else []);
            self.current_search_active = True; self.clear_search_button.config(state=tk.NORMAL)
            self.repopulate_treeview(self.df_displayed, select_first_item=False) # Show empty tree
            self.show_welcome_message() # Show welcome on no results
    # --- END _HANDLE_SEARCH_RESULTS ---
            self.show_welcome_message() # Show welcome on no results
    # --- END _HANDLE_SEARCH_RESULTS ---

    # --- START CLEAR_SEARCH_AND_SHOW_ALL ---
    def clear_search_and_show_all(self):
        if self.df_all_posts is None or self.df_all_posts.empty:
            self.show_welcome_message() # Already handles empty df_all_posts
            return

        self.df_displayed = self.df_all_posts.copy(); self.current_search_active = False; self.clear_search_button.config(state=tk.DISABLED)
        self.repopulate_treeview(self.df_displayed, select_first_item=True) # Select first post
        # update_display is called via on_tree_select if selection happens
        if self.df_displayed.empty: # Should not happen if df_all_posts is not empty
             self.show_welcome_message()
        # If df_displayed is not empty, repopulate_treeview with select_first_item=True should trigger update_display
        # If no item was selected for some reason (e.g. tree is empty after repopulation), ensure correct state:
        elif self.post_tree.selection() == (): # If nothing ended up selected
             self.show_welcome_message()
    # --- END CLEAR_SEARCH_AND_SHOW_ALL ---
    # --- END CLEAR_SEARCH_AND_SHOW_ALL ---

    # --- START EXPORT_DISPLAYED_LIST ---
    def export_displayed_list(self):
        if self.df_displayed is None or self.df_displayed.empty: messagebox.showwarning("Export", "No posts to export.", parent=self.root); return
        export_format = self.export_var.get(); default_fname = f"q_export_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"; file_types = [("HTML", "*.html"), ("CSV", "*.csv")] if export_format=="HTML" else [("CSV", "*.csv"), ("HTML", "*.html")]; initial_ext = ".html" if export_format=="HTML" else ".csv"
        final_filename = filedialog.asksaveasfilename(parent=self.root,initialdir=os.getcwd(),title=f"Save {export_format}",defaultextension=initial_ext,filetypes=file_types,initialfile=default_fname)
        if not final_filename: return
        df_exp = self.df_displayed.copy(); cols_to_use = [c for c in config.EXPORT_COLUMNS if c in df_exp.columns]
        if not cols_to_use: messagebox.showerror("Export Error", "No valid columns found for export. Check EXPORT_COLUMNS.", parent=self.root); return
        df_for_export = df_exp[cols_to_use]
        try:
            if final_filename.endswith(".csv"):
                df_csv = df_for_export.copy();
                if 'Themes' in df_csv.columns: df_csv['Themes'] = df_csv['Themes'].apply(lambda x: ', '.join(x) if isinstance(x,list) else str(x))
                if 'ImagesJSON' in df_csv.columns: df_csv['ImagesJSON'] = df_csv['ImagesJSON'].apply(lambda x: str(x) if isinstance(x, list) else "")
                df_csv.to_csv(final_filename,index=False,encoding='utf-8-sig'); messagebox.showinfo("Success",f"Exported {len(df_for_export)} posts to {final_filename}",parent=self.root)
            elif final_filename.endswith(".html"):
                import html
                df_html = df_for_export.copy();
                if 'Link' in df_html.columns: df_html['Link'] = df_html['Link'].apply(lambda x: f'<a href="{html.escape(x, quote=True)}" target="_blank">{html.escape(x)}</a>' if pd.notna(x) and x else "")
                if 'Text' in df_html.columns: df_html['Text'] = df_html['Text'].apply(utils.format_cell_text_for_gui_html)
                if 'Themes' in df_html.columns: df_html['Themes'] = df_html['Themes'].apply(lambda x: html.escape(', '.join(x)) if isinstance(x, list) else html.escape(str(x)))
                if 'Referenced Posts Display' in df_html.columns: df_html['Referenced Posts Display'] = df_html['Referenced Posts Display'].astype(str).apply(lambda x: x.replace('\n', '<br />\n'))
                if 'Datetime_UTC' in df_html.columns and pd.api.types.is_datetime64_any_dtype(df_html['Datetime_UTC']): df_html['Datetime_UTC'] = df_html['Datetime_UTC'].dt.strftime('%Y-%m-%d %H:%M:%S %Z')
                if 'ImagesJSON' in df_html.columns: df_html['ImagesJSON'] = df_html['ImagesJSON'].apply(lambda x: html.escape(str(x)) if isinstance(x, list) else "")
                html_table = df_html.to_html(escape=False,index=False,border=0,classes='qposts_table',na_rep=""); css = """<style>body{font-family:Arial,sans-serif;margin:20px;background-color:#f4f4f4;color:#333}h1{color:#333;text-align:center}.qposts_table{border-collapse:collapse;width:95%;margin:20px auto;background-color:#fff;box-shadow:0 0 10px rgba(0,0,0,.1)}.qposts_table th,.qposts_table td{border:1px solid #ddd;padding:10px;text-align:left;vertical-align:top}.qposts_table th{background-color:#4CAF50;color:#fff}.qposts_table tr:nth-child(even){background-color:#f9f9f9}.qposts_table tr:hover{background-color:#e2f0e8}.qposts_table td a{color:#007bff;text-decoration:none}.qposts_table td a:hover{text-decoration:underline}.qposts_table td{word-wrap:break-word;max-width:600px;min-width:100px;}</style>"""
                html_full = f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><title>Q Posts GUI Export</title>{css}</head><body><h1>Q Posts Export</h1>{html_table}</body></html>"""
                with open(final_filename,'w',encoding='utf-8') as f: f.write(html_full); messagebox.showinfo("Success",f"Exported {len(df_for_export)} posts to {final_filename}",parent=self.root)
                try: webbrowser.open_new_tab(f"file://{os.path.realpath(final_filename)}")
                except Exception as e: print(f"Could not auto-open HTML: {e}")
            else: messagebox.showerror("Error","Unsupported file extension. Please use .csv or .html.",parent=self.root)
        except Exception as e: messagebox.showerror("Export Error",f"Failed to export: {e}",parent=self.root); import traceback; traceback.print_exc()
    # --- END EXPORT_DISPLAYED_LIST ---

    # --- START BOOKMARKING_LOGIC ---
    def toggle_current_post_bookmark(self):
        if self.df_displayed is None or self.df_displayed.empty or self.current_display_idx < 0: messagebox.showwarning("Bookmark", "No post selected to bookmark/unbookmark.", parent=self.root); return
        original_df_index = self.df_displayed.index[self.current_display_idx]; post_series = self.df_all_posts.loc[original_df_index]; post_num_df = post_series.get('Post Number', original_df_index); post_id_str = f"#{post_num_df}" if pd.notna(post_num_df) else f"(Index: {original_df_index})"
        if original_df_index in self.bookmarked_posts: self.bookmarked_posts.remove(original_df_index); messagebox.showinfo("Bookmark", f"Q Drop {post_id_str} unbookmarked.", parent=self.root)
        else: self.bookmarked_posts.add(original_df_index); messagebox.showinfo("Bookmark", f"Q Drop {post_id_str} bookmarked!", parent=self.root)
        self.update_bookmark_button_status(); self.update_display(); self.repopulate_treeview(self.df_displayed); self.view_bookmarks_button.config(text=f"View Bookmarks ({len(self.bookmarked_posts)})")
    def update_bookmark_button_status(self, is_welcome=False): # Added is_welcome
        if is_welcome or self.df_displayed is None or self.df_displayed.empty or self.current_display_idx < 0:
            self.bookmark_button.config(text="Bookmark Post", state=tk.DISABLED)
            return
        self.bookmark_button.config(state=tk.NORMAL); original_df_index = self.df_displayed.index[self.current_display_idx]; self.bookmark_button.config(text="Unbookmark This Post" if original_df_index in self.bookmarked_posts else "Bookmark This Post")
    def view_bookmarked_gui_posts(self):
        if not self.bookmarked_posts: messagebox.showinfo("Bookmarks", "No posts bookmarked yet.", parent=self.root); return
        valid_bookmarked_indices = [idx for idx in self.bookmarked_posts if idx in self.df_all_posts.index]
        if not valid_bookmarked_indices: messagebox.showwarning("Bookmarks", "Bookmarked posts not found in current data.", parent=self.root); self.df_displayed = pd.DataFrame(columns=self.df_all_posts.columns if self.df_all_posts is not None else []); self.repopulate_treeview(self.df_displayed); self.show_welcome_message(); return
        results_df = self.df_all_posts.loc[list(valid_bookmarked_indices)].copy();
        if 'Datetime_UTC' in results_df.columns: results_df.sort_values(by='Datetime_UTC', inplace=True)
        self._handle_search_results(results_df, "Bookmarked Posts")
    # --- END BOOKMARKING_LOGIC ---

    # --- START REPOPULATE_TREEVIEW ---
    def repopulate_treeview(self, dataframe_to_show, select_first_item=True): # Added select_first_item
        self.post_tree.delete(*self.post_tree.get_children())
        if dataframe_to_show is not None:
            for original_df_index, row in dataframe_to_show.iterrows():
                date_val_real = row.get('Datetime_UTC'); date_str = date_val_real.strftime('%Y-%m-%d') if pd.notna(date_val_real) else "No Date"; post_num_real = row.get('Post Number'); iid_original_index_str = str(row.name)
                post_num_display = f"#{post_num_real}" if pd.notna(post_num_real) else f"Idx:{iid_original_index_str}"; is_bookmarked_char = "★" if row.name in self.bookmarked_posts else ""; self.post_tree.insert("", "end", iid=iid_original_index_str, values=(post_num_display, date_str, is_bookmarked_char))

        if dataframe_to_show is not None and not dataframe_to_show.empty:
            if select_first_item:
                idx_to_select_in_df = 0 # Default to first item
                # If already initialized and current_display_idx is valid for new df, try to maintain it
                if hasattr(self, '_init_complete') and self._init_complete and \
                   0 <= self.current_display_idx < len(dataframe_to_show):
                    idx_to_select_in_df = self.current_display_idx
                else: # Otherwise, if not init or index out of bounds, reset to 0
                    self.current_display_idx = 0 
                
                iid_to_select_original_index_str = str(dataframe_to_show.index[idx_to_select_in_df])
                if self.post_tree.exists(iid_to_select_original_index_str):
                    self.post_tree.selection_set(iid_to_select_original_index_str)
                    self.post_tree.focus(iid_to_select_original_index_str)
                    self.post_tree.see(iid_to_select_original_index_str)
            # If select_first_item is False, current_display_idx (likely -1 from welcome) persists.
            # UI updates for labels etc. will be handled by show_welcome_message or update_display.
        else: # dataframe_to_show is empty or None
            self.current_display_idx = -1
            if hasattr(self, '_init_complete') and self._init_complete: # If app is running and list becomes empty
                self.show_welcome_message()
            # Else (during __init__ with no data), __init__ handles error or calls show_welcome_message
            # Update labels for empty state only if not in init and not showing welcome (covered by show_welcome_message)
            elif not (hasattr(self, '_init_complete') and self._init_complete):
                 self.update_post_number_label(is_welcome=True)
                 self.update_bookmark_button_status(is_welcome=True)
                 if hasattr(self, 'edit_save_note_button'): self.edit_save_note_button.config(state=tk.DISABLED)
        
        if not hasattr(self, '_init_complete'): self._init_complete = False # Should already be set in __init__
    # --- END REPOPULATE_TREEVIEW ---

    # --- START DELTA_SEARCH_LOGIC ---
    def show_day_delta_dialog(self):
        try: dialog_bg = self.style.lookup("TFrame", "background")
        except tk.TclError: dialog_bg = "#2b2b2b" if self.current_theme == "dark" else "#f0f0f0"
        top = tk.Toplevel(self.root); top.title("Select Month and Day for Delta Search"); top.configure(bg=dialog_bg); top.transient(self.root); top.grab_set()
        dialog_width = 250; dialog_height = 160; root_x = self.root.winfo_x(); root_y = self.root.winfo_y(); root_width = self.root.winfo_width(); root_height = self.root.winfo_height(); x = root_x + (root_width // 2) - (dialog_width // 2); y = root_y + (root_height // 2) - (dialog_height // 2); top.geometry(f'{dialog_width}x{dialog_height}+{x}+{y}')
        ttk.Label(top, text="Month:").pack(pady=(10,2)); month_var = tk.StringVar(); months = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]; month_cb = ttk.Combobox(top, textvariable=month_var, values=months, state="readonly", width=18); month_cb.pack(); month_cb.set(datetime.datetime.now().strftime("%B"))
        ttk.Label(top, text="Day:").pack(pady=(5,2)); day_var = tk.StringVar(); days = [str(d) for d in range(1, 32)]; day_cb = ttk.Combobox(top, textvariable=day_var, values=days, state="readonly", width=5); day_cb.pack(); day_cb.set(str(datetime.datetime.now().day))
        def on_search():
            try:
                month_num = months.index(month_var.get()) + 1; day_num = int(day_var.get())
                if month_num == 2 and day_num > 29: messagebox.showerror("Invalid Date", "February cannot have more than 29 days for this search.", parent=top); return
                elif month_num in [4, 6, 9, 11] and day_num > 30: messagebox.showerror("Invalid Date", f"{month_var.get()} cannot have more than 30 days.", parent=top); return
                elif day_num > 31 or day_num < 1 : messagebox.showerror("Invalid Date", "Day must be between 1 and 31.", parent=top); return
                top.destroy(); self._search_by_month_day(month_num, day_num)
            except ValueError: messagebox.showerror("Input Error", "Please select a valid month and day.", parent=top)
            except Exception as e: messagebox.showerror("Error", f"An error occurred: {e}", parent=top)
        ttk.Button(top, text="Search Deltas", command=on_search).pack(pady=10)
    def _search_by_month_day(self, month, day):
        if self.df_all_posts is None or 'Datetime_UTC' not in self.df_all_posts.columns: messagebox.showerror("Error", "Post data or 'Datetime_UTC' column not available.", parent=self.root); return
        if not pd.api.types.is_datetime64_any_dtype(self.df_all_posts['Datetime_UTC']):
             self.df_all_posts['Datetime_UTC'] = pd.to_datetime(self.df_all_posts['Datetime_UTC'], errors='coerce')
             if self.df_all_posts['Datetime_UTC'].isna().any(): messagebox.showwarning("Data Warning", "Some dates could not be parsed. Results might be incomplete.", parent=self.root)
        try:
            valid_dates_df = self.df_all_posts.dropna(subset=['Datetime_UTC'])
            results = valid_dates_df[ (valid_dates_df['Datetime_UTC'].dt.month == month) & (valid_dates_df['Datetime_UTC'].dt.day == day) ]
            month_name = datetime.date(1900, month, 1).strftime('%B')
            self._handle_search_results(results, f"Posts from {month_name} {day} (All Years)")
        except Exception as e: messagebox.showerror("Search Error", f"An error occurred during delta search: {e}", parent=self.root)
    def search_today_deltas(self):
        today = datetime.datetime.now(); self._search_by_month_day(today.month, today.day)
    # --- END DELTA_SEARCH_LOGIC ---

    # --- START USER_NOTES_METHODS ---
    def show_note_popup(self):
        if self.df_displayed is None or self.df_displayed.empty or not (0 <= self.current_display_idx < len(self.df_displayed)):
            messagebox.showwarning("No Post Selected", "Please select a post to view or edit its note.", parent=self.root)
            return

        original_df_index = str(self.df_displayed.index[self.current_display_idx])
        current_note = self.user_notes.get(original_df_index, "")

        note_popup = tk.Toplevel(self.root)
        note_popup.title(f"Note for Post (Index: {original_df_index})")
        note_popup.geometry("500x400")
        note_popup.transient(self.root)
        note_popup.grab_set()

        try:
            dialog_bg = self.style.lookup("TFrame", "background")
            text_bg = self.style.lookup("TEntry", "fieldbackground")
            text_fg = self.style.lookup("TEntry", "foreground")
        except tk.TclError:
            dialog_bg = "#f0f0f0" if self.current_theme == "light" else "#2b2b2b"
            text_bg = "#ffffff" if self.current_theme == "light" else "#3c3f41"
            text_fg = "#000000" if self.current_theme == "light" else "#e0e0e0"
        
        note_popup.configure(bg=dialog_bg)

        popup_main_frame = ttk.Frame(note_popup, padding=10)
        popup_main_frame.pack(expand=True, fill=tk.BOTH)

        note_text_widget = tk.Text(popup_main_frame, wrap=tk.WORD, height=15, font=("TkDefaultFont", 10), relief=tk.SOLID, borderwidth=1, padx=5, pady=5)
        note_text_widget.configure(bg=text_bg, fg=text_fg, insertbackground=text_fg)
        note_text_widget.pack(expand=True, fill=tk.BOTH, pady=(0,10))
        note_text_widget.insert(tk.END, current_note)
        note_text_widget.focus_set()

        button_frame = ttk.Frame(popup_main_frame)
        button_frame.pack(fill=tk.X)

        def save_and_close():
            note_content = note_text_widget.get(1.0, tk.END).strip()
            if note_content:
                self.user_notes[original_df_index] = note_content
            elif original_df_index in self.user_notes: # If content is empty, remove note
                del self.user_notes[original_df_index]
            
            utils.save_user_notes(self.user_notes, config.USER_NOTES_FILE_PATH) # Save immediately
            print(f"Note for post index {original_df_index} saved.")
            note_popup.destroy()

        def cancel_and_close():
            note_popup.destroy()

        save_button = ttk.Button(button_frame, text="Save Note", command=save_and_close)
        save_button.pack(side=tk.RIGHT, padx=5)
        cancel_button = ttk.Button(button_frame, text="Cancel", command=cancel_and_close)
        cancel_button.pack(side=tk.RIGHT)

        # Ensure popup stays on top and handles closing via window manager
        note_popup.protocol("WM_DELETE_WINDOW", cancel_and_close)
    # --- END USER_NOTES_METHODS ---

    # --- START MOUSEWHEEL_HELPERS_FOR_SCROLLABLE_WINDOWS ---
    def _on_mousewheel(self, event, canvas_widget):
        if event.delta:
            canvas_widget.yview_scroll(int(-1 * (event.delta / 120)), "units")
        elif event.num == 4:
            canvas_widget.yview_scroll(-1, "units")
        elif event.num == 5:
            canvas_widget.yview_scroll(1, "units")

    def _on_scroll_up(self, event, canvas_widget):
        canvas_widget.yview_scroll(-1, "units")

    def _on_scroll_down(self, event, canvas_widget):
        canvas_widget.yview_scroll(1, "units")
    # --- END MOUSEWHEEL_HELPERS_FOR_SCROLLABLE_WINDOWS ---

    # --- START DOWNLOAD_WINDOW_AND_THREADING ---
    def show_download_window(self):
        if hasattr(self, 'download_win') and self.download_win is not None and self.download_win.winfo_exists():
            self.download_win.lift(); self.download_win.focus_set(); return

        self.download_win = tk.Toplevel(self.root); self.download_win.title("Download Offline Content")
        try: dialog_bg = self.style.lookup("TFrame", "background")
        except tk.TclError: dialog_bg = "#2b2b2b" if self.current_theme == "dark" else "#f0f0f0"
        self.download_win.configure(bg=dialog_bg)
        self.download_win.geometry("450x300"); self.download_win.transient(self.root); self.download_win.grab_set(); self.download_win.resizable(False, False)
        main_frame = ttk.Frame(self.download_win, padding="15"); main_frame.pack(expand=True, fill="both")
        ttk.Label(main_frame, text="Download Post Images", font=('Arial', 11, 'bold')).pack(pady=(0, 5), anchor='w')
        ttk.Label(main_frame, text="Downloads all post image attachments (approx. 400-500MB).", wraplength=400, justify=tk.LEFT).pack(anchor='w', padx=5, pady=(0, 5))
        self.download_images_button = ttk.Button(main_frame, text="Start Image Download", command=lambda: self._start_download_thread("images")); self.download_images_button.pack(pady=(0, 15), fill='x')
        ttk.Label(main_frame, text="Download Linked Articles", font=('Arial', 11, 'bold')).pack(pady=(10, 5), anchor='w')
        ttk.Label(main_frame, text="Downloads HTML from non-board/social links (700MB+ possible).", wraplength=400, justify=tk.LEFT).pack(anchor='w', padx=5, pady=(0, 5))
        self.download_articles_button = ttk.Button(main_frame, text="Start Article Download", command=lambda: self._start_download_thread("articles")); self.download_articles_button.pack(pady=(0, 15), fill='x')
        status_frame = ttk.Labelframe(main_frame, text="Status", padding="10"); status_frame.pack(fill="x", pady=5, expand=True)
        self.download_status_label = ttk.Label(status_frame, text="Idle.", wraplength=380, justify=tk.LEFT); self.download_status_label.pack(anchor='w')
        ttk.Button(main_frame, text="Close", command=self.download_win.destroy).pack(side="bottom", pady=10)

    def _update_download_status(self, message):
        if hasattr(self, 'download_status_label') and self.download_status_label.winfo_exists(): self.download_status_label.config(text=message)
        else: print(f"Download Status: {message}")

    def _execute_download_task(self, task_name):
        buttons_to_disable = []
        if hasattr(self, 'download_images_button') and self.download_images_button.winfo_exists(): buttons_to_disable.append(self.download_images_button)
        if hasattr(self, 'download_articles_button') and self.download_articles_button.winfo_exists(): buttons_to_disable.append(self.download_articles_button)
        try:
            for btn in buttons_to_disable: self.root.after(0, lambda b=btn: b.config(state=tk.DISABLED))
            if task_name == "images":
                self.root.after(0, lambda: self._update_download_status("Starting Image Download..."))
                utils.download_all_post_images_util(self.df_all_posts, lambda msg: self.root.after(0, lambda m=msg: self._update_download_status(m)))
                self.root.after(0, lambda: self._update_download_status("Image download finished."))
            elif task_name == "articles":
                self.root.after(0, lambda: self._update_download_status("Starting Article Download..."))
                utils.scan_and_download_all_articles_util(self.df_all_posts, lambda msg: self.root.after(0, lambda m=msg: self._update_download_status(m)))
                self.root.after(0, lambda: self._update_download_status("Article download finished."))
            else: self.root.after(0, lambda: self._update_download_status(f"Unknown task: {task_name}"))
        except Exception as e: error_msg = f"Error during {task_name} download: {e}"; print(error_msg); self.root.after(0, lambda: self._update_download_status(error_msg))
        finally:
            for btn in buttons_to_disable: self.root.after(0, lambda b=btn: b.config(state=tk.NORMAL))
            self.root.after(5000, lambda: self._update_download_status("Idle."))

    def _start_download_thread(self, task_name):
        if self.df_all_posts is None or self.df_all_posts.empty: messagebox.showinfo("No Data", "No posts loaded to download content from.", parent=self.download_win if hasattr(self, 'download_win') and self.download_win.winfo_exists() else self.root); return
        confirm_msg = "";
        if task_name == "images": confirm_msg = "This will download all available Q post images (approx. 400-500MB).\n\nThis can take a while. Continue?"
        elif task_name == "articles": confirm_msg = "This will download linked web articles (700MB+ possible).\n\nThis can take a *very* long time and consume significant disk space. Continue?"
        else: return
        if not messagebox.askyesno("Confirm Download", confirm_msg, parent=self.download_win if hasattr(self, 'download_win') and self.download_win.winfo_exists() else self.root): return
        thread = threading.Thread(target=self._execute_download_task, args=(task_name,), daemon=True); thread.start()
    # --- END DOWNLOAD_WINDOW_AND_THREADING ---

    # --- START SHOW_SETTINGS_WINDOW ---
    def show_settings_window(self):
        if hasattr(self, 'settings_win') and self.settings_win is not None and self.settings_win.winfo_exists(): self.settings_win.lift(); self.settings_win.focus_set(); return
        self.settings_win = tk.Toplevel(self.root); self.settings_win.title("QView Settings")
        try: dialog_bg = self.style.lookup("TFrame", "background")
        except tk.TclError: dialog_bg = "#2b2b2b" if self.current_theme == "dark" else "#f0f0f0"
        self.settings_win.configure(bg=dialog_bg); self.settings_win.geometry("400x255"); self.settings_win.transient(self.root); self.settings_win.grab_set(); self.settings_win.resizable(False, False); self.settings_win.protocol("WM_DELETE_WINDOW", self.on_settings_window_close)
        main_frame = ttk.Frame(self.settings_win, padding="10"); main_frame.pack(expand=True, fill="both")
        theme_frame = ttk.Labelframe(main_frame, text="Display Theme", padding="10"); theme_frame.pack(fill="x", pady=5)
        self.settings_theme_var = tk.StringVar(value=self.app_settings.get("theme", settings.DEFAULT_SETTINGS["theme"]))
        dark_rb_theme = ttk.Radiobutton(theme_frame, text="Dark", variable=self.settings_theme_var, value="dark", command=self.on_setting_change); dark_rb_theme.pack(side="left", padx=5, expand=True)
        light_rb_theme = ttk.Radiobutton(theme_frame, text="Light", variable=self.settings_theme_var, value="light", command=self.on_setting_change); light_rb_theme.pack(side="left", padx=5, expand=True)
        link_pref_frame = ttk.Labelframe(main_frame, text="Link Opening Preference", padding="10"); link_pref_frame.pack(fill="x", pady=5)
        self.settings_link_pref_var = tk.StringVar(value=self.app_settings.get("link_opening_preference", settings.DEFAULT_SETTINGS.get("link_opening_preference", "default"))) # Ensure default for preference
        rb_default = ttk.Radiobutton(link_pref_frame, text="System Default Browser", variable=self.settings_link_pref_var, value="default", command=self.on_setting_change); rb_default.pack(anchor="w", padx=5)
        rb_chrome_incognito = ttk.Radiobutton(link_pref_frame, text="Google Chrome (Incognito, if available)", variable=self.settings_link_pref_var, value="chrome_incognito", command=self.on_setting_change); rb_chrome_incognito.pack(anchor="w", padx=5)
        close_button_frame = ttk.Frame(main_frame); close_button_frame.pack(side="bottom", fill="x", pady=(10,0))
        ttk.Button(close_button_frame, text="Close", command=self.on_settings_window_close).pack(pady=5)
    # --- END SHOW_SETTINGS_WINDOW ---

    # --- START ON_SETTING_CHANGE ---
    def on_setting_change(self, event=None):
        # Theme
        new_theme = self.settings_theme_var.get() # Semicolon removed, statement on its own line
        theme_changed = False

        if self.app_settings.get("theme") != new_theme: # This is the controlling 'if'
            # These lines are now INSIDE the 'if' block
            self.app_settings["theme"] = new_theme
            self.current_theme = new_theme
            theme_changed = True
            
            # This nested 'if/else' is now correctly indented
            if new_theme == "dark": 
                self.apply_dark_theme()
            else: 
                self.apply_light_theme()
            
            if hasattr(self, 'theme_toggle_button'): 
                self.theme_toggle_button.config(text="Into the Dark" if new_theme == "light" else "Dark to Light")
            
            if hasattr(self, 'settings_win') and self.settings_win and self.settings_win.winfo_exists():
                try: 
                    self.settings_win.configure(bg=self.style.lookup("TFrame", "background"))
                except tk.TclError: 
                    pass

        # Link Opening Preference (This part was likely fine, but ensure its alignment is correct with the first 'if' block)
        new_link_pref = self.settings_link_pref_var.get() # Semicolon removed
        link_pref_changed = False
        if self.app_settings.get("link_opening_preference") != new_link_pref: # This 'if' should align with the first 'if'
            self.app_settings["link_opening_preference"] = new_link_pref
            link_pref_changed = True

        if theme_changed or link_pref_changed:
            settings.save_settings(self.app_settings)
            print(f"Settings saved: Theme='{self.app_settings.get('theme')}', Link Pref='{self.app_settings.get('link_opening_preference')}'")
            if theme_changed: # Only update full display if theme changed
                if self.current_display_idx != -1 and self.df_displayed is not None and not self.df_displayed.empty : 
                    self.update_display()
                else: 
                    self.show_welcome_message()
    # --- END ON_SETTING_CHANGE ---

    # --- START ON_SETTINGS_WINDOW_CLOSE ---
    def on_settings_window_close(self):
        if hasattr(self, 'settings_win') and self.settings_win: self.settings_win.destroy(); self.settings_win = None
    # --- END ON_SETTINGS_WINDOW_CLOSE ---

    # --- START SHOW_HELP_WINDOW ---
    def show_help_window(self):
        import webbrowser
        try: dialog_bg = self.style.lookup("TFrame", "background"); bold_font = ('Arial', 12, 'bold', 'underline'); normal_font = ('Arial', 10); link_fg = self.link_label_fg_dark if self.current_theme == "dark" else self.link_label_fg_light
        except tk.TclError: dialog_bg = "#2b2b2b" if self.current_theme == "dark" else "#f0f0f0"; bold_font = ('Arial', 12, 'bold', 'underline'); normal_font = ('Arial', 10); link_fg = "#6DAEFF" if self.current_theme == "dark" else "#0056b3"
        help_win = tk.Toplevel(self.root); help_win.title("QView - Help/Tips"); help_win.configure(bg=dialog_bg); help_win.geometry("550x500"); help_win.transient(self.root); help_win.grab_set() # Increased height for support section
        main_help_frame = ttk.Frame(help_win, padding="15", style="TFrame"); main_help_frame.pack(expand=True, fill="both")
        canvas = tk.Canvas(main_help_frame, bg=dialog_bg, highlightthickness=0); scrollbar = ttk.Scrollbar(main_help_frame, orient="vertical", command=canvas.yview); scrollable_content_frame = ttk.Frame(canvas, style="TFrame")
        scrollable_content_frame.bind("<Configure>",lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable_content_frame, anchor="nw"); canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True); scrollbar.pack(side="right", fill="y")
        ttk.Label(scrollable_content_frame, text="Help & Tips", font=bold_font).pack(pady=(0, 10), anchor='w')
        tips = ["- Use the Treeview (left) to navigate posts.", "- Click Treeview headers to sort (Post # & Date).", "- Use 'Post #' entry to jump directly (e.g., 123, 10-15, 1,5,10).", "- 'Keyword/Theme' searches post text and assigned themes.", "- 'Search by Date' uses a calendar for specific day lookups.", "- 'Delta Search' finds posts on the same Month/Day across all years.",  "- 'Today's Deltas' shows posts from this M/D (hover for date).", "- Bookmark posts and view them with 'View Bookmarks'.", "- Export the current list to HTML or CSV.", "- Toggle 'Dark to Light' / 'Into the Dark' for theme.", "- Links in post text and 'Show Links' window are clickable.", "- Use 'Settings' to change the application theme and link opening preferences."]
        for tip in tips: ttk.Label(scrollable_content_frame, text=tip, wraplength=480, justify=tk.LEFT, font=normal_font).pack(anchor='w', padx=5, pady=1)
        ttk.Label(scrollable_content_frame, text="Resources", font=bold_font).pack(pady=(20, 10), anchor='w')
        resources = {"QAnon.pub": "https://qanon.pub/", "Q Agg (qagg.news)": "https://qagg.news/", "Gematrix.org": "https://www.gematrix.org/"}
        for text, url in resources.items():
            label = ttk.Label(scrollable_content_frame, text=text, cursor="hand2", style="TLabel"); label.configure(font=(normal_font[0], normal_font[1], "underline"), foreground=link_fg); label.pack(anchor='w', padx=5, pady=2); label.bind("<Button-1>", lambda e, link=url: utils.open_link_with_preference(link, self.app_settings))
        # --- Support & Feedback Section ---
        ttk.Label(scrollable_content_frame, text="Support & Feedback", font=bold_font).pack(pady=(20, 10), anchor='w')
        support_text = "If you find QView helpful, you can show your support and help keep the coffee flowing!"
        ttk.Label(scrollable_content_frame, text=support_text, wraplength=460, justify=tk.LEFT, font=normal_font).pack(anchor='w', padx=5, pady=1)
        donation_link_text = "Buy me a coffee ☕"; donation_url = "https://www.buymeacoffee.com/qview1776"
        donation_label = ttk.Label(scrollable_content_frame, text=donation_link_text, cursor="hand2", style="TLabel"); donation_label.configure(font=(normal_font[0], normal_font[1], "underline"), foreground=link_fg); donation_label.pack(anchor='w', padx=5, pady=2); donation_label.bind("<Button-1>", lambda e, link=donation_url: utils.open_link_with_preference(link, self.app_settings))
        feedback_email_text = "Feedback/Suggestions: qview1776@gmail.com"; feedback_label = ttk.Label(scrollable_content_frame, text=feedback_email_text, style="TLabel"); feedback_label.configure(font=normal_font); feedback_label.pack(anchor='w', padx=5, pady=(5,2))
        # --- End Support & Feedback Section ---
        close_button_frame = ttk.Frame(main_help_frame, style="TFrame"); close_button_frame.pack(fill=tk.X, pady=(15,0))
        ttk.Button(close_button_frame, text="Close", command=help_win.destroy).pack(pady=(0,5))
        widgets_to_bind_scroll = [canvas, scrollable_content_frame] + list(scrollable_content_frame.winfo_children())
        for widget in widgets_to_bind_scroll:
            widget.bind("<MouseWheel>", lambda e, cw=canvas: self._on_mousewheel(e, cw), add="+")
            widget.bind("<Button-4>", lambda e, cw=canvas: self._on_scroll_up(e, cw), add="+")
            widget.bind("<Button-5>", lambda e, cw=canvas: self._on_scroll_down(e, cw), add="+")
    # --- END SHOW_HELP_WINDOW ---

    # --- START SHOW_ABOUT_DIALOG ---
    def show_about_dialog(self):
        messagebox.showinfo("About QView", "QView - Post Viewer\n\nVersion: 0.8.0 (Welcome Screen Update)\nDeveloped for exploring Q posts data.\n\nHappy digging!", parent=self.root)
    # --- END SHOW_ABOUT_DIALOG ---

    # --- START SHOW_POST_LINKS_WINDOW_EXTERNAL ---
    def show_post_links_window_external(self):
        if not self.current_post_urls: messagebox.showinfo("Links", "No URLs found in the current post.", parent=self.root); return
        display_urls = self.current_post_urls
        try: popup_bg = self.style.lookup("TFrame", "background"); canvas_bg = self.style.lookup("Treeview", "fieldbackground"); link_label_fg = self.link_label_fg_dark if self.current_theme == "dark" else self.link_label_fg_light
        except tk.TclError: popup_bg = "#2b2b2b" if self.current_theme == "dark" else "#f0f0f0"; canvas_bg = "#3c3f41" if self.current_theme == "dark" else "#ffffff"; link_label_fg = self.link_label_fg_dark if self.current_theme == "dark" else self.link_label_fg_light
        link_window = tk.Toplevel(self.root); link_window.title("Post URLs"); link_window.configure(bg=popup_bg); link_window.geometry("600x400"); link_window.transient(self.root); link_window.grab_set()
        canvas = tk.Canvas(link_window, bg=canvas_bg, highlightthickness=0); scrollbar = ttk.Scrollbar(link_window, orient="vertical", command=canvas.yview); scrollable_frame = ttk.Frame(canvas, style="TFrame")
        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas_window = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw"); canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True, padx=5, pady=5); scrollbar.pack(side="right", fill="y")
        for url in display_urls:
            def open_url_action_factory(u=url): return lambda e: utils.open_link_with_preference(u, self.app_settings)
            link_label = ttk.Label(scrollable_frame, text=url, cursor="hand2", style="TLabel"); link_label.configure(font=("TkDefaultFont", 10, "underline"), foreground=link_label_fg); link_label.pack(anchor="w", padx=10, pady=3); link_label.bind("<Button-1>", open_url_action_factory(url))
        def frame_width(event): canvas_width = event.width; canvas.itemconfig(canvas_window, width = canvas_width)
        canvas.bind("<Configure>", frame_width)
    # --- END SHOW_POST_LINKS_WINDOW_EXTERNAL ---

    # --- START OPEN_DOWNLOADED_ARTICLE ---
    def open_downloaded_article(self, filepath):
        if filepath and os.path.exists(filepath):
            file_url = f"file:///{os.path.abspath(filepath)}"
            utils.open_link_with_preference(file_url, self.app_settings)
        else:
            messagebox.showerror("Error", "Saved article file not found or path is invalid.", parent=self.root)
            self.update_display()
    # --- END OPEN_DOWNLOADED_ARTICLE ---

# --- END QPOSTVIEWER_CLASS_DEFINITION ---