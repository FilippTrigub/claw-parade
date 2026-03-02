"""Buffer posts API.

Usage:
    uv run posts.py list --org-id ORG_ID --status scheduled|sent
                         [--channel-id CHANNEL_ID] [--with-assets]
                         [--limit N] [--after CURSOR]

    uv run posts.py create --channel-id CHANNEL_ID --text TEXT
                           --mode shareNow|addToQueue|customScheduled
                           [--due-at ISO8601]
                           [--image-url URL|PATH ...]
                           [--video-url URL|PATH]
                           [--ig-type post|reel|story]
                           [--ig-first-comment TEXT]
                           [--li-first-comment TEXT]
                           [--link-attachment URL]
                           [--tunnel-wait SECONDS]

Image and video URLs:
    - Pass a public HTTPS URL directly.
    - Google Drive share URLs (drive.google.com/file/d/...) are auto-converted
      to direct-fetch format for images (lh3.googleusercontent.com) and direct-download
      format for video (drive.google.com/uc?export=download&id=FILE_ID).
    - Local file paths are supported via a cloudflared tunnel (cloudflared must be
      installed). All local files are served from a single HTTP server exposed through
      the tunnel. The tunnel stays alive for --tunnel-wait seconds (default 90) after
      the API call to give Buffer time to fetch the media, then shuts down automatically.
      Install cloudflared: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/
"""

