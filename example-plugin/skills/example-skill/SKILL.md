---
name: example-skill
description: Counts words, characters, and lines in text the user provides, using a bundled Python script. Use this as a starting template when adding a new skill to this repository, or when a user asks for a quick word/character/line count of some text.
license: MIT
metadata:
  maintainer: your-org
---

# Example skill

This is a template skill for the `example-plugin` scaffold. Copy this directory when
starting a new skill in this repository.

## When to use this skill

Use this skill when the user asks you to count words, characters, or lines in
a piece of text or a text file.

## How to use this skill

Run the bundled script against a file path or piped text, then report the
counts back to the user:

```bash
./scripts/word_count.py path/to/file.txt
# or
echo "some text" | ./scripts/word_count.py
```

The script prints a small JSON object with `lines`, `words`, and `chars`
counts. Summarize that JSON for the user rather than pasting it verbatim.

## Notes for skill authors

- `scripts/word_count.py` is a self-contained [PEP 723](https://peps.python.org/pep-0723/)
  script with inline metadata, run via `uv run` (see the shebang line). It
  needs no separate install step, which keeps this skill directory copyable
  on its own.
- Keep skill scripts small, deterministic, and side-effect free unless the
  skill's purpose requires side effects (and say so clearly in `description`).
