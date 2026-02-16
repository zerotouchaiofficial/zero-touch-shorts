# ================================================================
# 🏷️ Auto-generates click-worthy titles, descriptions, hashtags
# ================================================================

import random
import re

# ── Title templates (mix for variety) ────────────────────────────
TITLE_TEMPLATES = [
    "🤯 {keyword} Facts That Will BLOW Your Mind!",
    "Did You Know? 🧠 {keyword} Facts #shorts",
    "SHOCKING Facts Nobody Tells You! 🔥 #{n}",
    "You Won't Believe These {keyword} Facts! 😱",
    "🧠 Mind-Blowing Facts Vol.{n} | #shorts",
    "Facts That Sound Fake But Are 100% TRUE! 🤯",
    "Things You Never Knew About {keyword}! 🔥",
    "WOW! These Facts Are UNREAL 😲 #shorts",
    "🔥 Crazy Facts That Will Change How You Think!",
    "Random Facts That Are Actually Incredible 🧠",
    "Stop Scrolling — These Facts Are WILD 🤯",
    "FACTS: Vol.{n} — Guaranteed to Surprise You! ✨",
    "Did You Know THIS? 😱 {keyword} Edition",
    "🌍 Amazing Facts You Didn't Learn in School!",
    "These Facts Hit Different 🤯 #didyouknow",
]

# ── Keyword extraction from facts ────────────────────────────────
STOP_WORDS = {'the','a','an','is','are','was','were','be','been',
              'have','has','had','do','does','did','will','would',
              'could','should','may','might','shall','can','to',
              'of','in','on','at','by','for','with','about','as',
              'into','through','during','before','after','above',
              'below','from','up','down','and','but','or','nor',
              'so','yet','both','either','not','only','own','same',
              'than','too','very','just','that','this','these',
              'those','it','its','they','them','their','there',
              'when','where','which','who','how','what','if','then'}

def extract_keyword(facts):
    word_freq = {}
    for fact in facts:
        for word in re.findall(r'\b[a-zA-Z]{5,}\b', fact.lower()):
            if word not in STOP_WORDS:
                word_freq[word] = word_freq.get(word, 0) + 1
    if not word_freq:
        return 'Amazing'
    top = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
    return top[0][0].capitalize() if top else 'Amazing'

def generate_title(facts, video_number):
    keyword = extract_keyword(facts)
    template = TITLE_TEMPLATES[video_number % len(TITLE_TEMPLATES)]
    title = template.format(keyword=keyword, n=video_number)
    return title[:98]   # YouTube max 100 chars

# ── Description generator ────────────────────────────────────────
def generate_description(facts, video_number):
    lines = []
    lines.append("🧠 Welcome to Did You Know? — your daily dose of mind-blowing facts!")
    lines.append("")
    lines.append(f"📋 In this Short (Video #{video_number}):")
    for i, f in enumerate(facts[:5], 1):
        lines.append(f"  #{i} — {f[:80]}{'...' if len(f)>80 else ''}")
    if len(facts) > 5:
        lines.append(f"  ... and {len(facts)-5} more incredible facts!")
    lines.append("")
    lines.append("─"*40)
    lines.append("📌 SUBSCRIBE for daily facts that will blow your mind!")
    lines.append("🔔 Hit the bell so you never miss a new Short!")
    lines.append("❤️ Like if you learned something new today!")
    lines.append("💬 Comment your favourite fact below!")
    lines.append("📤 Share with someone who loves facts!")
    lines.append("─"*40)
    lines.append("")
    lines.append("📚 FACT SOURCES: Curated from public knowledge databases")
    lines.append("🎵 Background music: Original composition")
    lines.append("")
    lines.append("─"*40)
    lines.append("🏷️ TAGS & HASHTAGS")
    lines.append("")
    lines.append(generate_hashtags(facts, inline=True))
    return "\n".join(lines)[:4900]  # YouTube max 5000 chars

# ── Hashtag generator ────────────────────────────────────────────
CORE_HASHTAGS = [
    '#shorts', '#didyouknow', '#facts', '#mindblowindfacts',
    '#funfacts', '#amazingfacts', '#learnsomething', '#knowledge',
    '#factsyoudidntknow', '#factsoflife', '#education',
    '#shortsvideo', '#youtubeshorts', '#viral', '#trending',
    '#science', '#history', '#psychology', '#interestingfacts',
    '#randomfacts', '#dailyfacts', '#factcheck', '#wow',
    '#mindblown', '#unbelievable', '#incredible'
]

def generate_hashtags(facts, inline=False):
    keyword = extract_keyword(facts)
    dynamic = [f'#{keyword.lower()}facts', f'#{keyword.lower()}']
    all_tags = list(dict.fromkeys(dynamic + CORE_HASHTAGS))[:30]
    if inline:
        return ' '.join(all_tags)
    return all_tags

def generate_metadata(facts, video_number):
    return {
        'title':       generate_title(facts, video_number),
        'description': generate_description(facts, video_number),
        'tags':        generate_hashtags(facts),
        'category':    '27',      # Education
        'privacy':     'public',
    }
