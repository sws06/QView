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
    def __init__(self, widget, text_generator, delay=700, follow=True):
        self.widget = widget
        self.text_generator = text_generator
        self.delay = delay
        self.follow = follow
        self.tip_window = None
        self.id = None
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
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 1
        self.tip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
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

        # ---- START REPLACEMENT ICON/LOGO LOGIC ----
       # try:
        #    # Load the main application icon
         #   icon_path_ico = os.path.join(config.APP_ROOT_DIR, 'q_icon.ico')
          #  if os.path.exists(icon_path_ico):
           #     self.root.iconbitmap(icon_path_ico)
            
            # Pre-load the RWB theme-specific logo and keep a reference
            #self.rwb_logo_image = None
            #rwb_logo_path = os.path.join(config.APP_ROOT_DIR, 'rwb_logo.png')
            #if os.path.exists(rwb_logo_path):
                # Use Pillow to correctly handle PNG transparency
                #img_pil = Image.open(rwb_logo_path)
                #self.rwb_logo_image = ImageTk.PhotoImage(img_pil)
           # else:
                # This will print to your terminal if the logo is missing from your QView folder
               # print("NOTE: 'rwb_logo.png' not found. The welcome screen graphic will not be displayed.")

       # except Exception as e:
           # print(f"Error setting application icon or loading theme images: {e}")
        # ---- END REPLACEMENT ICON/LOGO LOGIC ----

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

        self.style = ttk.Style()

        # --- Main Panes ---

        self.tree_frame = ttk.Frame(root)
        self.tree_frame.grid(row=0, column=0, padx=10, pady=(10,0), sticky="nswe")
        root.grid_rowconfigure(0, weight=1)
        root.grid_columnconfigure(0, weight=1, minsize=280)

        self.details_outer_frame = ttk.Frame(root)
        self.details_outer_frame.grid(row=0, column=1, padx=(0,10), pady=(10,0), sticky="nswe")
        root.grid_columnconfigure(1, weight=3)
        # --- MODIFIED: Configure rows and columns INSIDE details_outer_frame for vertical split ---
        self.details_outer_frame.grid_rowconfigure(0, weight=1)    # Both components will be in row 0
        self.details_outer_frame.grid_columnconfigure(0, weight=3) # Text area column (75%)
        self.details_outer_frame.grid_columnconfigure(1, weight=1) # Image display column (25%)
        # --- END MODIFICATION ---

        # --- Treeview Setup ---

        self.post_tree = ttk.Treeview(self.tree_frame, columns=("Post #", "Date", "Bookmarked"), show="headings")
        self.scrollbar_y = ttk.Scrollbar(self.tree_frame, orient="vertical", command=self.post_tree.yview)
        self.post_tree.configure(yscrollcommand=self.scrollbar_y.set)
        self.post_tree.heading("Post #", text="Post #", anchor='w', command=lambda: self.sort_treeview_column("Post #", False))
        self.post_tree.heading("Date", text="Date", anchor='w', command=lambda: self.sort_treeview_column("Date", False))
        self.post_tree.heading("Bookmarked", text="★", anchor='center', command=lambda: self.sort_treeview_column("Bookmarked", False))
        self.post_tree.column("Post #", width=70, stretch=tk.NO, anchor='w')
        self.post_tree.column("Date", width=110, stretch=tk.YES, anchor='w')
        self.post_tree.column("Bookmarked", width=30, stretch=tk.NO, anchor='center')
        self.post_tree.grid(row=0, column=0, sticky="nswe")
        self.scrollbar_y.grid(row=0, column=1, sticky="ns")
        self.tree_frame.grid_rowconfigure(0, weight=1)
        self.tree_frame.grid_columnconfigure(0, weight=1)

        # --- Text Area Setup (gridding remains the same, it's in the correct new column 0)---
        self.text_area_frame = ttk.Frame(self.details_outer_frame) #
        self.text_area_frame.grid(row=0, column=0, sticky="nswe") # Now in column 0 of the vertical split
        self.text_area_frame.grid_rowconfigure(0, weight=1) #
        self.text_area_frame.grid_columnconfigure(0, weight=1) #

        self.post_text_area = tk.Text(self.text_area_frame, wrap=tk.WORD, #
                                   relief=tk.FLAT, borderwidth=1, font=("TkDefaultFont", 11), #
                                   padx=10, pady=10) #
        self.default_text_area_cursor = self.post_text_area.cget("cursor") #
        self.post_text_scrollbar = ttk.Scrollbar(self.text_area_frame, orient="vertical", command=self.post_text_area.yview) #
        self.post_text_area.configure(yscrollcommand=self.post_text_scrollbar.set) #
        self.post_text_area.grid(row=0, column=0, sticky="nswe") #
        self.post_text_scrollbar.grid(row=0, column=1, sticky="ns") #

        # --- MODIFIED: Image Display Frame Setup ---
        self.image_display_frame = ttk.Frame(self.details_outer_frame) #
        # Place in row 0, new column 1. Use padx for horizontal spacing.
        self.image_display_frame.grid(row=0, column=1, sticky="nswe", padx=(5,0)) # Changed from row=1, column=0 and pady
        self.image_display_frame.grid_columnconfigure(0, weight=1) # Allow content within to expand if needed
        # --- END MODIFICATION ---

        self.post_text_area.bind("<KeyPress>", self._prevent_text_edit)
        
