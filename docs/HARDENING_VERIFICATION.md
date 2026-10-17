# Hardening verification

Mode A: Docker client/server 29.8.2, Compose 5.6.0, Linux amd64,
12 Docker CPUs, 8,152,469,504 bytes RAM. Python 3.13.7; Node 24.16.0.
Initial tracked state: four PowerShell scripts modified only by UTF-8 BOM additions.
Pre-existing untracked .vscode/ remains user-owned and untouched.
Baseline architecture: one FastAPI process, ThreadPoolExecutor, Postgres persistence,
Russian React/Vite build committed in static/, no model or rules module present.
The existing running ngrok session must not be stopped, restarted, or reconfigured.
The existing .env will only be read internally for authorized validation; no copies or
key values are written or printed. API schema snapshot remains authoritative.

Step A: normalized scripts to UTF-8 BOM + CRLF without changing content, retained the
user's existing BOM fix, added Git checkout rules and BOM/PowerShell 5.1 parser tests.
