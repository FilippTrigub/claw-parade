"""Buffer channels API.

Usage:
    uv run channels.py list --org-id ORG_ID [--unlocked]
    uv run channels.py get --channel-id CHANNEL_ID
"""

import argparse
import json

from _client import graphql

LIST_QUERY = """
query ListChannels($input: ChannelsInput!) {
  channels(input: $input) {
    id
    name
    displayName
    service
    avatar
    isQueuePaused
    isLocked
  }
}
"""

GET_QUERY = """
query GetChannel($id: ChannelId!) {
  channel(input: { id: $id }) {
    id
    name
    displayName
    service
    avatar
    isQueuePaused
    isLocked
  }
}
"""


def cmd_list(args: argparse.Namespace) -> None:
    variables: dict = {"input": {"organizationId": args.org_id}}
    if args.unlocked:
        variables["input"]["filter"] = {"isLocked": False}
    data = graphql(LIST_QUERY, variables)
    print(json.dumps(data["channels"], indent=2))


def cmd_get(args: argparse.Namespace) -> None:
    data = graphql(GET_QUERY, {"id": args.channel_id})
    print(json.dumps(data["channel"], indent=2))



def main() -> None:
    parser = argparse.ArgumentParser(description="Buffer channels")
    sub = parser.add_subparsers(dest="command", required=True)

    p_list = sub.add_parser("list", help="List channels for an organization")
    p_list.add_argument("--org-id", required=True, metavar="ORG_ID", help="Organization ID")
    p_list.add_argument("--unlocked", action="store_true", help="Return only unlocked channels")

    p_get = sub.add_parser("get", help="Get a single channel by ID")
    p_get.add_argument("--channel-id", required=True, metavar="CHANNEL_ID", help="Channel ID")

    args = parser.parse_args()
    if args.command == "list":
        cmd_list(args)
    elif args.command == "get":
        cmd_get(args)


if __name__ == "__main__":
    main()
