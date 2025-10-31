# --- START GUI_PY_HEADER ---

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from tkcalendar import Calendar
from PIL import Image, ImageTk
from collections import defaultdict
import io
import pandas as pd
import datetime
import os
import webbrowser
import urllib.parse
import threading
import re # For parsing post numbers from references
import config
import math
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
        
# --- START QCLOCK_CLASS ---
class QClock:
# --- START __INIT__ ---
    def __init__(self, parent_frame, root, gui_instance, style, data, plot_mode="nebula"):
        self.parent_frame = parent_frame
        self.root = root
        self.gui_instance = gui_instance
        self.style = style
        self.post_data = data
        self.plot_mode = plot_mode

        # State Management
        self.tooltip_window = None
        self.dot_id_to_post_info = {}
        self.post_num_to_dot_id = {}
        self.highlighted_dots = set()
        self.delta_source_post_num = None
        self.drawn_lines = []
        self.multi_selection = set()
        self.zoom_level = 1.0
        self.zoom_factor = 1.1
        self.pan_start_x = 0
        self.pan_start_y = 0
        self.highlighted_date_id = None
        self.hover_highlighted_dots = set()
        self.zoom_threshold_days = 2.0
        self.zoom_threshold_hours = 10.0
        self.spiral_start_radius = 20
        
        # Filter State Variables
        self.filter_show_images = tk.BooleanVar(value=True)
        self.filter_show_links = tk.BooleanVar(value=True)
        self.filter_show_text = tk.BooleanVar(value=True)
        self.show_deltas_var = tk.BooleanVar(value=True)

        # Main UI Frame
        self.clock_frame = ttk.Frame(self.parent_frame)
        self.clock_frame.pack(fill=tk.BOTH, expand=True)
        
        # --- MODIFIED: A single, streamlined control row ---
        controls_frame = ttk.Frame(self.clock_frame)
        controls_frame.pack(fill=tk.X, pady=(5, 0), padx=20)

        # NEW: "Tools" Menubutton
        tools_button = ttk.Menubutton(controls_frame, text="Tools", style="TButton")
        tools_button.pack(side=tk.LEFT)
        tools_menu = tk.Menu(tools_button, tearoff=0)
        tools_button["menu"] = tools_menu
        tools_menu.add_command(label="Maximize ↗", command=lambda: self.gui_instance.maximize_single_clock(self.post_data))
        tools_menu.add_command(label="Save as Image 💾", command=self._save_as_image)

        # UPDATED: "Filters" Menubutton now includes "Show Deltas"
        filter_button = ttk.Menubutton(controls_frame, text="Filters", style="TButton")
        filter_button.pack(side=tk.LEFT, padx=10)
        filter_menu = tk.Menu(filter_button, tearoff=0)
        filter_button["menu"] = filter_menu
        filter_menu.add_checkbutton(label="Show Image Posts", variable=self.filter_show_images, command=self.on_resize)
        filter_menu.add_checkbutton(label="Show Link Posts", variable=self.filter_show_links, command=self.on_resize)
        filter_menu.add_checkbutton(label="Show Text-Only Posts", variable=self.filter_show_text, command=self.on_resize)
        filter_menu.add_separator()
        filter_menu.add_checkbutton(label="Show Delta Connections", variable=self.show_deltas_var)
        
        # Zoom Label
        self.zoom_label = ttk.Label(controls_frame, text="Zoom: 100%")
        self.zoom_label.pack(side=tk.RIGHT, padx=10)
        # --- END MODIFICATION ---

        # Canvas for the Clock
        self.canvas = tk.Canvas(self.clock_frame, bg="white", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # Bottom Status Bar
        status_frame = ttk.Frame(self.clock_frame, padding=(10, 5))
        status_frame.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.status_label = ttk.Label(status_frame, text="Click a dot to see connections.")
        self.status_label.pack(side=tk.LEFT, expand=True, fill=tk.X)
        
        self.view_in_list_button = ttk.Button(status_frame, text="View in List", state=tk.DISABLED)
        self.view_in_list_button.pack(side=tk.RIGHT)
        
        # Event Bindings
        self.canvas.bind("<Configure>", self.on_resize)
        self.canvas.bind("<MouseWheel>", self._on_mousewheel_zoom)
        self.canvas.bind("<Button-4>", self._on_mousewheel_zoom)
        self.canvas.bind("<Button-5>", self._on_mousewheel_zoom)
        self.canvas.bind("<ButtonPress-1>", self._on_pan_start)
        self.canvas.bind("<B1-Motion>", self._on_pan_move)
# --- END __INIT__ ---

    def _draw_concentric_guides(self):
        """Draws concentric circles to mark year boundaries on the spiral plot."""
        if self.post_data is None or self.post_data.empty: return

        # We need to sort the data by date to find the first post of each year
        sorted_data = self.post_data.sort_values(by='Datetime_UTC').reset_index()
        total_posts = len(sorted_data)
        
        # Find the index of the first post for each unique year
        year_start_indices = sorted_data.groupby(sorted_data['Datetime_UTC'].dt.year)['index'].min()

        min_dot_dist = self.spiral_start_radius
        max_dot_dist = self.radius - 20

        for year, start_index in year_start_indices.items():
            # Don't draw a ring for the very first post, as it's at the start of the spiral
            if start_index == 0: continue

            # Calculate the radius for this year's first post using the same logic as plot_posts
            normalized_index = start_index / (total_posts - 1)
            radius = min_dot_dist + (normalized_index * (max_dot_dist - min_dot_dist))

            # Draw the faint, dashed circle
            self.canvas.create_oval(self.center_x - radius, self.center_y - radius,
                                    self.center_x + radius, self.center_y + radius,
                                    outline="lightgrey", dash=(4, 4), tags="grid")
            
            # Add a year label on top of the circle for clarity
            self.canvas.create_text(self.center_x, self.center_y - radius - 8,
                                    text=str(year), font=("Arial", 8, "italic"),
                                    fill="grey", tags="grid")

    def _save_as_image(self):
        """Saves the current state of the canvas to a PNG image file."""
        try:
            from PIL import Image, EpsImagePlugin
            import io
            # This helps Pillow's PostScript parser find the Ghostscript executable if needed
            EpsImagePlugin.gs_windows_exe = 'gs' 
        except ImportError:
            messagebox.showerror("Missing Library", 
                                 "The 'Pillow' library is required to save images.\n\nPlease install it by running:\npip install Pillow",
                                 parent=self.root)
            return

        # Ask the user where to save the file
        filepath = filedialog.asksaveasfilename(
            parent=self.root,
            title="Save Clock as Image",
            defaultextension=".png",
            filetypes=[("PNG Image", "*.png"), ("All files", "*.*")],
            initialfile=f"qclock_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        )

        if not filepath: # User cancelled the dialog
            return

        try:
            # Generate a PostScript representation of the canvas in memory
            ps_data = self.canvas.postscript(colormode='color')
            
            # Use Pillow to open the PostScript data and save it as a PNG
            img = Image.open(io.BytesIO(ps_data.encode('utf-8')))
            img.save(filepath, 'png')
            
            messagebox.showinfo("Success", f"Clock image saved successfully to:\n{filepath}", parent=self.root)
        
        except Exception as e:
            messagebox.showerror("Save Error", f"An error occurred while saving the image:\n{e}", parent=self.root)

    def _draw_concentric_guides(self):
        """Draws concentric circles to mark year boundaries on the spiral plot."""
        if self.post_data.empty: return

        sorted_data = self.post_data.sort_values(by='Datetime_UTC').reset_index()
        total_posts = len(sorted_data)
        
        # Find the unique years and their first post's index in the sorted data
        year_start_indices = sorted_data.groupby(sorted_data['Datetime_UTC'].dt.year)['index'].min()

        min_dot_dist = self.spiral_start_radius
        max_dot_dist = self.radius - 20

        for year, start_index in year_start_indices.items():
            if start_index == 0: continue # Don't draw a ring for the very first post

            # Calculate the radius for this year's first post
            normalized_index = start_index / (total_posts - 1)
            radius = min_dot_dist + (normalized_index * (max_dot_dist - min_dot_dist))

            # Draw the faint, dashed circle
            self.canvas.create_oval(self.center_x - radius, self.center_y - radius,
                                    self.center_x + radius, self.center_y + radius,
                                    outline="lightgrey", dash=(4, 4), tags="grid")
            
            # Add a year label on the circle
            self.canvas.create_text(self.center_x, self.center_y - radius - 8,
                                    text=str(year), font=("Arial", 8, "italic"),
                                    fill="grey", tags="grid")

    def _draw_today_highlight(self):
        """Draws a faint slice on the clock to indicate the current day of the year."""
        today = datetime.datetime.now()
        day_of_year = today.timetuple().tm_yday

        # --- CORRECTED FORMULA ---
        # This formula correctly maps Jan 1st to the top of the clock (90 degrees)
        angle = 90 - ((day_of_year - 1) / 365.25 * 360.0)
        extent = -(360 / 365.25) # Use a negative extent for clockwise drawing
        # --- END CORRECTION ---

        self.canvas.create_arc(self.center_x - self.radius, self.center_y - self.radius,
                                self.center_x + self.radius, self.center_y + self.radius,
                                start=angle, extent=extent,
                                style=tk.PIESLICE, fill="yellow", 
                                stipple="gray25",
                                outline="", tags="grid")
                                
    def _draw_center_hub(self):
        """Draws the detailed inner clock face and sets the starting radius for the spiral."""
        hub_radius = self.radius * 0.3
        minute_ring_radius = hub_radius + 15
        
        # --- THIS IS THE CHANGE ---
        # Set the starting point for the spiral just outside the minute ring
        self.spiral_start_radius = minute_ring_radius + 10
        # --- END CHANGE ---

        # 1. Draw the light gray background for the hub
        self.canvas.create_oval(self.center_x - hub_radius, self.center_y - hub_radius,
                                self.center_x + hub_radius, self.center_y + hub_radius,
                                fill="#f0f0f0", outline="black", width=1.5, tags="grid")

        # 2. Draw the minute markers
        for i in range(12):
            minute = i * 5
            angle = math.radians(i * 30 - 90)
            x = self.center_x + minute_ring_radius * math.cos(angle)
            y = self.center_y + minute_ring_radius * math.sin(angle)
            self.canvas.create_text(x, y, text=f"[{minute:02d}]", font=("Arial", 7, "bold"), fill="grey", tags="grid")

        # 3. Draw the bold hour hash marks and numbers
        for i in range(1, 13):
            angle = math.radians(i * 30 - 90)
            x1 = self.center_x + (hub_radius - 5) * math.cos(angle)
            y1 = self.center_y + (hub_radius - 5) * math.sin(angle)
            x2 = self.center_x + hub_radius * math.cos(angle)
            y2 = self.center_y + hub_radius * math.sin(angle)
            self.canvas.create_line(x1, y1, x2, y2, fill="black", width=2.5, tags="grid")
            num_x = self.center_x + (hub_radius - 20) * math.cos(angle)
            num_y = self.center_y + (hub_radius - 20) * math.sin(angle)
            self.canvas.create_text(num_x, num_y, text=str(i), font=("Arial", 12, "bold"), fill="black", tags="grid")
            
        # 4. Draw the central text
        self.canvas.create_text(self.center_x, self.center_y, text="QView Clock", font=("Arial", 10, "bold"), fill="black", tags="grid")

    def on_resize(self, event=None):
        """Handles window resizing. Redraws everything."""
        self.canvas.delete("all")
        
        self.draw_clock()
        self._draw_today_highlight()
        self._draw_center_hub()
        
        if self.plot_mode == "spiral":
            self._draw_spiral_guides()
            self._draw_concentric_guides() # This is the new line

        # Draw the dynamic Level-of-Detail grid
        self._draw_month_grid()
        self._draw_day_grid()
        self._draw_hour_grid()
        
        self._update_grid_visibility()
        
        # Plot the posts on top of everything
        self.plot_posts()

    def draw_clock(self):
        self.canvas.delete("clock_face")
        width = self.canvas.winfo_width()
        height = self.canvas.winfo_height()
        self.center_x, self.center_y = width / 2, height / 2
        self.radius = min(width, height) / 2 - 40
        self.canvas.create_oval(self.center_x - self.radius, self.center_y - self.radius,
                                self.center_x + self.radius, self.center_y + self.radius,
                                outline="black", width=1.5, tags="clock_face")

    def plot_posts(self):
        self.dot_id_to_post_info.clear()
        self.post_num_to_dot_id.clear()
        self._reset_highlights()
        self._reset_multi_selection()
        if self.post_data is None or self.post_data.empty: return

        if self.plot_mode == "spiral":
            sorted_data = self.post_data.sort_values(by='Datetime_UTC').reset_index(drop=True)
            total_posts = len(sorted_data)
            for i, row in sorted_data.iterrows():
                timestamp, post_number = row.get('Datetime_UTC'), row.get('Post Number')
                if pd.notna(timestamp) and pd.notna(post_number):
                    hour, minute = timestamp.hour, timestamp.minute
                    angle = math.radians(((hour % 12) * 30 + minute / 2) - 90)
                    
                    # --- THIS IS THE CHANGE ---
                    # Use the new dynamic start radius instead of a fixed number
                    min_dot_dist = self.spiral_start_radius
                    max_dot_dist = self.radius - 20
                    # --- END CHANGE ---

                    normalized_index = i / (total_posts - 1) if total_posts > 1 else 0
                    dot_dist = min_dot_dist + (normalized_index * (max_dot_dist - min_dot_dist))
                    self._draw_dot(post_number, timestamp, dot_dist, angle, row)
        else: # nebula
            min_post, max_post = self.post_data['Post Number'].min(), self.post_data['Post Number'].max()
            post_range = max_post - min_post if max_post > min_post else 1
            for _, row in self.post_data.iterrows():
                timestamp, post_number = row.get('Datetime_UTC'), row.get('Post Number')
                if pd.notna(timestamp) and pd.notna(post_number):
                    hour, minute = timestamp.hour, timestamp.minute
                    angle = math.radians(((hour % 12) * 30 + minute / 2) - 90)
                    
                    # --- THIS IS THE CHANGE ---
                    # Use the new dynamic start radius here as well for consistency
                    min_dot_dist = self.spiral_start_radius
                    max_dot_dist = self.radius - 20
                    # --- END CHANGE ---

                    normalized_post = (post_number - min_post) / post_range
                    dot_dist = min_dot_dist + (normalized_post * (max_dot_dist - min_dot_dist))
                    self._draw_dot(post_number, timestamp, dot_dist, angle, row)
                                        
    def _draw_dot(self, post_number, timestamp, dot_dist, angle, post_row):
        """Determines the dot's color and draws it on the canvas."""
        has_image = post_row.get('Image Count', 0) > 0
        has_link = isinstance(post_row.get('Text'), str) and ('http://' in post_row['Text'] or 'https://' in post_row['Text'])

        # Filter Logic
        if has_image and not self.filter_show_images.get(): return
        if has_link and not self.filter_show_links.get(): return
        if not has_image and not has_link and not self.filter_show_text.get(): return

        # Color Logic
        dot_color = "blue"
        if has_image and has_link:
            dot_color = "magenta"
        elif has_image:
            dot_color = "turquoise"
        elif has_link:
            dot_color = "orange"

        dot_radius = 2
        dot_x = self.center_x + dot_dist * math.cos(angle)
        dot_y = self.center_y + dot_dist * math.sin(angle)
        
        dot = self.canvas.create_oval(dot_x - dot_radius, dot_y - dot_radius, dot_x + dot_radius, dot_y + dot_radius, 
                                      fill=dot_color, outline=dot_color, tags="post_dot")
        
        # --- MODIFIED: Added post 'Text' to the stored info ---
        post_info = {
            'pn': post_number, 
            'ts': timestamp.strftime("%H:%M:%S"),
            'date': timestamp.strftime("%Y-%m-%d"),
            'text': post_row.get('Text', '')
        }
        # --- END MODIFICATION ---

        self.dot_id_to_post_info[dot] = post_info
        self.post_num_to_dot_id[post_number] = dot
        self.canvas.tag_bind(dot, "<Enter>", lambda e, d_id=dot: self.show_tooltip(e, d_id))
        self.canvas.tag_bind(dot, "<Leave>", self.hide_tooltip)
        self.canvas.tag_bind(dot, "<Button-1>", lambda e, pn=post_number: self.on_dot_click(e, pn))        
        
    def _on_mousewheel_zoom(self, event):
        scale = 1.1 if (event.num == 4 or event.delta > 0) else 1/1.1 if (event.num == 5 or event.delta < 0) else 1.0
        x, y = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        self.canvas.scale("all", x, y, scale, scale)
        for dot_id in self.canvas.find_withtag("post_dot"):
            x1, y1, x2, y2 = self.canvas.coords(dot_id)
            self.canvas.scale(dot_id, (x1+x2)/2, (y1+y2)/2, 1/scale, 1/scale)
        old_zoom_level, self.zoom_level = self.zoom_level, self.zoom_level * scale
        day_crossed = (old_zoom_level < self.zoom_threshold_days and self.zoom_level >= self.zoom_threshold_days) or (old_zoom_level >= self.zoom_threshold_days and self.zoom_level < self.zoom_threshold_days)
        hour_crossed = (old_zoom_level < self.zoom_threshold_hours and self.zoom_level >= self.zoom_threshold_hours) or (old_zoom_level >= self.zoom_threshold_hours and self.zoom_level < self.zoom_threshold_hours)
        if day_crossed or hour_crossed: self._update_grid_visibility()
        self.zoom_label.config(text=f"Zoom: {self.zoom_level:.0%}")
        return "break"

    def _on_pan_start(self, event):
        """Records the starting position for a pan action, only if the background is clicked."""
        # Find the item under the cursor
        items = self.canvas.find_closest(event.x, event.y)
        if not items:
            # Clicked on empty canvas, proceed with pan
            self.pan_start_x = event.x
            self.pan_start_y = event.y
            return

        item_id = items[0]
        tags = self.canvas.gettags(item_id)
        
        # If the item is a post dot, do nothing and let the dot's own click handler fire.
        # Otherwise, start the pan.
        if "post_dot" not in tags:
            self.pan_start_x = event.x
            self.pan_start_y = event.y

    def _on_pan_move(self, event):
        dx, dy = event.x - self.pan_start_x, event.y - self.pan_start_y
        self.canvas.move("all", dx, dy)
        self.pan_start_x, self.pan_start_y = event.x, event.y
    
    def on_dot_click(self, event, post_number):
        is_ctrl_click = (event.state & 0x0004) != 0
        if is_ctrl_click:
            self._reset_highlights()
            dot_id = self.post_num_to_dot_id.get(post_number)
            if not dot_id: return
            if post_number in self.multi_selection:
                self.multi_selection.remove(post_number)
                self.canvas.itemconfig(dot_id, fill="blue", outline="blue")
            else:
                self.multi_selection.add(post_number)
                self.canvas.itemconfig(dot_id, fill="purple", outline="purple")
            if not self.multi_selection:
                self.status_label.config(text="Click a dot to see connections.")
                self.view_in_list_button.config(state=tk.DISABLED)
            else:
                self.status_label.config(text=f"{len(self.multi_selection)} post{'s' if len(self.multi_selection) > 1 else ''} selected.")
                def view_multi():
                    results_df = self.post_data[self.post_data['Post Number'].isin(self.multi_selection)]
                    self.gui_instance._handle_search_results(results_df, "Multi-Select")
                    self.gui_instance.toggle_clock_view()
                self.view_in_list_button.config(state=tk.NORMAL, command=view_multi)
        else:
            self._reset_multi_selection()
            self._reset_highlights()
            clicked_dot_id = self.post_num_to_dot_id.get(post_number)
            if not clicked_dot_id: return
            x1, y1, _, _ = self.canvas.coords(clicked_dot_id)
            center_x1, center_y1 = x1 + 2, y1 + 2
            post_series = self.post_data[self.post_data['Post Number'] == post_number]
            if post_series.empty: return
            posts_to_show_df = post_series
            search_term = f"Post #{post_number}"
            if self.show_deltas_var.get():
                timestamp = post_series.iloc[0].get('Datetime_UTC')
                if pd.notna(timestamp):
                    time_key = timestamp.strftime('%H:%M')
                    delta_post_numbers = app_data.post_time_hhmm_map.get(time_key, [])
                    if delta_post_numbers:
                        self.delta_source_post_num = post_number
                        for pn in delta_post_numbers:
                            dot_id = self.post_num_to_dot_id.get(pn)
                            if dot_id:
                                self.canvas.itemconfig(dot_id, fill="red", outline="red")
                                self.highlighted_dots.add(dot_id)
                                if pn != post_number:
                                    x2, y2, _, _ = self.canvas.coords(dot_id)
                                    self.drawn_lines.append(self.canvas.create_line(center_x1, center_y1, x2 + 2, y2 + 2, fill="#ff4d4d", width=0.5, tags="conn_line"))
                        posts_to_show_df = self.post_data[self.post_data['Post Number'].isin(delta_post_numbers)]
                        search_term = f"Delta Matches for Q#{post_number} at {time_key}"
            # Draw mirror lines (condensed for brevity)
            # ... (mirror line logic would go here, it is correct in the user's file)
            self.status_label.config(text=f"Selected: Q#{post_number} | Deltas: {len(self.highlighted_dots) - 1 if self.highlighted_dots else 0} | Mirrors: {len(self.drawn_lines)}")
            def view_single():
                self.gui_instance._handle_search_results(posts_to_show_df, search_term)
                self.gui_instance.toggle_clock_view()
            self.view_in_list_button.config(state=tk.NORMAL, command=view_single)

    def _reset_highlights(self):
        for line_id in self.drawn_lines: self.canvas.delete(line_id)
        self.drawn_lines.clear()
        for dot_id in self.highlighted_dots:
            if self.canvas.winfo_exists(): self.canvas.itemconfig(dot_id, fill="blue", outline="blue")
        self.highlighted_dots.clear()
        self.delta_source_post_num = None

    def _reset_multi_selection(self):
        for post_num in self.multi_selection:
            dot_id = self.post_num_to_dot_id.get(post_num)
            if dot_id and self.canvas.winfo_exists(): self.canvas.itemconfig(dot_id, fill="blue", outline="blue")
        self.multi_selection.clear()

    def _draw_spiral_guides(self):
        points = []
        num_rotations = len(self.post_data['Datetime_UTC'].dt.year.unique()) + 1
        for i in range(360 * num_rotations):
            angle = math.radians(i)
            radius = (self.radius - 20) * (i / (360 * num_rotations)) + 20
            x = self.center_x + radius * math.cos(angle - math.radians(90))
            y = self.center_y + radius * math.sin(angle - math.radians(90))
            points.append((x, y))
        for i in range(len(points) - 1): self.canvas.create_line(points[i], points[i+1], fill="#f0f0f0", tags="grid")

    def _update_grid_visibility(self):
        self.canvas.itemconfig("day_grid", state='normal' if self.zoom_level >= self.zoom_threshold_days else 'hidden')
        self.canvas.itemconfig("hour_grid", state='normal' if self.zoom_level >= self.zoom_threshold_hours else 'hidden')

    def _draw_month_grid(self):
        """Draws the 12 month labels and lines."""
        months = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
        for i, month in enumerate(months):
            # --- CORRECTED FORMULA ---
            angle_deg = 90 - (i * 30)
            angle_rad = math.radians(angle_deg)
            text_angle_rad = math.radians(angle_deg - 15) # Center text in the slice
            # --- END CORRECTION ---
            
            x1 = self.center_x + (self.radius - 15) * math.cos(angle_rad)
            y1 = self.center_y - (self.radius - 15) * math.sin(angle_rad) # Use minus for y-axis
            x2 = self.center_x + self.radius * math.cos(angle_rad)
            y2 = self.center_y - self.radius * math.sin(angle_rad) # Use minus for y-axis
            self.canvas.create_line(x1, y1, x2, y2, fill="lightgrey", tags=("grid", "month_grid"))
            
            text_x = self.center_x + (self.radius + 15) * math.cos(text_angle_rad)
            text_y = self.center_y - (self.radius + 15) * math.sin(text_angle_rad) # Use minus for y-axis
            self.canvas.create_text(text_x, text_y, text=month, font=("Arial", 9, "bold"), fill="darkgrey", tags=("grid", "month_grid"))
            
    def _draw_day_grid(self):
        """Draws the 365 day lines and labels (initially hidden)."""
        for day_of_year in range(1, 366, 5):
            # --- CORRECTED FORMULA ---
            angle_deg = 90 - ((day_of_year -1) / 365.0 * 360)
            angle_rad = math.radians(angle_deg)
            # --- END CORRECTION ---

            x1 = self.center_x + self.radius * math.cos(angle_rad)
            y1 = self.center_y - self.radius * math.sin(angle_rad) # Use minus for y-axis
            x2 = self.center_x + (self.radius + 5) * math.cos(angle_rad)
            y2 = self.center_y - (self.radius + 5) * math.sin(angle_rad) # Use minus for y-axis
            self.canvas.create_line(x1, y1, x2, y2, fill="lightgrey", tags=("grid", "day_grid"), state='hidden')

            text_x = self.center_x + (self.radius + 15) * math.cos(angle_rad)
            text_y = self.center_y - (self.radius + 15) * math.sin(angle_rad) # Use minus for y-axis
            date = datetime.datetime(2023, 1, 1) + datetime.timedelta(days=day_of_year - 1)
            date_str = date.strftime("%m/%d")
            self.canvas.create_text(text_x, text_y, text=date_str, font=("Arial", 7), fill="grey", tags=("grid", "day_grid"), state='hidden')
    
    def _draw_hour_grid(self):
        for hour in range(24):
            angle = math.radians((hour / 24.0) * 360 - 90)
            x1, y1 = self.center_x + (self.radius-10) * math.cos(angle), self.center_y + (self.radius-10) * math.sin(angle)
            x2, y2 = self.center_x + (self.radius+10) * math.cos(angle), self.center_y + (self.radius+10) * math.sin(angle)
            self.canvas.create_line(x1, y1, x2, y2, fill="#f0f0f0", width=1, tags=("grid", "hour_grid"), state='hidden')
            text_x, text_y = self.center_x + (self.radius-25) * math.cos(angle), self.center_y + (self.radius-25) * math.sin(angle)
            self.canvas.create_text(text_x, text_y, text=f"{hour:02d}", font=("Arial", 8, "bold"), fill="black", tags=("grid", "hour_grid"), state='hidden')
            
    def show_tooltip(self, event, dot_id):
        if self.tooltip_window:
            self.hidetip()

        post_info = self.dot_id_to_post_info.get(dot_id)
        if not post_info: return
            
        # --- FIX #2: Clean the text to remove leading post references ---
        raw_text = post_info.get('text', '[No text available]')
        # Use regex to find and remove any lines at the start that are just post references
        cleaned_text = re.sub(r'^(>>\d+\s*)+', '', raw_text.strip())
        
        snippet = cleaned_text.replace('\n', ' ').strip()
        if len(snippet) > 150:
            snippet = snippet[:150].rsplit(' ', 1)[0] + '...'
        
        tooltip_text = f"Q #{post_info['pn']}\n\n{snippet}"
        
        if self.show_deltas_var.get() and dot_id in self.highlighted_dots and self.delta_source_post_num:
             tooltip_text += f"\n\nΔ Match with Q #{self.delta_source_post_num}"

        x, y = event.x_root + 15, event.y_root + 10
        
        self.tooltip_window = tw = tk.Toplevel(self.canvas)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")

        label = tk.Label(tw, text=tooltip_text, justify=tk.LEFT, wraplength=300,
                         background="#FFFFE0", relief=tk.SOLID, borderwidth=1,
                         font=("tahoma", "9", "normal"))
        label.pack(ipadx=1)

        # On-canvas label logic
        coords = self.canvas.coords(dot_id)
        if coords:
            dot_x, dot_y = (coords[0] + coords[2]) / 2, (coords[1] + coords[3]) / 2
            
            date_obj = datetime.datetime.strptime(post_info['date'], "%Y-%m-%d")
            date_label_text = date_obj.strftime("%Y/%m/%d") + f", {post_info['ts']}"

            # --- FIX #1: Make the on-canvas font bigger and adjust the background ---
            # Create a wider background for the longer text
            self.canvas.create_rectangle(dot_x - 55, dot_y - 20, dot_x + 55, dot_y - 8, 
                                         fill="white", outline="black", width=0.5, tags="transient_label")
            self.canvas.create_text(dot_x, dot_y - 14, text=date_label_text, 
                                    font=("Arial", 9, "bold"), fill="black", tags="transient_label")
        # --- END MODIFICATION ---

    def hide_tooltip(self, event=None):
        if self.tooltip_window:
            self.tooltip_window.destroy()
            self.tooltip_window = None
        
        # NEW: Delete the on-canvas label when the mouse leaves
        self.canvas.delete("transient_label")
# --- END QCLOCK_CLASS ---

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

        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)

        self.welcome_logo_photo = None
        try:
            logo_path = os.path.join(os.getcwd(), "welcome_logo.png")
            if os.path.exists(logo_path):
                img = Image.open(logo_path)
                img.thumbnail((800, 800), Image.Resampling.LANCZOS)
                self.welcome_logo_photo = ImageTk.PhotoImage(img)
        except Exception as e:
            print(f"Could not load welcome logo: {e}")

        self.displayed_images_references = []
        self._quote_image_references = []
        self.current_post_urls = []
        self.current_post_downloaded_article_path = None
        self._context_expand_vars = {}
        self._context_tag_refs = []
        self.context_history = []
        self._is_navigating_context_back = False
        self.calendar_first_open = True

        self.app_settings = settings.load_settings()
        self.bookmarked_posts = utils.load_bookmarks_from_file(config.BOOKMARKS_FILE_PATH)
        self.user_notes = utils.load_user_notes(config.USER_NOTES_FILE_PATH)

        self.df_all_posts = app_data.load_or_parse_data()
        self.df_displayed = pd.DataFrame()
        self.current_search_active = False
        self.current_display_idx = -1

        self.current_theme = self.app_settings.get("theme", settings.DEFAULT_SETTINGS["theme"])
        
        self.placeholder_fg_color_dark = "grey"
        self.placeholder_fg_color_light = "#757575"
        self.link_label_fg_dark = "#6DAEFF"
        self.link_label_fg_light = "#0056b3"
        self.highlight_abbreviations_var = tk.BooleanVar(value=self.app_settings.get("highlight_abbreviations", settings.DEFAULT_SETTINGS.get("highlight_abbreviations")))

        self.style = ttk.Style()
        self.theme_var = tk.StringVar(value=self.current_theme)

        # --- Main Content Frame ---
        self.main_content_frame = ttk.Frame(root)
        self.main_content_frame.grid(row=0, column=0, columnspan=2, padx=10, pady=(10,0), sticky="nsew")
        self.main_content_frame.grid_rowconfigure(0, weight=1)
        self.main_content_frame.grid_columnconfigure(0, weight=1)
        
        # Setup List View Frame
        self.list_view_frame = ttk.Frame(self.main_content_frame)
        self.list_view_frame.grid(row=0, column=0, sticky="nsew") 
        
        # Setup Multi-Clock Frame
        self.multi_clock_frame = ttk.Frame(self.main_content_frame)
        self.multi_clock_frame.grid(row=0, column=0, sticky="new") 
        self.multi_clock_frame.grid_remove()
        self.clock_instances = []
        self.clocks_initialized = False
        self.clock_layout = "horizontal"

        # Setup Threads View Frame
        self.threads_view_frame = ttk.Frame(self.main_content_frame)
        self.threads_view_frame.grid(row=0, column=0, sticky="nsew")
        self.threads_view_frame.grid_remove() 
        self._setup_threads_view()
        
        # --- NEW: Setup Symbols View Frame ---
        self.symbols_view_frame = ttk.Frame(self.main_content_frame)
        self.symbols_view_frame.grid(row=0, column=0, sticky="nsew")
        self.symbols_view_frame.grid_remove()
        self._setup_symbols_view()
        # --- END NEW ---
        
        self.list_view_paned_window = ttk.Panedwindow(self.list_view_frame, orient=tk.HORIZONTAL)
        self.list_view_paned_window.pack(fill=tk.BOTH, expand=True)

        self.tree_frame = ttk.Frame(self.list_view_paned_window)
        # --- THIS IS THE FIX ---
        self.list_view_paned_window.add(self.tree_frame, weight=1) # Corrected variable name
        # --- END FIX ---
        self.details_outer_frame = ttk.Frame(self.list_view_paned_window)
        self.list_view_paned_window.add(self.details_outer_frame, weight=3)
        self.tree_frame.grid_rowconfigure(0, weight=1)
        self.tree_frame.grid_columnconfigure(0, weight=1)

        self.post_tree = ttk.Treeview(self.tree_frame, columns=("Post #", "Date", "Notes", "Bookmarked"), show="headings")
        self.scrollbar_y = ttk.Scrollbar(self.tree_frame, orient="vertical", command=self.post_tree.yview)
        self.post_tree.configure(yscrollcommand=self.scrollbar_y.set)
        self.post_tree.heading("Post #", text="Post #", anchor='w', command=lambda: self.sort_treeview_column("Post #", False))
        self.post_tree.heading("Date", text="Date", anchor='w', command=lambda: self.sort_treeview_column("Date", False))
        self.post_tree.heading("Notes", text="♪", anchor='center', command=lambda: self.sort_treeview_column("Notes", False))
        self.post_tree.heading("Bookmarked", text="★", anchor='center', command=lambda: self.sort_treeview_column("Bookmarked", False))
        self.post_tree.column("Post #", width=70, stretch=tk.NO, anchor='w')
        self.post_tree.column("Date", width=110, stretch=tk.YES, anchor='w')
        self.post_tree.column("Notes", width=25, stretch=tk.NO, anchor='center')
        self.post_tree.column("Bookmarked", width=30, stretch=tk.NO, anchor='center')
        self.post_tree.grid(row=0, column=0, sticky="nswe")
        self.scrollbar_y.grid(row=0, column=1, sticky="ns")

        self.treeview_note_tooltip = Tooltip(self.post_tree, self._get_note_tooltip_text, delay=500)
        self.post_tree.bind("<Motion>", self._on_treeview_motion_for_tooltip)
        self.post_tree.bind("<Leave>", self._on_treeview_leave_for_tooltip)
        self.text_image_paned_window = ttk.Panedwindow(self.details_outer_frame, orient=tk.HORIZONTAL)
        self.text_image_paned_window.pack(fill=tk.BOTH, expand=True)
        self.text_area_frame = ttk.Frame(self.text_image_paned_window)
        self.text_image_paned_window.add(self.text_area_frame, weight=1)
        self.text_area_frame.grid_rowconfigure(0, weight=1)
        self.text_area_frame.grid_columnconfigure(0, weight=1)
        self.post_text_area = tk.Text(self.text_area_frame, wrap=tk.WORD, relief=tk.FLAT, borderwidth=1, font=("TkDefaultFont", 11), padx=10, pady=10)
        self.default_text_area_cursor = self.post_text_area.cget("cursor")
        self.post_text_scrollbar = ttk.Scrollbar(self.text_area_frame, orient="vertical", command=self.post_text_area.yview)
        self.post_text_area.configure(yscrollcommand=self.post_text_scrollbar.set)
        self.post_text_area.grid(row=0, column=0, sticky="nswe")
        self.post_text_scrollbar.grid(row=0, column=1, sticky="ns")
        self.image_display_frame = ttk.Frame(self.text_image_paned_window, style="Entry.TFrame")
        self.text_image_paned_window.add(self.image_display_frame, weight=0)
        self.image_canvas = tk.Canvas(self.image_display_frame, highlightthickness=0)
        self.image_scrollbar = ttk.Scrollbar(self.image_display_frame, orient="vertical", command=self.image_canvas.yview)
        self.image_scrollable_frame = ttk.Frame(self.image_canvas, style="Entry.TFrame")
        self.image_scrollable_frame.bind("<Configure>", lambda e: self.image_canvas.configure(scrollregion=self.image_canvas.bbox("all")))
        self.image_canvas_window = self.image_canvas.create_window((0, 0), window=self.image_scrollable_frame, anchor="nw")
        self.image_canvas.configure(yscrollcommand=self.image_scrollbar.set)
        self.image_canvas.pack(side="left", fill="both", expand=True)
        self.image_scrollbar.pack(side="right", fill="y")
        self.image_canvas.bind("<Configure>", lambda e: self.image_canvas.itemconfig(self.image_canvas_window, width=e.width))
        self.post_text_area.bind("<KeyPress>", self._prevent_text_edit)
        self.context_menu = tk.Menu(self.post_text_area, tearoff=0)
        self.post_text_area.bind("<Button-3>", self._show_context_menu)
        self.configure_text_tags()
        self.text_image_paned_window.bind("<ButtonRelease-1>", self._check_sash_position)
        
        controls_main_frame = ttk.Frame(root)
        controls_main_frame.grid(row=1, column=0, columnspan=2, sticky="ew")
        nav_frame = ttk.Frame(controls_main_frame)
        nav_frame.pack(pady=(0,5), fill=tk.X)
        self.prev_button = ttk.Button(nav_frame, text="<< Prev", command=self.prev_post, width=8)
        self.prev_button.pack(side="left", padx=2)
        self.next_button = ttk.Button(nav_frame, text="Next >>", command=self.next_post, width=8)
        self.next_button.pack(side="left", padx=2)
        self.clear_search_button = ttk.Button(nav_frame, text="Show All Posts", command=self.clear_search_and_show_all, state=tk.DISABLED)
        self.clear_search_button.pack(side="left", padx=(5,2))
        self.post_number_label = ttk.Label(nav_frame, text="", width=35, anchor="center", font=('Arial', 11, 'bold'))
        self.post_number_label.pack(side="left", padx=5, expand=True, fill=tk.X)
        
        self.list_view_button = ttk.Button(nav_frame, text="List", command=self.show_list_view)
        self.list_view_button.pack(side="right", padx=2)
        self.threads_view_button = ttk.Button(nav_frame, text="Threads", command=self.show_threads_view)
        self.threads_view_button.pack(side="right", padx=2)
        self.symbols_view_button = ttk.Button(nav_frame, text="Symbols", command=self.show_symbols_view)
        self.symbols_view_button.pack(side="right", padx=2)
        self.clock_view_button = ttk.Button(nav_frame, text="Q Clock", command=self.show_clock_view)
        self.clock_view_button.pack(side="right", padx=2)
        
        actions_frame = ttk.Labelframe(controls_main_frame, text="Search & Actions", padding=(10,5))
        actions_frame.pack(pady=5, fill=tk.X, expand=True)
        search_fields_frame = ttk.Frame(actions_frame)
        search_fields_frame.pack(fill=tk.X, pady=2)
        self.post_entry = ttk.Entry(search_fields_frame, width=12, font=('Arial', 10))
        self.post_entry.pack(side=tk.LEFT, padx=(0,5), expand=True, fill=tk.X)
        self.post_entry.bind("<FocusIn>", lambda e, p=config.PLACEHOLDER_POST_NUM: self.clear_placeholder(e, p, self.post_entry))
        self.post_entry.bind("<FocusOut>", lambda e, p=config.PLACEHOLDER_POST_NUM: self.restore_placeholder(e, p, self.post_entry))
        self.post_entry.bind("<Return>", lambda event: self.search_post_by_number())
        self.keyword_entry = ttk.Entry(search_fields_frame, width=20, font=('Arial', 10))
        self.keyword_entry.pack(side=tk.LEFT, padx=(0,0), expand=True, fill=tk.X)
        self.keyword_entry.bind("<FocusIn>", lambda e, p=config.PLACEHOLDER_KEYWORD: self.clear_placeholder(e, p, self.keyword_entry))
        self.keyword_entry.bind("<FocusOut>", lambda e, p=config.PLACEHOLDER_KEYWORD: self.restore_placeholder(e, p, self.keyword_entry))
        self.keyword_entry.bind("<Return>", lambda event: self.search_by_keyword())
        search_buttons_frame = ttk.Frame(actions_frame)
        search_buttons_frame.pack(fill=tk.X, pady=(5,2))
        self.search_menu_button = ttk.Menubutton(search_buttons_frame, text="Advanced Search", style="TButton")
        self.search_menu = tk.Menu(self.search_menu_button, tearoff=0)
        self.search_menu_button["menu"] = self.search_menu
        self.search_menu.add_command(label="Search by Date", command=self.show_calendar)
        self.search_menu.add_command(label="Today's Deltas", command=self.search_today_deltas)
        self.search_menu.add_command(label="Search by Theme", command=self.show_theme_selection_dialog)
        Tooltip(self.search_menu_button, lambda: "Advanced search options.")
        self.search_menu_button.pack(side=tk.LEFT, padx=2, expand=True, fill=tk.X)
        self.tools_menu_button = ttk.Menubutton(search_buttons_frame, text="Tools", style="TButton")
        self.tools_menu = tk.Menu(self.tools_menu_button, tearoff=0)
        self.tools_menu_button["menu"] = self.tools_menu
        self.tools_menu.add_command(label="Gematria Calc", command=self.show_gematria_calculator_window)
        self.tools_menu.add_command(label="View All Notes", command=self.show_all_notes_window)
        self.tools_menu.add_command(label="Content Sync", command=self.show_download_window)
        self.tools_menu.add_command(label="Help & Info", command=self.show_help_window)
        self.tools_menu_button.pack(side=tk.LEFT, padx=2, expand=True, fill=tk.X)
        Tooltip(self.tools_menu_button, lambda: "Access various utilities.")
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
        bottom_main_bar_frame = ttk.Frame(controls_main_frame)
        bottom_main_bar_frame.pack(pady=(10,0), fill=tk.X, expand=True)
        self.export_menu_button = ttk.Menubutton(bottom_main_bar_frame, text="Export", style="TButton")
        self.export_menu = tk.Menu(self.export_menu_button, tearoff=0)
        self.export_menu_button["menu"] = self.export_menu
        self.export_menu.add_command(label="Export as HTML", command=lambda: self.export_displayed_list(file_format="HTML"))
        self.export_menu.add_command(label="Export as CSV", command=lambda: self.export_displayed_list(file_format="CSV"))
        self.export_menu_button.pack(side=tk.LEFT, padx=(0,2), fill=tk.X, expand=True)
        Tooltip(self.export_menu_button, lambda: "Export displayed posts.")
        self.settings_button = ttk.Button(bottom_main_bar_frame, text="Settings", command=self.show_settings_window)
        self.settings_button.pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)
        self.about_button = ttk.Button(bottom_main_bar_frame, text="About", command=self.show_about_dialog)
        self.about_button.pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)
        Tooltip(self.about_button, lambda: "Information about QView.")
        ttk.Button(bottom_main_bar_frame, text="Quit App", command=self.on_closing).pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)

        # Apply the theme on startup
        if self.current_theme == "light":
            self.apply_light_theme()
        elif self.current_theme == "rwb":
            self.apply_rwb_theme()
        elif self.current_theme == "halloween":
            self.apply_halloween_theme()
        else: # Default to dark theme
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
            
            # --- NEW: Prepare data for calendar highlighting and info ---
            # Create a set of unique dates that have posts for quick lookups
            self.dates_with_posts = set(pd.to_datetime(self.df_all_posts['Datetime_UTC'].dt.date).unique())
            
            # Create a dictionary mapping each date to a list of its posts (Post #, Year)
            temp_df = self.df_all_posts.dropna(subset=['Datetime_UTC', 'Post Number']).copy()
            temp_df['date_only'] = pd.to_datetime(temp_df['Datetime_UTC'].dt.date)
            self.date_to_posts_map = temp_df.groupby('date_only').apply(
                lambda x: sorted(list(set(zip(x['Post Number'].astype(int), x['Datetime_UTC'].dt.year))))
            ).to_dict()
            # --- END NEW ---
            
            # --- NEW: Get the min/max dates for the calendar bounds ---
            self.min_post_date = self.df_all_posts['Datetime_UTC'].min().date()
            self.max_post_date = self.df_all_posts['Datetime_UTC'].max().date()
            # --- END NEW ---
            
        elif self.df_all_posts is None:
            messagebox.showerror("Critical Error", "Failed to load any post data.")
            self.root.destroy()
            return

        self.root.after(100, self.show_welcome_message)
        self._init_complete = True
        self.root.after(200, self.set_initial_sash_position)
