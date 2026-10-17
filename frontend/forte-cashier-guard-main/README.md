# Фронтенд Форте Банка

React 18 + TypeScript + Vite, исходное оформление Айдына. Production использует только
относительные `/ui/api/analyze`, `/ui/api/jobs/{job_id}` и `/health`.
Ключи API и переменные VITE_API_KEY/VITE_API_BASE не нужны и не читаются.

Из корня проекта: `scripts/build-frontend.ps1` устанавливает lockfile через npm ci,
проверяет TypeScript, собирает dist/ и копирует его в static/. В Docker нет Node.js,
исходников frontend и node_modules; готовые локальные ресурсы static/ коммитятся.

Для разработки здесь: `npm ci`, затем `npm run dev`. Прокси Vite ведёт локальные
UI API/health-запросы на localhost:8000. `npm run build` создаёт dist/.

Шрифты @fontsource и логотипы локальные. Значения API рендерятся как текст React.
`rule` — строка, `evidence_frames` — JPEG в base64; кадры открываются в lightbox.
Дедлайн 5 минут включает загрузку; GET повторяется не более трёх раз при сетевых/5xx ошибках,
POST автоматически не повторяется во избежание дубликатов задач.

Исходные mock/scenario настройки и fake results сохранены в archive/ для истории,
не входят в TypeScript include и не импортируются приложением. В production нет
переключателя источника, синтетических browser результатов и ключа в localStorage.
Нет логина, истории, экспорта или batch-загрузки. Дизайн, плеер, drag/drop и таймлайн сохранены.
