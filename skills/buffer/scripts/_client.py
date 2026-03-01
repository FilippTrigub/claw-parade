"""Shared GraphQL client for Buffer API."""

import json
import os
import sys

import requests

BUFFER_API_URL = "https://api.buffer.com"


def graphql(query: str, variables: dict | None = None) -> dict:
    """POST a GraphQL query to Buffer API. Returns the data dict."""
    api_key = os.environ.get("BUFFER_API_KEY")
    if not api_key:
        print("Error: BUFFER_API_KEY environment variable is not set.", file=sys.stderr)
        print("Get your token at https://publish.buffer.com/settings/api", file=sys.stderr)
        sys.exit(1)

    payload: dict = {"query": query}
    if variables:
        payload["variables"] = variables

    response = requests.post(
        BUFFER_API_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=30,
    )
    response.raise_for_status()

    body = response.json()

    if "errors" in body:
        print("GraphQL errors:", file=sys.stderr)
        for err in body["errors"]:
            print(f"  {err.get('message', err)}", file=sys.stderr)
        sys.exit(1)

    return body["data"]
