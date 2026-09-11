---
name: youtube-content
category: community
description: YouTube transcripts to summaries, threads, blogs. (moved from media)
---

# YouTube Content — Transcripts to Summaries, Threads, Blogs

Extract YouTube video transcripts and repurpose them into structured content: concise summaries, social media threads, full blog posts.

## When to use

- You need to summarize a long YouTube video or lecture
- You want to extract key takeaways, quotes, or action items from a video
- You're repurposing video content into written formats (Twitter/X threads, blog drafts, LinkedIn posts)
- You need to search or reference spoken content from a video

## Requirements

- Python with `youtube-transcript-api` and `yt-dlp`
- Or the `yt` CLI tool if available
- For longer videos, consider rate limiting (YouTube may throttle)

## Usage

### Step 1: Get transcript

```python
from youtube_transcript_api import YouTubeTranscriptApi

video_id = "dQw4w9WgXcQ"  # replace with actual video ID
transcript = YouTubeTranscriptApi.get_transcript(video_id)
full_text = " ".join([entry['text'] for entry in transcript])
print(f"Transcribed {len(transcript)} segments, {len(full_text)} chars")
```

### Step 2: Save to file

```bash
python -c "
from youtube_transcript_api import YouTubeTranscriptApi
import sys
video_id = sys.argv[1]
t = YouTubeTranscriptApi.get_transcript(video_id)
text = ' '.join([e['text'] for e in t])
with open(f'{video_id}_transcript.txt', 'w') as f:
    f.write(text)
print(f'Saved {len(text)} chars to {video_id}_transcript.txt')
" dQw4w9WgXcQ
```

### Step 3: Generate summary

Feed the transcript to the LLM with a prompt like:

```
Summarize this YouTube video transcript in 3-5 bullet points.
Extract key quotes and actionable takeaways.

Transcript:
[transcript text]
```

### Step 4: Generate thread/blog

For a Twitter/X thread:

```
Convert this transcript into an engaging Twitter thread (10 tweets max).
Each tweet should be self-contained.
Start with a hook. End with a call to action.

Transcript:
[transcript text]
```

## Pitfalls

- Some videos have transcripts disabled — `youtube-transcript-api` will raise `TranscriptsDisabled`
- Auto-generated captions may contain transcription errors, especially for technical terms
- Very long transcripts may exceed context limits — chunk by timestamp segments
- YouTube may rate-limit frequent transcript requests — add delays for batch processing
- Video IDs can be extracted from URLs: `https://www.youtube.com/watch?v=VIDEO_ID`

## Verification

After generating a transcript, check that the first and last sentences match the video's actual start and end to confirm the full video was captured.
