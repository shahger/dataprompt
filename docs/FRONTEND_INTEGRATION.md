# Frontend integration: inspection and environment

**Historical development record.** This file describes an earlier build stage, not the current release.
For the integrated model, deployment and jury API use the [documentation index](README.md).
Statements about missing models, stubs or unavailable Docker are retained as historical evidence.

## Step 0

Docker client/server 29.8.2; Docker Desktop 4.95.0; Compose 5.6.0.
Server: Linux amd64, 12 CPUs, 8,152,469,504 bytes RAM.
Python 3.13.7; Node 24.16.0; npm 11.13.0. Mode A selected.
Initial git status: untracked .vscode/ and forte-cashier-guard-main/ only.
Moved forte-cashier-guard-main/ -> frontend/forte-cashier-guard-main/.
The existing .env is not printed, changed, regenerated or staged. No ngrok process is started.

## Step 1: original frontend inspection

React 18 + TypeScript + Vite; plain CSS; no client-side router. Package lock present.
Local @fontsource fonts and two local Forte image assets; no remote font/CDN imports found.
Default source was a browser mock, with a source/scenario selector and localStorage settings.
Real source used /api/v1/analyze and /api/v1/jobs/{id}, optional VITE_API_BASE and VITE_API_KEY.
The rule type was {document, clause, url?, placeholder?}; backend rule is a string.
Existing strengths retained: Forte styling, drag/drop, upload progress, video monitor, timeline,
status/results panel and evidence lightbox. Many texts already Russian; technical status labels,
product title and camera labels required translation.
External Forte navigation and mock regulatory URLs must not enter the production bundle.
No login/history/export/batch backend-dependent feature was found. Source/scenario settings
and synthetic browser results will be hidden; original source will be preserved outside src/.

## Initial tree (source/dependency caches omitted)

main.py, db.py, Dockerfile, docker-compose.yml, requirements*.txt, model_service.py.template
static/index.html
frontend/forte-cashier-guard-main/{package.json,package-lock.json,index.html,src/,...}
tools/{common,test_client,load_test,eval_labels}.py
tests/{conftest,test_api,test_tools,test_integration}.py, tests/api_contract.json
docs/{HANDOFF,VERIFICATION,FRONTEND_INTEGRATION}.md
models/.gitkeep
scripts/

## Implemented steps

- Step 2: source edits reproduce the Russian build via scripts/build-frontend.ps1. Runtime URLs
  are relative /ui/api routes. Removed browser credentials, mock imports and mode/scenario UI.
  Original code remains in archive/. Corrected string rule handling, translated display states,
  kept the Forte CSS/assets/monitor/lightbox, added upload-inclusive deadline, 30-second status
  request timeout and up to three consecutive polling failures. Upload POST is never retried
  automatically. Preserved static/index.legacy.html and committed the built resources.
- Static/SPA checks: external http(s) references are rejected except harmless namespace URIs.
  React's informational diagnostic URL is rewritten to a local fragment at build time. Default
  Swagger/ReDoc CDN pages are disabled; /openapi.json stays local. Missing API/health/assets
  remain 404, while UI deep links receive index.html. Windows path separators are normalized.
- Step 3: RULE_IN_DESCRIPTION defaults true; strict jury responses append a nonempty rule to
  description without adding fields. UI description/rule remain separate, unchanged. Tests
  cover both switches, absent/empty/whitespace rules, and repeated reads without mutation.
- Step 4: named deadline argument is optional; legacy one-argument functions work. The deadline
  uses submission monotonic time plus timeout minus min(10s, 10%). Added local rules adapter
  template, comment-only model requirements layer, read-only data mount, and explicit demo
  mode. Demo defaults off, cannot override a real model, and exposes demo_mode in health.
  No model, laws dataset or regulatory references were implemented.
- Step 5: start/stop/check PowerShell scripts parse successfully. ngrok version check: 3.39.11.
  Start/stop scripts were deliberately NOT executed: user owns the current tunnel. Public
  checker reads the key internally only for a video, calls the smoke client in-process and
  uses ngrok-skip-browser-warning. It does not expose the key through process arguments.
  Stop script uses PID+start time+executable identity and affects only its own recorded process.
