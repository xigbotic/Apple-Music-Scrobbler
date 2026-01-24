import customtkinter as ctk
import pystray
from pystray import MenuItem as item
from PIL import Image, ImageTk
import os
import sys
import threading
import ctypes
import io

class AppUI(ctk.CTk):
    def __init__(self, auth_handler, tracker_start_callback):
        super().__init__()

        # 1. Attributes
        self.auth_handler = auth_handler
        self.tracker_callback = tracker_start_callback
        self.current_raw_img = None
        
        # 2. Windows Taskbar Branding
        try:
            myappid = 'Xignotic.AppleMusicScrobbler.004' 
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        except:
            pass

        # 3. UI Styling Config
        self.bg_color = "#000000"  
        self.card_color = "#0A0A0A" 
        self.border_color = "#1A1A1A"
        self.font_family = "Segoe UI Variable Display"

        # 4. Window Setup
        self.title("Apple Music Scrobbler")
        self.geometry("380x720") 
        self.configure(fg_color=self.bg_color)
        self.resizable(False, False)

        # 5. Icon Logic
        if getattr(sys, 'frozen', False):
            self.icon_path = os.path.join(sys._MEIPASS, "icon.ico")
        else:
            self.icon_path = "icon.ico"

        if os.path.exists(self.icon_path):
            try:
                self.iconbitmap(self.icon_path)
                self.tray_img = Image.open(self.icon_path)
            except:
                self.tray_img = Image.new('RGB', (64, 64), color=(0, 0, 0))
        else:
            self.tray_img = Image.new('RGB', (64, 64), color=(0, 0, 0))

        # 6. Build UI
        self.setup_ui()
        
        # 7. Lifecycle
        self.protocol('WM_DELETE_WINDOW', self.hide_window)
        self.tray_icon = None

        if self.auth_handler.get_cached_session():
            self.update_stats()
            self.start_tracker()
        else:
            self.status_label.configure(text="STATUS: DISCONNECTED", text_color="#FF3B3B")

    def setup_ui(self):
        """Standard UI Setup with clean transparency and modern rounding."""
        
        # --- TOP SECTION ---
        self.top_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.top_frame.pack(fill="x", padx=30, pady=(25, 0))

        self.stats_label = ctk.CTkLabel(
            self.top_frame, text=f"SCROBBLES: {self.auth_handler.total_scrobbles}", 
            font=(self.font_family, 10, "bold"), 
            text_color="#AAAAAA",
            fg_color="transparent"
        )
        self.stats_label.pack(side="left")

        # --- BOTTOM SECTION (Packed first to reserve space) ---
        
        self.footer_label = ctk.CTkLabel(
            self, text="v0.0.5 • Developed by Xignotic", 
            font=(self.font_family, 9, "bold"), 
            text_color="#FFFFFF",
            fg_color="transparent"
        )
        self.footer_label.pack(side="bottom", pady=20)

        self.status_label = ctk.CTkLabel(
            self, text="SYSTEM INITIALIZED", 
            font=(self.font_family, 9, "bold"), 
            text_color="#BBBBBB",
            fg_color="transparent"
        )
        self.status_label.pack(side="bottom", pady=(0, 0))

        self.login_btn = ctk.CTkButton(
            self, text="CONNECT LAST.FM", 
            font=(self.font_family, 12, "bold"),
            fg_color="#FFFFFF", text_color="#000000",
            hover_color="#EEEEEE", 
            height=45, 
            corner_radius=20,
            command=self.login
        )
        self.login_btn.pack(side="bottom", pady=(10, 10), padx=35, fill="x")

        # --- MIDDLE SECTION (The Music Card) ---
        self.card = ctk.CTkFrame(
            self, 
            fg_color=self.card_color, 
            corner_radius=30,
            border_width=1,
            border_color=self.border_color
        )
        self.card.pack(padx=25, pady=10, fill="both", expand=True)

        self.cover_label = ctk.CTkLabel(self.card, text="", width=220, height=220, fg_color="transparent")
        self.cover_label.pack(pady=(25, 15))
        self.set_default_cover() 

        self.track_label = ctk.CTkLabel(
            self.card, text="Ready", 
            font=(self.font_family, 18, "bold"), 
            wraplength=280, text_color="#FFFFFF", 
            fg_color="transparent"
        )
        self.track_label.pack(pady=(5, 0))
        
        self.artist_label = ctk.CTkLabel(
            self.card, text="Waiting...", 
            font=(self.font_family, 14), 
            text_color="#888888", 
            fg_color="transparent"
        )
        self.artist_label.pack(pady=2)

        self.album_label = ctk.CTkLabel(
            self.card, text="", 
            font=(self.font_family, 11), 
            text_color="#555555", 
            fg_color="transparent"
        )
        self.album_label.pack(pady=2)

        self.progress = ctk.CTkProgressBar(
            self.card, height=2, fg_color="#111111", 
            progress_color="#FFFFFF", 
            determinate_speed=0.1
        )
        self.progress.pack(fill="x", padx=40, pady=15)
        self.progress.set(0)

        self.scrobble_status = ctk.CTkLabel(
            self.card, text="IDLE", 
            font=(self.font_family, 10, "bold"), 
            fg_color="#111111", corner_radius=20, 
            width=110, height=26
        )
        self.scrobble_status.pack(pady=(0, 20))

    def set_default_cover(self):
        """Sets the placeholder image."""
        img = Image.new('RGB', (220, 220), color='#111111')
        ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(220, 220))
        self.cover_label.configure(image=ctk_img)
        self.cover_label.image = ctk_img

    def update_track_info(self, artist, track, album, is_playing, thumbnail_stream=None):
        """Updates UI text, cover art, and playback status labels."""
        if track and track != "NO MEDIA":
            # 1. Update text only if it has changed (Saves CPU)
            if self.track_label.cget("text") != track:
                self.track_label.configure(text=track)
                self.artist_label.configure(text=artist)
                self.album_label.configure(text=album if album else "")

                # 2. Optimized Image Loading (Prevents Memory Leak)
                if thumbnail_stream:
                    try:
                        # Clear old reference to help GC (Garbage Collection)
                        self.cover_label.configure(image=None)
                        self.cover_label.image = None
                        
                        img = Image.open(thumbnail_stream).convert("RGB")
                        ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(220, 220))
                        
                        self.cover_label.configure(image=ctk_img)
                        self.cover_label.image = ctk_img
                    except Exception:
                        self.set_default_cover()
                else:
                    self.set_default_cover()

            # 3. Playback Status Logic
            curr_status = self.scrobble_status.cget("text")
            if is_playing:
                # Don't overwrite "QUALIFIED" if it's already showing
                if "QUALIFIED" not in curr_status:
                    self.scrobble_status.configure(text="● PLAYING", text_color="#00FF7F")
            else:
                self.scrobble_status.configure(text="● PAUSED", text_color="#FFB84D")
            

        else:
            # Fallback when no music is detected
            if self.track_label.cget("text") != "NO MEDIA":
                self.track_label.configure(text="NO MEDIA")
                self.artist_label.configure(text="System Standby")
                self.album_label.configure(text="")
                self.set_default_cover()
                self.scrobble_status.configure(text="IDLE", text_color="#444444")
                self.progress.set(0)

    def update_stats(self):
        """Refreshes the scrobble count and updates button state."""
        self.stats_label.configure(text=f"SCROBBLES: {self.auth_handler.total_scrobbles}")
        self.status_label.configure(text="SYSTEM INITIALIZED", text_color="#00FF7F")
        self.login_btn.configure(state="disabled", text="AUTHENTICATED", fg_color="#111111", text_color="#444444")

    def start_tracker(self):
        """Launches the tracker callback."""
        self.tracker_callback()

    def hide_window(self):
        """Hides the window to the system tray."""
        self.withdraw()
        if not self.tray_icon:
            menu = (item('OPEN', self.show_window), item('EXIT', self.exit_app))
            self.tray_icon = pystray.Icon("scrobbler", self.tray_img, "XIGNOTIC", menu)
            threading.Thread(target=self.tray_icon.run, daemon=True).start()


    def update_tray_tooltip(self, title):
        if self.tray_icon:
            self.tray_icon.title = title

    def show_window(self, icon=None, item=None):
        """Restores the window from the tray and brings to front."""
        if self.tray_icon:
            self.tray_icon.stop()
            self.tray_icon = None
        
        self.after(0, self.deiconify)
        self.after(100, self.focus_force)
        self.after(200, self.lift)

    def exit_app(self, icon=None, item=None):
        """Quits the application entirely and kills background threads."""
        print("Stopping Tray Icon...")
        if self.tray_icon:
            self.tray_icon.stop()
        print("Terminating Scrobbler...")
        self.quit()
        os._exit(0)

    def login(self):
        """Starts the auth process."""
        self.status_label.configure(text="AWAITING BROWSER AUTH...", text_color="#FFB84D")
        self.session_gen, self.auth_url = self.auth_handler.start_auth_process()
        self.login_btn.configure(text="CONFIRM LINK", command=self.complete_login)

    def complete_login(self):
        """Completes the auth process."""
        if self.auth_handler.complete_auth_process(self.session_gen, self.auth_url):
            self.status_label.configure(text="SYSTEM INITIALIZED", text_color="#00FF7F")
            self.update_stats()
            self.start_tracker()
        else:
            self.status_label.configure(text="AUTH FAILED", text_color="#FF3B3B")
            self.login_btn.configure(text="RETRY CONNECT", command=self.login)