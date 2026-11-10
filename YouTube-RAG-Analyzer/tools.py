import re
from typing import List, Dict, Optional

import yt_dlp
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    TranscriptsDisabled,
    NoTranscriptFound,
    VideoUnavailable,
)
from langchain_core.tools import tool

# Matches watch?v=, youtu.be/, /embed/, /shorts/, and /live/ URLs.
# (The original pattern only matched v=, be/, and embed/ — Shorts and Live
# URLs silently failed to extract a video ID.)
_VIDEO_ID_PATTERN = re.compile(r'(?:v=|/(?:be|embed|shorts|live)/)([a-zA-Z0-9_-]{11})')


def looks_like_youtube_url(text: str) -> bool:
    """
    Quick heuristic to tell a pasted URL apart from a search query, so main.py
    can route plain search terms (e.g. "curso de docker en español") through
    search_youtube instead of failing on extract_video_id.
    """
    t = text.strip().lower()
    return t.startswith("http://") or t.startswith("https://") or "youtube.com" in t or "youtu.be" in t


@tool
def extract_video_id(url: str) -> str:
    """
    Extracts the 11-character YouTube video ID from a URL.
    Supports watch, youtu.be, embed, shorts, and live URLs.

    Args:
        url (str): A YouTube URL containing a video ID.

    Returns:
        str: Extracted video ID or an "Error: ..." message if parsing fails.
    """
    match = _VIDEO_ID_PATTERN.search(url)
    return match.group(1) if match else "Error: Invalid YouTube URL"


@tool
def fetch_transcript(video_id: str, language: str = "en") -> str:
    """
    Fetches the transcript of a YouTube video, preferring a transcript in the
    requested language and falling back to Spanish or English (manual first,
    then auto-generated).

    Args:
        video_id (str): The YouTube video ID (e.g., "dQw4w9WgXcQ").
        language (str): Preferred language code for the transcript (e.g., "en", "es").

    Returns:
        str: The transcript text, or a message starting with "Error" on failure.
    """
    try:
        transcript_list = YouTubeTranscriptApi().list(video_id)
    except TranscriptsDisabled:
        return "Error fetching transcript: transcripts are disabled for this video."
    except VideoUnavailable:
        return "Error fetching transcript: video is unavailable (private, deleted, or region-locked)."
    except Exception as e:
        # Network/API errors we don't specifically handle above — surfaced
        # instead of silently swallowed, so failures are easier to debug.
        return f"Error fetching transcript: {str(e)}"

    try:
        transcript = transcript_list.find_transcript([language, "es", "en"])
    except NoTranscriptFound:
        try:
            transcript = transcript_list.find_generated_transcript(["en", "es"])
        except NoTranscriptFound:
            return "Error fetching transcript: no transcript available in the requested languages."
    except Exception as e:
        return f"Error fetching transcript: {str(e)}"

    try:
        data = transcript.fetch()
        return " ".join(snippet.text for snippet in data)
    except Exception as e:
        return f"Error fetching transcript: failed to download transcript data ({str(e)})."


@tool
def get_full_metadata(url: str) -> dict:
    """Extract metadata given a YouTube URL, including title, views, duration, channel, likes, comments."""
    try:
        with yt_dlp.YoutubeDL({'quiet': True, 'no_warnings': True}) as ydl:
            info = ydl.extract_info(url, download=False)
            return {
                'title': info.get('title'),
                'views': info.get('view_count'),
                'duration': info.get('duration'),
                'channel': info.get('uploader'),
                'likes': info.get('like_count'),
                'comments': info.get('comment_count'),
                'description': info.get('description'),
            }
    except Exception as e:
        return {"error": str(e)}


@tool
def search_youtube(query: str) -> List[Dict]:
    """
    Search YouTube for videos matching the query.

    Args:
        query (str): The search term to look for on YouTube

    Returns:
        List of dictionaries containing video titles and URLs.
    """
    try:
        with yt_dlp.YoutubeDL({'quiet': True, 'no_warnings': True, 'extract_flat': True}) as ydl:
            result = ydl.extract_info(f"ytsearch5:{query}", download=False)
            if 'entries' in result:
                return [
                    {
                        "title": entry.get('title'),
                        "url": entry.get('url') if entry.get('url', '').startswith('http')
                        else f"https://www.youtube.com/watch?v={entry.get('id')}",
                    }
                    for entry in result['entries']
                ]
            return []
    except Exception as e:
        return [{"error": f"Search failed: {str(e)}"}]
