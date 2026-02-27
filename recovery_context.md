# NovelAI CLI Project - Context Recovery

This document summarizes the progress, discoveries, and current state of the NovelAI Image Generation CLI project. It is intended to be passed to an AI assistant to quickly restore context.

## Project Goal
Develop a command-line interface (CLI) for the `nai.py` script to control image generation parameters, including precise references and vibe transfer, specifically tailored for the NovelAI V4.5 model.

## Key Files
- **`src/nai.py`**: The core API interaction script. It handles base64 encoding of images, ZIP archive extraction, and constructing the JSON payload for the NovelAI API.
- **`src/nai_cli.py`**: The argparse wrapper. It exposes parameters like `--prompt`, `--negative-prompt`, `--scale`, `--steps`, `--sampler`, and reference image flags. It features flexible delimiter parsing (commas or colons) and config file support (via `@args.txt`).

## Key API Discoveries
- **Precise References (V4.5 Model)**: The web UI for V4.5 does *not* use the standard `reference_` parameters. Instead, it relies on undocumented `director_reference_` arrays:
  - `director_reference_descriptions`: Defines the type (`character` vs `style`).
  - `director_reference_information_extracted`: Maps to "Fidelity".
  - `director_reference_strength_values`: Maps to "Strength".
  - `director_reference_secondary_strength_values`: Calculated differently based on type (for character: `1.0 - strength`, for style: `strength * 0.5`).
- **Image Pre-encoding**: The V4.5 model rejects raw base64 images for precise references. They must first be pre-encoded by sending them to `https://image.novelai.net/ai/encode-vibe`.
- **Pose Locking Limitations**: Vibe Transfer and Precise References cannot be combined effectively in the same request because they clash in the underlying API payload structure.

## Unresolved Issues / Next Steps
- **Upscaler Endpoint**: Attempted to implement an `--upscale` flag hitting `/ai/upscale`. The NovelAI web UI successfully upscales, but manually hitting `image.novelai.net/ai/upscale` or `api.novelai.net/ai/upscale` resulted in a 404 error. The upscale code in `nai.py` and `nai_cli.py` exists but has been temporarily commented out until the correct endpoint/payload format is discovered.

## Logs Directory
A full memory dump of the raw system session logs is available at `C:\Users\Administrator\.gemini\antigravity\brain\3471c79b-f13a-40ce-ad4b-c910649edb62\dump.txt`
