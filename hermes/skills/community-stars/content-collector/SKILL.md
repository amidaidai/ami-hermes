---
name: content-collector
description: Collect social media content into structured storage — Feishu bitable, databases, or spreadsheets. Use when user asks to collect, scrape, or save social media content, mentions, or discussions into a structured format for analysis.
---

# Content Collector

Collect social media content from multiple platforms into structured storage (Feishu bitable, database, or spreadsheet).

## Collection Process

### 1. Define Collection Criteria
- **Sources**: Which platforms (Reddit, X/Twitter, YouTube, HN, etc.)
- **Keywords**: Search terms and filters
- **Date range**: How far back to collect
- **Volume**: Max items per source
- **Fields to collect**: Title, text, author, date, URL, engagement stats, sentiment

### 2. Collect from Each Source

For each platform, extract:
- **Reddit**: Title, body, subreddit, score, comment count, author, timestamp, URL
- **X/Twitter**: Text, author, likes, retweets, replies, timestamp, URL
- **YouTube**: Title, description, channel, views, likes, comment count, timestamp, URL
- **Hacker News**: Title, points, comment count, author, timestamp, URL

### 3. Clean and Normalize
- Remove duplicates (same URL)
- Normalize timestamps to ISO 8601
- Standardize author fields
- Strip HTML entities from text
- Extract emoji/text indicators of sentiment

### 4. Store Structured Data

Insert into the target storage:

**Feishu Bitables**
- Map fields to bitable columns
- Use batch create to insert rows
- Add a "source URL" column for traceability

**Spreadsheet (CSV/XLSX)**
- Columns: Source, Type, URL, Title, Text, Author, Date, Score, Engagement, Sentiment
- One row per item

### 5. Annotate and Analyze
After collection, add:
- Label categories (bug report, praise, feature request, question)
- Priority tags for items needing response
- Trend grouping (bundle related items)

## Output Format

Present the collection results with:
1. **Summary**: Total items collected per source, date range
2. **Storage location**: Where the data was saved
3. **Key findings**: Main themes observed in the collection
