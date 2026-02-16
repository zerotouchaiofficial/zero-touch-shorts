# ================================================================
# 📤 YouTube Uploader — Thumbnail Fixed + Retry
# ================================================================
import os, time, random, logging
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from scripts.metadata_generator import generate_metadata

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')
log = logging.getLogger(__name__)

SCOPES = [
    'https://www.googleapis.com/auth/youtube.upload',
    'https://www.googleapis.com/auth/youtube',
]

def get_youtube_client():
    creds = Credentials(
        token=None,
        refresh_token=os.environ['YT_REFRESH_TOKEN'],
        token_uri='https://oauth2.googleapis.com/token',
        client_id=os.environ['YT_CLIENT_ID'],
        client_secret=os.environ['YT_CLIENT_SECRET'],
        scopes=SCOPES,
    )
    creds.refresh(Request())
    return build('youtube', 'v3', credentials=creds,
                 cache_discovery=False)

def set_thumbnail(video_id, thumb_path, max_retries=6):
    """
    Retries with increasing waits because YouTube needs time
    to process the video before accepting a thumbnail.
    """
    if not thumb_path or not os.path.exists(thumb_path):
        log.warning(f'⚠️  Thumbnail not found: {thumb_path}')
        return False

    file_size = os.path.getsize(thumb_path)
    if file_size == 0:
        log.warning('⚠️  Thumbnail file is empty — skipping.')
        return False

    log.info(f'🖼️  Setting thumbnail ({file_size/1024:.1f} KB)...')

    for attempt in range(1, max_retries + 1):
        # Wait: 20s, 35s, 50s, 65s, 80s, 95s
        wait = 20 + (attempt - 1) * 15
        log.info(f'  Attempt {attempt}/{max_retries} '
                 f'— waiting {wait}s for video to process...')
        time.sleep(wait)
        try:
            yt = get_youtube_client()
            yt.thumbnails().set(
                videoId=video_id,
                media_body=MediaFileUpload(
                    thumb_path,
                    mimetype='image/jpeg',
                    resumable=False,
                )
            ).execute()
            log.info('  ✅ Thumbnail set successfully!')
            return True
        except Exception as e:
            err = str(e).lower()
            if 'forbidden' in err or '403' in err:
                log.error(
                    '  ❌ Custom thumbnails blocked.\n'
                    '     Fix: Verify your channel at '
                    'https://www.youtube.com/verify\n'
                    '     (Phone verification required for custom thumbnails)'
                )
                return False
            elif 'quotaexceeded' in err or '429' in err:
                log.warning('  ⏳ Quota exceeded — waiting 60s...')
                time.sleep(60)
            elif 'videonotfound' in err or 'notfound' in err:
                log.warning(f'  ⏳ Video not ready yet (attempt {attempt})...')
            else:
                log.warning(f'  ⚠️  Attempt {attempt}: {e}')

    log.warning('  ⚠️  Thumbnail failed after all retries.')
    return False

def upload_video(video_path, facts, video_number,
                 thumb_path=None, max_retries=5):
    log.info(f'\n📤 Uploading Short #{video_number}...')

    # Auto-find thumbnail if not passed explicitly
    if not thumb_path:
        candidate = os.path.join(
            os.path.dirname(os.path.abspath(video_path)),
            'thumbnail.jpg')
        if os.path.exists(candidate):
            thumb_path = candidate
            log.info(f'  🖼️  Thumbnail found: {thumb_path}')
        else:
            log.warning('  ⚠️  No thumbnail found.')

    meta = generate_metadata(facts, video_number)
    log.info(f'  📌 Title: {meta["title"]}')
    log.info(f'  🏷️  Tags : {len(meta["tags"])} hashtags')

    body = {
        'snippet': {
            'title':                meta['title'],
            'description':          meta['description'],
            'tags':                 meta['tags'],
            'categoryId':           meta['category'],
            'defaultLanguage':      'en',
            'defaultAudioLanguage': 'en',
        },
        'status': {
            'privacyStatus':           meta['privacy'],
            'selfDeclaredMadeForKids': False,
            'madeForKids':             False,
        },
    }

    media = MediaFileUpload(
        video_path,
        mimetype='video/mp4',
        resumable=True,
        chunksize=512 * 1024,
    )

    for attempt in range(1, max_retries + 1):
        try:
            yt       = get_youtube_client()
            req      = yt.videos().insert(
                part='snippet,status',
                body=body,
                media_body=media,
            )
            response = None
            while response is None:
                status, response = req.next_chunk()
                if status:
                    pct = int(status.progress() * 100)
                    print(f'  ⬆️  Uploading... {pct}%', end='\r')

            vid_id = response['id']
            url    = f'https://www.youtube.com/shorts/{vid_id}'
            log.info(f'\n  ✅ Uploaded! {url}')

            # Set thumbnail with retry
            if thumb_path:
                set_thumbnail(vid_id, thumb_path)

            return vid_id, url

        except Exception as e:
            wait = (2 ** attempt) + random.random()
            log.warning(f'\n  ⚠️  Upload attempt {attempt} failed: {e}')
            if attempt < max_retries:
                log.info(f'  ⏳ Retrying in {wait:.1f}s...')
                time.sleep(wait)
            else:
                raise RuntimeError(
                    f'Upload failed after {max_retries} attempts: {e}')
