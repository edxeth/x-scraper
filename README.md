# X/Twitter Scraper

A Python CLI tool for scraping tweets from X (formerly Twitter).

Uses [Bird CLI](https://github.com/steipete/bird) for X's GraphQL API and [botasaurus](https://github.com/omkarcloud/botasaurus) for parallel processing with retry logic.

## Features

- **Tweet extraction** - Text, images (full resolution), and videos
- **Multiple output formats** - JSON or Markdown
- **Smart output paths** - Auto-organized by date/author/tweet_id
- **Parallel processing** - Scrape multiple tweets concurrently
- **Auto-retry** - Exponential backoff on failures
- **Cookie-based auth** - Uses your existing X login session

---

## Quick Start

### 1. Install Dependencies

```bash
git clone https://github.com/edxeth/x-scraper.git
cd x-scraper
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### 2. Install Bird CLI

```bash
bun install -g @nicepkg/bird
```

### 3. Set Up Authentication

Extract cookies from your browser (must be logged into X):

1. Open X.com → Press F12 → Application tab → Cookies → x.com
2. Copy `auth_token` and `ct0` values
3. Create `.env` file:

```bash
cat > .env << 'EOF'
AUTH_TOKEN=your_auth_token_here
CT0=your_ct0_here
EOF
```

### 4. Verify Setup

```bash
x-scraper check-auth
```

---

## Usage

### Quick Read (Display Only)

```bash
# Markdown format (default)
x-scraper read "https://x.com/user/status/123"

# JSON format
x-scraper read "https://x.com/user/status/123" --format json

# Raw Bird CLI output
x-scraper read "https://x.com/user/status/123" --raw
```

### Scrape and Save

```bash
# Save as JSON (auto-path: output/YYYY/MM/DD/author/tweet_id.json)
x-scraper scrape "https://x.com/user/status/123"

# Save as Markdown (auto-path: output/YYYY/MM/DD/author/tweet_id.md)
x-scraper scrape "https://x.com/user/status/123" --format markdown

# Custom output path
x-scraper scrape "https://x.com/user/status/123" -f markdown -o custom/path.md

# Multiple tweets
x-scraper scrape url1 url2 url3 -f markdown -o collected.md

# With proxy
x-scraper scrape url1 --proxy "socks5://user:pass@host:port"

# More parallel workers
x-scraper scrape url1 url2 url3 --parallel 10
```

---

## Output Formats

### JSON (`--format json`)

```json
[
  {
    "success": true,
    "url": "https://x.com/user/status/123",
    "data": {
      "id": "123",
      "text": "Tweet content...",
      "author_handle": "user",
      "author_name": "User Name",
      "created_at": "2026-01-15T09:54:50Z",
      "images": ["https://pbs.twimg.com/media/xxx.jpg?format=jpg&name=orig"],
      "videos": []
    }
  }
]
```

### Markdown (`--format markdown`)

```markdown
# Scraped Tweets

**Total:** 1 tweets | **Success:** 1 | **Failed:** 0

---

## User Name (@user)

Tweet content...

**Posted:** 2026-01-15T09:54:50Z
**URL:** [https://x.com/user/status/123](https://x.com/user/status/123)

### Images (1)

![Image 1](https://pbs.twimg.com/media/xxx.jpg?format=jpg&name=orig)

---
```

---

## CLI Reference

| Command | Description |
|---------|-------------|
| `x-scraper scrape URL...` | Scrape tweets and save to file |
| `x-scraper read URL` | Quick read (display only) |
| `x-scraper check-auth` | Verify authentication |
| `x-scraper show-cookie-help` | Cookie extraction guide |
| `x-scraper version` | Show version info |

### Scrape Options

| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--output` | `-o` | Output file path | `output/tweets.json` |
| `--format` | `-f` | `json` or `markdown` | `json` |
| `--parallel` | `-p` | Parallel workers | `5` |
| `--proxy` | | SOCKS5 proxy URL | None |
| `--verbose` | `-v` | Debug logging | `false` |

### Read Options

| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--format` | `-f` | `json` or `markdown` | `markdown` |
| `--raw` | `-r` | Raw Bird CLI output | `false` |

---

## Python API

```python
from x_scraper import scrape_tweets, BirdClient
from x_scraper.utils import format_results_as_markdown

# Scrape multiple URLs
results = scrape_tweets([
    {"url": "https://x.com/user1/status/123"},
    {"url": "https://x.com/user2/status/456"},
])

for result in results:
    if result["success"]:
        data = result["data"]
        print(f"@{data['author_handle']}: {data['text'][:100]}...")

# Convert to markdown
print(format_results_as_markdown(results))

# Direct Bird CLI access
client = BirdClient()
raw_data = client.read_tweet("https://x.com/user/status/123")
```

---

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `AUTH_TOKEN` | X auth cookie | Yes |
| `CT0` | X CSRF token | Yes |
| `PROXY_URL` | SOCKS5 proxy | No |

---

## Troubleshooting

### "Bird CLI not found"
```bash
bun install -g @nicepkg/bird
```

### "Authentication failed"
Re-extract cookies from browser and update `.env`

### "Tweet not found"
```bash
bird query-ids --fresh
```

### Rate limited
- Reduce workers: `--parallel 2`
- Use proxy: `--proxy socks5://...`

---

## Project Structure

```
x-scraper/
├── src/x_scraper/
│   ├── cli.py           # Typer CLI
│   ├── scraper.py       # botasaurus scraper
│   ├── bird_client.py   # Bird CLI wrapper
│   ├── models.py        # Pydantic models
│   └── utils.py         # Helpers + formatters
├── tests/
├── pyproject.toml
└── .env
```

---

## Credits

- [Bird CLI](https://github.com/steipete/bird) - X GraphQL API
- [botasaurus](https://github.com/omkarcloud/botasaurus) - Scraping framework
