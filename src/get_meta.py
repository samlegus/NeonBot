import argparse
import json
from pathlib import Path

from PIL import Image


def make_json_safe(value):
    """Convert image metadata into JSON-serializable values."""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, dict):
        return {str(k): make_json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [make_json_safe(v) for v in value]
    return value


def extract_metadata(image_path):
    image_path = Path(image_path)
    with Image.open(image_path) as img:
        result = {
            "path": str(image_path),
            "format": img.format,
            "mode": img.mode,
            "size": {
                "width": img.width,
                "height": img.height,
            },
            "info": {},
        }

        for key, value in img.info.items():
            result["info"][str(key)] = make_json_safe(value)

        comment = result["info"].get("Comment")
        if isinstance(comment, str):
            try:
                result["comment_json"] = json.loads(comment)
            except json.JSONDecodeError:
                result["comment_json_error"] = "Comment field is not valid JSON"

        exif = img.getexif()
        if exif:
            result["exif"] = {str(tag): make_json_safe(value) for tag, value in exif.items()}

    return result


def main():
    parser = argparse.ArgumentParser(
        description="Extract image metadata and write it to <file>.json"
    )
    parser.add_argument("file", help="Path to the image file to inspect.")
    args = parser.parse_args()

    image_path = Path(args.file)
    if not image_path.exists():
        raise SystemExit(f"File not found: {image_path}")

    metadata = extract_metadata(image_path)
    output_path = image_path.with_name(image_path.name + ".json")
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(metadata, handle, indent=2, ensure_ascii=True, sort_keys=True)

    print(output_path)


if __name__ == "__main__":
    main()
