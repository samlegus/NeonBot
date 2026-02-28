import os
import sys
import requests
import json
import base64
import zipfile
from io import BytesIO
from dotenv import load_dotenv


load_dotenv()
NOVELAI_API_KEY = os.getenv("NOVELAI_CURRENT_API_KEY")
if not NOVELAI_API_KEY:
    raise RuntimeError("NOVELAI_CURRENT_API_KEY is not set")
NOVELAI_API_URL = "https://image.novelai.net/ai/generate-image"

name = "img" #optional finename to be overriden
model_name = "nai-diffusion-4-5-full"
prompt = "An emo shota snow leopard male with dark purple hair on his knees with a suggestive expression. tease, femboy, snow leopard, cyberpunk" 
quality_tags_enabled = True
negative_prompt = "lowres, bad anatomy, bad hands, text, error, missing fingers, extra digit" 
uc_preset_enabled = True
character_prompts = [] 

#https://docs.novelai.net/en/image/controltools
base_image_path = None 
base_image_strength = 0.75   
base_image_noise = 0.0      

#https://docs.novelai.net/en/image/vibetransfer
vibe_transfer_image_path = None 
vibe_transfer_information_extracted = 1.0 
vibe_transfer_strength = 0.5             

#https://docs.novelai.net/en/image/precisereference
precise_references = [
    {
        "image_path": "input/ceru.jpg",
        "type": "style",       
        "fidelity": .9, # how much detail?
        "strength": .9  # how "hard"?
    }
]

steps = 28 
guidance = 5.0 
seed = 0 
sampler = "k_euler_ancestral"
width = 832
height = 1216
n_samples = 1



#Engine
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
        "width": width,
        "height": height,
        "scale": guidance,
        "sampler": sampler,
        "steps": steps,
        "n_samples": n_samples,
        "ucPreset": 0 if uc_preset_enabled else 1, # Depending on API rules, 0 or 1 maps to presets
        "qualityToggle": quality_tags_enabled,
        "seed": final_seed,
        "negative_prompt": negative_prompt,
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
            }
        }

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
    if precise_references:
        ref_images = []
        ref_info_extracted = []
        ref_strengths = []
        for ref in precise_references:
            print(f"  Encoding reference: {ref.get('image_path')}...")
            encoded = encode_reference_image(ref.get("image_path"), model_name, ref.get("fidelity", 1.0))
            if encoded:
                ref_images.append(encoded)
                ref_info_extracted.append(ref.get("fidelity", 1.0))
                ref_strengths.append(ref.get("strength", 0.6))
        if ref_images:
            parameters["reference_image_multiple"] = ref_images
            parameters["reference_information_extracted_multiple"] = ref_info_extracted
            parameters["reference_strength_multiple"] = ref_strengths
            parameters["normalize_reference_strength_multiple"] = True

    return payload

def run_gui_emulation():
    print("Preparing payload...")
    payload = construct_payload()
    print("Full payload:")
    print(json.dumps(redact_payload_for_debug(payload), indent=2, ensure_ascii=True))
    os.makedirs("output", exist_ok=True)
    
    headers = {
        "Authorization": f"Bearer {NOVELAI_API_KEY}",
        "Content-Type": "application/json"
    }

    print("Sending generation request to NovelAI API...")
    try:
        response = requests.post(NOVELAI_API_URL, headers=headers, json=payload, timeout=180)
    except requests.RequestException as exc:
        raise RuntimeError(f"NovelAI request failed: {exc}") from exc

    if response.status_code == 200:
        print("Success! Unpacking zip file...")
        saved_paths = []
        with zipfile.ZipFile(BytesIO(response.content)) as z:
            for idx, filename in enumerate(z.namelist()):
                # Find the next available filename so we never overwrite existing outputs
                counter = 0
                while True:
                    output_path = os.path.join("output", f"{name}_{counter}.png")
                    if not os.path.exists(output_path):
                        break
                    counter += 1
                with open(output_path, "wb") as f:
                    f.write(z.read(filename))
                print(f"-> Saved: {output_path}")
                saved_paths.append(output_path)
        return saved_paths
    else:
        detail = response.text.strip()
        if len(detail) > 400:
            detail = detail[:400] + "..."
        raise RuntimeError(f"NovelAI API returned {response.status_code}: {detail}")

def run_upscale(image_filepath, scale_factor=2):
    print(f"Preparing upscale payload for {image_filepath} at {scale_factor}x...")
    from PIL import Image
    os.makedirs("output", exist_ok=True)
    try:
        with Image.open(image_filepath) as img:
            w, h = img.size
    except Exception as e:
        print(f"Error opening image: {e}")
        return

    b64_img = image_to_base64(image_filepath)
    if not b64_img:
        print("Failed to encode image to base64.")
        return

    payload = {
        "image": b64_img,
        "width": w,
        "height": h,
        "scale": scale_factor
    }
    
    headers = {
        "Authorization": f"Bearer {NOVELAI_API_KEY}",
        "Content-Type": "application/json"
    }

    url = "https://image.novelai.net/ai/upscale"
    print("Sending upscale request to NovelAI API...")
    response = requests.post(url, headers=headers, json=payload)

    if response.status_code == 200:
        print("Success! Unpacking zip file...")
        with zipfile.ZipFile(BytesIO(response.content)) as z:
            for idx, filename in enumerate(z.namelist()):
                counter = 0
                while True:
                    output_path = os.path.join("output", f"upscale_{counter}.png")
                    if not os.path.exists(output_path):
                        break
                    counter += 1
                with open(output_path, "wb") as f:
                    f.write(z.read(filename))
                print(f"-> Saved: {output_path}")
    else:
        print(f"Error {response.status_code}: {response.text}")

if __name__ == "__main__":
    try:
        run_gui_emulation()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
