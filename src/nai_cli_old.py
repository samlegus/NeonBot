import argparse
import sys
import os

# Import the existing novelai module
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))
import nai

def main():
    parser = argparse.ArgumentParser(description="NovelAI Image Generation CLI")
    
    # Core Generation Arguments
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
    
    # Image-to-Image (i2i) Arguments
    parser.add_argument("--i2i-image", type=str, help="Path to the base image for Image-to-Image.")
    parser.add_argument("--i2i-strength", type=float, help="Strength of the image generation over the base image.")
    parser.add_argument("--i2i-noise", type=float, help="Extra noise added to the base image.")
    
    # Vibe Transfer Arguments
    parser.add_argument("--vibe-image", type=str, help="Path to the reference image for Vibe Transfer.")
    parser.add_argument("--vibe-strength", type=float, help="How much the vibe image influences the output.")
    parser.add_argument("--vibe-fidelity", type=float, help="Information extracted / Fidelity of the vibe transfer.")
    
    # Precise Reference Arguments (Grouped string approach)
    parser.add_argument(
        "--precise-ref", 
        action="append", 
        help="Precise reference in format 'filepath:type:strength:fidelity' (e.g., 'image.png:character:0.8:1.0'). Can be used multiple times."
    )
    # Upscale Arguments (Currently unused / 404 endpoint)
    # parser.add_argument("--upscale", type=str, help="Path to an image to upscale. Skips generation.")
    # parser.add_argument("--upscale-factor", type=int, choices=[2, 4], default=2, help="Upscale factor (2 or 4). Default is 2.")
    
    args = parser.parse_args()
    
    # Override novelai.py globals with any provided CLI arguments
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
    if args.precise_ref is not None:
        nai.precise_references = [] # Clear defaults if CLI provides them
        import re
        for ref_str in args.precise_ref:
            parts = re.split(r'[:,]', ref_str)
            filepath = parts[0]
            
            ref_type = "character"
            if len(parts) > 1 and parts[1].strip():
                ref_type = parts[1].strip().lower()
                
            strength = 0.6
            if len(parts) > 2 and parts[2].strip():
                try:
                    strength = float(parts[2].strip())
                except ValueError:
                    pass
                    
            fidelity = 1.0
            if len(parts) > 3 and parts[3].strip():
                try:
                    fidelity = float(parts[3].strip())
                except ValueError:
                    pass
            
            nai.precise_references.append({
                "image_path": filepath,
                "type": ref_type,
                "strength": strength,
                "fidelity": fidelity
            })

    # If upscaling, do that and skip generation
    # if args.upscale:
    #    nai.run_upscale(args.upscale, args.upscale_factor)
    #    return

    print(f"Starting generation with prompt: {nai.prompt[:50]}...")
    
    # Run the core generation logic
    nai.run_gui_emulation()

if __name__ == "__main__":
    main()
