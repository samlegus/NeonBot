# NAI Job Contract

Use this skill with the repo entrypoint:

```bash
python src/nai_job.py --json '<payload>'
```

For safe preview without execution:

```bash
python src/nai_job.py --json '<payload>' --dry-run
```

## Core Payload

All fields are optional unless required by the selected mode.

```json
{
  "mode": "text | i2i | vibe | precise | i2i+vibe | i2i+precise",
  "prompt": "string",
  "negative_prompt": "string",
  "model": "nai-diffusion-4-5-full",
  "seed": 0,
  "steps": 28,
  "scale": 5.0,
  "sampler": "k_euler_ancestral",
  "width": 832,
  "height": 1216,
  "samples": 1
}
```

## Mode Blocks

### `i2i`

```json
{
  "mode": "i2i",
  "i2i": {
    "image": "input/neon.jpg",
    "strength": 0.75,
    "noise": 0.0
  }
}
```

### `vibe`

```json
{
  "mode": "vibe",
  "vibe": {
    "image": "input/ceru_for_vibe.png",
    "strength": 0.5,
    "fidelity": 1.0
  }
}
```

### `precise`

```json
{
  "mode": "precise",
  "precise": [
    {
      "image": "input/ceru.jpg",
      "type": "character",
      "strength": 0.8,
      "fidelity": 0.6
    }
  ]
}
```

## Validation Rules

- `mode` must be empty/`text` or a `+` combination of `i2i`, `vibe`, `precise`.
- `vibe+precise` is invalid.
- `i2i` requires `i2i.image`.
- `vibe` requires `vibe.image`.
- `precise` requires a non-empty `precise[]`.
- Each `precise[]` item requires `image`.

## Mapping Notes

- `precise[].type` defaults to `character` if omitted.
- `precise[].strength` defaults to `0.6` if omitted.
- `precise[].fidelity` defaults to `1.0` if omitted.
- `seed: 0` means random seed selection.
- Omit `samples` to use the project default of `1`.
- `nai_job.py` converts the JSON payload into safe CLI args for `nai_cli.py`.
- Human-readable failures are preferred over raw tracebacks.

## Example Translations

Telegram message:
`make this one use neon.jpg as the base and ceru.jpg as a precise style ref`

Result:

```json
{
  "mode": "i2i+precise",
  "i2i": {
    "image": "input/neon.jpg"
  },
  "precise": [
    {
      "image": "input/ceru.jpg",
      "type": "style"
    }
  ]
}
```

Telegram message:
`same prompt as before but use ceru_for_vibe.png as vibe`

Interpretation:
- If previous prompt is available in current context, reuse it.
- If previous prompt is not available, ask a short clarifying question instead of inventing it.