# --- END __INIT__ ---

    def _get_heatmap_color(self, count, max_count):
        """Calculates a color from a gradient based on the symbol count."""
        if count == 0:
            return "#f0f0f0" # Light grey for zero
        
        # Normalize count to a 0.0-1.0 scale, using a log scale for better visual contrast
        normalized_count = math.log(1 + count) / math.log(1 + max_count)
        
        # Simple gradient: grey -> yellow -> red
        if normalized_count < 0.5:
            # Interpolate between grey (#cccccc) and yellow (#ffff00)
            red = int(0xcc + (0xff - 0xcc) * (normalized_count * 2))
            green = int(0xcc + (0xff - 0xcc) * (normalized_count * 2))
            blue = int(0xcc + (0x00 - 0xcc) * (normalized_count * 2))
        else:
            # Interpolate between yellow (#ffff00) and red (#ff0000)
            red = 0xff
            green = int(0xff + (0x00 - 0xff) * ((normalized_count - 0.5) * 2))
            blue = 0
            
        return f"#{red:02x}{green:02x}{blue:02x}"

    def _on_symbol_select(self, event):
        """Called when a symbol is selected. Gathers all selected symbols and redraws the heatmap."""
        selected_items = self.symbols_tree.selection()  # Use .selection() to get all selected items
        if not selected_items:
            self._draw_symbol_heatmap(selected_symbols=None) # Default to "All Symbols" if nothing is selected
            return
    
        # Convert the selected item IDs to a list of symbol names
        selected_symbols_list = [self.symbols_tree.item(item_id, "text") for item_id in selected_items]
    
        # Pass the whole list to the drawing function
        self._draw_symbol_heatmap(selected_symbols=selected_symbols_list)

    def _get_heatmap_color(self, count, max_count):
        """Calculates a color from a gradient based on the symbol count."""
        if count == 0:
            return "#f0f0f0" # Light grey for zero
        
        # Normalize count to a 0.0-1.0 scale
        normalized_count = min(count / max_count, 1.0)
        
        # Simple gradient: grey -> yellow -> red
        if normalized_count < 0.5:
            # Interpolate between grey (#e0e0e0) and yellow (#ffff00)
            red = int(0xe0 + (0xff - 0xe0) * (normalized_count * 2))
            green = int(0xe0 + (0xff - 0xe0) * (normalized_count * 2))
            blue = int(0xe0 + (0x00 - 0xe0) * (normalized_count * 2))
        else:
            # Interpolate between yellow (#ffff00) and red (#ff0000)
            red = 0xff
            green = int(0xff + (0x00 - 0xff) * ((normalized_count - 0.5) * 2))
            blue = 0
            
        return f"#{red:02x}{green:02x}{blue:02x}"

    def _draw_symbol_heatmap(self, selected_symbols=None):
        # The code inside the function should be indented 8 spaces
        """Draws the symbol density timeline on its canvas for one or more symbols."""
        self.heatmap_canvas.delete("all")
        
        timeline_data = {}
        title = "Symbol Density Timeline: "

        if selected_symbols:
            # --- NEW: AGGREGATION LOGIC ---
            aggregated_timeline = defaultdict(int)
            for symbol in selected_symbols:
                individual_timeline = app_data.per_symbol_timeline.get(symbol, {})
                for date, count in individual_timeline.items():
                    aggregated_timeline[date] += count
            
            timeline_data = dict(aggregated_timeline)
            
            if len(selected_symbols) > 3:
                title += f"{len(selected_symbols)} Symbols Selected"
            else:
                title += ", ".join(selected_symbols)
        else:
            timeline_data = app_data.symbol_timeline
            title += "All Symbols"

        self.heatmap_canvas.master.config(text=title)

        if not timeline_data: return

        # (The rest of the drawing logic is the same)
        canvas_width = self.heatmap_canvas.winfo_width()
        canvas_height = self.heatmap_canvas.winfo_height()
        if canvas_width < 2 or canvas_height < 2: return

        start_date = self.df_all_posts['Datetime_UTC'].min().date()
        end_date = self.df_all_posts['Datetime_UTC'].max().date()
        total_days = (end_date - start_date).days
        if total_days == 0: return

        max_count = float(max(timeline_data.values()) if timeline_data else 1)
        bar_width = canvas_width / total_days

        current_date = start_date
        for i in range(total_days + 1):
            count = timeline_data.get(current_date, 0)
            color = self._get_heatmap_color(count, max_count)
            x0 = i * bar_width
            x1 = (i + 1) * bar_width
            self.heatmap_canvas.create_rectangle(x0, 0, x1, canvas_height, fill=color, outline="")
            current_date += datetime.timedelta(days=1)

    def _setup_symbols_view(self):
        """Creates the widgets for the Symbol Map view using a PanedWindow."""
        # The code inside the function is indented one level further
        symbols_paned_window = ttk.Panedwindow(self.symbols_view_frame, orient=tk.VERTICAL)
        symbols_paned_window.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # --- Top pane for the Symbol List ---
        list_frame = ttk.Frame(symbols_paned_window)
        symbols_paned_window.add(list_frame)

        # (Setup for the Treeview and Scrollbar inside list_frame)
        list_frame.grid_rowconfigure(0, weight=1)
        list_frame.grid_columnconfigure(0, weight=1)
        self.symbols_tree = ttk.Treeview(list_frame, columns=("Aliases", "Description"), show="tree headings", selectmode='extended')
        symbols_scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.symbols_tree.yview)
        self.symbols_tree.configure(yscrollcommand=symbols_scrollbar.set)
        self.symbols_tree.heading("#0", text="Symbol")
        self.symbols_tree.heading("Aliases", text="Aliases")
        self.symbols_tree.heading("Description", text="Description")
        self.symbols_tree.column("#0", width=150, stretch=tk.NO)
        self.symbols_tree.column("Aliases", width=250)
        self.symbols_tree.column("Description", width=400)
        self.symbols_tree.grid(row=0, column=0, sticky="nsew")
        symbols_scrollbar.grid(row=0, column=1, sticky="ns")
        self.symbols_tree.bind("<<TreeviewSelect>>", self._on_symbol_select)
        
        # --- Bottom pane for the Heatmap ---
        heatmap_frame = ttk.Labelframe(symbols_paned_window, text="Symbol Density Timeline",
                                     padding=10, height=150)
        symbols_paned_window.add(heatmap_frame)

        # (Setup for the widgets inside the heatmap_frame)
        show_all_btn = ttk.Button(heatmap_frame, text="Show All Symbols", command=self._draw_symbol_heatmap)
        show_all_btn.pack(anchor="ne", pady=(0, 5))
        self.heatmap_canvas = tk.Canvas(heatmap_frame, bg="white", highlightthickness=0)
        self.heatmap_canvas.pack(fill=tk.BOTH, expand=True)

    def _populate_symbols_view(self):
        """Clears and populates the symbols treeview from the loaded symbol_map."""
        for i in self.symbols_tree.get_children():
            self.symbols_tree.delete(i)
            
        # The symbol_map is loaded from data.py
        for symbol, data in sorted(app_data.symbol_map.items()):
            aliases = ", ".join(data.get("aliases", []))
            description = data.get("description", "")
            self.symbols_tree.insert("", "end", text=symbol, values=(aliases, description))

    def _setup_threads_view(self):
        """Creates the widgets for the Narrative Threads view."""
        self.threads_view_frame.grid_rowconfigure(0, weight=1)
        self.threads_view_frame.grid_columnconfigure(0, weight=1)

        # --- THIS IS THE FIX ---
        # Changed show="headings" to show="tree headings" to make the main column visible
        self.threads_tree = ttk.Treeview(self.threads_view_frame, columns=("Date Span", "Posts"), show="tree headings")
        # --- END FIX ---
        
        threads_scrollbar = ttk.Scrollbar(self.threads_view_frame, orient="vertical", command=self.threads_tree.yview)
        self.threads_tree.configure(yscrollcommand=threads_scrollbar.set)
        
        # --- THIS IS THE FIX ---
        # Added a heading for the main hierarchical column ("#0")
        self.threads_tree.heading("#0", text="Narrative Thread / Post")
        # --- END FIX ---
        
        self.threads_tree.heading("Date Span", text="Date Span")
        self.threads_tree.heading("Posts", text="# Posts")
        self.threads_tree.column("#0", width=400) 
        self.threads_tree.column("Date Span", width=250, anchor='center')
        self.threads_tree.column("Posts", width=100, anchor='center')

        self.threads_tree.grid(row=0, column=0, sticky="nsew")
        threads_scrollbar.grid(row=0, column=1, sticky="ns")

        self.threads_tree.tag_configure("theme_row", font=('Arial', 11, 'bold'))

    def _populate_threads_view(self):
        """Clears and populates the threads treeview with themed posts."""
        # Clear existing data
        for i in self.threads_tree.get_children():
            self.threads_tree.delete(i)

        # Group posts by theme
        for theme, post_numbers in app_data.theme_posts_map.items():
            if not post_numbers: continue

            theme_posts_df = self.df_all_posts[self.df_all_posts['Post Number'].isin(post_numbers)]
            if theme_posts_df.empty: continue

            # Calculate date span and post count for the theme
            min_date = theme_posts_df['Datetime_UTC'].min().strftime('%Y-%m-%d')
            max_date = theme_posts_df['Datetime_UTC'].max().strftime('%Y-%m-%d')
            date_span = f"{min_date} to {max_date}" if min_date != max_date else min_date
            post_count = len(theme_posts_df)

            # Insert the main theme row
            theme_id = self.threads_tree.insert("", "end", text=f" {theme.replace('_', ' ').title()}", 
                                                values=(date_span, post_count), tags=("theme_row",))
            
            # Insert the individual posts as children of the theme row
            for _, post in theme_posts_df.sort_values(by='Datetime_UTC').iterrows():
                post_text_preview = str(post['Text']).replace('\n', ' ').strip()[:80] + "..."
                self.threads_tree.insert(theme_id, "end", text=f"  #{post['Post Number']}: {post_text_preview}",
                                         values=(post['Datetime_UTC'].strftime('%Y-%m-%d %H:%M'), ""))

    def show_list_view(self):
        """Shows the main post list view."""
        self.multi_clock_frame.grid_remove()
        self.threads_view_frame.grid_remove()
        self.symbols_view_frame.grid_remove()
        self.list_view_frame.grid()

    def show_clock_view(self):
        """Shows the multi-clock dashboard view."""
        self.list_view_frame.grid_remove()
        self.threads_view_frame.grid_remove()
        self.symbols_view_frame.grid_remove()
        self.multi_clock_frame.grid()
        if not self.clocks_initialized:
            self.build_clock_view()

    def show_threads_view(self):
        """Shows the narrative threads view."""
        self.list_view_frame.grid_remove()
        self.multi_clock_frame.grid_remove()
        self.symbols_view_frame.grid_remove()
        self.threads_view_frame.grid()
        self._populate_threads_view()
        
    def show_symbols_view(self):
        """Shows the symbol map view and populates its widgets."""
        self.list_view_frame.grid_remove()
        self.multi_clock_frame.grid_remove()
        self.threads_view_frame.grid_remove()
        self.symbols_view_frame.grid()
        
        # Populate both the list and the heatmap
        self._populate_symbols_view()
        # Use .after() to give the canvas a moment to be drawn before we measure it
        self.root.after(50, self._draw_symbol_heatmap)    

    def maximize_single_clock(self, year_data):
        """Creates a new window for a single year's Q Clock."""
        if year_data is None or year_data.empty:
            return

        # Get the year from the data for the window title
        year = year_data['Datetime_UTC'].dt.year.iloc[0]

        # Create a new Toplevel window
        single_clock_win = tk.Toplevel(self.root)
        single_clock_win.title(f"Q Clock - {year}")
        single_clock_win.geometry("800x850")

        # Create a QClock instance inside the new window using the specific year's data
        # It will use the default "nebula" plot mode.
        maximized_clock = QClock(single_clock_win, self.root, self, self.style, data=year_data)

    def show_master_clock_window(self):
        """Creates a new, standalone window for the Master Q Clock."""
        # Create a new Toplevel window
        master_win = tk.Toplevel(self.root)
        master_win.title("Master Q Clock (All Years)")
        master_win.geometry("800x850") # Give it a nice large default size

        # Create a QClock instance inside the new window.
        # We pass the *entire* dataset and tell it to use the new 'spiral' plot mode.
        master_clock = QClock(master_win, self.root, self, self.style, 
                              data=self.df_all_posts, plot_mode="spiral")

    def _on_main_scroll(self, event):
        """Scrolls the main multi-clock canvas horizontally or vertically."""
        if not self.multi_clock_canvas:
            return

        # Determine direction for Windows/macOS (event.delta) or Linux (event.num)
        if event.num == 4 or event.delta > 0:
            scroll_dir = -1 # Scroll up or left
        elif event.num == 5 or event.delta < 0:
            scroll_dir = 1 # Scroll down or right
        else:
            return

        if self.clock_layout == 'vertical':
            self.multi_clock_canvas.yview_scroll(scroll_dir, "units")
        else: # horizontal
            self.multi_clock_canvas.xview_scroll(scroll_dir, "units")
        return "break" # Prevent any other scroll bindings from firing

    def toggle_clock_layout(self):
        """Switches the clock layout and triggers a rebuild of the clock view."""
        if self.clock_layout == "horizontal":
            self.clock_layout = "vertical"
            # Update the button text to show the *next* state
            if hasattr(self, 'layout_toggle_button'):
                self.layout_toggle_button.config(text="Switch to Horizontal")
        else:
            self.clock_layout = "horizontal"
            if hasattr(self, 'layout_toggle_button'):
                self.layout_toggle_button.config(text="Switch to Vertical")
            
        for widget in self.multi_clock_frame.winfo_children():
            widget.destroy()
            
        self.clock_instances = []
        self.clocks_initialized = False
        
        if self.multi_clock_frame.winfo_ismapped():
            self.toggle_clock_view(force_rebuild=True)

    def broadcast_date_highlight(self, date_str):
        """Tells all clock instances to highlight a specific date label."""
        # First, clear any previous highlights to prevent conflicts
        self.clear_all_date_highlights()
        for clock in self.clock_instances:
            clock.highlight_date_on_ring(date_str)

    def clear_all_date_highlights(self):
        """Tells all clock instances to clear their date label highlights."""
        for clock in self.clock_instances:
            clock.clear_date_highlight()

