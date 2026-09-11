---
name: browse-cli-integration
category: community
description: "browse.sh CLI: 400+ browser automation skills."
---

# Browse CLI Integration — browse.sh Shell Script

Integrate with the `browse.sh` CLI — a comprehensive shell script that provides 400+ browser automation skills for web scraping, form filling, screenshot capture, and more.

## When to use

- You need quick browser automation from the command line
- You want to leverage 400+ pre-built browser automation recipes
- You need to capture screenshots, scrape content, or automate repetitive web tasks
- You prefer shell-based automation over Python/JS scripts

## Basic Usage

```bash
# Browse to a URL
browse https://example.com

# Capture screenshot
browse screenshot https://example.com output.png

# Get page text
browse text https://example.com

# Get HTML source
browse html https://example.com

# Search for text
browse search "keyword" https://example.com

# Click an element and capture result
browse click "#button" https://example.com
```

## Common Commands

```bash
# Navigation
browse goto <url>
browse back
browse forward
browse refresh
browse history

# Content extraction
browse text <url>                    # Extract visible text
browse html <url>                    # Get full HTML
browse markdown <url>                # Convert to markdown
browse links <url>                   # Extract all links
browse images <url>                  # Extract image URLs
browse tables <url>                  # Extract HTML tables
browse metadata <url>                # Get meta tags

# Screenshots
browse screenshot <url> <file.png>   # Full page screenshot
browse screenshot-viewport <url>     # Viewport only
browse screenshot-element <css>      # Element screenshot

# Form interaction
browse type <css> <text>
browse select <css> <option>
browse check <css>
browse uncheck <css>
browse submit <form-css>

# Automation
browse wait <seconds>
browse wait-for <css>
browse scroll <direction> [px]
browse click <css>
browse hover <css>
browse evaluate <js-code>
```

## Pipeline Usage

```bash
# Chain commands
browse https://example.com \
  | browse click "a.next" \
  | browse wait 2 \
  | browse screenshot "page2.png"

# Or pipe URLs
cat urls.txt | while read url; do
  browse text "$url" > "$(basename $url).txt"
done
```

## Scripting with browse.sh

```bash
#!/bin/bash
# Automated product monitor

URL="https://example.com/product"
PRICE_SELECTOR=".price-value"

current_price=$(browse text "$PRICE_SELECTOR" "$URL" | grep -oP '\$[\d.]+')
threshold=50.00

if (( $(echo "$current_price > $threshold" | bc -l) )); then
  browse screenshot "$URL" "price-alert-$(date +%Y%m%d).png"
  echo "Price alert: $current_price (above $threshold)"
fi
```

## Available Skill Categories

The 400+ skills cover:

| Category | Examples |
|----------|---------|
| E-commerce | Product search, price monitoring, review extraction |
| Social Media | Tweet collection, profile scraping, trend monitoring |
| News | Article extraction, headline aggregation, feed monitoring |
| Search | Google scraping, image search, reverse image search |
| Maps | Address lookup, direction extraction, place details |
| Video | YouTube metadata, transcript extraction, comments |
| Code | GitHub repo info, package lookup, documentation |
| Reference | Wikipedia, dictionary, translation, calculation |

## Pitfalls

- Not all 400+ skills are available in every installation — run `browse help` to see what's installed
- Some sites may block the default user agent — use `browse --user-agent "..."` to customize
- JavaScript-heavy sites may need `browse --wait-for-network-idle` before extracting content
- `browse.sh` requires a headless browser engine (Playwright/Puppeteer) — install it first
- Rate limiting is your responsibility — add delays for bulk operations

## Verification

After installation, run `browse --version` to confirm it's available, then `browse text https://example.com` to verify basic functionality.
