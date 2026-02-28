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
        "requires": { "bins": ["curl", "jq"], "env": ["BUFFER_API_KEY"] },
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

## API Basics

All requests use a single GraphQL endpoint:

```bash
curl -s -X POST https://api.buffer.com \
  -H "Authorization: Bearer $BUFFER_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"query": "YOUR_GRAPHQL_QUERY"}' | jq
```

> **Note:** Buffer's API is in Beta. All operations use POST with a JSON body containing `query` (and optionally `variables`).

## Operations

### Get Organizations

Retrieve your organization IDs — needed for all other calls.

```bash
curl -s -X POST https://api.buffer.com \
  -H "Authorization: Bearer $BUFFER_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"query": "query { account { organizations { id name ownerEmail } } }"}' | jq '.data.account.organizations'
```

### Get Channels

List connected channels for an organization. Filter by `service` field to find Instagram (`instagram`) or LinkedIn (`linkedin`) channels.

```bash
curl -s -X POST https://api.buffer.com \
  -H "Authorization: Bearer $BUFFER_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"query": "query { channels(input: { organizationId: \"ORG_ID\" }) { id name displayName service avatar isQueuePaused } }"}' | jq '.data.channels'
```

Filter to Instagram and LinkedIn only:

```bash
curl -s -X POST https://api.buffer.com \
  -H "Authorization: Bearer $BUFFER_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"query": "query { channels(input: { organizationId: \"ORG_ID\" }) { id name displayName service avatar isQueuePaused } }"}' | jq '[.data.channels[] | select(.service == "instagram" or .service == "linkedin")]'
```

### Create Text Post

Post text to a channel. Modes: `addToQueue`, `shareNow`, `shareNext`, `customSchedule`, `recommendedTime`.

**Share now:**

```bash
curl -s -X POST https://api.buffer.com \
  -H "Authorization: Bearer $BUFFER_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "mutation { createPost(input: { text: \"Your post text here\", channelId: \"CHANNEL_ID\", schedulingType: automatic, mode: shareNow }) { ... on PostActionSuccess { post { id text dueAt } } ... on MutationError { message } } }"
  }' | jq '.data.createPost'
```

**Schedule for a specific time:**

```bash
curl -s -X POST https://api.buffer.com \
  -H "Authorization: Bearer $BUFFER_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "mutation { createPost(input: { text: \"Your scheduled post\", channelId: \"CHANNEL_ID\", schedulingType: automatic, mode: customSchedule, dueAt: \"2026-03-01T14:00:00Z\" }) { ... on PostActionSuccess { post { id text dueAt } } ... on MutationError { message } } }"
  }' | jq '.data.createPost'
```

**Add to queue:**

```bash
curl -s -X POST https://api.buffer.com \
  -H "Authorization: Bearer $BUFFER_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "mutation { createPost(input: { text: \"Queued post\", channelId: \"CHANNEL_ID\", schedulingType: automatic, mode: addToQueue }) { ... on PostActionSuccess { post { id text dueAt } } ... on MutationError { message } } }"
  }' | jq '.data.createPost'
```

### Create Image Post

Same as text post but include `assets` with an `images` array.

```bash
curl -s -X POST https://api.buffer.com \
  -H "Authorization: Bearer $BUFFER_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "mutation { createPost(input: { text: \"Check out this photo!\", channelId: \"CHANNEL_ID\", schedulingType: automatic, mode: shareNow, assets: { images: [{ url: \"https://example.com/photo.jpg\" }] } }) { ... on PostActionSuccess { post { id text } } ... on MutationError { message } } }"
  }' | jq '.data.createPost'
```

Multiple images:

```bash
assets: { images: [{ url: "https://example.com/1.jpg" }, { url: "https://example.com/2.jpg" }] }
```

### Instagram-Specific Features

Use the `metadata` field within `createPost` input for Instagram-specific options:

- **Post type** — `type`: `post` (default), `reel`, or `story`
- **First comment** — `firstComment`: text posted as the first comment
- **Geolocation** — `geolocation`: location tagging object
- **Share reel to feed** — `shouldShareToFeed`: `true`/`false` (for reels)
- **Scheduling type** — Use `schedulingType: notification` for reminder-based posting (required for stories and some post types that need manual publish)

Example — Create an Instagram reel with first comment:

```bash
curl -s -X POST https://api.buffer.com \
  -H "Authorization: Bearer $BUFFER_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "mutation { createPost(input: { text: \"Amazing reel!\", channelId: \"IG_CHANNEL_ID\", schedulingType: automatic, mode: shareNow, assets: { images: [{ url: \"https://example.com/video.mp4\" }] }, metadata: { type: reel, firstComment: \"Follow for more!\", shouldShareToFeed: true } }) { ... on PostActionSuccess { post { id text } } ... on MutationError { message } } }"
  }' | jq '.data.createPost'
```

### LinkedIn-Specific Features

Use the `metadata` field for LinkedIn-specific options:

- **First comment** — `firstComment`: initial comment on the post
- **Link attachment** — `linkAttachment`: `{ url: "https://..." }` to attach a link preview
- **Annotations** — `annotations`: for @mentions in the post

Example — LinkedIn post with link attachment:

```bash
curl -s -X POST https://api.buffer.com \
  -H "Authorization: Bearer $BUFFER_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "mutation { createPost(input: { text: \"Great article on AI trends\", channelId: \"LI_CHANNEL_ID\", schedulingType: automatic, mode: shareNow, metadata: { linkAttachment: { url: \"https://example.com/article\" }, firstComment: \"What do you think?\" } }) { ... on PostActionSuccess { post { id text } } ... on MutationError { message } } }"
  }' | jq '.data.createPost'
```

### Get Scheduled Posts

Query posts filtered by `status: [scheduled]`.

```bash
curl -s -X POST https://api.buffer.com \
  -H "Authorization: Bearer $BUFFER_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "query { posts(input: { organizationId: \"ORG_ID\", filter: { status: [scheduled], channelIds: [\"CHANNEL_ID\"] }, sort: [{ field: dueAt, direction: asc }] }) { edges { node { id text createdAt dueAt channelId status } } } }"
  }' | jq '.data.posts.edges[].node'
```

### Get Sent Posts

Same pattern with `status: sent`.

```bash
curl -s -X POST https://api.buffer.com \
  -H "Authorization: Bearer $BUFFER_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "query { posts(input: { organizationId: \"ORG_ID\", filter: { status: [sent], channelIds: [\"CHANNEL_ID\"] }, sort: [{ field: dueAt, direction: desc }] }) { edges { node { id text createdAt dueAt channelId status } } } }"
  }' | jq '.data.posts.edges[].node'
```

### Create Idea

Save content ideas to Buffer for later use.

```bash
curl -s -X POST https://api.buffer.com \
  -H "Authorization: Bearer $BUFFER_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "mutation { createIdea(input: { organizationId: \"ORG_ID\", content: { title: \"Post idea title\", text: \"Draft content for the post...\" } }) { ... on Idea { id content { title text } } } }"
  }' | jq '.data.createIdea'
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

Check for errors:

```bash
# Check for top-level GraphQL errors
... | jq '.errors'

# Check for mutation-level errors
... | jq '.data.createPost | if .message then {error: .message} else {post: .post} end'
```

## Limitations

- Cannot edit or delete posts via the API
- TikTok channels are not supported (Instagram and LinkedIn only)
- The Buffer API is in Beta — endpoints may change
- Image URLs must be publicly accessible for Buffer to fetch them
