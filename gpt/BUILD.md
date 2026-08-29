# Custom GPT build

`gpt/INSTRUCTIONS.txt` is the only Custom GPT instruction source. Keep it at or below 8,000 characters.

Build a private upload package from the canonical dCore source:

```bash
dcore build-gpt --root . --output build/dcore-gpt
```

In the GPT editor:

1. Enable **Code Interpreter & Data Analysis**.
2. Paste `build/dcore-gpt/INSTRUCTIONS.txt` into the instruction field.
3. Upload every file in `build/dcore-gpt/Knowledge/`.

The GPT is a delivery of dCore, not a second database or an Actions service. Do not publish private GPT configuration, icons, eval conversations, or user project files. The repository source is MIT; the dCore name follows `TRADEMARKS.md`.