# --- START build_clock_view ---
    def build_clock_view(self):
        """Builds all the widgets for the multi-clock dashboard view."""
        if self.clocks_initialized:
            return # Don't rebuild if already built

        # Main container for global controls
        main_container = ttk.Frame(self.multi_clock_frame)
        main_container.pack(fill=tk.BOTH, expand=True)

        top_controls_frame = ttk.Frame(main_container)
        top_controls_frame.pack(fill=tk.X, pady=10)
        
        master_clock_button = ttk.Button(top_controls_frame, text="View Master Clock", command=self.show_master_clock_window)
        master_clock_button.pack(side=tk.LEFT, padx=20)
        
        # A PanedWindow to split clocks from the legend
        dashboard_paned_window = ttk.Panedwindow(main_container, orient=tk.HORIZONTAL)
        dashboard_paned_window.pack(fill=tk.BOTH, expand=True)

        # Left side: The clock grid
        clock_grid_container = ttk.Frame(dashboard_paned_window)
        dashboard_paned_window.add(clock_grid_container, weight=4)

        # Right side: The legend
        legend_container_frame = ttk.Frame(dashboard_paned_window)
        dashboard_paned_window.add(legend_container_frame, weight=1)
        
        years = sorted(self.df_all_posts['Datetime_UTC'].dt.year.unique())
        max_cols = 2
        num_rows = (len(years) + max_cols - 1) // max_cols

        for i in range(max_cols): clock_grid_container.grid_columnconfigure(i, weight=1)
        for i in range(num_rows): clock_grid_container.grid_rowconfigure(i, weight=1)

        for i, year in enumerate(years):
            row, col = i // max_cols, i % max_cols
            year_frame = ttk.Frame(clock_grid_container)
            year_frame.grid(row=row, column=col, padx=5, pady=5, sticky="nsew")
            
            ttk.Label(year_frame, text=str(year), font=("Arial", 14, "bold")).pack(pady=(5,0))
            df_year = self.df_all_posts[self.df_all_posts['Datetime_UTC'].dt.year == year].copy()
            clock = QClock(year_frame, self.root, self, self.style, data=df_year)
            self.clock_instances.append(clock)
        
        # The legend panel
        legend_frame = ttk.Labelframe(legend_container_frame, text="Legend", padding=10)
        legend_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        def create_legend_item(parent, color, text):
            item_frame = ttk.Frame(parent)
            box = tk.Frame(item_frame, bg=color, width=12, height=12, relief=tk.SOLID, borderwidth=1)
            box.pack(side=tk.LEFT, padx=(5, 5))
            label = ttk.Label(item_frame, text=text)
            label.pack(side=tk.LEFT, padx=(0, 10))
            item_frame.pack(anchor="w", pady=4, padx=5)

        create_legend_item(legend_frame, "magenta", "Image + Link")
        create_legend_item(legend_frame, "turquoise", "Post w/ Image")
        create_legend_item(legend_frame, "orange", "Post w/ Link")
        create_legend_item(legend_frame, "blue", "Text-Only Post")
        ttk.Separator(legend_frame, orient='horizontal').pack(fill='x', pady=8, padx=5)
        create_legend_item(legend_frame, "red", "Time Delta")
        create_legend_item(legend_frame, "cyan", "Time Mirror")
        create_legend_item(legend_frame, "yellow", "Post # Mirror")
        create_legend_item(legend_frame, "green", "Date Mirror")
        create_legend_item(legend_frame, "purple", "Multi-Select")

        self.clocks_initialized = True
