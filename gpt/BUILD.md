# Custom GPT setup

Build with `python -m dcore.cli build-gpt --root . --output build/dcore-gpt` after regenerating the verified manifest.

1. In the GPT editor enable **Code Interpreter & Data Analysis**.
2. Paste `build/dcore-gpt/INSTRUCTIONS.txt` into Instructions (under 8,000 characters).
3. Upload all files from `build/dcore-gpt/Knowledge/`: runtime zip, database, bootstrap, manifest, shared instructions and example contract.
4. Upload a small .dsc project in a conversation and ask for an actual Python lint run. The bootstrap extracts the runtime and installs the database beside the core. The same bootstrap is exercised in the isolated delivery test.

No Actions, API keys or hosted service are needed. Basic analysis needs Python 3.12+ and its standard library. Encrypted packing additionally needs cryptography and is not part of the dependency-free analysis test.

Knowledge indexing does not guarantee that binary files are accessible to Python in every GPT session. If the editor rejects a file type or Code Interpreter cannot locate the runtime files, attach **dcore_runtime.zip**, **dcore.sqlite** and **dcore_bootstrap.py** directly in the conversation. Instructions explicitly prohibit inventing a run when these are unavailable. The local isolated bootstrap test does not verify the hosted GPT product's current upload behavior or account settings.

All public GPT files here are MIT licensed. Keep actual user projects and separately supplied private material out of public releases. The name/brand policy is separate in TRADEMARKS.md.
