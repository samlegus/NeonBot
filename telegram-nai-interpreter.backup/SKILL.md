---
name: telegram-nai-interpreter
description: Interpret informal, messy, shorthand, or contradictory Telegram messages into valid NovelAI generation requests for this repo. Use when an OpenClaw agent needs to turn a human Telegram message into a safe `src/nai_job.py` JSON payload, detect the correct generation mode (`text`, `i2i`, `vibe`, `precise`, `i2i+vibe`, `i2i+precise`), normalize partial settings, ask minimal clarifying questions, and return human-readable errors.
---

# Telegram NAI Interpreter

Convert a Telegram message into a valid `nai_job.py` request for this repository.
Prefer a usable result over a perfect interpretation, but do not invent missing required inputs such as image paths.

## Workflow

1. Read the user message and extract:
   - positive prompt text
   - negative prompt text
   - requested mode hints (`img2img`, vibe, reference, style ref, etc.)
   - explicit generation settings such as width, height, steps, scale, sampler, seed, samples
   - referenced input images
2. Choose the narrowest valid `nai_job.py` mode.
3. Normalize the request into a JSON payload that matches the repository contract.
4. If a required field is missing, ask one short clarifying question instead of guessing.
5. Present the final command or payload in a way that a human can read and debug quickly.

## Mode Selection

- Use `text` when no image input is required.
- Use `i2i` when the user wants to transform a base image.
- Use `vibe` when the user wants one reference image to influence style/composition broadly.
- Use `precise` when the user wants one or more explicit reference images with `type`, `strength`, and `fidelity`.
- Use `i2i+vibe` when both a base image and a vibe image are provided.
- Use `i2i+precise` when both a base image and precise references are provided.
- Reject `vibe+precise`; this repo does not support that combination.

## Interpretation Rules

- Treat casual separators, shorthand, and sloppy phrasing as normal. Extract the meaning; do not complain about wording.
- Preserve the user's actual prompt intent. Clean whitespace and obvious punctuation noise, but do not rewrite the prompt into a different aesthetic.
- If the user says "same settings as before" and no prior structured state is available in context, say that the previous settings are unavailable and ask for the missing pieces.
- If the user provides a reference image but does not specify `type` for `precise`, default to `character`.
- If the user provides a precise reference without `strength` or `fidelity`, default to the repo defaults used by `nai_job.py` mapping:
  - `strength`: `0.6`
  - `fidelity`: `1.0`
- If the user does not specify `samples`, default to `1`. Do not increase batch size unless the user explicitly asks for it.
- Keep human readability first when errors occur. Prefer short explanations like `Missing vibe image path.` over schema jargon.

## Clarification Policy

Ask a follow-up only when one of these is true:
- a required image path is missing
- the user requests an unsupported mode combination
- the message is too ambiguous to determine whether the image is base, vibe, or precise input
- the user references a file that does not exist in known context

If clarification is needed, ask one short concrete question, not a checklist.

## Output Shape

When producing an executable request, prefer:

```bash
python src/nai_job.py --json '<payload>'
```

When debugging or previewing, prefer:

```bash
python src/nai_job.py --json '<payload>' --dry-run
```

Keep payloads single-line unless the caller explicitly wants pretty JSON.

## Error Handling

- Surface repository errors as-is when they are already human-readable.
- Keep important failures visible:
  - invalid JSON payload
  - invalid mode combination
  - missing required image
  - NovelAI API failure
  - concurrent generation lock (`429`)
- Treat `Concurrent generation is locked` as retryable, not as a malformed request.

## References

- Read [references/nai-job-contract.md](references/nai-job-contract.md) for the exact payload fields, defaults, and command examples.
