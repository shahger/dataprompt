# Frontend integration: inspection and environment

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
