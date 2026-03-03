import argparse
import sys
import re
import json

# Import the existing novelai module
import nai

CLI_DEFAULTS = {
    "name": None,
    "prompt": "",
    "negative_prompt": "",
    "model_name": "nai-diffusion-4-5-full",
    "seed": 0,
    "steps": 28,
    "guidance": 5.0,
    "sampler": "k_euler_ancestral",
    "width": 832,
    "height": 1216,
    "n_samples": 1,
    "repeats": 1,
    "character_prompts": [],
    "quality_tags_enabled": False,
    "uc_preset_enabled": True,
    "base_image_path": None,
    "base_image_strength": 0.75,
    "base_image_noise": 0.0,
    "vibe_transfer_image_path": None,
    "vibe_transfer_information_extracted": 1.0,
    "vibe_transfer_strength": 0.5,
    "precise_references": [],
    "print_payload_debug": False,
    "use_timestamped_output": False,
}


def apply_cli_defaults():
    """Reset nai.py globals so CLI runs do not inherit scratchpad state."""
    for attr, value in CLI_DEFAULTS.items():
        setattr(nai, attr, list(value) if isinstance(value, list) else value)


def parse_precise_ref(ref_str):
    """Parse precise ref safely on Windows.
    Preferred format: filepath,type,strength,fidelity
    Back-compat format: filepath:type:strength:fidelity (non-Windows paths only)
    """
    if "," in ref_str:
        parts = [p.strip() for p in ref_str.split(",", 3)]
    else:
        # Preserve drive letter for paths like C:\...
        windows_drive = re.match(r"^[A-Za-z]:[\\/]", ref_str)
        if windows_drive:
            drive = ref_str[:2]
            rest = ref_str[2:]
            rest_parts = re.split(r"[:,]", rest, maxsplit=3)
            parts = [drive + rest_parts[0]] + [p.strip() for p in rest_parts[1:]]
        else:
            parts = re.split(r"[:,]", ref_str, maxsplit=3)
            parts = [p.strip() for p in parts]

    filepath = parts[0] if parts and parts[0] else ""
    ref_type = "character"
    strength = 1.0
    fidelity = 1.0

    if len(parts) > 1 and parts[1]:
        ref_type = parts[1].lower()
    if len(parts) > 2 and parts[2]:
        try:
            strength = float(parts[2])
        except ValueError:
            pass
    if len(parts) > 3 and parts[3]:
        try:
            fidelity = float(parts[3])
        except ValueError:
            pass

    return {
        "image_path": filepath,
        "type": ref_type,
        "strength": strength,
        "fidelity": fidelity
    }

def normalize_precise_refs(raw_refs):
    """Parse and filter precise refs, dropping empty placeholders."""
    parsed = []
    for ref_str in raw_refs or []:
        ref = parse_precise_ref(ref_str)
        if ref["image_path"]:
            parsed.append(ref)
    return parsed

def redact_payload_for_debug(payload):
    """Redact large image/base64 fields for readable debug output."""
    def scrub(key, value):
        if isinstance(value, dict):
            return {k: scrub(k, v) for k, v in value.items()}
        if isinstance(value, list):
            if "image" in key.lower():
                redacted = []
                for item in value:
                    if isinstance(item, str):
                        redacted.append(f"<redacted:{len(item)} chars>")
                    else:
                        redacted.append(item)
                return redacted
            return [scrub(key, item) for item in value]
        if isinstance(value, str) and "image" in key.lower() and len(value) > 80:
            return f"<redacted:{len(value)} chars>"
        return value

    return scrub("root", payload)

