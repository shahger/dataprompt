# Current project status

## Architecture and constraints

One FastAPI/uvicorn process serves the Russian Forte React/Vite build from static/.
Jury routes require X-API-Key; browser UI uses same-origin /ui/api routes without embedding
credentials. ThreadPoolExecutor performs local CPU analysis; Postgres persists jobs and JPEG
results. Uploaded videos are deleted on completion/failure; interrupted files are cleaned at
startup. The public ngrok tunnel forwards to port 8000 and must remain untouched during checks.

The model and laws database are still pending. No cloud AI, CUDA, runtime model downloads,
remote fonts or CDN resources are part of the service. Model/rules templates and a cached
requirements-model layer are ready. Empty model/data mounts work.

## Decisions

- Preserve the public API and saved schema snapshot. Rules can be appended to description
  for strict jury output; UI keeps its separate rule string.
- EVIDENCE_FRAMES defaults to 3 (validated 1..3): event +/-1 second, chronological, clamped
  and deduplicated by decoded timestamp. The center/event frame always survives selection.
- Preserve Aidyn's design; local fonts/assets; browser gallery/lightbox handles all frames.
- PowerShell 5.1 scripts are UTF-8 BOM with CRLF checkout rules and parser/BOM regression tests.
- Standalone diagnostics share the service deadline call helper. Offline socket monkeypatches
  and static source scanning are useful checks, not an OS security sandbox.
- Benchmarks report measured worker counts only; Python threads cannot be killed.
- Preflight is deliberately strict. AllowStub only changes model readiness to WARN; missing
  finalization or a dirty Git tree still fails. Finalization requires a connected real model.
- Clean archives contain committed HEAD only and are scanned in memory before being saved.
  Existing .env and the running tunnel are never changed by hardening/verification.

## Verified and pending

Previous stage: 60 tests plus real HTTP, UI upload, assets, auth and restart persistence verified.
Current stage adds evidence, diagnostics, archive/preflight and PowerShell 5.1 tests. Detailed
current results are recorded in docs/HARDENING_VERIFICATION.md after the final run.
Pending: Alfia's real model, local law sources, license/source review, labeled accuracy and
several-video CPU throughput on the Intel i5-13500. The user-owned untracked .vscode/ is
untouched; it makes strict preflight's clean-tree check fail until the user resolves it.
The pre-model jury note is retained until a real model is connected.

## Commands (PowerShell, project root)

```powershell
.\scripts\build-frontend.ps1
.venv\Scripts\python -X utf8 -m pytest -q
.venv\Scripts\python -X utf8 tools/check_model.py --video C:\data\video.mov
.venv\Scripts\python -X utf8 tools/bench_model.py --videos C:\data\videos --count 5 --workers 1 --sweep
.\scripts\status.ps1
.\scripts\prepare-handover.ps1 -AllowStub
.\scripts\make-clean-zip.ps1 -Out .\.test-artifacts\dataprompt-clean.zip
docker compose up -d --build --force-recreate
```

After a reboot, when no tunnel is running: `.\scripts\start-public.ps1 -NoBuild`.
Stopping outside jury checks: `.\scripts\stop-public.ps1` (do not run while preserving the
current tunnel). Normal preflight after model delivery: prepare-handover.ps1 -Finalize,
review/commit the jury-document change, then prepare-handover.ps1 without AllowStub.
Keep the laptop powered/awake; during checking do not restart the tunnel or containers.
