---
name: buffer
description: >-
  Schedule, create, and manage social media posts on Instagram and LinkedIn
  using the Buffer GraphQL API. Use when the user wants to publish content,
  schedule posts, check scheduled posts, list connected channels, or create
  content ideas on Buffer.
metadata:
  {
    "openclaw":
      {
        "emoji": "📲",
        "requires": { "bins": ["uv"], "env": ["BUFFER_API_KEY"] },
        "primaryEnv": "BUFFER_API_KEY",
      },
  }
---

# buffer

Schedule, create, and manage social media posts on Instagram and LinkedIn via the Buffer GraphQL API.

## Setup

1. Go to https://publish.buffer.com/settings/api
2. Copy your access token
3. Set the environment variable:
   ```bash
   export BUFFER_API_KEY="your-access-token"
   ```
4. Install script dependencies:
   ```bash
   cd skills/buffer/scripts && uv sync
   ```

> **Note:** Buffer's API is in Beta. All operations use POST with a JSON body containing `query` (and optionally `variables`).

## Operations

All scripts are run from `skills/buffer/scripts/` with `uv run`.

### Get Organizations

Retrieve your organization IDs — needed for all other calls.

```bash
uv run organizations.py list
```

### List Channels

List connected channels for an organization.

```bash
uv run channels.py list --org-id ORG_ID
```

List only unlocked (active) channels:

```bash
uv run channels.py list --org-id ORG_ID --unlocked
```

### Get a Single Channel

```bash
uv run channels.py get --channel-id CHANNEL_ID
```

### Get Scheduled Posts

```bash
uv run posts.py list --org-id ORG_ID --status scheduled
```

Filter by channel and include asset details:

```bash
uv run posts.py list --org-id ORG_ID --status scheduled --channel-id CHANNEL_ID --with-assets
```

Paginate results:

```bash
uv run posts.py list --org-id ORG_ID --status scheduled --limit 10 --after CURSOR
```

### Get Sent Posts

```bash
uv run posts.py list --org-id ORG_ID --status sent
```

### Create Text Post

**Share now:**

```bash
uv run posts.py create --channel-id CHANNEL_ID --text "Your post text here" --mode shareNow
```

**Add to queue:**

```bash
uv run posts.py create --channel-id CHANNEL_ID --text "Queued post" --mode addToQueue
```

**Schedule for a specific time:**

```bash
uv run posts.py create --channel-id CHANNEL_ID --text "Your scheduled post" --mode customSchedule --due-at "2026-03-01T14:00:00Z"
```

### Create Image Post

```bash
uv run posts.py create --channel-id CHANNEL_ID --text "Check out this photo!" --mode shareNow \
  --image-url "https://example.com/photo.jpg"
```

Multiple images:

```bash
uv run posts.py create --channel-id CHANNEL_ID --text "Photo carousel" --mode shareNow \
  --image-url "https://example.com/1.jpg" \
  --image-url "https://example.com/2.jpg"
```

### Instagram-Specific Features

- **Post type** — `--ig-type`: `post` (default), `reel`, or `story`
- **First comment** — `--first-comment TEXT`

Example — Instagram reel with first comment:

```bash
uv run posts.py create --channel-id IG_CHANNEL_ID \
  --text "Amazing reel!" \
  --mode shareNow \
  --image-url "https://example.com/video.mp4" \
  --ig-type reel \
  --first-comment "Follow for more!"
```

### LinkedIn-Specific Features

- **First comment** — `--first-comment TEXT`
- **Link attachment** — `--link-attachment URL`

Example — LinkedIn post with link attachment:

```bash
uv run posts.py create --channel-id LI_CHANNEL_ID \
  --text "Great article on AI trends" \
  --mode shareNow \
  --link-attachment "https://example.com/article" \
  --first-comment "What do you think?"
```

### Create Idea

Save content ideas to Buffer for later use.

```bash
uv run ideas.py create --org-id ORG_ID --title "Post idea title" --text "Draft content for the post..."
```

## Workflow Guidance

When the user asks to interact with Buffer, follow these steps:

1. **Fetch organizations** first to get the `organizationId`
2. **Fetch channels** and filter to only Instagram (`service: "instagram"`) and LinkedIn (`service: "linkedin"`)
3. **Confirm channel selection** with the user before posting
4. **Show post preview** — display the text, images, and scheduling details before submitting
5. **Report back** the post ID and status after creation

## Error Handling

GraphQL errors return in the `errors` array or as `MutationError` union types. Common errors:

- `NotFoundError` — Invalid org/channel/post ID
- `UnauthorizedError` — Bad or expired API key
- `InvalidInputError` — Malformed query or missing required fields
- `LimitReachedError` — Plan limits exceeded (e.g., too many scheduled posts)

Scripts exit with a non-zero code and print the error message to stderr on failure.

## Limitations

- Cannot edit or delete posts via the API
- TikTok channels are not supported (Instagram and LinkedIn only)
- The Buffer API is in Beta — endpoints may change
- Image URLs must be publicly accessible for Buffer to fetch them