# --- START CONTEXT_MENU_SETUP ---

        # Create the pop-up menu
        self.context_menu = tk.Menu(self.post_text_area, tearoff=0)
        # Add other search providers as needed here

        # Bind the right-click event to the show_context_menu method
        self.post_text_area.bind("<Button-3>", self._show_context_menu)

# --- END CONTEXT_MENU_SETUP ---

        self.configure_text_tags()

# --- START _PREVENT_TEXT_EDIT ---

        def _prevent_text_edit(self, event):
            if event.state & 0x0004: # If Control key is pressed
                if event.keysym.lower() == 'c': return # Allow Ctrl+C
                if event.keysym.lower() == 'a': return # Allow Ctrl+A
            allowed_nav_keys = ["Left", "Right", "Up", "Down", "Prior", "Next", "Home", "End",
                                "Control_L", "Control_R", "Shift_L", "Shift_R", "Alt_L", "Alt_R",
                                "leftarrow", "rightarrow", "uparrow", "downarrow", "PageUp", "PageDown"] #
            if event.keysym in allowed_nav_keys: return #
            return "break" #

# --- END _PREVENT_TEXT_EDIT ---

        # --- Controls Setup ---

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
        Tooltip(self.todays_deltas_button, lambda: f"Posts from {datetime.datetime.now().strftime('%m/%d')} (all years)")

        buttons_frame2 = ttk.Frame(actions_frame)
        buttons_frame2.pack(fill=tk.X, pady=2)
        self.clear_search_button = ttk.Button(buttons_frame2, text="Show All Posts", command=self.clear_search_and_show_all, state=tk.DISABLED)
        self.clear_search_button.pack(side=tk.LEFT, padx=2, expand=True, fill=tk.X)
        self.show_links_button = ttk.Button(buttons_frame2, text="Show Links", command=self.show_post_links_window_external, state=tk.DISABLED)
        self.show_links_button.pack(side=tk.LEFT, padx=2, expand=True, fill=tk.X)
        self.view_article_button = ttk.Button(buttons_frame2, text="Article Not Saved", command=lambda: None, state=tk.DISABLED)
        self.view_article_button.pack(side=tk.LEFT, padx=2, expand=True, fill=tk.X)

        buttons_frame3 = ttk.Frame(actions_frame)
        buttons_frame3.pack(fill=tk.X, pady=2)
        self.bookmark_button = ttk.Button(buttons_frame3, text="Bookmark This Post", command=self.toggle_current_post_bookmark, state=tk.DISABLED)
        self.bookmark_button.pack(side=tk.LEFT, padx=2, expand=True, fill=tk.X)
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
        # --- New Theme Menu Button ---
        self.theme_menu_button = ttk.Menubutton(bottom_buttons_frame, text="Themes", style="TButton")
        self.theme_menu = tk.Menu(self.theme_menu_button, tearoff=0)
        self.theme_menu_button["menu"] = self.theme_menu
        
        self.theme_var = tk.StringVar(value=self.current_theme)
        
        self.theme_menu.add_radiobutton(label="Dark Theme", variable=self.theme_var, value="dark", command=lambda: self._set_theme("dark"))
        self.theme_menu.add_radiobutton(label="Light Theme", variable=self.theme_var, value="light", command=lambda: self._set_theme("light"))
        self.theme_menu.add_radiobutton(label="RWB Theme", variable=self.theme_var, value="rwb", command=lambda: self._set_theme("rwb"))

        self.theme_menu_button.pack(side=tk.LEFT, padx=5) # Use padx=5 instead of fill=tk.X
        # --- End New Theme Menu Button ---

        self.gematria_button = ttk.Button(bottom_buttons_frame, text="Gematria Calc", command=self.show_gematria_calculator_window)
        self.gematria_button.pack(side=tk.LEFT, padx=5, fill=tk.X)
        self.help_button = ttk.Button(bottom_buttons_frame, text="Help & Info", command=self.show_help_window)
        self.help_button.pack(side=tk.LEFT, padx=5, fill=tk.X)
        self.about_button = ttk.Button(bottom_buttons_frame, text="About", command=self.show_about_dialog)
        self.about_button.pack(side=tk.LEFT, padx=5, fill=tk.X)
        ttk.Button(bottom_buttons_frame, text="Quit App", command=self.on_closing).pack(side=tk.LEFT, padx=5, fill=tk.X)

        if self.current_theme == "light":
            self.apply_light_theme()
        elif self.current_theme == "rwb":
            self.apply_rwb_theme()
        else: # Default to dark if theme is "dark" or unknown
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

