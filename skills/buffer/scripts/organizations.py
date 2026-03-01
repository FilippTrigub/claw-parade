"""Buffer organizations API.

Usage:
    uv run organizations.py list
"""

import argparse
import json
import sys

from _client import graphql

QUERY = """
query {
  account {
    organizations {
      id
      name
      ownerEmail
    }
  }
}
"""


def cmd_list(_args: argparse.Namespace) -> None:
    data = graphql(QUERY)
    orgs = data["account"]["organizations"]
    print(json.dumps(orgs, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="Buffer organizations")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list", help="List organizations")

    args = parser.parse_args()
    if args.command == "list":
        cmd_list(args)


if __name__ == "__main__":
    main()