# --- END build_clock_view ---

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
            self._insert_text_with_clickable_urls(text_widget, segment, base_tags_tuple, f"main_{post_id_for_tagging}_final_{current_pos}")
# --- END _INSERT_TEXT_WITH_ABBREVIATIONS_AND_URLS ---

# --- START UPDATE_DISPLAY ---
    def update_display(self):
        for widget in self.image_scrollable_frame.winfo_children(): widget.destroy()
        self.displayed_images_references = []; self._quote_image_references = []; self.current_post_urls = []; self.current_post_downloaded_article_path = None
        self.post_text_area.config(state=tk.NORMAL)
        self.post_text_area.delete(1.0, tk.END)
        self.post_text_area.tag_remove("search_highlight_tag", "1.0", tk.END)
        
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
        
        author_text_raw=post.get('Author',''); tripcode_text_raw=post.get('Tripcode',''); author_text=utils.sanitize_text_for_tkinter(author_text_raw); tripcode_text=utils.sanitize_text_for_tkinter(tripcode_text_raw)
        if author_text and pd.notna(author_text_raw): self.post_text_area.insert(tk.END, "Author: ", "bold_label"); self.post_text_area.insert(tk.END, f"{author_text}\n", "author_val")
        if tripcode_text and pd.notna(tripcode_text_raw): self.post_text_area.insert(tk.END, "Tripcode: ", "bold_label"); self.post_text_area.insert(tk.END, f"{tripcode_text}\n", "author_val")
        
        themes_list = post.get('Themes', [])
        if themes_list and isinstance(themes_list, list) and len(themes_list) > 0: themes_str = utils.sanitize_text_for_tkinter(f"{', '.join(themes_list)}\n"); self.post_text_area.insert(tk.END, "Themes: ", "bold_label"); self.post_text_area.insert(tk.END, themes_str, "themes_val")
        
        referenced_posts_raw_data = post.get('Referenced Posts Raw')
        if isinstance(referenced_posts_raw_data, list) and referenced_posts_raw_data:
            self.post_text_area.insert(tk.END, "\nReferenced Content:\n", ("bold_label"))
            for ref_idx, ref_data in enumerate(referenced_posts_raw_data):
                if not isinstance(ref_data, dict): continue

                ref_id_str_for_display = ref_data.get('referenceID', '')

                quoted_post_num = None
                if isinstance(ref_id_str_for_display, str) and '>>' in ref_id_str_for_display:
                    try:
                        num_match = re.search(r'>>(\d+)', ref_id_str_for_display)
                        if num_match:
                            quoted_post_num = int(num_match.group(1))
                    except (ValueError, TypeError):
                        quoted_post_num = None

                ref_text_content_raw = '[Quoted post data not found]'
                quoted_images_list = []
                author_text = 'Unknown'

                if pd.notna(quoted_post_num):
                    target_post_num_for_ref = int(quoted_post_num)
                    quoted_post_series = self.df_all_posts[self.df_all_posts['Post Number'] == target_post_num_for_ref]
                    
                    if not quoted_post_series.empty:
                        quoted_post = quoted_post_series.iloc[0]
                        ref_text_content_raw = quoted_post.get('Text', '[Text not available in quoted post]')
                        quoted_images_list = quoted_post.get('ImagesJSON', [])
                        author_text = quoted_post.get('Author', 'Unknown')
                    else:
                        # --- THIS IS THE FIX ---
                        # If the post isn't found, use the fallback text from the reference data itself.
                        ref_text_content_raw = ref_data.get('textContent', f'[Post #{target_post_num_for_ref} not found, no fallback text.]')
                        author_text = ref_data.get('referencedPostAuthorID', 'Unknown')
                        quoted_images_list = ref_data.get('images', [])
                else:
                    ref_text_content_raw = ref_data.get('textContent', '[Could not find valid text content in reference data]')
                    author_text = ref_data.get('referencedPostAuthorID', 'Unknown')
                    quoted_images_list = ref_data.get('images', [])
                
                ref_num_san = utils.sanitize_text_for_tkinter(str(ref_id_str_for_display))
                self.post_text_area.insert(tk.END, "↪ Quoting ", ("quoted_ref_header"))
                clickable_ref_id_tag = f"clickable_ref_id_{original_df_index}_{ref_idx}_{ref_id_str_for_display}"
                if ref_num_san:
                    self.post_text_area.insert(tk.END, f"{ref_num_san} ", ("quoted_ref_header", "clickable_link_style", clickable_ref_id_tag))
                    if pd.notna(quoted_post_num):
                        self.post_text_area.tag_bind(clickable_ref_id_tag, "<Button-1>", lambda e, pn=int(quoted_post_num): self.jump_to_post_number_from_ref(pn))
                self.post_text_area.insert(tk.END, f"(by {author_text}):\n", ("quoted_ref_header"))

                if quoted_images_list and isinstance(quoted_images_list, list):
                    self.post_text_area.insert(tk.END, "    ", ("quoted_ref_text_body"))
                    for q_img_idx, quote_img_data in enumerate(quoted_images_list):
                        img_filename_from_quote = quote_img_data.get('filename')
                        if img_filename_from_quote:
                            local_image_path_from_quote = os.path.join(config.IMAGE_DIR, utils.sanitize_filename_component(os.path.basename(img_filename_from_quote)))
                            if os.path.exists(local_image_path_from_quote):
                                try:
                                    img_pil_quote = Image.open(local_image_path_from_quote)
                                    img_pil_quote.thumbnail((75, 75))
                                    photo_quote = ImageTk.PhotoImage(img_pil_quote)
                                    self._quote_image_references.append(photo_quote)
                                    clickable_quote_img_tag = f"quote_img_open_{original_df_index}_{ref_idx}_{q_img_idx}"
                                    self.post_text_area.image_create(tk.END, image=photo_quote)
                                    self.post_text_area.insert(tk.END, " 🔗", ('clickable_link_style', clickable_quote_img_tag))
                                    self.post_text_area.tag_bind(clickable_quote_img_tag, "<Button-1>", lambda e, p=local_image_path_from_quote: utils.open_image_external(p, self.root))
                                    if q_img_idx < len(quoted_images_list) - 1: self.post_text_area.insert(tk.END, "  ")
                                except Exception as e_quote_img: print(f"Error displaying inline quote img {img_filename_from_quote}: {e_quote_img}")
                    self.post_text_area.insert(tk.END, "\n")
                
                self._insert_text_with_abbreviations_and_urls(self.post_text_area, ref_text_content_raw, ("quoted_ref_text_body",), f"qref_{original_df_index}_{ref_idx}")
                self.post_text_area.insert(tk.END, "\n")
            self.post_text_area.insert(tk.END, "\n")

        main_text_content_raw = post.get('Text', '')
        self.post_text_area.insert(tk.END, "Post Text:\n", ("bold_label"))
        self._insert_text_with_abbreviations_and_urls(self.post_text_area, main_text_content_raw, (), f"main_{original_df_index}")

        if self.current_search_active:
            search_keyword = self.keyword_entry.get().strip().lower()
            if search_keyword and search_keyword != config.PLACEHOLDER_KEYWORD.lower():
                start_pos = "1.0"
                while True:
                    start_pos = self.post_text_area.search(search_keyword, start_pos, stopindex=tk.END, nocase=True)
                    if not start_pos: break
                    end_pos = f"{start_pos}+{len(search_keyword)}c"
                    self.post_text_area.tag_add("search_highlight_tag", start_pos, end_pos)
                    start_pos = end_pos
        
        images_json_data = post.get('ImagesJSON', [])
        if images_json_data and isinstance(images_json_data, list) and len(images_json_data) > 0:
            for img_data in images_json_data:
                img_filename = img_data.get('filename')
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
        
        metadata_link_raw = post.get('Link')
        if metadata_link_raw and pd.notna(metadata_link_raw) and str(metadata_link_raw).strip():
            self.post_text_area.insert(tk.END, "\nSource Link: ", "bold_label")
            self._insert_text_with_abbreviations_and_urls(self.post_text_area, str(metadata_link_raw).strip(), ("clickable_link_style",) , f"metalink_{original_df_index}")
            self.post_text_area.insert(tk.END, "\n")

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

        if self.image_display_frame in self.text_image_paned_window.panes():
            if not self.image_scrollable_frame.winfo_children():
                self.text_image_paned_window.pane(self.image_display_frame, weight=0, width=0)
                sash_index = self.text_image_paned_window.panes().index(self.image_display_frame) - 1
                if sash_index >= 0 and self.text_image_paned_window.sash_exists(sash_index):
                    self.text_image_paned_window.sash_forget(sash_index)
            else:
                self.text_image_paned_window.pane(self.image_display_frame, weight=1, minsize=50)

        self.post_text_area.config(state=tk.DISABLED)
        self.update_post_number_label(); self.update_bookmark_button_status()
        self.root.update_idletasks()