def main():
    parser = argparse.ArgumentParser(description="NovelAI Image Generation CLI")
    
    # Core Generation Arguments
    parser.add_argument("--name", type=str, help="Base filename for saved output images.")
    parser.add_argument("-p", "--prompt", type=str, help="The positive text prompt to generate.")
    parser.add_argument("-n", "--negative-prompt", type=str, help="The negative prompt (undesired content).")
    parser.add_argument("-m", "--model", type=str, help="The model to use for generation (e.g., nai-diffusion-4-5-full).")
    parser.add_argument("-s", "--seed", type=int, help="Seed for reproducible generations (0 for random).")
    parser.add_argument("--steps", type=int, help="Number of sampling steps.")
    parser.add_argument("--scale", type=float, help="Guidance scale (Prompt adherence).")
    parser.add_argument("--sampler", type=str, help="The sampling method to use.")
    parser.add_argument("-W", "--width", type=int, help="Width of the generated image.")
    parser.add_argument("-H", "--height", type=int, help="Height of the generated image.")
    parser.add_argument("--samples", type=int, help="Number of images to generate.")
    parser.add_argument(
        "--repeats",
        type=int,
        help="Number of sequential single-image requests to send.",
    )
    parser.add_argument(
        "--character-prompt",
        action="append",
        help="Extra character prompt fragment to append. Can be used multiple times.",
    )
    parser.add_argument(
        "--quality-tags",
        dest="quality_tags_enabled",
        action="store_true",
        help="Enable quality tags behavior from nai.py globals.",
    )
    parser.add_argument(
        "--no-quality-tags",
        dest="quality_tags_enabled",
        action="store_false",
        help="Disable quality tags behavior from nai.py globals.",
    )
    parser.add_argument(
        "--uc-preset",
        dest="uc_preset_enabled",
        action="store_true",
        help="Enable GUI-style ucPreset behavior.",
    )
    parser.add_argument(
        "--no-uc-preset",
        dest="uc_preset_enabled",
        action="store_false",
        help="Disable GUI-style ucPreset behavior.",
    )
    parser.set_defaults(
        quality_tags_enabled=None,
        uc_preset_enabled=None,
    )
    
    # Image-to-Image (i2i) Arguments
    parser.add_argument("--i2i-image", type=str, help="Path to the base image for Image-to-Image.")
    parser.add_argument("--i2i-strength", type=float, help="Strength of the image generation over the base image.")
    parser.add_argument("--i2i-noise", type=float, help="Extra noise added to the base image.")
    
    # Vibe Transfer Arguments
    parser.add_argument("--vibe-image", type=str, help="Path to the reference image for Vibe Transfer.")
    parser.add_argument("--vibe-strength", type=float, help="How much the vibe image influences the output.")
    parser.add_argument("--vibe-fidelity", type=float, help="Information extracted / Fidelity of the vibe transfer.")
    parser.add_argument("--debug-payload", action="store_true", help="Print redacted final payload before API request.")
    
    # Precise Reference Arguments (Grouped string approach)
    parser.add_argument(
        "--precise-ref", 
        action="append", 
        help="Precise reference. Preferred: 'filepath,type,strength,fidelity'. Legacy: 'filepath:type:strength:fidelity'. Can be used multiple times."
    )
    # Upscale Arguments (Currently unused / 404 endpoint)
    # parser.add_argument("--upscale", type=str, help="Path to an image to upscale. Skips generation.")
    # parser.add_argument("--upscale-factor", type=int, choices=[2, 4], default=2, help="Upscale factor (2 or 4). Default is 2.")
    
    args = parser.parse_args()
    apply_cli_defaults()

    parsed_precise_refs = normalize_precise_refs(args.precise_ref)
    i2i_mode = args.i2i_image is not None
    vibe_mode = args.vibe_image is not None
    precise_mode = len(parsed_precise_refs) > 0

    # Current compatibility rule:
    # - vibe + precise is invalid
    # - i2i can be combined with either vibe or precise
    if vibe_mode and precise_mode:
        parser.error("Invalid combination: vibe (--vibe-image) and precise (--precise-ref) cannot be used together.")
    
    # Override the CLI baseline with any provided arguments.
    if args.name is not None:
        nai.name = args.name
    if args.prompt is not None:
        nai.prompt = args.prompt
    if args.negative_prompt is not None:
        nai.negative_prompt = args.negative_prompt
    if args.model is not None:
        nai.model_name = args.model
    if args.seed is not None:
        nai.seed = args.seed
    if args.steps is not None:
        nai.steps = args.steps
    if args.scale is not None:
        nai.guidance = args.scale
    if args.sampler is not None:
        nai.sampler = args.sampler
    if args.width is not None:
        nai.width = args.width
    if args.height is not None:
        nai.height = args.height
    if args.samples is not None:
        nai.n_samples = args.samples
    if args.repeats is not None:
        nai.repeats = args.repeats
    if args.character_prompt is not None:
        nai.character_prompts = args.character_prompt
    if args.quality_tags_enabled is not None:
        nai.quality_tags_enabled = args.quality_tags_enabled
    if args.uc_preset_enabled is not None:
        nai.uc_preset_enabled = args.uc_preset_enabled

    # i2i overrides
    if args.i2i_image is not None:
        nai.base_image_path = args.i2i_image
    if args.i2i_strength is not None:
        nai.base_image_strength = args.i2i_strength
    if args.i2i_noise is not None:
        nai.base_image_noise = args.i2i_noise
        
    # Vibe transfer overrides
    if args.vibe_image is not None:
        nai.vibe_transfer_image_path = args.vibe_image
    if args.vibe_strength is not None:
        nai.vibe_transfer_strength = args.vibe_strength
    if args.vibe_fidelity is not None:
        nai.vibe_transfer_information_extracted = args.vibe_fidelity
        
    # Precise reference parsing
    if precise_mode:
        nai.precise_references = parsed_precise_refs

    # If upscaling, do that and skip generation
    # if args.upscale:
    #    nai.run_upscale(args.upscale, args.upscale_factor)
    #    return

    if args.debug_payload:
        payload_preview = nai.construct_payload()
        redacted = redact_payload_for_debug(payload_preview)
        print("Payload preview (redacted):")
        print(json.dumps(redacted, indent=2, ensure_ascii=True))
        return

    print(f"Starting generation with prompt: {nai.prompt[:50]}...")

    try:
        nai.run_gui_emulation()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)

if __name__ == "__main__":
    main()
