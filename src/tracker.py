import asyncio
import io # REQUIRED for thumbnail processing
import os
from winsdk.windows.storage.streams import Buffer, DataReader
from winsdk.windows.media.control import (
    GlobalSystemMediaTransportControlsSessionManager,
    GlobalSystemMediaTransportControlsSessionPlaybackStatus
)

class MediaTracker:
    def __init__(self, callback_func=None):
        self.current_track = None
        self.current_artist = None
        self.current_album = None
        self.is_playing = False
        self.last_position = -1
        self.still_count = 0
        self.callback = callback_func
        self.cached_thumbnail = None
        self.manager = None # Cache the manager

    async def get_media_info(self):
        if not self.manager:
            self.manager = await GlobalSystemMediaTransportControlsSessionManager.request_async()
        
        sessions = self.manager.get_sessions()
        current_session = None

        for session in sessions:
            try:
                app_id = session.source_app_user_model_id.lower()
                if any(keyword in app_id for keyword in ["apple", "music", "itunes"]):
                    current_session = session
                    break
            except:
                continue
        
        if not current_session:
            if self.is_playing:
                self.is_playing = False
                if self.callback: self.callback(None, None, None, False, 0, 0, None)
            return

        # EXTRACT REAL POSITION DATA
        timeline = current_session.get_timeline_properties()
        duration = timeline.end_time.total_seconds()
        current_pos = timeline.position.total_seconds()

        # Motion detection
        if current_pos != self.last_position:
            is_playing_now = True
            self.still_count = 0 
        else:
            self.still_count += 1
            is_playing_now = False if self.still_count > 2 else self.is_playing

        media_properties = await current_session.try_get_media_properties_async()
        if media_properties and media_properties.title:
            title = media_properties.title
            raw_artist = media_properties.artist if media_properties.artist else "Unknown Artist"
            raw_album = media_properties.album_title

            # Only fetch thumbnail and process metadata if the track title changed
            if title != self.current_track:
                # 1. Handle Thumbnail Memory Safely
                if media_properties.thumbnail:
                    try:
                        thumb_stream = await media_properties.thumbnail.open_read_async()
                        size = thumb_stream.size
                        buffer = Buffer(size)
                        await thumb_stream.read_async(buffer, size, 0)
                        
                        with DataReader.from_buffer(buffer) as reader:
                            byte_array = bytearray(size)
                            reader.read_bytes(byte_array)
                            self.cached_thumbnail = io.BytesIO(byte_array)
                        
                        thumb_stream.close() # Prevents memory leak
                    except:
                        self.cached_thumbnail = None
                else:
                    self.cached_thumbnail = None

                # 2. Split Artist and Album (Fixes the "same line" issue)
                display_artist = raw_artist
                display_album = raw_album

                if " — " in raw_artist:
                    parts = raw_artist.split(" — ", 1)
                    display_artist = parts[0].strip()
                    if not display_album: display_album = parts[1].strip()
                elif " - " in raw_artist:
                    parts = raw_artist.split(" - ", 1)
                    display_artist = parts[0].strip()
                    if not display_album: display_album = parts[1].strip()

                self.current_track = title
                self.current_artist = display_artist
                self.current_album = display_album

            # Send update to main.py
            if self.callback:
                if self.cached_thumbnail: self.cached_thumbnail.seek(0)
                self.callback(self.current_artist, self.current_track, self.current_album, is_playing_now, duration, current_pos, self.cached_thumbnail)
        
        self.last_position = current_pos
        self.is_playing = is_playing_now

    async def run_loop(self):
        while True:
            try:
                await self.get_media_info()
                sleep_time = 1.0 if self.is_playing else 3.0
                await asyncio.sleep(sleep_time)
                
            except Exception as e:
                # Log error and wait before retrying
                await asyncio.sleep(5)