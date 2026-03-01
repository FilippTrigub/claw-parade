"""Buffer posts API.

Usage:
    uv run posts.py list --org-id ORG_ID --status scheduled|sent
                         [--channel-id CHANNEL_ID] [--with-assets]
                         [--limit N] [--after CURSOR]

    uv run posts.py create --channel-id CHANNEL_ID --text TEXT
                           --mode shareNow|addToQueue|customSchedule
                           [--due-at ISO8601]
                           [--image-url URL ...]
                           [--ig-type post|reel|story]
                           [--first-comment TEXT]
                           [--link-attachment URL]
"""

import argparse
import json

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
        post_input["assets"] = {"images": [{"url": url} for url in args.image_url]}

    metadata: dict = {}
    if args.ig_type:
        metadata["type"] = args.ig_type
    if args.first_comment:
        metadata["firstComment"] = args.first_comment
    if args.link_attachment:
        metadata["linkAttachment"] = {"url": args.link_attachment}
    if metadata:
        post_input["metadata"] = metadata

    data = graphql(CREATE_MUTATION, {"input": post_input})
    result = data["createPost"]
    print(json.dumps(result, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="Buffer posts")
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
        choices=["shareNow", "addToQueue", "shareNext", "customSchedule", "recommendedTime"],
    )
    p_create.add_argument("--due-at", metavar="ISO8601", help="Schedule time (for customSchedule)")
    p_create.add_argument(
        "--image-url", action="append", metavar="URL", help="Image URL (repeat for multiple)"
    )
    p_create.add_argument("--ig-type", choices=["post", "reel", "story"], help="Instagram post type")
    p_create.add_argument("--first-comment", metavar="TEXT", help="First comment text")
    p_create.add_argument("--link-attachment", metavar="URL", help="LinkedIn link attachment URL")

    args = parser.parse_args()
    if args.command == "list":
        cmd_list(args)
    elif args.command == "create":
        cmd_create(args)


if __name__ == "__main__":
    main()