import argparse
import http.server
import json
import os
import re
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

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
      __typename
      post {
        id
        text
        dueAt
        status
      }
    }
    ... on MutationError {
      __typename
      message
    }
  }
}
"""

# Matches: https://drive.google.com/file/d/FILE_ID/view...
_GDRIVE_SHARE_RE = re.compile(
    r"https://drive\.google\.com/file/d/([a-zA-Z0-9_-]+)"
)


_TUNNEL_URL_RE = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")


def _serve_local_files(paths: list[str]) -> tuple[dict[str, str], "callable"]:
    """Start a single HTTP server + cloudflared tunnel for one or more local files.

    Serves from the common ancestor directory of all files so a single server
    can cover images and video together even if they live in different subdirs.

    Returns ({original_path: public_url}, shutdown_fn).
    Requires `cloudflared` on PATH.
    """
    resolved = [Path(p).resolve() for p in paths]

    for fp in resolved:
        if not fp.exists():
            print(f"Error: file not found: {fp}", file=sys.stderr)
            sys.exit(1)

    # Serve from the common ancestor of all files.
    if len(resolved) == 1:
        serve_dir = resolved[0].parent
    else:
        serve_dir = Path(os.path.commonpath([str(fp) for fp in resolved]))
        if serve_dir.is_file():
            serve_dir = serve_dir.parent

    with socket.socket() as s:
        s.bind(("", 0))
        port = s.getsockname()[1]

    class _Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(serve_dir), **kwargs)

        def log_message(self, fmt, *args):
            print(f"HTTP server: {fmt % args}", file=sys.stderr)

    server = http.server.HTTPServer(("", port), _Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print(f"Local HTTP server started on :{port} (serving {serve_dir})", file=sys.stderr)

    try:
        proc = subprocess.Popen(
            ["cloudflared", "tunnel", "--url", f"http://localhost:{port}"],
            stderr=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            text=True,
        )
    except FileNotFoundError:
        server.shutdown()
        print(
            "Error: 'cloudflared' not found on PATH.\n"
            "Install it from: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/",
            file=sys.stderr,
        )
        sys.exit(1)

    print("Waiting for cloudflared tunnel URL...", file=sys.stderr)
    tunnel_base = None
    for line in proc.stderr:
        m = _TUNNEL_URL_RE.search(line)
        if m:
            tunnel_base = m.group(0)
            break

    if not tunnel_base:
        proc.terminate()
        server.shutdown()
        print("Error: could not obtain cloudflared tunnel URL.", file=sys.stderr)
        sys.exit(1)

    url_map = {
        orig: f"{tunnel_base}/{fp.relative_to(serve_dir)}"
        for orig, fp in zip(paths, resolved)
    }

    print(f"Tunnel ready → {tunnel_base}", file=sys.stderr)
    for orig, url in url_map.items():
        print(f"  {orig} → {url}", file=sys.stderr)
    print("Waiting 10s for tunnel to propagate...", file=sys.stderr)
    time.sleep(10)

    def shutdown() -> None:
        proc.terminate()
        server.shutdown()
        print("Tunnel and local server stopped.", file=sys.stderr)

    return url_map, shutdown


def _probe_url(url: str, retries: int = 3) -> None:
    """HEAD-probe a URL, retrying on failure. Exits if all attempts fail."""
    import urllib.request
    import urllib.error

    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, method="HEAD")
            resp = urllib.request.urlopen(req, timeout=10)
            cl = int(resp.headers.get("content-length") or 0)
            if resp.status == 200 and cl > 0:
                print(f"  verified: {url} ({cl} bytes)", file=sys.stderr)
                return
            print(f"  attempt {attempt}: status={resp.status} content-length={cl}", file=sys.stderr)
        except Exception as e:
            print(f"  attempt {attempt} failed: {e}", file=sys.stderr)
        if attempt < retries:
            time.sleep(3)

    print(f"Error: URL not accessible after {retries} attempts: {url}", file=sys.stderr)
    sys.exit(1)


def resolve_image_url(raw: str) -> str:
    """Convert a remote image argument to a fetchable URL.

    Accepts:
    - Public HTTPS URLs — returned as-is.
    - Google Drive share URLs — converted to lh3.googleusercontent.com/d/FILE_ID.
    - Local paths must be resolved via _serve_local_files() before calling this.
    """
    m = _GDRIVE_SHARE_RE.search(raw)
    if m:
        file_id = m.group(1)
        direct = f"https://lh3.googleusercontent.com/d/{file_id}"
        print(f"Google Drive URL detected → converted to: {direct}", file=sys.stderr)
        return direct

    return raw


def resolve_video_url(raw: str) -> str:
    """Convert a raw video argument to a direct-download URL.

    Accepts:
    - Public HTTPS direct-download URLs — returned as-is.
    - Google Drive share URLs — converted to drive.google.com/uc?export=download&id=FILE_ID.
    - Local paths — callers must handle via _serve_local_files() before calling this.
    """
    m = _GDRIVE_SHARE_RE.search(raw)
    if m:
        file_id = m.group(1)
        direct = f"https://drive.google.com/uc?export=download&id={file_id}"
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

    # Collect all local paths so they can share a single tunnel.
    local_paths = []
    if args.image_url:
        local_paths.extend(u for u in args.image_url if not u.startswith("http"))
    if args.video_url and not args.video_url.startswith("http"):
        local_paths.append(args.video_url)

    url_map: dict[str, str] = {}
    shutdown_tunnel = None
    if local_paths:
        url_map, shutdown_tunnel = _serve_local_files(local_paths)
        print("Verifying tunnel URLs...", file=sys.stderr)
        for url in url_map.values():
            _probe_url(url)

    assets: dict = {}
    if args.image_url:
        assets["images"] = [
            {"url": url_map[u] if u in url_map else resolve_image_url(u)}
            for u in args.image_url
        ]
    if args.video_url:
        video_url = url_map.get(args.video_url) or resolve_video_url(args.video_url)
        assets["videos"] = [{"url": video_url}]
    if assets:
        post_input["assets"] = assets

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

    try:
        data = graphql(CREATE_MUTATION, {"input": post_input})
    finally:
        if shutdown_tunnel:
            wait = getattr(args, "tunnel_wait", 60)
            print(f"API call complete. Keeping tunnel alive for {wait}s while Buffer fetches the video...", file=sys.stderr)
            time.sleep(wait)
            shutdown_tunnel()

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
        metavar="URL|PATH",
        help="Image URL, Google Drive share URL, or local file path (repeat for multiple). Local paths served via cloudflared tunnel.",
    )
    p_create.add_argument(
        "--video-url",
        metavar="URL|PATH",
        help="Video URL, Google Drive share URL, or local file path. Local paths are served via a cloudflared tunnel (cloudflared must be installed).",
    )
    p_create.add_argument(
        "--ig-type",
        choices=["post", "reel", "story"],
        help="Instagram post type (required for Instagram channels)",
    )
    p_create.add_argument("--ig-first-comment", metavar="TEXT", help="Instagram first comment")
    p_create.add_argument("--li-first-comment", metavar="TEXT", help="LinkedIn first comment")
    p_create.add_argument("--link-attachment", metavar="URL", help="LinkedIn link attachment URL")
    p_create.add_argument(
        "--tunnel-wait",
        type=int,
        default=60,
        metavar="SECONDS",
        help="Seconds to keep cloudflared tunnel alive after API call (for local video files). Default: 60",
    )

    args = parser.parse_args()
    if args.command == "list":
        cmd_list(args)
    elif args.command == "create":
        cmd_create(args)


if __name__ == "__main__":
    main()
