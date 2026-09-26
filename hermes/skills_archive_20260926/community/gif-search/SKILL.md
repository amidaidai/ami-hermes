---
name: gif-search
category: community
description: Search/download GIFs from Tenor via curl + jq. (moved from media to community)
tags:
  - gif
  - tenor
  - search
  - download
  - curl
---

# GIF Search

Search and download GIFs from the Tenor API using `curl` and `jq`.

## Overview

Search the Tenor GIF database and download matching GIFs directly. Useful for adding animated reactions, illustrations, or visual references to content.

## Setup

### Get a Tenor API Key
1. Visit [Tenor API](https://tenor.com/gifapi) or Google Cloud Console
2. Register for a free API key
3. Set as environment variable: `export TENOR_API_KEY="your_key_here"`

## Basic Search

```bash
# Search for GIFs matching a query
curl -s "https://tenor.googleapis.com/v2/search?q=cat+wave&key=$TENOR_API_KEY&limit=5" | jq '.results[] | {id, description: .content_description, url: .media_formats.gif.url}'

# Get results with more detail
curl -s "https://tenor.googleapis.com/v2/search?q=excited&key=$TENOR_API_KEY&limit=3" | jq '.results[] | {id, desc: .content_description, gif: .media_formats.gif.url, preview: .media_formats.tinygif.url}'
```

## Download a GIF

```bash
# Get the URL from search results, then download
curl -s "https://tenor.googleapis.com/v2/search?q=happy+dance&key=$TENOR_API_KEY&limit=1" \
  | jq -r '.results[0].media_formats.gif.url' \
  | xargs curl -o happy_dance.gif -L
```

## Advanced Search Parameters

| Parameter | Description | Example |
|-----------|-------------|---------|
| `q` | Search query | `q=funny+cat` |
| `limit` | Results per request (1-50) | `limit=10` |
| `pos` | Pagination cursor | `pos=...` |
| `media_filter` | Filter format types | `media_filter=gif,mp4` |
| `ar_range` | Aspect ratio filter | `ar_range=wide` |
| `random` | Randomize results | `random=true` |

## API Endpoints

| Endpoint | Purpose |
|----------|---------|
| `/v2/search` | Main search |
| `/v2/featured` | Trending/featured GIFs |
| `/v2/search_suggestions` | Auto-complete suggestions |
| `/v2/categories` | Browse categories |
| `/v2/trending` | Trending search terms |
| `/v2/gifs` | Get GIFs by ID |

## Trending GIFs

```bash
# Get trending GIFs
curl -s "https://tenor.googleapis.com/v2/featured?key=$TENOR_API_KEY&limit=5" \
  | jq '.results[].content_description'
```

## Pipeline Examples

### Search + Download All Results
```bash
search_term="celebration"
mkdir -p gifs
curl -s "https://tenor.googleapis.com/v2/search?q=$search_term&key=$TENOR_API_KEY&limit=5" \
  | jq -r '.results[] | .media_formats.gif.url' \
  | while read url; do
      filename="gifs/$(echo "$url" | grep -oP '[\w-]+(?=\.gif)' | head -1).gif"
      curl -s -L "$url" -o "$filename"
      echo "Downloaded: $filename"
    done
```

### Search + Show Preview (tinygif)
```bash
curl -s "https://tenor.googleapis.com/v2/search?q=thank+you&key=$TENOR_API_KEY&limit=3" \
  | jq -r '.results[].media_formats.tinygif.url'
```

## Pitfalls

- API key is required — free tier has rate limits (~100 requests/day initially)
- Some GIFs have expired/deleted URLs — handle 404s gracefully
- Respect content filters (`contentfilter=high/medium/low`)
- Tenor API v2 requires Google Cloud billing to increase quotas
- Always respect Tenor's attribution requirements for public usage