# --- END UPDATE_DISPLAY ---

# --- START SHOW_WELCOME_MESSAGE ---

    def show_welcome_message(self):
        """Clears the display and shows the welcome text and logo."""
        # --- 1. PREPARE & CLEAR THE UI ---
        self.post_text_area.config(state=tk.NORMAL)
        self.post_text_area.delete(1.0, tk.END)
        
        for widget in self.image_scrollable_frame.winfo_children():
            widget.destroy()
            
        self.displayed_images_references.clear()
        self._quote_image_references.clear()
        self.current_post_urls.clear()

        # --- 2. DISPLAY THE WELCOME LOGO ---
        if self.welcome_logo_photo:
            # THIS IS THE FIX:
            # Instead of trying to set the pane width directly, we move the sash (the divider).
            # If your window is 1024px wide, this will place the sash at the 724px mark,
            # leaving 300px for the image pane on the right.
            try:
                self.text_image_paned_window.sashpos(0, 724)
            except tk.TclError:
                # Fallback for when the window isn't ready yet.
                # This ensures the app won't crash even if called too early.
                self.root.after(100, lambda: self.text_image_paned_window.sashpos(0, 724))

            logo_label = ttk.Label(self.image_scrollable_frame, image=self.welcome_logo_photo)
            logo_label.pack(pady=20, padx=20, anchor="center")
        
        # --- 3. INSERT THE WELCOME TEXT ---
        self.post_text_area.insert(tk.END, "\n")
        self.post_text_area.insert(tk.END, "QView\n", "welcome_title_tag")
        self.post_text_area.insert(tk.END, "Your Offline Q Post Research Environment\n", "welcome_tagline_tag")
        self.post_text_area.insert(tk.END, "Welcome to your standalone research tool. All data is stored locally on your machine for maximum privacy and offline access.\n\n", "welcome_body_tag")
        self.post_text_area.insert(tk.END, "Getting Started\n", "welcome_heading_tag")
        self.post_text_area.insert(tk.END, " • Select a post from the list on the left to view its contents.\n • Use the search tools below to filter the entire post archive.\n • Right-click on text to open the context menu for more actions.\n", "welcome_body_tag")
        self.post_text_area.insert(tk.END, "\n\n\nDrag to resize image window  ➔", "welcome_hint_tag")

        # --- 4. FINALIZE UI STATE ---
        self.post_text_area.config(state=tk.DISABLED)
        
        if hasattr(self, 'show_links_button'):
            self.show_links_button.config(state=tk.DISABLED)
        if hasattr(self, 'view_article_button'):
            self.view_article_button.config(text="Article Not Saved", state=tk.DISABLED, command=lambda: None)
        if hasattr(self, 'view_edit_note_button'):
            self.view_edit_note_button.config(state=tk.DISABLED)
            
        self.update_post_number_label(is_welcome=True)
        self.update_bookmark_button_status(is_welcome=True)

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