# --- START CONTEXT_MENU_METHODS ---

    def _search_selection_with(self, search_engine):
        """Takes selected text and searches it on a given platform."""
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
        """Clears and re-adds commands to the context menu."""
        self.context_menu.delete(0, tk.END)
        
        try:
            # Check if there is a selection to enable/disable menu items
            selected_text = self.post_text_area.get(tk.SEL_FIRST, tk.SEL_LAST).strip()
            state = tk.NORMAL if selected_text else tk.DISABLED
        except tk.TclError:
            state = tk.DISABLED

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
        """Shows the context menu if text is selected."""
        # First, ensure the menu has the latest commands
        self._add_context_menu_options()
        
        try:
            # Check if there is a selection
            self.post_text_area.get(tk.SEL_FIRST, tk.SEL_LAST)
            # Display the menu at the cursor's position
            self.context_menu.tk_popup(event.x_root, event.y_root)
        except tk.TclError:
            # No text is selected, do nothing.
            pass

    def _copy_selection_to_clipboard(self):
        """Copies the currently selected text to the clipboard."""
        try:
            selected_text = self.post_text_area.get(tk.SEL_FIRST, tk.SEL_LAST)
            self.root.clipboard_clear()
            self.root.clipboard_append(selected_text)
            print(f"Copied to clipboard: '{selected_text[:50]}...'")
        except tk.TclError:
            print("Copy to clipboard called with no text selected.")
            pass # No text selected

    def _filter_for_selection(self):
        """Takes the selected text and initiates a keyword search for it."""
        try:
            selected_text = self.post_text_area.get(tk.SEL_FIRST, tk.SEL_LAST).strip()
            if not selected_text:
                return

            # Use the existing keyword search logic
            self.keyword_entry.delete(0, tk.END)
            self.keyword_entry.insert(0, selected_text)
            self.search_by_keyword()
            
        except tk.TclError:
            pass # No text selected
            
    def show_gematria_calculator_window(self, initial_text=""):
        """Creates and shows a standalone window for Gematria calculations."""
        if hasattr(self, 'gematria_win') and self.gematria_win.winfo_exists():
            self.gematria_win.lift()
            self.gematria_win.focus_set()
            # If initial text is provided, update the existing window's entry
            if initial_text and hasattr(self, 'gematria_input_entry'):
                 self.gematria_input_entry.delete(0, tk.END)
                 self.gematria_input_entry.insert(0, initial_text)
                 self.gematria_input_entry.focus_set()
                 # Automatically calculate
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
        
        # --- Input Frame ---
        input_frame = ttk.Frame(main_frame)
        input_frame.pack(fill=tk.X)
        
        ttk.Label(input_frame, text="Text:").pack(side=tk.LEFT, padx=(0, 5))
        self.gematria_input_entry = ttk.Entry(input_frame, font=('Arial', 10))
        self.gematria_input_entry.pack(side=tk.LEFT, expand=True, fill=tk.X)
        self.gematria_input_entry.insert(0, initial_text)
        
        # --- Results Frame ---
        results_frame = ttk.Labelframe(main_frame, text="Results", padding="10")
        results_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        self.gematria_simple_var = tk.StringVar(value="Simple: 0")
        self.gematria_reverse_var = tk.StringVar(value="Reverse: 0")
        self.gematria_hebrew_var = tk.StringVar(value="Hebrew: 0")
        
        ttk.Label(results_frame, textvariable=self.gematria_simple_var, font=('Arial', 10, 'bold')).pack(anchor="w")
        ttk.Label(results_frame, textvariable=self.gematria_reverse_var, font=('Arial', 10, 'bold')).pack(anchor="w")
        ttk.Label(results_frame, textvariable=self.gematria_hebrew_var, font=('Arial', 10, 'bold')).pack(anchor="w")
        
        # --- Calculation Logic ---
        def _calculate_and_display():
            text_to_calc = self.gematria_input_entry.get()
            results = utils.calculate_gematria(text_to_calc)
            self.gematria_simple_var.set(f"Simple: {results['simple']}")
            self.gematria_reverse_var.set(f"Reverse: {results['reverse']}")
            self.gematria_hebrew_var.set(f"Hebrew: {results['hebrew']}")
        
        # Add binding to the entry field as well
        self.gematria_input_entry.bind("<Return>", lambda e: _calculate_and_display())

        # --- Button Frame ---
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, side=tk.BOTTOM)
        ttk.Button(button_frame, text="Calculate", command=_calculate_and_display).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 5))
        ttk.Button(button_frame, text="Close", command=self.gematria_win.destroy).pack(side=tk.LEFT, expand=True, fill=tk.X)
        
        # If text was passed in, calculate it immediately
        if initial_text:
            _calculate_and_display()

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
                    # A search filter was active. Clear it and show all posts.
                    # Invalidate current_display_idx before repopulating.
                    # repopulate_treeview(select_first_item=True) will trigger on_tree_select,
                    # which will then correctly set current_display_idx and update the display
                    # to show the first post of the full list.
                    self.current_display_idx = -1 
                    self.df_displayed = self.df_all_posts.copy() #
                    self.current_search_active = False #
                    self.clear_search_button.config(state=tk.DISABLED) #
                    self.repopulate_treeview(self.df_displayed, select_first_item=True) #
                    self.root.update_idletasks() # Allow UI to update
                    # At this point, self.current_display_idx is likely 0 (or the index of the first post)
                    # and the viewer shows that first post.

                # Now, find the actual 'post_to_find' to select it.
                # We search in df_all_posts to get its consistent original DataFrame index.
                matching_posts = self.df_all_posts[self.df_all_posts['Post Number'] == post_to_find] #
                if not matching_posts.empty: #
                    original_df_idx_of_target = matching_posts.index[0]

                    # Ensure the target post's original index is in the current self.df_displayed
                    # (it should be, as df_displayed is now essentially self.df_all_posts).
                    if self.df_displayed is not None and original_df_idx_of_target in self.df_displayed.index:
                        # Get the positional index of the target post within the current df_displayed.
                        target_display_idx_in_current_df = self.df_displayed.index.get_loc(original_df_idx_of_target)

                        # ---- KEY FIX for jump-to-single-post ----
                        # Invalidate current_display_idx RIGHT BEFORE selecting the specific target post.
                        # This ensures that when on_tree_select is triggered for this target_display_idx_in_current_df,
                        # the condition (new_display_idx != self.current_display_idx) inside on_tree_select
                        # will be true (e.g., target_idx != -1), forcing update_display().
                        self.current_display_idx = -1
                        # ---- END KEY FIX ----
                        
                        self.select_tree_item_by_idx(target_display_idx_in_current_df) #
                    else:
                         # This case would be unusual if df_displayed is correctly set to df_all_posts
                         messagebox.showinfo("Not Found", f"Post # {post_to_find} (Original Index {original_df_idx_of_target}) not found in current display view.", parent=self.root) #
                else:
                    messagebox.showinfo("Not Found", f"Post # {post_to_find} not found in all posts.", parent=self.root) #
            else: # This is for range or list search (e.g., "10-15" or "10,12,15")
                results = self.df_all_posts[self.df_all_posts['Post Number'].isin(target_post_numbers)] #
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
                                   "Please enter a keyword or theme to search.",
                                   parent=self.root)
            if not keyword: # If truly empty, restore placeholder
                self.restore_placeholder(None, placeholder, entry_widget)
            return

        keyword_lower = keyword.lower()
        
        # Ensure df_all_posts is not None before trying to search
        if self.df_all_posts is None:
            messagebox.showerror("Data Error", "Post data is not loaded.", parent=self.root)
            return

        results = self.df_all_posts[
            (self.df_all_posts['Text'].str.lower().str.contains(keyword_lower, na=False, regex=False)) |
            (self.df_all_posts['Themes'].apply(lambda x: isinstance(x, list) and any(keyword_lower in theme.lower() for theme in x)))
        ]
        
        self._handle_search_results(results, f"Keyword/Theme = '{keyword}'")
        
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
        if self.df_displayed.empty: # Should not happen if df_all_posts is not empty
             self.show_welcome_message()
        # If no item was selected for some reason (e.g. tree is empty after repopulation), ensure correct state:
        elif self.post_tree.selection() == (): # If nothing ended up selected after repopulate
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
        if self.df_displayed is None or self.df_displayed.empty or self.current_display_idx < 0: #
            messagebox.showwarning("Bookmark", "No post selected to bookmark/unbookmark.", parent=self.root) #
            return
        
        # Get the original DataFrame index of the currently displayed post
        original_df_index_of_current_post = self.df_displayed.index[self.current_display_idx] #

        post_series = self.df_all_posts.loc[original_df_index_of_current_post] #
        post_num_df = post_series.get('Post Number', original_df_index_of_current_post) #
        post_id_str = f"#{post_num_df}" if pd.notna(post_num_df) else f"(Index: {original_df_index_of_current_post})" #
        
        if original_df_index_of_current_post in self.bookmarked_posts: #
            self.bookmarked_posts.remove(original_df_index_of_current_post) #
            messagebox.showinfo("Bookmark", f"Q Drop {post_id_str} unbookmarked.", parent=self.root) #
        else:
            self.bookmarked_posts.add(original_df_index_of_current_post) #
            messagebox.showinfo("Bookmark", f"Q Drop {post_id_str} bookmarked!", parent=self.root) #
        
        self.update_bookmark_button_status() # Updates button text
        
        # Crucially, update_display() refreshes the text content (e.g., [BOOKMARKED] header)
        # It relies on self.current_display_idx, which should still be correct for the post being bookmarked.
        self.update_display() #

        # Repopulate tree to update the '★' column, but DO NOT auto-select the first item.
        self.repopulate_treeview(self.df_displayed, select_first_item=False) #
        
        # Re-select the item that was just bookmarked/unbookmarked.
        # Its positional index (self.current_display_idx) within self.df_displayed has not changed.
        # The iid for the treeview is the original_df_index_of_current_post.
        iid_to_reselect = str(original_df_index_of_current_post)
        if self.post_tree.exists(iid_to_reselect): #
            self.post_tree.selection_set(iid_to_reselect) #
            self.post_tree.focus(iid_to_reselect) #
            self.post_tree.see(iid_to_reselect) #
            # Note: self.post_tree.selection_set() will trigger on_tree_select.
            # Since new_display_idx will equal self.current_display_idx, and welcome_was_showing is false,
            # on_tree_select will NOT call update_display() again, which is correct as we just called it.
        
        self.view_bookmarks_button.config(text=f"View Bookmarks ({len(self.bookmarked_posts)})") # 

    def update_bookmark_button_status(self, is_welcome=False): # Added is_welcome
        if is_welcome or self.df_displayed is None or self.df_displayed.empty or self.current_display_idx < 0:
            self.bookmark_button.config(text="Bookmark Post", state=tk.DISABLED)
            return
        self.bookmark_button.config(state=tk.NORMAL)
        original_df_index = self.df_displayed.index[self.current_display_idx]
        self.bookmark_button.config(text="Unbookmark This Post" if original_df_index in self.bookmarked_posts else "Bookmark This Post")

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

        note_popup.protocol("WM_DELETE_WINDOW", cancel_and_close)

