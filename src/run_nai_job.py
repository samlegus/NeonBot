import argparse
import json
import subprocess
import sys
from pathlib import Path


def load_payload(args):
    if args.json:
        return json.loads(args.json)
    if args.json_file:
        return json.loads(Path(args.json_file).read_text(encoding="utf-8-sig"))
    raise ValueError("Provide --json or --json-file")


def add_opt(argv, flag, value):
    if value is None:
        return
    argv.extend([flag, str(value)])


def validate_payload(payload):
    if not isinstance(payload, dict):
        raise ValueError("payload must be a JSON object")

    raw_mode = payload.get("mode")
    if raw_mode in (None, "", "text"):
        mode_parts = set()
    else:
        mode_parts = {part.strip() for part in str(raw_mode).split("+") if part.strip()}

    valid_parts = {"i2i", "vibe", "precise"}
    if not mode_parts.issubset(valid_parts):
        raise ValueError("mode must be text/empty or a '+' combination of: i2i, vibe, precise")
    if "vibe" in mode_parts and "precise" in mode_parts:
        raise ValueError("Invalid mode combination: vibe+precise is not supported")

    if "i2i" in mode_parts:
        i2i = payload.get("i2i", {})
        if not i2i.get("image"):
            raise ValueError("i2i mode requires i2i.image")

    if "vibe" in mode_parts:
        vibe = payload.get("vibe", {})
        if not vibe.get("image"):
            raise ValueError("vibe mode requires vibe.image")

    if "precise" in mode_parts:
        precise = payload.get("precise", [])
        if not isinstance(precise, list) or not precise:
            raise ValueError("precise mode requires a non-empty precise array")
        for idx, ref in enumerate(precise):
            if not isinstance(ref, dict):
                raise ValueError(f"precise[{idx}] must be an object")
            if not ref.get("image"):
                raise ValueError(f"precise[{idx}].image is required")

    return mode_parts


def build_argv(payload):
    argv = []

    add_opt(argv, "--prompt", payload.get("prompt"))
    add_opt(argv, "--negative-prompt", payload.get("negative_prompt"))
    add_opt(argv, "--model", payload.get("model"))
    add_opt(argv, "--seed", payload.get("seed"))
    add_opt(argv, "--steps", payload.get("steps"))
    add_opt(argv, "--scale", payload.get("scale"))
    add_opt(argv, "--sampler", payload.get("sampler"))
    add_opt(argv, "--width", payload.get("width"))
    add_opt(argv, "--height", payload.get("height"))
    add_opt(argv, "--samples", payload.get("samples"))

    mode_parts = validate_payload(payload)

    if "i2i" in mode_parts:
        i2i = payload.get("i2i", {})
        add_opt(argv, "--i2i-image", i2i.get("image"))
        add_opt(argv, "--i2i-strength", i2i.get("strength"))
        add_opt(argv, "--i2i-noise", i2i.get("noise"))
    if "vibe" in mode_parts:
        vibe = payload.get("vibe", {})
        add_opt(argv, "--vibe-image", vibe.get("image"))
        add_opt(argv, "--vibe-strength", vibe.get("strength"))
        add_opt(argv, "--vibe-fidelity", vibe.get("fidelity"))
    if "precise" in mode_parts:
        precise = payload.get("precise", [])
        for ref in precise:
            image = ref.get("image")
            ref_type = ref.get("type", "character")
            strength = ref.get("strength", 0.6)
            fidelity = ref.get("fidelity", 1.0)
            if image:
                argv.extend(
                    ["--precise-ref", f"{image},{ref_type},{strength},{fidelity}"]
                )

    return argv


def main():
    parser = argparse.ArgumentParser(description="Run nai_cli_v2.py from JSON payload")
    parser.add_argument("--json", type=str, help="Inline JSON payload")
    parser.add_argument("--json-file", type=str, help="Path to JSON payload file")
    parser.add_argument(
        "--dry-run", action="store_true", help="Print command without executing"
    )
    args = parser.parse_args()

    payload = load_payload(args)
    cli_args = build_argv(payload)

    cmd = [sys.executable, str(Path(__file__).with_name("nai_cli_v2.py")), *cli_args]

    if args.dry_run:
        print(" ".join(f'"{p}"' if " " in p else p for p in cmd))
        return

    proc = subprocess.run(cmd)
    raise SystemExit(proc.returncode)


if __name__ == "__main__":
    main()
