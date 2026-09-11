---
name: site-browser-automation
category: community
description: "Site-specific browser automation with pre-optimized selectors for common sites."
---

# Site Browser Automation — Pre-Optimized Selectors

Browser automation for common websites using pre-optimized CSS selectors and XPath expressions. Avoids the trial-and-error of finding stable selectors on popular sites.

## When to use

- You need to automate interactions with common websites (Google, GitHub, Twitter/X, Reddit, Amazon)
- You want stable selectors that won't break with minor site updates
- You're building scrapers or automation bots for specific services
- You need a reference library of reliable element selectors

## Common Site Selectors

### Google Search

```python
# Search box
selectors = {
    "search_input": "textarea[name='q']",
    "search_button": "input[name='btnK']",
    "search_results": "div#search div.g",
    "result_title": "h3",
    "result_link": "a",
    "result_snippet": "div.VwiC3b",
    "next_page": "a#pnnext",
}
```

### GitHub

```python
# Repository page
selectors = {
    "repo_name": "strong[itemprop='name']",
    "description": "p[itemprop='about']",
    "stars": "a[href$='/stargazers'] span",
    "forks": "a[href$='/forks'] span",
    "readme": "article.markdown-body",
    "file_list": "div[role='rowheader'] a",
    "code_content": "div.blob-wrapper table",
}
```

### Twitter/X

```python
# Timeline and tweets
selectors = {
    "tweet": "article[data-testid='tweet']",
    "tweet_text": "div[data-testid='tweetText']",
    "tweet_author": "div[data-testid='User-Name'] a",
    "like_button": "div[data-testid='like']",
    "retweet_button": "div[data-testid='retweet']",
    "reply_button": "div[data-testid='reply']",
    "trends": "div[aria-label='Trending'] div[dir='ltr']",
}
```

### Reddit

```python
selectors = {
    "post": "div[data-testid='post-container']",
    "post_title": "h3",
    "post_body": "div[data-testid='post-content'] div.md",
    "upvote": "button[aria-label='upvote']",
    "comment": "div[data-testid='comment']",
    "comment_body": "div.md p",
    "sidebar": "div[data-testid='subreddit-sidebar']",
}
```

### Amazon

```python
selectors = {
    "product_title": "span#productTitle",
    "price": "span.a-price span.a-offscreen",
    "rating": "span#acrPopover",
    "review_count": "span#acrCustomerReviewText",
    "add_to_cart": "input#add-to-cart-button",
    "buy_now": "input#buy-now-button",
    "search_input": "input#twotabsearchtextbox",
    "search_results": "div[data-component-type='s-search-result']",
}
```

### LinkedIn

```python
selectors = {
    "profile_name": "h1",
    "headline": "div.text-body-medium",
    "about": "div[aria-label='About'] + div",
    "experience": "section#experience-section",
    "education": "section#education-section",
    "skills": "section#skills-section",
}
```

## Usage Pattern

```python
def automate_github_search(repo_name):
    from browser_use import Agent
    
    agent = Agent()
    agent.goto(f"https://github.com/{repo_name}")
    
    # Use pre-optimized selectors
    description = agent.text("p[itemprop='about']")
    stars = agent.text("a[href$='/stargazers'] span")
    
    agent.close()
    return {
        "description": description,
        "stars": int(stars.replace(",", "")) if stars else 0
    }
```

## Custom Site: Building Your Own Selectors

```python
# Strategy for finding stable selectors:
# 1. Use data-testid attributes when available (most stable)
# 2. Prefer id over class (more specific)
# 3. Use aria-label for accessibility-based selectors
# 4. Avoid positional selectors (nth-child) that break on layout changes
# 5. Combine attributes for uniqueness: button[data-testid='login'][type='submit']
```

## Pitfalls

- Site updates can break selectors — test periodically and maintain a fallback strategy
- A/B testing means different users see different selectors — handle multiple variants
- Dark patterns — some sites deliberately change selectors to block automation
- Rate limiting — always add delays between automated requests to the same site
- Legal compliance — check the site's ToS before automating
- Prefer `data-testid` attributes — they're intentionally stable for testing

## Verification

For any site automation, run a test that loads the page and checks that at least 3 key elements are found using the selectors. Log a warning if a selector returns no results.