# --- END USER_NOTES_METHODS ---

# --- START EXPORT_DISPLAYED_LIST ---

    def export_displayed_list(self):
        if self.df_displayed is None or self.df_displayed.empty:
            messagebox.showwarning("Export", "No posts to export.", parent=self.root)
            return
        
        export_format = self.export_var.get()
        default_fname = f"q_export_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        if export_format == "HTML":
            file_types = [("HTML files", "*.html"), ("All files", "*.*")]
            initial_ext = ".html"
        elif export_format == "CSV":
            file_types = [("CSV files", "*.csv"), ("All files", "*.*")]
            initial_ext = ".csv"
        else: # Should not happen with OptionMenu
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
                html_full = f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><title>Q Posts GUI Export</title>{css}</head><body><h1>Q Posts Export</h1>{html_full_table}</body></html>"""
                
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

# --- START SETTINGS_WINDOW_METHODS ---
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

        self.settings_win.geometry("400x255")
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
# --- END SETTINGS_WINDOW_METHODS ---

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
            except tk.TclError: # Fallback if style lookup fails
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
            except ValueError: 
                print(f"Error: Tree iid '{selected_iid_str}' not a valid integer for index.")
            except Exception as e: 
                print(f"Error in on_tree_select: {e}")
        else: # No items selected in tree
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
                self.post_tree.insert("", "end", iid=iid_original_index_str, values=(post_num_display, date_str, is_bookmarked_char))

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

        else: # No results found
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
        self.post_text_area.tag_configure("bold_label",foreground="#a9b7c6"); self.post_text_area.tag_configure("post_number_val",foreground="#FFCB6B")
        self.post_text_area.tag_configure("date_val",foreground="#A5C25C"); self.post_text_area.tag_configure("author_val",foreground="#B0B0B0")
        self.post_text_area.tag_configure("themes_val",foreground="#C39AC9"); self.post_text_area.tag_configure("image_val",foreground="#589DF6")
        self.post_text_area.tag_configure("clickable_link_style",foreground=self.link_label_fg_dark); self.post_text_area.tag_configure("bookmarked_header",foreground="#FFD700")
        self.post_text_area.tag_configure("quoted_ref_header",foreground="#ABBFD0"); self.post_text_area.tag_configure("quoted_ref_text_body",foreground="#FFEE77")
        self.post_text_area.tag_configure("welcome_title_tag", foreground="#FFCB6B"); self.post_text_area.tag_configure("welcome_text_tag", foreground="#e0e0e0")
        self.post_text_area.tag_configure("welcome_emphasis_tag", foreground="#A5C25C"); self.post_text_area.tag_configure("welcome_closing_tag", foreground="#FFD700")

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
        
        # --- FIX: Added complete set of tag configurations ---
        self.post_text_area.tag_configure("bold_label",foreground=fg)
        self.post_text_area.tag_configure("post_number_val",foreground=accent_gold)
        self.post_text_area.tag_configure("date_val",foreground=subtle_text_color)
        self.post_text_area.tag_configure("author_val",foreground=subtle_text_color)
        self.post_text_area.tag_configure("themes_val",foreground=link_color)
        self.post_text_area.tag_configure("image_val",foreground=link_color)
        self.post_text_area.tag_configure("clickable_link_style",foreground=link_color)
        self.post_text_area.tag_configure("bookmarked_header",foreground=accent_red)
        self.post_text_area.tag_configure("quoted_ref_header",foreground=accent_gold)
        self.post_text_area.tag_configure("quoted_ref_text_body",foreground=fg)
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
        
        # --- Add this new tag configuration ---
        self.post_text_area.tag_configure("stringer_tag", foreground="#00C853", underline=True)

        self.post_text_area.tag_configure("clickable_link_style", underline=True)
        def show_hand_cursor(event): event.widget.config(cursor="hand2")
        def show_arrow_cursor(event): event.widget.config(cursor=self.default_text_area_cursor)
        
        # --- Also bind the hand cursor to the new stringer tag ---
        self.post_text_area.tag_bind("stringer_tag", "<Enter>", show_hand_cursor)
        self.post_text_area.tag_bind("stringer_tag", "<Leave>", show_arrow_cursor)

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

    def _insert_text_with_clickable_urls(self, text_content_raw, base_tags_tuple, main_post_original_df_index, link_event_tag_prefix):
        if pd.isna(text_content_raw) or not str(text_content_raw).strip():
            self.post_text_area.insert(tk.END, "", base_tags_tuple if base_tags_tuple else ())
            return
        text_content = utils.sanitize_text_for_tkinter(text_content_raw)
        if not isinstance(text_content, str) or not text_content.strip():
            self.post_text_area.insert(tk.END, str(text_content) if pd.notna(text_content) else "", base_tags_tuple if base_tags_tuple else ())
            return

        last_end = 0
        for url_match in config.URL_REGEX.finditer(text_content):
            start, end = url_match.span()
            if start > last_end: self.post_text_area.insert(tk.END, text_content[last_end:start], base_tags_tuple if base_tags_tuple else ())
            url = url_match.group(0)
            clickable_tag_instance = f"{link_event_tag_prefix}_url_{url_match.start()}"
            current_tags = list(base_tags_tuple) if base_tags_tuple else []
            current_tags.extend(['clickable_link_style', clickable_tag_instance])
            self.post_text_area.insert(tk.END, url, tuple(current_tags))
            self.post_text_area.tag_bind(clickable_tag_instance, "<Button-1>", lambda e, u=url: utils.open_link_with_preference(u, self.app_settings))
            last_end = end
        if last_end < len(text_content): self.post_text_area.insert(tk.END, text_content[last_end:], base_tags_tuple if base_tags_tuple else ())

# --- END _INSERT_TEXT_WITH_CLICKABLE_URLS ---

# --- START UPDATE_DISPLAY ---

    def update_display(self):
        for widget in self.image_display_frame.winfo_children(): widget.destroy()
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
                                    
# --- FIX: Add clickable link icon next to quote thumbnail ---
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
                                    # --- END FIX ---
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

                # --- FIX: Revert call to use _insert_text_with_clickable_urls ---
                self._insert_text_with_clickable_urls(ref_text_content_raw, ("quoted_ref_text_body",), original_df_index, f"qref_{original_df_index}_{ref_idx}")
                self.post_text_area.insert(tk.END, "\n")
            self.post_text_area.insert(tk.END, "\n")
        
        # --- FIX: Revert call to use _insert_text_with_clickable_urls ---
        main_text_content_raw = post.get('Text', '')
        self.post_text_area.insert(tk.END, "Post Text:\n", ("bold_label"))
        self._insert_text_with_clickable_urls(main_text_content_raw, (), original_df_index, f"main_{original_df_index}")
        
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
                # --- FIX: Revert call to use _insert_text_with_clickable_urls ---
                self.post_text_area.insert(tk.END, "\nSource Link: ", "bold_label")
                self._insert_text_with_clickable_urls(actual_metadata_link_str, ("clickable_link_style",) , original_df_index, f"metalink_{original_df_index}")
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
            if self.current_search_active: self.clear_search_and_show_all()
            if self.df_displayed is not None and original_df_idx_to_jump_to in self.df_displayed.index: 
                display_idx = self.df_displayed.index.get_loc(original_df_idx_to_jump_to)
                self.current_display_idx = display_idx; self.select_tree_item_by_idx(self.current_display_idx)
            else: messagebox.showinfo("Not Found", f"Post # {target_post_num_int} could not be focused.", parent=self.root)
        else: messagebox.showinfo("Not Found", f"Post # {target_post_num_int} not found in dataset.", parent=self.root)

# --- END JUMP_TO_POST_FROM_REF ---

# --- END QPOSTVIEWER_CLASS_DEFINITION ---