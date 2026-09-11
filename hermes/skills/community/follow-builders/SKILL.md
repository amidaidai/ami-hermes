---
name: follow-builders
category: community
description: AI builders digest — monitors top AI builders on X and YouTube.
---

# Follow Builders — AI Builders Digest

Monitor top AI builders and researchers on X (Twitter) and YouTube. Aggregate their latest posts, papers, and projects into a daily or weekly digest.

## When to use

- You want to stay current on AI research and industry developments
- You need to track specific researchers, engineers, or thought leaders
- You're curating a daily briefing on AI/ML news
- You want to discover new projects, papers, and tools from the community

## Builders to Follow

### X (Twitter)
- @karpathy — Andrej Karpathy (AI education, LLMs)
- @ylecun — Yann LeCun (deep learning, AGI)
- @AndrewYNg — Andrew Ng (ML education, AI applications)
- @drfeifei — Fei-Fei Li (computer vision, AI ethics)
- @jimfan_ — Jim Fan (embodied AI, foundation models)
- @sama — Sam Altman (OpenAI, AI policy)
- @ylecun — Yann LeCun
- @miramurati — Mira Murati

### YouTube
- Andrej Karpathy — Neural Networks from Scratch, LLM tutorials
- Yannic Kilcher — Paper reviews, AI news analysis
- Two Minute Papers — Concise paper summaries
- AI Explained — LLM deep-dives
- Stanford MLSys — Academic talks and seminars

## Digest Generation Workflow

### Step 1: Collect X posts

Use the X API or a scraping tool to get recent posts:

```python
# Pseudocode for X timeline
def get_recent_posts(username, count=10):
    # Using X API v2
    url = f"https://api.twitter.com/2/users/by/username/{username}/tweets"
    params = {"max_results": count, "expansions": "referenced_tweets.id"}
    headers = {"Authorization": f"Bearer {BEARER_TOKEN}"}
    resp = requests.get(url, headers=headers, params=params)
    return resp.json()
```

### Step 2: Collect YouTube videos

```python
# Using YouTube Data API
def get_recent_videos(channel_id, max_results=5):
    url = "https://www.googleapis.com/youtube/v3/search"
    params = {
        "channelId": channel_id,
        "order": "date",
        "part": "snippet",
        "maxResults": max_results,
        "type": "video"
    }
    headers = {"Authorization": f"Bearer {YOUTUBE_API_KEY}"}
    resp = requests.get(url, params=params)
    return resp.json()
```

### Step 3: Generate digest

Feed the collected content to an LLM:

```
Generate a concise AI builders digest from these posts.
Group by theme, highlight important papers/projects, and flag controversial or noteworthy opinions.

[collected content]
```

## Digest Template

```markdown
# AI Builders Digest — {{date}}

## 🔬 Research & Papers
- [Paper summary]
- [Code release]

## 🛠️ Projects & Tools
- [New tool or library]

## 💬 Notable Opinions
- [Controversial take or insightful thread]

## 📺 Videos
- [New tutorial or talk]

## 📅 Upcoming Events
- [Conference, deadline, or release]
```

## Pitfalls

- X API v2 has strict rate limits (1500 posts/month on Basic tier)
- YouTube API costs quota per request — cache results aggressively
- Some builders post infrequently; a weekly digest is usually sufficient
- Verify information before amplifying — AI builders sometimes post speculative content
- Respect content licensing — don't republish full posts verbatim without attribution

## Verification

Generate one digest, share it with someone familiar with the AI space, and ask if they found it useful and complete.
