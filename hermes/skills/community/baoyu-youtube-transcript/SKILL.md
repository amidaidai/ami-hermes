---
name: baoyu-youtube-transcript
category: community
description: Download YouTube transcripts and cover images by URL.
tags:
  - youtube
  - transcript
  - subtitles
  - cover-image
  - media
---

# Baoyu YouTube Transcript

Download YouTube video transcripts (subtitles/captions) and cover images by providing a YouTube URL.

## Overview

Extract text transcripts from YouTube videos and download cover thumbnails. Supports multiple languages, timestamped output, and various formats.

## Supported Operations

### Transcript Download
- Auto-generated captions (when available)
- Manual/uploaded subtitles (when available)
- Multi-language support
- Timestamped or plain text output
- SRT, VTT, TXT, JSON formats

### Cover Image Download
- Video thumbnail (maxresdefault, hqdefault, mqdefault)
- Channel avatar
- Custom timestamp frame (coming soon)

## Usage

### Input
Provide a YouTube URL:
```
https://www.youtube.com/watch?v=VIDEO_ID
https://youtu.be/VIDEO_ID
https://www.youtube.com/embed/VIDEO_ID
```

### Output Formats

**Plain Text (TXT):**
```
[00:00:00] Speaker: First line of transcript
[00:00:05] Speaker: Second line
```

**SRT (SubRip):**
```
1
00:00:00,000 --> 00:00:05,000
First line of transcript

2
00:00:05,000 --> 00:00:10,000
Second line
```

**VTT (WebVTT):**
```
WEBVTT

00:00:00.000 --> 00:00:05.000
First line

00:00:05.000 --> 00:00:10.000
Second line
```

## Language Support

- Auto-detect available languages
- Specify language: `en`, `zh-Hans`, `ja`, `ko`, etc.
- Fallback to English if requested language unavailable
- Translation mode (when available)

## Cover Image Quality

| Suffix | Resolution | Reliability |
|--------|-----------|-------------|
| `maxresdefault.jpg` | 1280×720 | Often available |
| `hqdefault.jpg` | 480×360 | Always available |
| `mqdefault.jpg` | 320×180 | Always available |
| `default.jpg` | 120×90 | Always available |

## Dependencies

Requires one of:
- `youtube-transcript-api` (Python)
- `yt-dlp` (CLI, for transcripts + thumbnails)

## Pitfalls

- Some videos have transcripts disabled by the uploader
- Auto-generated captions may have accuracy issues (especially non-English)
- Age-restricted videos require authentication
- Very long videos (>2hr) may have truncated transcripts
- Rate limiting on transcript API — cache results when possible
