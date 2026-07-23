import re
from typing import List, Dict
import yt_dlp
from youtube_transcript_api import YouTubeTranscriptApi
from langchain_core.tools import tool

@tool
def extract_video_id(url: str) -> str:
    """
    Extracts the 11-character YouTube video ID from a URL.
    
    Args:
        url (str): A YouTube URL containing a video ID.

    Returns:
        str: Extracted video ID or error message if parsing fails.
    """
    pattern = r'(?:v=|be/|embed/)([a-zA-Z0-9_-]{11})'
    match = re.search(pattern, url)
    return match.group(1) if match else "Error: Invalid YouTube URL"

@tool
def fetch_transcript(video_id: str, language: str = "en") -> str:
    """
    Fetches the transcript of a YouTube video.
    
    Args:
        video_id (str): The YouTube video ID (e.g., "dQw4w9WgXcQ").
        language (str): Language code for the transcript (e.g., "en", "es").
    
    Returns:
        str: The transcript text or an error message.
    """
    try:
        transcript_list = YouTubeTranscriptApi().list(video_id)
        
        try:
            transcript = transcript_list.find_transcript([language, 'es', 'en'])
        except:
            transcript = transcript_list.find_generated_transcript(['en', 'es'])
            
        data = transcript.fetch()
        full_text = " ".join([snippet.text for snippet in data])
        return full_text
    except Exception as e:
        return f"Error fetching transcript: {str(e)}"

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
                'comments': info.get('comment_count')
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
                        "url": entry.get('url') if entry.get('url', '').startswith('http') else f"https://www.youtube.com/watch?v={entry.get('id')}"
                    }
                    for entry in result['entries']
                ]
            return []
    except Exception as e:
        return [{"error": f"Search failed: {str(e)}"}]
