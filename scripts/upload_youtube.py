# ================================================================
# 📤 YouTube Uploader — Thumbnail + Auto Pin + Auto Playlist
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
    'https://www.googleapis.com/auth/youtube.force-ssl',
]

PLAYLIST_NAME = 'Did You Know? — Daily Facts 🧠'
PLAYLIST_DESC = (
    'Daily mind-blowing facts! New Shorts uploaded every day. '
    'Subscribe and hit the bell so you never miss a fact!'
)

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

# ── Thumbnail with retry ──────────────────────────────────────────
def set_thumbnail(video_id, thumb_path, max_retries=6):
    if not thumb_path or not os.path.exists(thumb_path):
        log.warning(f'⚠️  Thumbnail not found: {thumb_path}')
        return False
    if os.path.getsize(thumb_path) == 0:
        log.warning('⚠️  Thumbnail file is empty')
        return False

    log.info(f'🖼️  Setting thumbnail '
             f'({os.path.getsize(thumb_path)//1024}KB)...')

    for attempt in range(1, max_retries + 1):
        wait = 20 + (attempt - 1) * 15
        log.info(f'  Attempt {attempt}/{max_retries} — '
                 f'waiting {wait}s for YouTube to process video...')
        time.sleep(wait)
        try:
            get_youtube_client().thumbnails().set(
                videoId=video_id,
                media_body=MediaFileUpload(
                    thumb_path,
                    mimetype='image/jpeg',
                    resumable=False,
                )
            ).execute()
            log.info('  ✅ Thumbnail set!')
            return True
        except Exception as e:
            err = str(e).lower()
            if 'forbidden' in err or '403' in err:
                log.error(
                    '  ❌ Custom thumbnails blocked.\n'
                    '     → Verify your channel at '
                    'https://www.youtube.com/verify\n'
                    '     → Phone verification required.\n'
                    '     → Skipping thumbnail.'
                )
                return False
            elif 'quotaexceeded' in err or '429' in err:
                log.warning('  ⏳ Quota exceeded — waiting 60s...')
                time.sleep(60)
            else:
                log.warning(f'  ⚠️  Attempt {attempt}: {e}')

    log.warning('  ⚠️  Thumbnail failed after all retries.')
    return False

# ── Auto pin comment ──────────────────────────────────────────────
def pin_comment(video_id, comment_text, max_retries=3):
    """
    Posts a comment on the video then pins it.
    Pinned comments boost engagement signals to the algorithm.
    """
    log.info('📌 Posting pinned comment...')
    for attempt in range(1, max_retries + 1):
        try:
            yt = get_youtube_client()

            # Post the comment
            comment_resp = yt.commentThreads().insert(
                part='snippet',
                body={
                    'snippet': {
                        'videoId': video_id,
                        'topLevelComment': {
                            'snippet': {
                                'textOriginal': comment_text,
                            }
                        }
                    }
                }
            ).execute()

            comment_id = comment_resp['id']
            log.info(f'  💬 Comment posted: {comment_text[:60]}')

            # Pin it
            yt.comments().setModerationStatus(
                id=comment_id,
                moderationStatus='published',
            ).execute()

            # Mark as pinned via update
            yt.comments().update(
                part='snippet',
                body={
                    'id': comment_id,
                    'snippet': {
                        'textOriginal': comment_text,
                        'isPinned': True,
                    }
                }
            ).execute()

            log.info('  ✅ Comment pinned!')
            return comment_id

        except Exception as e:
            log.warning(f'  ⚠️  Comment attempt {attempt}: {e}')
            if attempt < max_retries:
                time.sleep(5 * attempt)

    log.warning('  ⚠️  Could not pin comment (non-critical).')
    return None

# ── Auto playlist ─────────────────────────────────────────────────
def get_or_create_playlist(yt):
    """
    Finds existing playlist by name or creates it.
    Stores playlist ID in playlist_id.txt to avoid API calls.
    """
    # Cache playlist ID locally so we don't search every time
    cache_file = 'playlist_id.txt'
    if os.path.exists(cache_file):
        pid = open(cache_file).read().strip()
        if pid:
            log.info(f'  📋 Using cached playlist: {pid}')
            return pid

    log.info('  🔍 Searching for existing playlist...')
    try:
        resp = yt.playlists().list(
            part='snippet',
            mine=True,
            maxResults=50,
        ).execute()

        for item in resp.get('items', []):
            if item['snippet']['title'] == PLAYLIST_NAME:
                pid = item['id']
                open(cache_file, 'w').write(pid)
                log.info(f'  ✅ Found playlist: {pid}')
                return pid
    except Exception as e:
        log.warning(f'  ⚠️  Playlist search failed: {e}')

    # Create new playlist
    log.info('  ✨ Creating new playlist...')
    try:
        resp = yt.playlists().insert(
            part='snippet,status',
            body={
                'snippet': {
                    'title':       PLAYLIST_NAME,
                    'description': PLAYLIST_DESC,
                    'defaultLanguage': 'en',
                },
                'status': {'privacyStatus': 'public'},
            }
        ).execute()
        pid = resp['id']
        open(cache_file, 'w').write(pid)
        log.info(f'  ✅ Playlist created: {pid}')
        return pid
    except Exception as e:
        log.warning(f'  ⚠️  Playlist creation failed: {e}')
        return None

def add_to_playlist(video_id, max_retries=3):
    """Adds video to the channel playlist."""
    log.info('📋 Adding to playlist...')
    for attempt in range(1, max_retries + 1):
        try:
            yt  = get_youtube_client()
            pid = get_or_create_playlist(yt)
            if not pid:
                log.warning('  ⚠️  No playlist ID — skipping.')
                return False
            yt.playlistItems().insert(
                part='snippet',
                body={
                    'snippet': {
                        'playlistId': pid,
                        'resourceId': {
                            'kind':    'youtube#video',
                            'videoId': video_id,
                        }
                    }
                }
            ).execute()
            log.info(f'  ✅ Added to playlist!')
            return True
        except Exception as e:
            log.warning(f'  ⚠️  Playlist attempt {attempt}: {e}')
            if attempt < max_retries:
                time.sleep(5 * attempt)

    log.warning('  ⚠️  Could not add to playlist (non-critical).')
    return False

# ── Main upload ───────────────────────────────────────────────────
def upload_video(video_path, facts, video_number,
                 thumb_path=None, max_retries=5):
    log.info(f'\n📤 Uploading Short #{video_number}...')

    # Auto-find thumbnail
    if not thumb_path:
        candidate = os.path.join(
            os.path.dirname(os.path.abspath(video_path)),
            'thumbnail.jpg')
        if os.path.exists(candidate):
            thumb_path = candidate
            log.info(f'  🖼️  Thumbnail auto-found: {thumb_path}')
        else:
            log.warning('  ⚠️  No thumbnail found.')

    meta = generate_metadata(facts, video_number)
    log.info(f'  📌 Title       : {meta["title"]}')
    log.info(f'  🏷️  Tags        : {len(meta["tags"])} hashtags')
    log.info(f'  📌 Pin comment : {meta["pin_comment"][:60]}')

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

            # ── Post-upload growth actions ───────────────────────
            # 1. Set thumbnail (with retry — needs processing time)
            if thumb_path:
                set_thumbnail(vid_id, thumb_path)

            # 2. Pin engagement comment
            pin_comment(vid_id, meta['pin_comment'])

            # 3. Add to playlist
            add_to_playlist(vid_id)

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
