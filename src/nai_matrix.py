#!/usr/bin/env python3
"""
NAI Matrix - Systematic NovelAI reference method comparison
Generates images across i2i, vibe, and precise reference methods with configurable parameters.
"""

import argparse
import sys

def parse_strengths(strength_str):
    """Parse comma-separated strength values."""
    if not strength_str:
        return []
    return [float(s.strip()) for s in strength_str.split(',')]

def parse_types(type_str):
    """Parse comma-separated precise ref types."""
    if not type_str:
        return []
    return [t.strip() for t in type_str.split(',')]

def generate_commands(args):
    """Generate all CLI commands for the matrix."""
    commands = []
    
    # i2i commands
    for strength in parse_strengths(args.i2i_strengths):
        cmd = (
            f'./.venv/bin/python src/nai_cli.py '
            f'--name "{args.output_name}_i2i_{int(strength*100)}" '
            f'-p "{args.prompt}" '
            f'--i2i-image "{args.input_image}" '
            f'--i2i-strength {strength} '
            f'--repeats {args.repeats}'
        )
        commands.append(("i2i", strength, cmd))
    
    # Vibe commands
    for strength in parse_strengths(args.vibe_strengths):
        cmd = (
            f'./.venv/bin/python src/nai_cli.py '
            f'--name "{args.output_name}_vibe_{int(strength*100)}" '
            f'-p "{args.prompt}" '
            f'--vibe-image "{args.input_image}" '
            f'--vibe-strength {strength} '
            f'--vibe-fidelity 1.0 '
            f'--repeats {args.repeats}'
        )
        commands.append(("vibe", strength, cmd))
    
    # Precise reference commands
    for ptype in parse_types(args.precise_types):
        for strength in parse_strengths(args.precise_strengths):
            type_abbr = ptype.replace('&', '').replace('character', 'char')[:10]
            cmd = (
                f'./.venv/bin/python src/nai_cli.py '
                f'--name "{args.output_name}_precise_{type_abbr}_{int(strength*100)}" '
                f'-p "{args.prompt}" '
                f'--precise-ref "{args.input_image},{ptype},{strength},1.0" '
                f'--repeats {args.repeats}'
            )
            commands.append((f"precise_{ptype}", strength, cmd))
    
    return commands

def estimate_cost(commands, repeats):
    """Estimate anlas cost (roughly 6 anlas per image)."""
    total_images = len(commands) * repeats
    return total_images * 6

def generate_markdown(args, commands):
    """Generate Obsidian markdown content."""
    md = f"""# {args.output_name.replace('_', ' ').title()} Matrix

*Generated with NAI Matrix*  
*Prompt: {args.prompt}*  
*Reference: {args.input_image}*

---

"""
    
    # Group by method
    methods = {}
    for method, strength, cmd in commands:
        if method not in methods:
            methods[method] = []
        methods[method].append((strength, cmd))
    
    # Generate sections
    for method, items in methods.items():
        md += f"## Method: {method.replace('_', ' ').title()}\n\n"
        
        for strength, cmd in items:
            base_name = f"{args.output_name}_{method}_{int(strength*100)}"
            if method.startswith("precise_"):
                ptype = method.replace("precise_", "")
                type_abbr = ptype.replace('&', '').replace('character', 'char')[:10]
                base_name = f"{args.output_name}_precise_{type_abbr}_{int(strength*100)}"
            
            md += f"### Strength {strength}\n\n"
            md += "| " + " | ".join([f'<img src="../output/{base_name}{suffix}.png" width="{args.md_width}" alt="{base_name}{suffix}">' for suffix in ["", "_1", "_2", "_3"][:args.repeats]]) + " |\n"
            md += "|" + "|".join([":---:" for _ in range(args.repeats)]) + "|\n"
            md += "| " + " | ".join([f'`{base_name}{suffix}.png`' for suffix in ["", "_1", "_2", "_3"][:args.repeats]]) + " |\n\n"
    
    # Summary table
    md += "---\n\n## Summary\n\n"
    md += f"| Method | Configurations | Repeats | Subtotal |\n"
    md += f"|--------|----------------|---------|----------|\n"
    
    total = 0
    for method, items in methods.items():
        subtotal = len(items) * args.repeats
        total += subtotal
        md += f"| {method} | {len(items)} | {args.repeats} | {subtotal} |\n"
    
    md += f"| **Total** | | | **{total}** |\n"
    
    return md

def main():
    parser = argparse.ArgumentParser(description='NAI Matrix - NovelAI reference method comparison')
    parser.add_argument('--prompt', required=True, help='Base generation prompt')
    parser.add_argument('--input-image', required=True, help='Reference image path')
    parser.add_argument('--output-name', required=True, help='Base name for outputs')
    parser.add_argument('--repeats', type=int, default=4, help='Images per configuration')
    parser.add_argument('--i2i-strengths', default='0.25,0.5,0.75', help='Comma-separated i2i strengths')
    parser.add_argument('--vibe-strengths', default='0.25,0.5,0.75,1.0', help='Comma-separated vibe strengths')
    parser.add_argument('--precise-strengths', default='0.25,0.5,0.75,1.0', help='Comma-separated precise strengths')
    parser.add_argument('--precise-types', default='character,style,character&style', help='Comma-separated precise types')
    parser.add_argument('--md-width', type=int, default=300, help='Image width in markdown (px)')
    parser.add_argument('--vault-path', default='neon-bot/notes/', help='Obsidian vault path')
    parser.add_argument('--dry-run', action='store_true', help='Print commands without running')
    
    args = parser.parse_args()
    
    # Generate commands
    commands = generate_commands(args)
    
    if not commands:
        print("Error: No configurations generated. Check your strength/type parameters.")
        sys.exit(1)
    
    # Calculate cost
    cost = estimate_cost(commands, args.repeats)
    total_images = len(commands) * args.repeats
    
    # Print summary
    print(f"\n🎨 NAI Matrix Configuration")
    print(f"=" * 50)
    print(f"Output name: {args.output_name}")
    print(f"Total configs: {len(commands)}")
    print(f"Repeats per config: {args.repeats}")
    print(f"Total images: {total_images}")
    print(f"Est. anlas cost: ~{cost}")
    print(f"=" * 50)
    
    if args.dry_run:
        print("\n📋 Commands to run (sequentially):")
        for i, (method, strength, cmd) in enumerate(commands, 1):
            print(f"\n{i}. [{method} @ {strength}]")
            print(cmd)
        sys.exit(0)
    
    # Generate markdown
    md_content = generate_markdown(args, commands)
    print("\n✅ Markdown template generated")
    print(f"Save to: {args.vault_path}{args.output_name}_matrix.md")
    
    # Output the subagent task
    print("\n🚀 Subagent task payload:")
    print("-" * 50)
    print(f"""Run NovelAI Matrix generation and DELIVER images.

Workdir: /home/ceru/.openclaw/workspace-neon/neon-bot

## Generation ({len(commands)} commands, run SEQUENTIALLY):

""")
    for method, strength, cmd in commands:
        print(f"# {method} @ {strength}")
        print(cmd)
        print()
    
    print(f"""## Delivery:
Total: {total_images} images in {total_images // 8 + (1 if total_images % 8 else 0)} batches

## Create MD at: {args.vault_path}{args.output_name}_matrix.md

```markdown
{md_content}
```
""")

if __name__ == '__main__':
    main()
