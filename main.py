# --- START MAIN_PY_HEADER ---
import tkinter as tk
from tkinter import messagebox  # For initial CHROME_PATH check info

import gui  # The main application GUI
import utils  # For CHROME_PATH check

# --- END MAIN_PY_HEADER ---

# --- START MAIN_APP_LAUNCH ---
if __name__ == "__main__":
    # Inform user if Chrome path wasn't found, as it affects 'Open in Incognito'
    if not utils.CHROME_PATH:
        print(
            f"{utils.TermColors.LIGHT_YELLOW}Note:{utils.TermColors.RESET} Google Chrome path was not automatically found (CHROME_PATH='{utils.CHROME_PATH}')."
        )
        print(
            "The 'Open in Incognito' feature for links will attempt to use the system default browser or may fail if Chrome is not set up correctly."
        )
        # Optionally, show a non-blocking messagebox if Tkinter is available
        # info_root = tk.Tk()
        # info_root.withdraw() # Hide the root window for the messagebox
        # messagebox.showinfo("Chrome Path Note", "Google Chrome path was not automatically found. 'Open in Incognito' might not work as expected.", parent=None)
        # info_root.destroy()

    root = tk.Tk()
    try:
        # Create and run the application
        app = gui.QPostViewer(root)

        # Check if the root window still exists after QPostViewer initialization
        # (it might be destroyed if data loading fails in __init__)
        if root.winfo_exists():
            root.mainloop()
        else:
            print(
                f"{utils.TermColors.LIGHT_RED}Error:{utils.TermColors.RESET} GUI root window was destroyed during initialization (likely a critical data loading error). Application cannot start."
            )
            # A messagebox here might also fail if Tk is already in a bad state.
            # messagebox.showerror("Fatal Error", "Application failed to initialize GUI. Check console for errors.", parent=None) # parent=None if root destroyed

    except tk.TclError as e:
        # Handle cases where the mainloop might not have started or was interrupted badly
        if 'can\'t invoke "winfo" command' in str(
            e
        ) or "application has been destroyed" in str(e):
            print(
                f"{utils.TermColors.LIGHT_YELLOW}Info:{utils.TermColors.RESET} GUI startup failed or was closed very early."
            )
        else:
            print(
                f"{utils.TermColors.LIGHT_RED}TclError during GUI startup:{utils.TermColors.RESET} {e}"
            )
            import traceback

            traceback.print_exc()
            # messagebox.showerror("TclError", f"A TclError occurred: {e}\nApplication might not have started correctly.", parent=None)
            raise  # Re-raise for more serious TclErrors
    except Exception as e:
        print(
            f"{utils.TermColors.LIGHT_RED}Unexpected error during GUI startup:{utils.TermColors.RESET} {e}"
        )
        import traceback

        traceback.print_exc()
        # messagebox.showerror("Fatal Error", f"An unexpected error occurred: {e}\nApplication will exit. Check console.", parent=None)
# --- END MAIN_APP_LAUNCH ---