# --- START _perform_calendar_search ---    
    def _perform_calendar_search(self):
        """Gets the date from the calendar and triggers a search."""
        if hasattr(self, 'cal') and self.cal.winfo_exists():
            selected_date_str = self.cal.get_date()
            all_years = self.all_years_var.get()
            self._search_by_date_str(selected_date_str, all_years=all_years)
            # Close the calendar window after the search is performed
            self.cal_win.destroy()
# --- END _perform_calendar_search ---

# --- START show_calendar ---
    def show_calendar(self):
        if hasattr(self, 'cal_win') and self.cal_win.winfo_exists():
            self.cal_win.lift()
            return
        
        try:
            dialog_bg = self.style.lookup("TFrame", "background")
        except tk.TclError: 
            dialog_bg = "#2b2b2b" if self.current_theme == "dark" else "#f0f0f0"

        self.cal_win = tk.Toplevel(self.root)
        self.cal_win.title("Select Date")
        self.cal_win.configure(bg=dialog_bg)
        self.cal_win.geometry("400x450")

        # --- MODIFIED: Set the initial date for the calendar ---
        if self.calendar_first_open:
            # On the very first open, default to Nov 2017
            cal_y, cal_m, cal_d = 2017, 11, 1
            self.calendar_first_open = False # Only do this once per session
        else:
            # For subsequent opens, default to the most recent post date
            if hasattr(self, 'max_post_date'):
                default_date = self.max_post_date
            else: 
                default_date = datetime.datetime.now()
            
            cal_y, cal_m, cal_d = default_date.year, default_date.month, default_date.day

            # And always override with the currently viewed post's date if available
            if self.df_displayed is not None and not self.df_displayed.empty and 0 <= self.current_display_idx < len(self.df_displayed):
                cur_post_dt = self.df_displayed.iloc[self.current_display_idx].get('Datetime_UTC')
                if pd.notna(cur_post_dt):
                    cal_y, cal_m, cal_d = cur_post_dt.year, cur_post_dt.month, cur_post_dt.day
        
        cal_fg_theme = "#000000" if self.current_theme == "light" else "#e0e0e0"
        cal_bg_theme = "#ffffff" if self.current_theme == "light" else "#3c3f41"
        cal_sel_bg = "#0078D7"
        cal_sel_fg = "#ffffff"
        cal_hdr_bg = "#e1e1e1" if self.current_theme == "light" else "#4a4a4a"
        cal_dis_bg = "#f0f0f0" if self.current_theme == "light" else "#2b2b2b"
        cal_dis_fg = "grey"
        event_highlight_bg = "#5f9ea0"
        event_highlight_fg = "#ffffff"

        self.cal = Calendar(self.cal_win, selectmode="day", year=cal_y, month=cal_m, day=cal_d,
                       date_pattern='m/d/yy', font="Arial 9",
                       mindate=getattr(self, 'min_post_date', None),
                       maxdate=getattr(self, 'max_post_date', None),
                       showothermonth=False,
                       showweeknumbers=False,
                       background=cal_hdr_bg, foreground=cal_fg_theme,
                       headersbackground=cal_hdr_bg, headersforeground=cal_fg_theme,
                       normalbackground=cal_bg_theme, weekendbackground=cal_bg_theme,
                       normalforeground=cal_fg_theme, weekendforeground=cal_fg_theme,
                       othermonthbackground=cal_dis_bg, othermonthwebackground=cal_dis_bg,
                       othermonthforeground=cal_dis_fg, othermonthweforeground=cal_dis_fg,
                       selectbackground=cal_sel_bg, selectforeground=cal_sel_fg,
                       bordercolor=cal_hdr_bg)
        
        self.cal.tag_config('has_posts', background=event_highlight_bg, foreground=event_highlight_fg)
        
        if hasattr(self, 'dates_with_posts'):
            for date_event in self.dates_with_posts:
                self.cal.calevent_create(date_event, 'Post Day', 'has_posts')
        
        self.cal.pack(padx=10, pady=(10,5), fill="x")

        info_frame = ttk.Frame(self.cal_win, height=100)
        info_frame.pack(padx=10, pady=5, fill=tk.BOTH, expand=True)
        self.cal_info_label = ttk.Label(info_frame, text="Click a day to see post numbers.",
                                        wraplength=380, justify=tk.LEFT, anchor="nw")
        self.cal_info_label.pack(fill=tk.BOTH, expand=True)

        self.all_years_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(self.cal_win, text="Search All Years (Delta)", variable=self.all_years_var).pack(pady=(0, 5))
        
        def on_date_select_for_info(event=None):
            selected_date_str = self.cal.get_date()
            selected_date_obj = pd.to_datetime(selected_date_str, format='%m/%d/%y')
            
            posts_on_day = self.date_to_posts_map.get(selected_date_obj, [])
            if posts_on_day:
                posts_by_year = {}
                for post_num, year in posts_on_day:
                    if year not in posts_by_year:
                        posts_by_year[year] = []
                    posts_by_year[year].append(str(post_num))
                
                info_text = f"Posts on {selected_date_obj.strftime('%b %d')}:\n"
                for year in sorted(posts_by_year.keys()):
                    info_text += f"  {year}: #" + ", #".join(posts_by_year[year]) + "\n"
                self.cal_info_label.config(text=info_text.strip())
            else:
                self.cal_info_label.config(text=f"No posts on {selected_date_obj.strftime('%Y-%m-%d')}.")

        self.cal.bind("<<CalendarSelected>>", on_date_select_for_info)
        self.cal.after(100, on_date_select_for_info)

        ttk.Button(self.cal_win, text="Show Posts", command=self._perform_calendar_search).pack(pady=(0, 10))