- Step 6: Russian README and JURY_INSTRUCTIONS; short English MODEL_INTEGRATION; frontend
  README updated. Existing .env is preserved; no token or key is included in documentation.
  powercfg AC commands are documentation only. A read-only powercfg query confirmed the
  LIDACTION alias and its do-nothing index 0; no machine power settings were changed.

## Mode A evidence

Initial rebuild/recreation: 27.74 seconds, core requirements cached. Docker reported Linux amd64.
Initial rebuilt image: 559,189,576 bytes. Final rebuild metrics are recorded below.
Empty mounted models/ and data/ folders (apart from .gitkeep) started successfully, with
no model_service.py. Image inspection confirmed no /app/frontend and no /app/.env.
Server upload directory was empty after generated-video processing.

Real HTTP verifier passed Russian index, 14 asset responses with correct sizes, deep-link SPA,
reserved-route 404s, missing/wrong-key 401s, unknown-job 404, upload response schema and final
no_violation schema. Generated single MOV: 0.129s; three concurrent tiny MOVs:
0.144s / 0.142s / 0.138s; UI route: 0.035s. Completed job remained retrievable after
`docker compose restart api`. The verifier checked .env bytes unchanged during verification.
These are stub/plumbing timings, NOT inference benchmarks.

Browser verification: opened localhost UI, uploaded a generated MOV through its file chooser,
observed processing -> done, Russian verdict/status, local design and no mock selectors.
The tiny generated mp4v MOV was unsupported for browser preview; the Russian fallback appeared
and server analysis still completed. Screenshot: .test-artifacts/frontend-result.png (untracked).
No evidence lightbox was manually exercised with a real model; JSX rendering is connected to
real evidence arrays, and backend tests validate evidence JPEGs and synthetic demo output.

Full pytest with the real HTTP integration enabled passed 56 tests before the final retry/absent
rule regressions were added. Final suite results are recorded below. The existing public API
schema snapshot was not regenerated. One upstream Starlette/httpx deprecation warning remains.

Existing public tunnel: /health and missing-key 401 succeeded. Initial upload/poll attempts
saw transient RemoteDisconnected errors; a generated upload was accepted. After bounded
idempotent GET retries (no POST resubmission), the public smoke script completed with done /
no_violation in 2.565 seconds. This indicates a remaining network-stability risk. No ngrok
process was started, stopped or reconfigured by this task.

## Remaining risks and unverified behavior

- Real model and local laws source are absent: accuracy, regulation mapping, full dataset,
  real inference deadlines and five-video throughput remain unverified.
- Demo behavior is tested with the real code in unit tests, but demo was never enabled on
  the public/local production stack. Its default remains false.
- ngrok launch flag fallback and authentication diagnostics are syntax/code reviewed only;
  executing the launch/stop scripts would violate the instruction not to start/reconfigure ngrok.
- Browser validation covered a real upload and no-violation result; browser evidence enlargement,
  slow-network failures and all camera codecs were not exhaustively exercised.
- One worker + five videos needs roughly <54s/video within the default 270-second
  queue-inclusive budget. Upload/poll time, CPU oversubscription and public UI traffic reduce
  the margin. Threads cannot be killed; models must cooperate with the monotonic deadline.
- API and UI now agree on route paths, field names, string rules and JPEG evidence. No known
  schema mismatch remains. Frontend intentionally restricts selection to MOV even though
  backend decodes any readable uploaded container.
- The existing running local stack is upgraded and left running. The pre-existing untracked
  .vscode/ directory belongs to the user and is untouched. Nothing is pushed.


## Final verification

- Final frontend build: npm ci + TypeScript + Vite succeeded; 14 local assets.
- Final API rebuild/recreation: 12.08 seconds, dependency layers cached.
- Final image size: 559,265,994 bytes (Linux amd64).
- Final pytest with live HTTP integration enabled: 60 passed, one upstream deprecation warning,
  7.22 seconds. No integration test skipped in that run; no API schema snapshot updates.
- Final real HTTP verifier: secret absent from static assets, model_loaded=false, demo_mode=false,
  14 assets, single 0.113s, three concurrent 0.059/0.124/0.118s, UI route 0.101s,
  persistence after restart passed, .env unchanged. All timings use generated tiny videos/stub.
- pip check, Python compilation, PowerShell parsing, Compose config --quiet and git diff --check
  succeeded. Existing ngrok was not started/stopped/reconfigured, and power settings were not changed.
