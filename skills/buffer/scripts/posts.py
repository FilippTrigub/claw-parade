"""Buffer posts API.

Usage:
    uv run posts.py list --org-id ORG_ID --status scheduled|sent
                         [--channel-id CHANNEL_ID] [--with-assets]
                         [--limit N] [--after CURSOR]

    uv run posts.py create --channel-id CHANNEL_ID --text TEXT
                           --mode shareNow|addToQueue|customScheduled
                           [--due-at ISO8601]
                           [--image-url URL|PATH ...]
                           [--ig-type post|reel|story]
                           [--ig-first-comment TEXT]
                           [--li-first-comment TEXT]
                           [--link-attachment URL]

Image URLs:
    - Pass a public HTTPS URL directly.
    - Google Drive share URLs (drive.google.com/file/d/...) are auto-converted
      to direct-fetch format.
    - Local file paths are NOT supported — upload to Google Drive first:
        gdrive files upload /path/to/image.jpg
      Then share the file and pass the share URL here.
"""

import argparse
import json
import os
import re
import sys

from _client import graphql

BASE_NODE_FIELDS = """
  id
  text
  createdAt
  dueAt
  channelId
  status
"""

ASSETS_FIELDS = """
  assets {
    thumbnail
    mimeType
    source
    ... on ImageAsset {
      image {
        altText
        width
        height
      }
    }
  }
"""

LIST_QUERY_TEMPLATE = """
query ListPosts($after: String, $first: Int, $input: PostsInput!) {{
  posts(after: $after, first: $first, input: $input) {{
    edges {{
      node {{
        {node_fields}
      }}
    }}
    pageInfo {{
      endCursor
      hasNextPage
    }}
  }}
}}
"""

CREATE_MUTATION = """
mutation CreatePost($input: CreatePostInput!) {
  createPost(input: $input) {
    ... on PostActionSuccess {
      post {
        id
        text
        dueAt
        status
      }
    }
    ... on MutationError {
      message
    }
  }
}
"""

# Matches: https://drive.google.com/file/d/FILE_ID/view...
_GDRIVE_SHARE_RE = re.compile(
    r"https://drive\.google\.com/file/d/([a-zA-Z0-9_-]+)"
)


def resolve_image_url(raw: str) -> str:
    """Convert a raw image argument to a fetchable URL.

    Accepts:
    - Public HTTPS URLs — returned as-is.
    - Google Drive share URLs — converted to lh3.googleusercontent.com/d/FILE_ID.
    - Local paths — exits with a helpful error message.
    """
    # Local file path
    if not raw.startswith("http"):
        abs_path = os.path.abspath(raw)
        print(
            f"Error: '{raw}' looks like a local file path.\n"
            "Buffer requires a publicly accessible URL.\n"
            "Upload the file to Google Drive first:\n"
            f"    gdrive files upload \"{abs_path}\"\n"
            "Then share it (Anyone with the link) and pass the share URL here.",
            file=sys.stderr,
        )
        sys.exit(1)

    # Google Drive share URL → direct URL
    m = _GDRIVE_SHARE_RE.search(raw)
    if m:
        file_id = m.group(1)
        direct = f"https://lh3.googleusercontent.com/d/{file_id}"
        print(f"Google Drive URL detected → converted to: {direct}", file=sys.stderr)
        return direct

    return raw


def cmd_list(args: argparse.Namespace) -> None:
    node_fields = BASE_NODE_FIELDS
    if args.with_assets:
        node_fields += ASSETS_FIELDS

    query = LIST_QUERY_TEMPLATE.format(node_fields=node_fields)

    post_filter: dict = {"status": [args.status]}
    if args.channel_id:
        post_filter["channelIds"] = [args.channel_id]

    sort_direction = "asc" if args.status == "scheduled" else "desc"

    variables: dict = {
        "input": {
            "organizationId": args.org_id,
            "filter": post_filter,
            "sort": [{"field": "dueAt", "direction": sort_direction}],
        }
    }
    if args.limit:
        variables["first"] = args.limit
    if args.after:
        variables["after"] = args.after

    data = graphql(query, variables)
    posts = [edge["node"] for edge in data["posts"]["edges"]]
    page_info = data["posts"]["pageInfo"]

    output = {"posts": posts, "pageInfo": page_info}
    print(json.dumps(output, indent=2))


def cmd_create(args: argparse.Namespace) -> None:
    post_input: dict = {
        "channelId": args.channel_id,
        "text": args.text,
        "schedulingType": "automatic",
        "mode": args.mode,
    }

    if args.due_at:
        post_input["dueAt"] = args.due_at

    if args.image_url:
        resolved = [resolve_image_url(u) for u in args.image_url]
        post_input["assets"] = {"images": [{"url": url} for url in resolved]}

    ig_meta: dict = {}
    if args.ig_type:
        ig_meta["type"] = args.ig_type
        ig_meta.setdefault("shouldShareToFeed", False)
    if args.ig_first_comment:
        ig_meta["firstComment"] = args.ig_first_comment

    li_meta: dict = {}
    if args.li_first_comment:
        li_meta["firstComment"] = args.li_first_comment
    if args.link_attachment:
        li_meta["linkAttachment"] = {"url": args.link_attachment}

    metadata: dict = {}
    if ig_meta:
        metadata["instagram"] = ig_meta
    if li_meta:
        metadata["linkedin"] = li_meta
    if metadata:
        post_input["metadata"] = metadata

    data = graphql(CREATE_MUTATION, {"input": post_input})
    result = data["createPost"]
    print(json.dumps(result, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Buffer posts",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_list = sub.add_parser("list", help="List posts")
    p_list.add_argument("--org-id", required=True, metavar="ORG_ID")
    p_list.add_argument("--status", required=True, choices=["scheduled", "sent"])
    p_list.add_argument("--channel-id", metavar="CHANNEL_ID")
    p_list.add_argument("--with-assets", action="store_true", help="Include asset details")
    p_list.add_argument("--limit", type=int, metavar="N")
    p_list.add_argument("--after", metavar="CURSOR", help="Pagination cursor")

    p_create = sub.add_parser("create", help="Create a post")
    p_create.add_argument("--channel-id", required=True, metavar="CHANNEL_ID")
    p_create.add_argument("--text", required=True)
    p_create.add_argument(
        "--mode",
        required=True,
        choices=["shareNow", "addToQueue", "shareNext", "customScheduled", "recommendedTime"],
    )
    p_create.add_argument("--due-at", metavar="ISO8601", help="Schedule time (for customScheduled)")
    p_create.add_argument(
        "--image-url",
        action="append",
        metavar="URL",
        help="Image URL or Google Drive share URL (repeat for multiple). Local paths not supported — upload via gdrive CLI first.",
    )
    p_create.add_argument(
        "--ig-type",
        choices=["post", "reel", "story"],
        help="Instagram post type (required for Instagram channels)",
    )
    p_create.add_argument("--ig-first-comment", metavar="TEXT", help="Instagram first comment")
    p_create.add_argument("--li-first-comment", metavar="TEXT", help="LinkedIn first comment")
    p_create.add_argument("--link-attachment", metavar="URL", help="LinkedIn link attachment URL")

    args = parser.parse_args()
    if args.command == "list":
        cmd_list(args)
    elif args.command == "create":
        cmd_create(args)


if __name__ == "__main__":
    main()
