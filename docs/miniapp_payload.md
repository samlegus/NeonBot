# Mini App Payload Contract

`nai_job.py` accepts either:
- `--json '<payload>'`
- `--json-file <path>`

## Core fields

All fields are optional unless required by mode.
`seed: 0` means random seed selection.
Omit `samples` to use the project default of `1`.

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

## Mode blocks

### i2i
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

### vibe
```json
{
  "mode": "vibe",
  "vibe": {
    "image": "input/ceru.jpg",
    "strength": 0.5,
    "fidelity": 1.0
  }
}
```

### precise
```json
{
  "mode": "precise",
  "precise": [
    {
      "image": "input/ceru.jpg",
      "type": "style",
      "strength": 0.9,
      "fidelity": 0.9
    }
  ]
}
```

### Combined modes

Allowed:
- `i2i+vibe`
- `i2i+precise`

Blocked:
- `vibe+precise`

## Validation rules (enforced)

- `mode` must be empty/`text` or a `+` combination of `i2i`, `vibe`, `precise`.
- `vibe+precise` is rejected.
- `i2i` mode requires `i2i.image`.
- `vibe` mode requires `vibe.image`.
- `precise` mode requires non-empty `precise[]`, and each item needs `image`.
