# ================================================================
# 📤 YouTube Uploader with Auto Metadata
# ================================================================

import os
import json
import time
import random
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from scripts.metadata_generator import generate_metadata

SCOPES = ['https://www.googleapis.com/auth/youtube.upload',
          'https://www.googleapis.com/auth/youtube']

def get_youtube_client():
    creds = Credentials(
        token=None,
        refresh_token=os.environ['YT_REFRESH_TOKEN'],
        token_uri='https://oauth2.googleapis.com/token',
        client_id=os.environ['YT_CLIENT_ID'],
        client_secret=os.environ['YT_CLIENT_SECRET'],
        scopes=SCOPES
    )
    creds.refresh(Request())
    return build('youtube', 'v3', credentials=creds)

def upload_video(video_path, facts, video_number, max_retries=5):
    print(f'\n📤 Uploading video #{video_number}...')
    meta = generate_metadata(facts, video_number)

    print(f'  📌 Title: {meta["title"]}')
    print(f'  🏷️  Tags:  {len(meta["tags"])} hashtags')

    body = {
        'snippet': {
            'title':       meta['title'],
            'description': meta['description'],
            'tags':        meta['tags'],
            'categoryId':  meta['category'],
            'defaultLanguage': 'en',
            'defaultAudioLanguage': 'en',
        },
        'status': {
            'privacyStatus':          meta['privacy'],
            'selfDeclaredMadeForKids': False,
            'madeForKids':             False,
        }
    }

    media = MediaFileUpload(
        video_path,
        mimetype='video/mp4',
        resumable=True,
        chunksize=256 * 1024
    )

    for attempt in range(1, max_retries + 1):
        try:
            yt = get_youtube_client()
            req = yt.videos().insert(
                part='snippet,status',
                body=body,
                media_body=media
            )
            response = None
            while response is None:
                status, response = req.next_chunk()
                if status:
                    pct = int(status.progress() * 100)
                    print(f'  ⬆️  Uploading... {pct}%', end='\r')

            vid_id = response['id']
            url    = f'https://www.youtube.com/shorts/{vid_id}'
            print(f'\n  ✅ Uploaded! {url}')

            # Set thumbnail if it exists
            if os.path.exists('thumbnail.jpg'):
                try:
                    yt.thumbnails().set(
                        videoId=vid_id,
                        media_body=MediaFileUpload('thumbnail.jpg', mimetype='image/jpeg')
                    ).execute()
                    print('  🖼️  Thumbnail set!')
                except Exception as e:
                    print(f'  ⚠️  Thumbnail failed (need channel verification): {e}')

            return vid_id, url

        except Exception as e:
            wait = (2 ** attempt) + random.random()
            print(f'\n  ⚠️  Attempt {attempt} failed: {e}')
            if attempt < max_retries:
                print(f'  ⏳ Retrying in {wait:.1f}s...')
                time.sleep(wait)
            else:
                raise RuntimeError(f'Upload failed after {max_retries} attempts: {e}')
