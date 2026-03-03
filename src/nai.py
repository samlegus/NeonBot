import os
import sys
import requests
import json
import base64
import hashlib
import zipfile
from datetime import datetime
from io import BytesIO
from dotenv import load_dotenv
from PIL import Image
from PIL.PngImagePlugin import PngInfo


load_dotenv()
NOVELAI_API_KEY = os.getenv("NOVELAI_CURRENT_API_KEY")
if not NOVELAI_API_KEY:
    raise RuntimeError("NOVELAI_CURRENT_API_KEY is not set")
NOVELAI_API_URL = "https://image.novelai.net/ai/generate-image"

name = None #"img" 
model_name = "nai-diffusion-4-5-full"
prompt = "a slender shota catboy {{{male}}} with black cat ears, glowing purple eyes, wearing a black and purple cyberpunk outfit with neon accents, {{{1boy}}}, clearn lineart, cinematic lighting, ponytail, medium length neon violet hair, blurred night city background"
quality_tags_enabled = True
negative_prompt = "1girl, female, boobs, breasts, text, caption, subtitles, watermark, fur" 
uc_preset_enabled = True
character_prompts = [] 

#https://docs.novelai.net/en/image/controltools
base_image_path = "output/zTest.png" 
base_image_strength = 0.01                        #low = preserve, high = draw more freely
base_image_noise = 0     

#https://docs.novelai.net/en/image/vibetransfer
vibe_transfer_image_path = None #"input/Ceru.png"#"input/Ceru.png" 
vibe_transfer_information_extracted = 1.0           #
vibe_transfer_strength = 1

#https://docs.novelai.net/en/image/precisereference
precise_references = [
    {
        "image_path": None,
        "type": "style",       
        "strength": .8,  # how "hard"?
        "fidelity": .8   # how much detail?
    }
]

repeats = 4 # how many times to repeatedly send a single image request, rate limiting not tested be careful
steps = 28 
guidance = 5.0 
seed = 0 # Set to 0 for random seed, or any integer for reproducible results.
sampler = "k_euler_ancestral"
width = 832
height = 1216
n_samples = 1 # number of images to generate per request (the API supports up to 4, but beware of rate limits and timeouts)
print_payload_debug = False
use_timestamped_output = False
run_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")


def default_output_prefix():
    """Infer a default output prefix from the active input image, if any."""
    candidate_paths = [
        base_image_path,
        vibe_transfer_image_path,
    ]
    candidate_paths.extend(
        ref.get("image_path")
        for ref in (precise_references or [])
        if str(ref.get("image_path") or "").strip()
    )

    for path in candidate_paths:
        if not path:
            continue
        stem = os.path.splitext(os.path.basename(path))[0]
        if stem:
            return stem
    return "img"

def output_filename(prefix, suffix="", ext=""):
    """Build an output filename, optionally prefixed with a run timestamp."""
    filename = (
        prefix
        if isinstance(prefix, str) and prefix.strip()
        else default_output_prefix()
    )
    if use_timestamped_output:
        filename = f"{run_timestamp}_{filename}"
    if suffix:
        filename += f"_{suffix}"
    if ext:
        filename += ext
    path = os.path.join("output", filename)
    if use_timestamped_output:
        return path

    if not os.path.exists(path):
        return path

    stem, extension = os.path.splitext(filename)
    counter = 1
    while True:
        candidate = os.path.join("output", f"{stem}_{counter}{extension}")
        if not os.path.exists(candidate):
            return candidate
        counter += 1


def current_local_metadata():
    """Build minimal human-readable local provenance metadata for saved PNGs."""
    active_precise_images = [
        ref.get("image_path")
        for ref in (precise_references or [])
        if str(ref.get("image_path") or "").strip()
    ]
    return {
        "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "base_image": base_image_path,
        "vibe_image": vibe_transfer_image_path,
        "precise_images": active_precise_images,
    }


