import argparse
import json
import os
import sys

import requests
from dotenv import load_dotenv


USER_DATA_URL = "https://api.novelai.net/user/data"


def extract_balance(data):
    """Return the derived Anlas/training-step balance from /user/data."""
    # Maintenance note:
    # The source of truth for this script is the live official NovelAI response
    # from GET https://api.novelai.net/user/data, not any third-party repo.
    # We originally found this endpoint via ComfyUI_NAIDGenerator, but the
    # actual parser here was validated against a real response from this
    # account, where the GUI balance matched:
    #   fixedTrainingStepsLeft + purchasedTrainingSteps
    # If this script breaks in the future, inspect the current /user/data
    # response shape first and update this extractor to match the official
    # response, rather than treating any external project as authoritative.
    subscription = data.get("subscription")
    if not isinstance(subscription, dict):
        raise ValueError("response is missing 'subscription'")

    training = subscription.get("trainingStepsLeft")
    if not isinstance(training, dict):
        raise ValueError("response is missing 'subscription.trainingStepsLeft'")

    fixed_steps = training.get("fixedTrainingStepsLeft")
    purchased_steps = training.get("purchasedTrainingSteps")
    if not isinstance(fixed_steps, int) or not isinstance(purchased_steps, int):
        raise ValueError(
            "response is missing integer training-step balance fields"
        )

    return {
        "fixedTrainingStepsLeft": fixed_steps,
        "purchasedTrainingSteps": purchased_steps,
        "total": fixed_steps + purchased_steps,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Print the current NovelAI balance derived from /user/data"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the parsed balance object as JSON instead of plain text.",
    )
    args = parser.parse_args()

    load_dotenv()
    token = os.getenv("NOVELAI_CURRENT_API_KEY")
    if not token:
        print("ERROR: NOVELAI_CURRENT_API_KEY is not set", file=sys.stderr)
        raise SystemExit(1)

    try:
        response = requests.get(
            USER_DATA_URL,
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )
    except requests.RequestException as exc:
        print(f"ERROR: request failed: {exc}", file=sys.stderr)
        raise SystemExit(1)

    if response.status_code != 200:
        detail = response.text.strip()
        if len(detail) > 300:
            detail = detail[:300] + "..."
        print(
            f"ERROR: NovelAI API returned {response.status_code}: {detail}",
            file=sys.stderr,
        )
        raise SystemExit(1)

    try:
        data = response.json()
    except json.JSONDecodeError as exc:
        print(f"ERROR: response was not valid JSON: {exc}", file=sys.stderr)
        raise SystemExit(1)

    try:
        balance = extract_balance(data)
    except ValueError as exc:
        print(f"ERROR: unexpected /user/data shape: {exc}", file=sys.stderr)
        raise SystemExit(1)

    if args.json:
        print(json.dumps(balance, indent=2, ensure_ascii=True, sort_keys=True))
    else:
        print(balance["total"])


if __name__ == "__main__":
    main()