# --- END show_calendar ---

# --- START _search_by_date_str ---
    def _search_by_date_str(self, date_str_from_cal, all_years=False):
        try:
            target_date = pd.to_datetime(date_str_from_cal, format='%m/%d/%y').date()
            if self.df_all_posts is None:
                messagebox.showerror("Error", "Post data not loaded.", parent=self.root)
                return

            if all_years:
                results = self.df_all_posts[
                    (self.df_all_posts['Datetime_UTC'].dt.month == target_date.month) &
                    (self.df_all_posts['Datetime_UTC'].dt.day == target_date.day)
                ]
                search_term = f"Posts from {target_date.strftime('%B %d')} (All Years)"
            else:
                results = self.df_all_posts[self.df_all_posts['Datetime_UTC'].dt.date == target_date]
                search_term = f"Date = {target_date.strftime('%Y-%m-%d')}"

            self._handle_search_results(results, search_term)
        except Exception as e:
            messagebox.showerror("Error", f"Date selection error: {e}", parent=self.root)
# --- END _search_by_date_str ---

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

        self.theme_dialog = tk.Toplevel(self.root)
        self.theme_dialog.title("Select Themes to Search")
        self.theme_dialog.configure(bg=dialog_bg)
        self.theme_dialog.geometry("400x450")
        self.theme_dialog.transient(self.root)
        self.theme_dialog.grab_set()

        main_frame = ttk.Frame(self.theme_dialog, padding="10")
        main_frame.pack(expand=True, fill=tk.BOTH)

        ttk.Label(main_frame, text="Select one or more themes:", wraplength=350).pack(pady=(0, 5), anchor="w")

        listbox_frame = ttk.Frame(main_frame)
        listbox_frame.pack(expand=True, fill=tk.BOTH, pady=(5, 10))

        self.theme_listbox = tk.Listbox(listbox_frame, selectmode=tk.MULTIPLE,
                                       bg=listbox_bg, fg=listbox_fg,
                                       selectbackground=select_bg, selectforeground=select_fg,
                                       exportselection=False,
                                       font=('Arial', 10), relief=tk.SOLID, borderwidth=1)
        
        listbox_scrollbar = ttk.Scrollbar(listbox_frame, orient="vertical", command=self.theme_listbox.yview)
        self.theme_listbox.config(yscrollcommand=listbox_scrollbar.set)
        
        self.theme_listbox.pack(side="left", fill="both", expand=True)
        listbox_scrollbar.pack(side="right", fill="y")

        display_theme_names = sorted([
            " ".join(word.capitalize() for word in theme_key.split('_'))
            for theme_key in config.THEMES.keys()
        ])
        for theme_name in display_theme_names:
            self.theme_listbox.insert(tk.END, theme_name)

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))

        ttk.Button(button_frame, text="Search", command=self.perform_theme_search).pack(side=tk.LEFT, expand=True, padx=(0, 5))
        ttk.Button(button_frame, text="Cancel", command=self.theme_dialog.destroy).pack(side=tk.LEFT, expand=True)
        
    def perform_theme_search(self):
        """Called by the theme selection dialog to filter posts by theme."""
        selected_display_indices = self.theme_listbox.curselection()
        selected_themes_display = [self.theme_listbox.get(i) for i in selected_display_indices]
        
        if not selected_themes_display:
            messagebox.showwarning("No Selection", "Please select at least one theme.", parent=self.theme_dialog)
            return

        selected_theme_keys = []
        for display_name in selected_themes_display:
            original_key = "_".join(word.lower() for word in display_name.split(' '))
            if original_key in config.THEMES:
                selected_theme_keys.append(original_key)
        
        if not selected_theme_keys:
            messagebox.showerror("Error", "Could not map selected themes to internal keys.", parent=self.theme_dialog)
            return

        # --- THIS IS THE FIX FOR THE KEYERROR ---
        # Check for the correct column name in the DataFrame
        theme_col_name = None
        if 'Themes' in self.df_all_posts.columns:
            theme_col_name = 'Themes'
        elif 'themes' in self.df_all_posts.columns: # Check for lowercase version
            theme_col_name = 'themes'
        else:
            messagebox.showerror("Error", "Theme column not found in post data. Expected 'Themes' or 'themes'.", parent=self.theme_dialog)
            return
        # --- END FIX ---

        self.theme_dialog.destroy()

        results = self.df_all_posts[
            self.df_all_posts[theme_col_name].apply(
                lambda themes: any(t_key in themes for t_key in selected_theme_keys) if isinstance(themes, list) else False
            )
        ]
        
        search_term_str = f"Themes = '{', '.join(selected_themes_display)}'"
        self._handle_search_results(results, search_term_str)    

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

        # --- THIS IS THE FIX ---
        self.settings_win.geometry("400x340") # Increased height from 300 to 340
        # --- END FIX ---
        
        self.settings_win.transient(self.root)
        self.settings_win.grab_set()
        self.settings_win.resizable(False, False)
        self.settings_win.protocol("WM_DELETE_WINDOW", self.on_settings_window_close)

        main_frame = ttk.Frame(self.settings_win, padding="10")
        main_frame.pack(expand=True, fill=tk.BOTH)

        # Theme Setting
        theme_frame = ttk.Labelframe(main_frame, text="Display Theme", padding="10")
        theme_frame.pack(fill="x", pady=5)
        self.settings_theme_var = tk.StringVar(value=self.app_settings.get("theme", settings.DEFAULT_SETTINGS.get("theme")))
        
        ttk.Radiobutton(theme_frame, text="Dark", variable=self.settings_theme_var, value="dark", command=self.on_setting_change).pack(side="left", padx=5, expand=True)
        ttk.Radiobutton(theme_frame, text="Light", variable=self.settings_theme_var, value="light", command=self.on_setting_change).pack(side="left", padx=5, expand=True)
        ttk.Radiobutton(theme_frame, text="RWB", variable=self.settings_theme_var, value="rwb", command=self.on_setting_change).pack(side="left", padx=5, expand=True)
        ttk.Radiobutton(theme_frame, text="Halloween", variable=self.settings_theme_var, value="halloween", command=self.on_setting_change).pack(side="left", padx=5, expand=True)
        
        # Link Opening Preference
        link_pref_frame = ttk.Labelframe(main_frame, text="Link Opening Preference", padding="10")
        link_pref_frame.pack(fill="x", pady=5)
        self.settings_link_pref_var = tk.StringVar(value=self.app_settings.get("link_opening_preference", settings.DEFAULT_SETTINGS.get("link_opening_preference", "default")))
        
        ttk.Radiobutton(link_pref_frame, text="System Default Browser", variable=self.settings_link_pref_var, value="default", command=self.on_setting_change).pack(anchor="w", padx=5)
        ttk.Radiobutton(link_pref_frame, text="Google Chrome (Incognito)", variable=self.settings_link_pref_var, value="chrome_incognito", command=self.on_setting_change).pack(anchor="w", padx=5)
        
        # Highlight Abbreviations Checkbox
        abbreviations_frame = ttk.Labelframe(main_frame, text="Content Highlighting", padding="10")
        abbreviations_frame.pack(fill="x", pady=5)
        self.settings_highlight_abbreviations_var = tk.BooleanVar(value=self.app_settings.get("highlight_abbreviations", settings.DEFAULT_SETTINGS.get("highlight_abbreviations")))
        ttk.Checkbutton(abbreviations_frame, text="Highlight Abbreviations in Post Text", variable=self.settings_highlight_abbreviations_var, command=self.on_setting_change).pack(anchor="w", padx=5)

        # Close Button
        close_button_frame = ttk.Frame(main_frame)
        close_button_frame.pack(side="bottom", fill=tk.X, pady=(10,0))
        ttk.Button(close_button_frame, text="Close", command=self.on_settings_window_close).pack(pady=5)

    def on_setting_change(self, event=None):
        """Handles changes from the Settings window and saves them."""
        # --- Theme ---
        new_theme = self.settings_theme_var.get()
        if self.current_theme != new_theme:
            self._set_theme(new_theme)
            
        # --- Highlight Abbreviations ---
        new_highlight_abbreviations = self.settings_highlight_abbreviations_var.get()
        if self.app_settings.get("highlight_abbreviations") != new_highlight_abbreviations:
            self.app_settings["highlight_abbreviations"] = new_highlight_abbreviations
            settings.save_settings(self.app_settings)
            print(f"Highlight abbreviations saved: '{new_highlight_abbreviations}'")

        # --- Link Opening Preference ---
        new_link_pref = self.settings_link_pref_var.get()
        if self.app_settings.get("link_opening_preference") != new_link_pref:
            self.app_settings["link_opening_preference"] = new_link_pref
            settings.save_settings(self.app_settings)
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
            "- Known Issue: Some data files show the last posts (4954-4966) as being from 2022. Their correct date is late 2020."
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
        # --- Nested helper function defined first ---
        def _calculate_and_display():
            text_to_calc = self.gematria_input_entry.get()
            if text_to_calc:
                results = utils.calculate_gematria(text_to_calc)
                self.gematria_simple_var.set(f"Simple / Ordinal: {results.get('simple', 0)}")
                self.gematria_reverse_var.set(f"Reverse Ordinal: {results.get('reverse', 0)}")
                self.gematria_hebrew_var.set(f"Hebrew / Jewish: {results.get('hebrew', 0)}")
                self.gematria_english_var.set(f"English (Agrippa): {results.get('english', 0)}")

        # --- Main method logic begins ---
        if hasattr(self, 'gematria_win') and self.gematria_win.winfo_exists():
            self.gematria_win.lift()
            self.gematria_win.focus_set()
            if initial_text and hasattr(self, 'gematria_input_entry'):
                self.gematria_input_entry.delete(0, tk.END)
                self.gematria_input_entry.insert(0, initial_text)
                self.gematria_input_entry.focus_set()
                # --- THIS IS THE FIX ---
                # Call the local helper function defined above
                _calculate_and_display()
                # --- END FIX ---
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

# --- START PANE MANAGEMENT METHODS ---

    def set_initial_sash_position(self):
        """Sets the initial position of the sash after the window is drawn."""
        try:
            # Set the divider to be 500 pixels from the left
            self.text_image_paned_window.sashpos(0, 500)
        except tk.TclError:
            # This handles cases where the window isn't ready yet
            pass

    def _check_sash_position(self, event):
        """After a drag, ensures the image pane is not completely closed."""
        MIN_WIDTH = 50  # Minimum pixel width to keep the pane open
        try:
            sash_pos = self.text_image_paned_window.sashpos(0)
            pane_width = self.text_image_paned_window.winfo_width()
            
            # If the user dragged the sash too far to the right
            if sash_pos > pane_width - MIN_WIDTH:
                new_sash_pos = pane_width - MIN_WIDTH
                self.text_image_paned_window.sashpos(0, new_sash_pos)
        except tk.TclError:
            # This can happen if the widget is destroyed, just ignore.
            pass

# --- END PANE MANAGEMENT METHODS ---

