import pylast
import webbrowser
import os
import json

APPDATA_PATH = os.path.join(os.getenv('APPDATA'), 'Xignotic', 'AppleMusicScrobbler')
CONFIG_FILE = os.path.join(APPDATA_PATH, "session_config.json")

class LastFMAuthenticator:
    def __init__(self, api_key, api_secret):

        if not os.path.exists(APPDATA_PATH):
            os.makedirs(APPDATA_PATH)

        self.api_key = api_key
        self.api_secret = api_secret
        self.network = pylast.LastFMNetwork(api_key=self.api_key, api_secret=self.api_secret)
        self.session_key = None
        self.total_scrobbles = 0

    def get_cached_session(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    data = json.load(f)
                    self.session_key = data.get('session_key')
                    self.total_scrobbles = data.get('total_scrobbles', 0)
                    if self.session_key:
                        self.network.session_key = self.session_key
                        return True
            except Exception: return False
        return False

    def start_auth_process(self):
        sg = pylast.SessionKeyGenerator(self.network)
        auth_url = sg.get_web_auth_url()
        print(f"Auth URL: {auth_url}")
        webbrowser.open(auth_url)
        return sg, auth_url

    def complete_auth_process(self, session_generator, auth_url):
        try:
            self.session_key = session_generator.get_web_auth_session_key(auth_url)
            self.network.session_key = self.session_key
            self.save_session()
            return True
        except Exception as e:
            print(f"Auth failed: {e}")
            return False

    def increment_scrobble_count(self):
        """Called by main.py whenever a scrobble succeeds."""
        self.total_scrobbles += 1
        self.save_session()
        return self.total_scrobbles

    def save_session(self):
        with open(CONFIG_FILE, 'w') as f:
            json.dump({
                'session_key': self.session_key,
                'total_scrobbles': self.total_scrobbles
            }, f)

    def get_network(self):
        return self.network