def augment_png_metadata(image_path):
    """Append local debug provenance to the saved PNG without affecting generation."""
    local_meta = current_local_metadata()

    with Image.open(image_path) as img:
        pnginfo = PngInfo()

        for key, value in img.info.items():
            if key == "Comment" and isinstance(value, str):
                try:
                    comment_obj = json.loads(value)
                except json.JSONDecodeError:
                    comment_obj = {"original_comment": value}
                comment_obj["local_debug"] = local_meta
                pnginfo.add_text("Comment", json.dumps(comment_obj, ensure_ascii=True))
            elif isinstance(value, bytes):
                pnginfo.add_text(str(key), value.decode("utf-8", errors="replace"))
            else:
                pnginfo.add_text(str(key), str(value))

        if "Comment" not in img.info:
            pnginfo.add_text("Comment", json.dumps({"local_debug": local_meta}, ensure_ascii=True))

        img.save(image_path, pnginfo=pnginfo)

#region Debug Helpers
def redact_payload_for_debug(payload):
    """Redact large image/base64 fields for readable debug output."""
    def scrub(key, value):
        if isinstance(value, dict):
            if key == "director_reference_images_cached":
                redacted_items = []
                for item in value.values():
                    if isinstance(item, str) and len(item) > 80:
                        redacted_items.append(f"<redacted:{len(item)} chars>")
                    else:
                        redacted_items.append(item)
                return redacted_items
            return {k: scrub(k, v) for k, v in value.items()}
        if isinstance(value, list):
            if "image" in key.lower():
                redacted = []
                for item in value:
                    if isinstance(item, str):
                        redacted.append(f"<redacted:{len(item)} chars>")
                    elif isinstance(item, dict):
                        redacted.append(
                            {
                                k: (
                                    f"<redacted:{len(v)} chars>"
                                    if isinstance(v, str) and len(v) > 80
                                    else scrub(k, v)
                                )
                                for k, v in item.items()
                            }
                        )
                    else:
                        redacted.append(item)
                return redacted
            return [scrub(key, item) for item in value]
        if isinstance(value, str) and "image" in key.lower() and len(value) > 80:
            return f"<redacted:{len(value)} chars>"
        if key == "data" and isinstance(value, str) and len(value) > 80:
            return f"<redacted:{len(value)} chars>"
        return value

    return scrub("root", payload)

def print_reference_debug_summary():
    """Print active input features in a compact terminal table."""
    rows = []

    if base_image_path:
        rows.append(
            {
                "feature": "i2i",
                "path": base_image_path,
                "param1": f"strength={base_image_strength}",
                "param2": f"noise={base_image_noise}",
            }
        )

    if vibe_transfer_image_path:
        rows.append(
            {
                "feature": "vibe",
                "path": vibe_transfer_image_path,
                "param1": f"strength={vibe_transfer_strength}",
                "param2": f"info={vibe_transfer_information_extracted}",
            }
        )

    active_precise_references = [
        ref
        for ref in (precise_references or [])
        if str(ref.get("image_path") or "").strip()
    ]
    for idx, ref in enumerate(active_precise_references):
        rows.append(
            {
                "feature": f"precise[{idx}]",
                "path": ref.get("image_path"),
                "param1": f"type={ref.get('type', 'character')}",
                "param2": (
                    f"strength={ref.get('strength', 1.0)}, fidelity={ref.get('fidelity', 1.0)}"
                ),
            }
        )

    if not rows:
        return

    feature_width = max(len(row["feature"]) for row in rows)
    path_width = max(len(str(row["path"])) for row in rows)

    print("Inputs:")
    for row in rows:
        print(
            f"  {row['feature']:<{feature_width}}  "
            f"{str(row['path']):<{path_width}}  "
            f"{row['param1']:<18}  "
            f"{row['param2']}"
        )

