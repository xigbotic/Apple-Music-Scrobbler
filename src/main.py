import threading
import asyncio
import time
import customtkinter as ctk
import winreg
import os
import sys
from auth import LastFMAuthenticator
from tracker import MediaTracker
from ui import AppUI
from concurrent.futures import ThreadPoolExecutor


from dotenv import load_dotenv
if getattr(sys, 'frozen', False):
    base_path = sys._MEIPASS
else:
    base_path = os.path.dirname(os.path.dirname(__file__))
env_path = os.path.join(base_path, ".env")
load_dotenv(dotenv_path=env_path)


API_KEY = os.environ.get("LASTFM_API_KEY", "")
API_SECRET = os.environ.get("LASTFM_API_SECRET", "")

class MainApp:
    def __init__(self):
        ctk.set_appearance_mode("System")
        self.executor = ThreadPoolExecutor(max_workers=4)

        self.auth = LastFMAuthenticator(API_KEY, API_SECRET)
        self.ui = AppUI(self.auth, self.start_tracker_thread)
        
        self.tracker = MediaTracker(callback_func=self.on_track_change)
        
        self.current_scrobble_track = None
        self.pending_scrobble = None
        self.ready_to_submit = False
        self.ui.after(0, lambda: self.ui.progress.set(0))
        self.last_state = None
        self.last_pos = 0
        self.last_now_playing_ping = 0
        self.ui.startup_callback = self.update_startup_registry
        self.auth.get_cached_session() 
        
    def update_startup_registry(self, enabled):
        """Adds or removes the app from the Windows Startup Registry."""
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        app_name = "XignoticScrobbler"
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE)
            if enabled:
                path = os.path.realpath(sys.executable if getattr(sys, 'frozen', False) else __file__)
                winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, path)
                print("Registry: Startup Enabled")
            else:
                try:
                    winreg.DeleteValue(key, app_name)
                    print("Registry: Startup Disabled")
                except FileNotFoundError: pass
            winreg.CloseKey(key)
        except Exception as e:
            print(f"Registry Error: {e}")

    def start_tracker_thread(self):
        thread = threading.Thread(target=self.run_async_tracker, daemon=True)
        thread.start()
        
    def run_async_tracker(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self.tracker.run_loop())

    def on_track_change(self, artist, track, album, is_playing, duration, current_pos, thumbnail):
        """
        Main heartbeat triggered by tracker.py every ~1 second.
        """
        if duration > 0:
            prog = min(1.0, current_pos / duration)
            self.ui.after(0, lambda p=prog: self.ui.progress.set(p))

        if self.pending_scrobble and track == self.pending_scrobble['track']:
            if current_pos < (self.last_pos - 10):
                if self.ready_to_submit:
                    self.submit_final_scrobble(self.pending_scrobble)
                
                self.pending_scrobble['timestamp'] = int(time.time())
                self.ready_to_submit = False

                if self.auth.session_key and track:
                    self.executor.submit(self.safe_now_playing, artist, track, album)
        
        self.last_pos = current_pos

        if track is None:
            self.ui.after(0, lambda: self.ui.update_track_info(None, None, None, False, None))
            self.last_state = False
            self.current_scrobble_track = None
            return

        if track != self.current_scrobble_track or is_playing != self.last_state:
            self.ui.after(0, lambda: self.ui.update_track_info(artist, track, album, is_playing, thumbnail))
            self.last_state = is_playing

        if track:
            self.ui.update_tray_tooltip(f"{track} - {artist}")
        else:
            self.ui.update_tray_tooltip("Apple Music Scrobbler")

        self.handle_scrobble_logic(artist, track, album, is_playing, duration, current_pos)

    def handle_scrobble_logic(self, artist, track, album, is_playing, duration, current_pos):
        """Logic based on real system position rather than estimated timers."""
        real_time_now = int(time.time())

        if not self.pending_scrobble or self.pending_scrobble['track'] != track:
            if self.pending_scrobble and self.ready_to_submit:
                self.submit_final_scrobble(self.pending_scrobble)

            print(f"🎵 New Track: {track}")
            self.pending_scrobble = {
                'artist': artist, 'track': track, 'album': album,
                'timestamp': real_time_now,
                'duration': duration
            }
            self.ready_to_submit = False
            self.current_scrobble_track = track
            self.last_now_playing_ping = time.monotonic()
            
            if self.auth.session_key and track:
                self.executor.submit(self.safe_now_playing, artist, track, album)

        target = max(30, min(240, duration / 2)) if duration > 0 else 30
        
        if not self.ready_to_submit and current_pos >= target:
            self.ready_to_submit = True
            self.ui.after(0, lambda: self.ui.scrobble_status.configure(
                text="● SCROBBLE QUALIFIED", text_color="cyan"
            ))
            self.ui.after(5000, self.reset_status_text)

        if is_playing and (time.monotonic() - self.last_now_playing_ping > 120):
            self.executor.submit(self.safe_now_playing, artist, track, album)
            self.last_now_playing_ping = time.monotonic()

    def reset_status_text(self):
        """Cleanly reverts the UI status text if still playing."""
        if self.last_state: 
            self.ui.scrobble_status.configure(text="● PLAYING", text_color="#00FF7F")

    def safe_now_playing(self, artist, track, album):
        try:
            self.auth.get_network().update_now_playing(artist=artist, title=track, album=album)
        except Exception as e:
            print(f"Network Warning (Now Playing): {e}")

    def submit_final_scrobble(self, track_data):
        try:
            self.auth.get_network().scrobble(
                artist=track_data['artist'],
                title=track_data['track'],
                album=track_data['album'],
                timestamp=track_data['timestamp']
            )
            self.auth.increment_scrobble_count()
            self.ui.after(0, self.ui.update_stats)
            print(f"✅ SCROBBLED: {track_data['track']}")
        except Exception as e:
            print(f"Scrobble Error: {e}")

    def run(self):
        self.ui.mainloop()

    def on_close(self):
        """Ensures all background threads are killed before exiting."""
        print("Shutting down...")
        self.executor.shutdown(wait=False)
        self.ui.quit()
        sys.exit(0)

if __name__ == "__main__":
    app = MainApp()
    app.run()