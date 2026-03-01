"""Buffer ideas API.

Usage:
    uv run ideas.py create --org-id ORG_ID --title TITLE --text TEXT
"""

import argparse
import json

from _client import graphql

CREATE_MUTATION = """
mutation CreateIdea($input: CreateIdeaInput!) {
  createIdea(input: $input) {
    ... on Idea {
      id
      content {
        title
        text
      }
    }
    ... on MutationError {
      message
    }
  }
}
"""


def cmd_create(args: argparse.Namespace) -> None:
    variables = {
        "input": {
            "organizationId": args.org_id,
            "content": {
                "title": args.title,
                "text": args.text,
            },
        }
    }
    data = graphql(CREATE_MUTATION, variables)
    print(json.dumps(data["createIdea"], indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="Buffer ideas")
    sub = parser.add_subparsers(dest="command", required=True)

    p_create = sub.add_parser("create", help="Create a content idea")
    p_create.add_argument("--org-id", required=True, metavar="ORG_ID")
    p_create.add_argument("--title", required=True)
    p_create.add_argument("--text", required=True)

    args = parser.parse_args()
    if args.command == "create":
        cmd_create(args)


if __name__ == "__main__":
    main()
