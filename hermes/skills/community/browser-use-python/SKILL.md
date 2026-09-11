---
name: browser-use-python
category: community
description: "browser-use: Python browser automation for AI agents. 99.5K+ installs."
---

# Browser-Use Python — Browser Automation for AI Agents

Use the `browser-use` Python package (99.5K+ installs) to automate browser interactions from AI agents. Supports navigation, clicks, form fills, screenshots, and JavaScript execution.

## When to use

- You need to automate browser-based tasks (form filling, data extraction)
- Your AI agent needs to interact with web pages that don't have APIs
- You need to take screenshots of web pages programmatically
- You're building automated workflows that involve web browsing

## Installation

```bash
pip install browser-use
```

## Basic Usage

```python
from browser_use import Agent

agent = Agent()
agent.goto("https://example.com")
agent.click("#login-button")
agent.type("#username", "myuser")
agent.type("#password", "mypass")
agent.click("#submit")
page_text = agent.text()
print(page_text[:500])
```

## Common Actions

```python
# Navigate
agent.goto("https://example.com")
agent.back()
agent.forward()
agent.refresh()

# Interact
agent.click(".button-class")
agent.type("input[name='email']", "user@example.com")
agent.select("select#country", "US")
agent.hover("#tooltip-trigger")

# Read
text = agent.text()                     # Page text
html = agent.html()                     # Full HTML
title = agent.title()                   # Page title
url = agent.url()                       # Current URL

# Screenshot
agent.screenshot("page.png")

# JavaScript
result = agent.evaluate("document.title")
agent.execute("document.body.style.backgroundColor = 'red'")

# Wait
agent.wait(2)                           # Seconds
agent.wait_for_element(".loaded-class")
agent.wait_for_navigation()
```

## Advanced: Multi-step Workflows

```python
from browser_use import Agent

def search_and_extract(query):
    agent = Agent(headless=False)
    
    agent.goto("https://google.com")
    agent.type("textarea[name='q']", query)
    agent.press("Enter")
    agent.wait_for_navigation()
    
    results = []
    links = agent.find_elements("a")
    for link in links[:5]:
        href = link.get_attribute("href")
        if href and href.startswith("http"):
            results.append(href)
    
    agent.close()
    return results
```

## Headless Mode

```python
# Run without visible browser window
agent = Agent(headless=True)

# Or with specific browser options
agent = Agent(
    headless=True,
    window_size=(1920, 1080),
    user_agent="Mozilla/5.0 ..."
)
```

## Working with Selectors

```python
# CSS selectors
agent.click("button.primary")
agent.type("#username", "user")

# XPath (when CSS is tricky)
agent.click_xpath("//button[contains(text(), 'Submit')]")

# Text matching
agent.click_by_text("Sign In")
agent.click_by_text("Continue", partial=True)

# By position (when no unique selector exists)
agent.click_at(100, 200)
```

## Pitfalls

- Anti-bot systems (Cloudflare, reCAPTCHA) may block automated browsers
- Always use `wait_for_element` or `wait_for_navigation` instead of fixed `time.sleep()`
- Headless mode is faster but more detectable — some sites may serve different content
- If you need to log in, consider saving and restoring cookies for repeat visits
- Network conditions affect timing — use generous timeouts for slow pages

## Verification

Write a test script that navigates to a known page, clicks a link, waits for the next page to load, and confirms the URL has changed to verify navigation works.
