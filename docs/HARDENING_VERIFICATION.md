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

Steps B-F implementation:
- B: 1-3 timestamp-deduplicated JPEGs, centered on the event and ordered; default 3.
  Short/edge clips may have fewer. Gallery/lightbox show precise per-frame timestamps.
  Rebuilt via the BOM-preserving frontend script. Targeted evidence/API/encoding suite: 66 passed.
- C: standalone model checking and thread benchmarks; shared service deadline invocation,
  local AST traversal, cloud import rejection, hidden-value URL warnings, default Python
  socket offline guard, finite JSON/type/timecode validation, no result payload output.
  Optional sweep measures worker counts 1..4 rather than inventing scaling. Fake model tests pass.
- D: strict preflight, model-guarded document finalization, in-memory HEAD zip inspection
  before writing, forbidden-file and real-key scans output counts only. Model note retained.
- E: NoBuild startup option and URLs, status helper with metadata-only log whitelist;
  existing recorded ngrok process is inspected read-only, never stopped/restarted.
- F: README jury-day recovery/runbook, notebook/checker/benchmark instructions, STATUS.md.
  PowerShell 5.1 parses all scripts; BOM tests cover new scripts too.

Step G live verification so far:
- Rebuilt/recreated main stack in 10.71s; image 559,619,621 bytes, Linux amd64.
- Separate localhost-only demo stack with independent Postgres/uploads and a fake test key
  returned exactly 3 JPEGs through jury and UI routes, timestamps 1.5/2.5/3.5 seconds, all
  decoded correctly. The public stack never enabled demo. Test containers/volumes removed.
- Main real HTTP checks, assets, auth, generated uploads and restart persistence passed;
  .env bytes were unchanged and no secret occurred in static assets.
- Full suite with live integration: 118 passed before the final package-initializer scan
  regression was added. Final test result is recorded below.
- PowerShell 5.1 status ran successfully: api/db healthy, local/public health ok,
  model_loaded=false, demo_mode=false, workers=1. Recorded ngrok process alive=True.
  Log output contained approved metadata only. The tunnel was never stopped/reconfigured.