def image_to_base64(filepath, force_png=False):
    """Helper to convert local image to base64 string for the API.
    NAI reference images (vibe/precise) require PNG format.
    Set force_png=True to auto-convert JPEGs before encoding.
    """
    if not filepath or not os.path.exists(filepath):
        return None
    if force_png and filepath.lower().endswith(('.jpg', '.jpeg')):
        from PIL import Image
        import io
        img = Image.open(filepath).convert('RGBA')
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        return base64.b64encode(buf.getvalue()).decode('utf-8')
    with open(filepath, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def encode_reference_image(filepath, model, information_extracted=1.0):
    """Pre-encodes a reference image via NAI's /ai/encode-vibe endpoint.
    NAI's Precise Reference for V4+ models requires images processed through
    this endpoint first — raw base64 causes a 500 error.
    Returns the encoded blob as base64, ready for reference_image_multiple[].
    """
    b64 = image_to_base64(filepath, force_png=True)
    if not b64:
        return None
    headers = {
        "Authorization": f"Bearer {NOVELAI_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "image": b64,
        "model": model,
        "informationExtracted": information_extracted
    }
    r = requests.post("https://image.novelai.net/ai/encode-vibe", headers=headers, json=payload)
    if r.status_code == 200:
        return base64.b64encode(r.content).decode('utf-8')
    print(f"  [warn] encode-vibe failed ({r.status_code}) for {filepath}: {r.text[:100]}")
    return None

def normalize_reference_type(reference_type):
    """Map user-friendly precise types to the frontend strings."""
    value = str(reference_type or "character").strip().lower()
    if value in {"character", "style", "character&style"}:
        return value
    if value in {"both", "character_style", "character+style"}:
        return "character&style"
    print(f"  [warn] unknown precise reference type {reference_type!r}; defaulting to 'character'")
    return "character"

def compute_secondary_strength(reference_type, strength, fidelity):
    """Mirror the frontend's secondary strength mapping for precise refs."""
    if reference_type == "character":
        return 1.0 - fidelity
    if reference_type == "style":
        return 1.0 - fidelity
    return 1.0 - fidelity

def build_director_reference_image(filepath):
    """Build the GUI-style inline cached image object for precise refs."""
    if not filepath or not os.path.exists(filepath):
        return None
    from PIL import Image, ImageOps

    with Image.open(filepath) as img:
        rgba = img.convert("RGBA")
        target_size = (1472, 1472)
        contained = ImageOps.contain(rgba, target_size, Image.Resampling.LANCZOS)
        canvas = Image.new("RGBA", target_size, (0, 0, 0, 255))
        offset = (
            (target_size[0] - contained.width) // 2,
            (target_size[1] - contained.height) // 2,
        )
        canvas.paste(contained, offset)
        buf = BytesIO()
        canvas.save(buf, format="PNG")
        png_bytes = buf.getvalue()

    png_b64 = base64.b64encode(png_bytes).decode("utf-8")
    # The GUI sends both a cache_secret_key and inline PNG data. The key does
    # not appear to be a simple SHA-256 of either the PNG bytes or the base64
    # text, but a stable content-derived key is still the safest client value.
    cache_secret_key = hashlib.sha256(png_bytes).hexdigest()
    return {
        "cache_secret_key": cache_secret_key,
        "data": png_b64,
    }

def export_director_reference_debug(parameters):
    """Write precise-reference debug artifacts for comparison against HAR data."""
    refs = parameters.get("director_reference_images_cached", [])
    if not refs:
        return

    os.makedirs("output", exist_ok=True)
    manifest = []
    for idx, ref in enumerate(refs):
        png_b64 = ref.get("data")
        if not png_b64:
            continue
        png_bytes = base64.b64decode(png_b64)
        png_path = output_filename("director_ref", str(idx), ".png")
        with open(png_path, "wb") as handle:
            handle.write(png_bytes)
        manifest.append(
            {
                "index": idx,
                "png_path": png_path,
                "cache_secret_key": ref.get("cache_secret_key"),
                "png_bytes": len(png_bytes),
                "base64_chars": len(png_b64),
                "sha256_png": hashlib.sha256(png_bytes).hexdigest(),
                "sha256_b64txt": hashlib.sha256(png_b64.encode("utf-8")).hexdigest(),
                "head_b64": png_b64[:64],
            }
        )

    debug_path = output_filename("director_ref_debug", ext=".json")
    with open(debug_path, "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2, ensure_ascii=True)
    print(f"Director reference debug written: {debug_path}")

def normalize_payload_for_diff(payload):
    """Collapse unstable/huge fields into diff-friendly summaries."""
    payload_copy = json.loads(json.dumps(payload))
    payload_copy.pop("recaptcha_token", None)
    payload_copy.pop("use_new_shared_trial", None)

    parameters = payload_copy.get("parameters", {})

    director_refs = parameters.get("director_reference_images_cached", [])
    normalized_director_refs = []
    for ref in director_refs:
        data = ref.get("data", "")
        data_bytes = base64.b64decode(data) if data else b""
        normalized_director_refs.append(
            {
                "cache_secret_key": ref.get("cache_secret_key"),
                "data_base64_chars": len(data),
                "data_sha256_png": hashlib.sha256(data_bytes).hexdigest() if data_bytes else None,
                "data_sha256_b64txt": hashlib.sha256(data.encode("utf-8")).hexdigest() if data else None,
                "data_head_b64": data[:64],
            }
        )
    if director_refs:
        parameters["director_reference_images_cached"] = normalized_director_refs

    if "image" in parameters and isinstance(parameters["image"], str):
        image_b64 = parameters["image"]
        image_bytes = base64.b64decode(image_b64)
        parameters["image"] = {
            "base64_chars": len(image_b64),
            "sha256_png": hashlib.sha256(image_bytes).hexdigest(),
            "head_b64": image_b64[:64],
        }

    if "reference_image" in parameters and isinstance(parameters["reference_image"], str):
        ref_b64 = parameters["reference_image"]
        ref_bytes = base64.b64decode(ref_b64)
        parameters["reference_image"] = {
            "base64_chars": len(ref_b64),
            "sha256_bytes": hashlib.sha256(ref_bytes).hexdigest(),
            "head_b64": ref_b64[:64],
        }

    return payload_copy

def export_payload_debug(payload):
    """Write raw and normalized payload JSON for side-by-side GUI diffing."""
    os.makedirs("output", exist_ok=True)
    raw_path = output_filename("script_payload", ext=".json")
    normalized_path = output_filename("script_payload_normalized", ext=".json")

    with open(raw_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=True)
    with open(normalized_path, "w", encoding="utf-8") as handle:
        json.dump(normalize_payload_for_diff(payload), handle, indent=2, ensure_ascii=True, sort_keys=True)

    print(f"Payload debug written: {raw_path}")
    print(f"Payload debug written: {normalized_path}")

#endregion

#region Engine 
def construct_payload():
    """Builds the JSON payload imitating the NovelAI frontend logic."""
    import random
    
    # Process seed
    final_seed = seed if seed != 0 else random.randint(1, 4294967295)
    
    # Process Character Prompts (merge into main prompt)
    final_prompt = prompt
    if character_prompts:
        final_prompt += ", " + ", ".join(character_prompts)
        
    parameters = {
        "params_version": 3,
        "width": width,
        "height": height,
        "scale": guidance,
        "sampler": sampler,
        "steps": steps,
        "n_samples": n_samples,
        "ucPreset": 4 if uc_preset_enabled else 1,
        "qualityToggle": quality_tags_enabled,
        "autoSmea": False,
        "dynamic_thresholding": False,
        "controlnet_strength": 1,
        "legacy": False,
        "add_original_image": True,
        "cfg_rescale": 0,
        "noise_schedule": "karras",
        "legacy_v3_extend": False,
        "skip_cfg_above_sigma": None,
        "use_coords": False,
        "inpaintImg2ImgStrength": 1,
        "seed": final_seed,
        "characterPrompts": [],
        "negative_prompt": negative_prompt,
        "deliberate_euler_ancestral_bug": False,
        "prefer_brownian": True,
        "image_format": "png",
    }

    if "nai-diffusion-4" in model_name:
        parameters["v4_prompt"] = {
            "caption": {
                "base_caption": final_prompt,
                "char_captions": []
            },
            "use_coords": False,
            "use_order": True
        }
        parameters["v4_negative_prompt"] = {
            "caption": {
                "base_caption": negative_prompt,
                "char_captions": []
            },
            "legacy_uc": False
        }
        parameters["legacy_uc"] = False

    payload = {
        "input": final_prompt,
        "model": model_name,
        "action": "generate",
        "parameters": parameters
    }

    # 1. Inject Base Image logic
    if base_image_path:
        b64_img = image_to_base64(base_image_path)
        if b64_img:
            payload["action"] = "img2img"
            parameters["image"] = b64_img
            parameters["strength"] = base_image_strength
            parameters["noise"] = base_image_noise
            parameters["extra_noise_seed"] = final_seed
            
    # 2. Inject Vibe Transfer (Reference Information) logic
    if vibe_transfer_image_path:
        # Use encode-vibe preprocessing for V4/V4.5 compatibility.
        b64_vibe = encode_reference_image(
            vibe_transfer_image_path,
            model_name,
            vibe_transfer_information_extracted
        )
        if b64_vibe:
            parameters["reference_image"] = b64_vibe
            parameters["reference_information_extracted"] = vibe_transfer_information_extracted
            parameters["reference_strength"] = vibe_transfer_strength
            
    # 3. Inject Precise Reference (Character/Style Reference) logic
    # Uses the multi-reference arrays, same underlying API as Vibe Transfer but
    # interpreted differently by the V4/V4.5 model for higher-fidelity matching.
    active_precise_references = [
        ref
        for ref in (precise_references or [])
        if str(ref.get("image_path") or "").strip()
    ]
    if active_precise_references:
        ref_info_extracted = []
        ref_strengths = []
        director_reference_descriptions = []
        director_reference_secondary_strengths = []
        director_reference_images_cached = []
        failed_precise_paths = []
        for ref in active_precise_references:
            image_path = ref.get("image_path")
            print(f"  Preparing reference: {image_path}...")
            reference_type = normalize_reference_type(ref.get("type", "character"))
            reference_strength = ref.get("strength", 1.0)
            reference_fidelity = ref.get("fidelity", 1.0)
            director_image = build_director_reference_image(image_path)
            if director_image:
                # Current API validation requires literal 1.0 for each director
                # reference entry, regardless of the GUI's displayed fidelity.
                ref_info_extracted.append(1.0)
                ref_strengths.append(reference_strength)
                director_reference_descriptions.append(
                    {
                        "caption": {
                            "base_caption": reference_type,
                            "char_captions": []
                        },
                        "legacy_uc": False
                    }
                )
                director_reference_secondary_strengths.append(
                    compute_secondary_strength(reference_type, reference_strength, reference_fidelity)
                )
                director_reference_images_cached.append(director_image)
            else:
                failed_precise_paths.append(image_path)
        if failed_precise_paths:
            missing = ", ".join(repr(path) for path in failed_precise_paths)
            raise FileNotFoundError(
                f"Failed to load precise reference image(s): {missing}"
            )
        if director_reference_images_cached:
            parameters["normalize_reference_strength_multiple"] = True
            parameters["director_reference_descriptions"] = director_reference_descriptions
            parameters["director_reference_information_extracted"] = ref_info_extracted
            parameters["director_reference_strength_values"] = ref_strengths
            parameters["director_reference_secondary_strength_values"] = director_reference_secondary_strengths
            parameters["director_reference_images_cached"] = director_reference_images_cached

    return payload

def run_gui_emulation():
    os.makedirs("output", exist_ok=True)
    headers = {
        "Authorization": f"Bearer {NOVELAI_API_KEY}",
        "Content-Type": "application/json"
    }

    total_repeats = max(1, int(repeats))
    all_saved_paths = []

    for repeat_index in range(total_repeats):
        progress = f"[{repeat_index + 1}/{total_repeats}]"
        print(f"{progress} Preparing payload...")
        print_reference_debug_summary()
        payload = construct_payload()
        # Disabled by default now that payload parity work is mostly complete.
        # export_payload_debug(payload)
        # export_director_reference_debug(payload["parameters"])
        if print_payload_debug:
            print(f"{progress} Full payload:")
            print(json.dumps(redact_payload_for_debug(payload), indent=2, ensure_ascii=True))

        print(f"{progress} Sending generation request to NovelAI API...")
        try:
            response = requests.post(
                NOVELAI_API_URL, headers=headers, json=payload, timeout=180
            )
        except requests.RequestException as exc:
            raise RuntimeError(f"NovelAI request failed: {exc}") from exc

        if response.status_code != 200:
            detail = response.text.strip()
            if len(detail) > 400:
                detail = detail[:400] + "..."
            raise RuntimeError(
                f"NovelAI API returned {response.status_code}: {detail}"
            )

        print(f"{progress} Success! Unpacking zip file...")
        with zipfile.ZipFile(BytesIO(response.content)) as z:
            for idx, filename in enumerate(z.namelist()):
                suffix = str(idx) if len(z.namelist()) > 1 else ""
                output_path = output_filename(name, suffix, ".png")
                with open(output_path, "wb") as f:
                    f.write(z.read(filename))
                augment_png_metadata(output_path)
                print(f"{progress} -> Saved: {output_path}")
                all_saved_paths.append(output_path)

        print(f"{progress} Repeat complete.")

    return all_saved_paths

#endregion
if __name__ == "__main__":
    try:
        run_gui_emulation()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
