---
name: blogwatcher
category: community
description: Monitor blogs and RSS/Atom feeds via blogwatcher-cli tool. (moved from research)
---

# BlogWatcher — Monitor Blogs and RSS/Atom Feeds

Monitor blogs and RSS/Atom feeds using the `blogwatcher-cli` tool. Stay updated on new posts from your favorite sources without manual checking.

## When to use

- You want to track new posts from a list of blogs or news sites
- You need automated monitoring of RSS/Atom feeds
- You're aggregating content from multiple sources into a daily digest
- You want to be notified when specific topics appear in tracked feeds

## Requirements

- `blogwatcher-cli` installed (or implement with Python `feedparser`)
- List of RSS/Atom feed URLs to monitor
- Storage for tracking seen entries (SQLite or flat file)

## Setup

### Using blogwatcher-cli (if available)

```bash
# Install
pip install blogwatcher-cli

# Initialize config
blogwatcher init

# Add feeds
blogwatcher add https://example.com/rss
blogwatcher add https://blog.example.org/feed.xml

# Check for new posts
blogwatcher check

# Show recent entries
blogwatcher recent --limit 10
```

### Manual RSS monitoring with Python

```python
import feedparser
import json
import os
from datetime import datetime

DB_FILE = "seen_entries.json"

def load_seen():
    if os.path.exists(DB_FILE):
        with open(DB_FILE) as f:
            return json.load(f)
    return {}

def save_seen(seen):
    with open(DB_FILE, 'w') as f:
        json.dump(seen, f, indent=2)

def check_feed(url, name):
    seen = load_seen()
    feed = feedparser.parse(url)
    new_entries = []
    
    for entry in feed.entries:
        eid = entry.get('id', entry.get('link'))
        if eid not in seen:
            new_entries.append({
                'title': entry.get('title', 'No title'),
                'link': entry.get('link', ''),
                'published': entry.get('published', ''),
                'summary': entry.get('summary', '')[:200]
            })
            seen[eid] = datetime.now().isoformat()
    
    save_seen(seen)
    return new_entries

# Usage
feeds = {
    "Blog Name": "https://example.com/rss",
    "Another Blog": "https://blog.example.org/feed.xml"
}

for name, url in feeds.items():
    new = check_feed(url, name)
    if new:
        print(f"\n## {name} ({len(new)} new)")
        for entry in new:
            print(f"- [{entry['title']}]({entry['link']})")
```

## Daily Digest Workflow

1. Run the checker script daily (via cron, scheduled task, or manual)
2. Collect all new entries across feeds
3. Generate a markdown digest:

```python
# Generate daily digest
digest = []
for name, url in feeds.items():
    new = check_feed(url, name)
    for entry in new:
        digest.append(f"- **{name}**: [{entry['title']}]({entry['link']})")

if digest:
    print("# Daily Feed Digest\n")
    print("\n".join(digest))
else:
    print("No new posts today.")
```

## Pitfalls

- RSS feeds sometimes change URLs — verify feeds periodically
- Some sites only provide partial content in RSS (just titles) — you'll need to scrape full articles separately
- Timezone handling: feed dates are often in UTC but may vary by source
- Feed parsing can fail on malformed XML — wrap in try/except
- Respect `robots.txt` and feed update frequency recommendations

## Verification

Add one known blog RSS feed, wait for it to return entries, and confirm the checker correctly identifies new vs. already-seen entries on the second run.
