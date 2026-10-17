# Environment check (Step 1)

- Docker client: 29.8.2, windows/amd64, context desktop-linux.
- Docker Compose: v5.6.0.
- Docker server/info: unavailable; named pipe dockerDesktopLinuxEngine does not exist.
- Python: 3.13.7; pip: 25.2.
- Network: pip download requests succeeded after sandbox network approval (requests 2.34.2).
- Mode B: Docker engine unavailable. No image pull/build or real Postgres stack verification is possible in this state.

Step 0 moves (original files preserved by moving):
- index.html -> static/index.html
- test_client.py -> tools/test_client.py
- load_test.py -> tools/load_test.py
- eval_labels.py -> tools/eval_labels.py
- datathon26_handoff_en.md -> docs/HANDOFF.md

Created models/.gitkeep and .gitignore; existing .dockerignore and .env.example were present.
