# Apple Music Scrobbler

A Python application for Windows that tracks your Apple Music or iTunes playback and scrobbles your listening activity to Last.fm. This tool uses the Windows Global System Media Transport Controls API to detect what you're playing in Apple Music/iTunes, and submits qualified tracks to your Last.fm account.

## Features
- Authenticates with Last.fm (via pylast)
- Detects and tracks songs played in Apple Music or iTunes on Windows
- Scrobbles tracks to Last.fm when they meet standard criteria (50% played or 4 minutes)
- Modern, responsive UI with real-time updates
- System tray integration and Windows startup registration
- Keeps a local count of total scrobbles

## Requirements
- Windows 10 or later
- Python 3.7+
- See `requirements.txt` for dependencies


## Installation
### Option 1: Download a Release
Pre-built releases (Windows executables) are available. Download the latest release from the Releases section and run the installer or executable—no Python setup required.


### Option 2: Run from Source
1. Clone this repository or download the source code.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Create a `.env` file in the project root with your own Last.fm API credentials:
   ```env
   LASTFM_API_KEY=your_api_key_here
   LASTFM_API_SECRET=your_api_secret_here
   ```
   You must register your own Last.fm API application to obtain these keys. They are not provided in this repository.

## Usage
1. Run the main application:
   ```bash
   python src/main.py
   ```
2. On first launch, connect your Last.fm account by following the authentication prompt in your browser, then confirm in the app.
3. Play music in Apple Music or iTunes. The app will automatically detect playback and scrobble tracks to Last.fm.

## File Structure
- `src/auth.py` – Handles Last.fm authentication and session management
- `src/tracker.py` – Detects and tracks currently playing media from Apple Music/iTunes
- `src/ui.py` – User interface and system tray logic
- `src/main.py` – Application entry point and main logic
- `src/file_version_info.txt` – Version information

## Contributing
Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.

## License
This project is licensed under the MIT License.