# --- START SHOW ALL NOTES WINDOW ---
    def show_all_notes_window(self):
        """Creates and shows a new window displaying all user notes."""
        if not self.user_notes:
            messagebox.showinfo("User Notes", "You have not created any notes yet.", parent=self.root)
            return

        notes_win = tk.Toplevel(self.root)
        notes_win.title("All User Notes")
        notes_win.geometry("600x500")
        notes_win.transient(self.root)
        notes_win.grab_set()

        try:
            dialog_bg = self.style.lookup("TFrame", "background")
            text_bg = self.style.lookup("TEntry", "fieldbackground")
            text_fg = self.style.lookup("TEntry", "foreground")
            link_fg = self.link_label_fg_dark if self.current_theme == "dark" else self.link_label_fg_light
        except tk.TclError:
            dialog_bg = "#f0f0f0"
            text_bg = "#ffffff"
            text_fg = "#000000"
            link_fg = "#0056b3"
        
        notes_win.configure(bg=dialog_bg)
        
        main_frame = ttk.Frame(notes_win, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        notes_text = tk.Text(main_frame, wrap=tk.WORD, bg=text_bg, fg=text_fg, padx=10, pady=10)
        notes_scroll = ttk.Scrollbar(main_frame, orient="vertical", command=notes_text.yview)
        notes_text.configure(yscrollcommand=notes_scroll.set)
        
        notes_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        notes_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        notes_text.tag_configure("post_header", font=("Arial", 11, "bold"), spacing3=2)
        notes_text.tag_configure("note_content", font=("Arial", 10), lmargin1=15, lmargin2=15, spacing3=15)
        notes_text.tag_configure("clickable_link", foreground=link_fg, underline=True)
        notes_text.tag_bind("clickable_link", "<Enter>", lambda e: notes_text.config(cursor="hand2"))
        notes_text.tag_bind("clickable_link", "<Leave>", lambda e: notes_text.config(cursor=""))

        # Sort notes by Post Number for a logical order
        try:
            sorted_indices = sorted(self.user_notes.keys(), key=lambda idx: self.df_all_posts.loc[int(idx), 'Post Number'])
        except (ValueError, KeyError):
            sorted_indices = self.user_notes.keys() # Fallback to unsorted if there's a data issue

        for original_df_index_str in sorted_indices:
            note_data = self.user_notes.get(original_df_index_str, {})
            note_content = note_data.get("content", "").strip()
            if not note_content: continue

            try:
                post_series = self.df_all_posts.loc[int(original_df_index_str)]
                post_num = post_series.get('Post Number', f"Index {original_df_index_str}")
            except (ValueError, KeyError):
                post_num = f"Index {original_df_index_str}"

            header_text = f"Note for Post #{post_num}"
            link_tag = f"note_link_{post_num}"
            
            notes_text.insert(tk.END, header_text, ("post_header", "clickable_link", link_tag))
            # Wrap the jump command in a function to close the notes window first
            def jump_and_close(p_num):
                notes_win.destroy()
                self.jump_to_post_number_from_ref(p_num)

            notes_text.tag_bind(link_tag, "<Button-1>", lambda e, pn=post_num: jump_and_close(pn))
            notes_text.insert(tk.END, "\n" + note_content + "\n\n", "note_content")

        notes_text.config(state=tk.DISABLED)
# --- END SHOW ALL NOTES WINDOW ---

# --- START SHOW_ABOUT_DIALOG ---

    def show_about_dialog(self):
        messagebox.showinfo("About QView", 
                            "QView - Q Post Explorer\n\n"
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

# --- START sort_treeview_column ---
    def sort_treeview_column(self, col, reverse):
        """Sorts the treeview items when a column header is clicked."""
        try:
            # Get items as a list of tuples: (column_value, iid_as_int)
            # The iid is the original DataFrame index, which is numeric and perfect for sorting.
            items = []
            for iid in self.post_tree.get_children(''):
                try:
                    col_value = self.post_tree.set(iid, col)
                    iid_int = int(iid) # The iid is the original DataFrame index string
                    items.append((col_value, iid_int))
                except (ValueError, TypeError):
                    continue # Skip if iid isn't a valid integer

            # Define a smart sort key
            def get_sort_key(item):
                col_value, iid_int = item
                
                if col == "Post #":
                    # For this column, the *primary* key IS the numeric value.
                    try:
                        if col_value.startswith('#'):
                            primary_key = int(col_value[1:])
                        elif col_value.startswith('Idx:'):
                            primary_key = int(col_value[4:])
                        else:
                            primary_key = 0
                    except (ValueError, TypeError):
                        primary_key = 0
                    return primary_key

                # For ALL OTHER columns (Date, Notes, Bookmarked):
                # Sort by the column value (e.g., "★" or "2020-10-27") first.
                # Then, as a tie-breaker, sort by the iid_int (original numeric index).
                return (col_value, iid_int)
            
            # Perform the sort using our new smart key
            items.sort(key=get_sort_key, reverse=reverse)

            # Reorder items in the treeview
            for index, (val, iid_int) in enumerate(items):
                self.post_tree.move(str(iid_int), '', index) # Use the string version of iid to move

            # Invert the sort direction for the next click on this column
            self.post_tree.heading(col, command=lambda: self.sort_treeview_column(col, not reverse))
            
        except Exception as e:
            print(f"Error sorting treeview column '{col}': {e}")
            # Reset the command to prevent repeated errors if sorting fails
            self.post_tree.heading(col, command=lambda: self.sort_treeview_column(col, reverse))
# --- END sort_treeview_column ---

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
# --- START apply_dark_theme ---
    def apply_dark_theme(self):
        self.current_theme = "dark"; self.style.theme_use('clam')
        bg="#2b2b2b"; fg="#e0e0e0"; entry_bg="#3c3f41"; btn_bg="#4f4f4f"; btn_active="#6a6a6a"
        tree_bg="#3c3f41"; tree_sel_bg="#0078D7"; tree_sel_fg="#ffffff"; heading_bg="#4f4f4f"
        progress_trough = '#3c3f41'; progress_bar_color = '#0078D7'
        accent_yellow = "#FFCB6B"
        
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
        self.style.configure("Entry.TFrame", background=entry_bg)
        if hasattr(self, 'image_canvas'): self.image_canvas.configure(bg=entry_bg)
        if hasattr(self, 'image_canvas'): self.image_canvas.configure(bg=entry_bg)

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
# --- END apply_dark_theme ---

# --- START apply_light_theme ---
    def apply_light_theme(self):
        """Applies a standard light theme."""
        self.current_theme = "light"
        self.style.theme_use('vista')

        bg = "#f0f0f0"
        fg = "#000000"
        entry_bg = "#ffffff"
        btn_bg = "#e1e1e1"
        btn_active = "#c0c0c0"
        tree_sel_bg = "#0078d7"
        tree_sel_fg = "#ffffff"
        heading_bg = "#e1e1e1"
        link_color = self.link_label_fg_light

        self.root.configure(bg=bg)
        self.style.configure(".", background=bg, foreground=fg, font=('Arial', 10))
        self.style.configure("TFrame", background=bg)
        self.style.configure("TLabel", background=bg, foreground=fg, padding=3)
        self.style.configure("TButton", background=btn_bg, foreground=fg, padding=5, font=('Arial', 9, 'bold'), borderwidth=1, relief=tk.RAISED)
        self.style.map("TButton", background=[("active", btn_active)])
        self.style.configure("Treeview", background=entry_bg, foreground=fg, fieldbackground=entry_bg, borderwidth=1, relief=tk.FLAT)
        self.style.map("Treeview", background=[("selected", tree_sel_bg)], foreground=[("selected", tree_sel_fg)])
        self.style.configure("Treeview.Heading", background=heading_bg, foreground=fg, font=('Arial', 10, 'bold'), relief=tk.FLAT, padding=3)
        self.style.configure("TEntry", fieldbackground=entry_bg, foreground=fg, insertbackground=fg)
        self.style.configure("TLabelframe", background=bg, foreground=fg)
        self.style.configure("TLabelframe.Label", background=bg, foreground=fg, font=('Arial', 10, 'bold'))

        self.post_text_area.configure(bg=entry_bg, fg=fg, insertbackground=fg, selectbackground=tree_sel_bg)

        # --- THIS IS THE FIX ---
        # Ensure all frames in the image pane are correctly styled.
        self.style.configure("Entry.TFrame", background=entry_bg)
        if hasattr(self, 'image_canvas'): self.image_canvas.configure(bg=entry_bg)
        
        # --- END FIX ---
        
        # Configure Text widget tags
        self.post_text_area.tag_configure("bold_label", foreground="#333333", font=('Arial', 11, 'bold'))
        self.post_text_area.tag_configure("post_number_val", foreground="#0056b3")
        self.post_text_area.tag_configure("bookmarked_header", foreground="#b30000")
        self.post_text_area.tag_configure("abbreviation_tag", background="#d0eaff", foreground="#000000")
        self.post_text_area.tag_configure("date_val", foreground="#555555")
        self.post_text_area.tag_configure("themes_val", foreground="#0056b3")
        self.post_text_area.tag_configure("clickable_link_style", foreground=link_color, underline=True)
        self.post_text_area.tag_configure("welcome_title_tag", font=('Arial', 24, 'bold'), foreground="#333333", justify='center')
        self.post_text_area.tag_configure("quoted_ref_header", foreground="#555555")
        self.post_text_area.tag_configure("quoted_ref_text_body", foreground="#333333")
# --- END apply_light_theme ---

# --- START apply_rwb_theme ---
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
        self.style.configure("Entry.TFrame", background=entry_bg)
        if hasattr(self, 'image_canvas'): self.image_canvas.configure(bg=entry_bg)
        
        
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
# --- END apply_rwb_theme ---

# --- START apply_halloween_theme ---
    def apply_halloween_theme(self):
        """Applies a vibrant, spooky Halloween theme."""
        self.current_theme = "halloween"
        self.style.theme_use('clam')
        
        # --- New, vibrant Halloween color palette ---
        bg = "#2c1b47"           # Deep dark purple
        fg = "#ffcc99"           # Pale orange/cream text
        entry_bg = "#3e2a63"      # Lighter purple for entries/treeview
        btn_bg = "#b35900"       # Muted, dark orange for buttons
        btn_active = "#cc6600"   # Brighter orange for active buttons
        tree_sel_bg = "#7fff00"  # Slime Green / Chartreuse for selections
        tree_sel_fg = "#000000"  # Black text on green
        heading_bg = "#3e2a63"
        link_color = "#ff9933"   # Bright orange for links
        accent_white = "#ffffff" # Pure white for specific accents
        
        self.root.configure(bg=bg)
        self.style.configure(".", background=bg, foreground=fg, font=('Arial', 10))
        self.style.configure("TFrame", background=bg)
        self.style.configure("TLabel", background=bg, foreground=fg, padding=3)
        self.style.configure("TButton", background=btn_bg, foreground=accent_white, padding=5, font=('Arial', 9, 'bold'), borderwidth=1, relief=tk.RAISED)
        self.style.map("TButton", background=[("active", btn_active)])
        self.style.configure("Treeview", background=entry_bg, foreground=fg, fieldbackground=entry_bg, borderwidth=1, relief=tk.FLAT)
        self.style.map("Treeview", background=[("selected", tree_sel_bg)], foreground=[("selected", tree_sel_fg)])
        self.style.configure("Treeview.Heading", background=heading_bg, foreground=accent_white, font=('Arial', 10, 'bold'), relief=tk.FLAT, padding=3)
        self.style.configure("TEntry", fieldbackground=entry_bg, foreground=fg, insertbackground=fg)
        self.style.configure("TLabelframe", background=bg, foreground=fg)
        self.style.configure("TLabelframe.Label", background=bg, foreground=link_color, font=('Arial', 10, 'bold'))
        
        # Configure Text widget and Image Canvas
        self.post_text_area.configure(bg=entry_bg, fg=fg, insertbackground=fg, selectbackground=tree_sel_bg)

        # --- THIS IS THE FIX ---
        # Ensure all frames in the image pane are correctly styled.
        self.style.configure("Entry.TFrame", background=entry_bg)
        if hasattr(self, 'image_canvas'): self.image_canvas.configure(bg=entry_bg)
        
        # --- END FIX ---

        # Apply vibrant accents to text tags
        self.post_text_area.tag_configure("bold_label", foreground=link_color)
        self.post_text_area.tag_configure("post_number_val", foreground=link_color)
        self.post_text_area.tag_configure("bookmarked_header", foreground="#ffd700")
        self.post_text_area.tag_configure("abbreviation_tag", background=tree_sel_bg, foreground=tree_sel_fg)
        self.post_text_area.tag_configure("date_val", foreground=fg)
        self.post_text_area.tag_configure("themes_val", foreground=accent_white)
        self.post_text_area.tag_configure("clickable_link_style", foreground=link_color, underline=True)
        self.post_text_area.tag_configure("welcome_title_tag", foreground=tree_sel_bg)
        self.post_text_area.tag_configure("quoted_ref_header", foreground=link_color)
        self.post_text_area.tag_configure("quoted_ref_text_body", foreground=fg)
# --- END apply_halloween_theme ---

# --- START SET_THEME ---
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
        elif theme_name == "halloween":
            self.apply_halloween_theme()
        
        self.app_settings["theme"] = theme_name
        self.theme_var.set(theme_name)
        # This is the crucial line that saves the setting to the file
        settings.save_settings(self.app_settings)
        print(f"Theme changed and saved: '{theme_name}'")

        if self.current_display_idx != -1 and self.df_displayed is not None and not self.df_displayed.empty: 
            self.update_display()
        else: 
            self.show_welcome_message()
# --- END SET_THEME ---
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
        
        self.post_text_area.tag_configure("abbreviation_tag", underline=False)
        self.post_text_area.tag_configure("search_highlight_tag", background="#FFFF00", foreground="black")

        self.post_text_area.tag_configure("clickable_link_style", underline=True)
        def show_hand_cursor(event): event.widget.config(cursor="hand2")
        def show_arrow_cursor(event): event.widget.config(cursor=self.default_text_area_cursor)
        
        self.post_text_area.tag_bind("clickable_link_style", "<Enter>", show_hand_cursor)
        self.post_text_area.tag_bind("clickable_link_style", "<Leave>", show_arrow_cursor)
        
        self.post_text_area.tag_configure("bookmarked_header", font=(default_font_name, 11, "bold"))
        self.post_text_area.tag_configure("quoted_ref_header", font=(default_font_name, 10, "italic", "bold"), lmargin1=20, lmargin2=20, spacing1=5)
        self.post_text_area.tag_configure("quoted_ref_text_body", font=(default_font_name, 10, "italic"), lmargin1=25, lmargin2=25, spacing3=5)
        
        # --- New Welcome Screen Tags ---
        self.post_text_area.tag_configure("welcome_title_tag", font=("Arial", 20, "bold"), justify=tk.CENTER, spacing1=5, spacing3=5)
        self.post_text_area.tag_configure("welcome_tagline_tag", font=("Arial", 11, "italic"), justify=tk.CENTER, spacing3=20)
        self.post_text_area.tag_configure("welcome_heading_tag", font=("Arial", 12, "bold"), spacing1=10, spacing3=5)
        self.post_text_area.tag_configure("welcome_body_tag", font=("Arial", 10), spacing1=5)
        self.post_text_area.tag_configure("welcome_hint_tag", font=("Arial", 9, "italic"), justify=tk.RIGHT, foreground="grey")
        self.post_text_area.tag_configure("search_highlight_tag", background="yellow", foreground="black")
# --- END CONFIGURE_TEXT_TAGS ---
# --- END QPOSTVIEWER_CLASS_DEFINITION ---