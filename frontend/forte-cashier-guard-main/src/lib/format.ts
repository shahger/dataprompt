/** 44.2 → "00:44.2" (MM:SS.d), от часа — "H:MM:SS.d" */
export function fmtTimecode(sec: number): string {
  if (!Number.isFinite(sec) || sec < 0) sec = 0;
  const total = Math.floor(sec);
  return `${String(Math.floor(total / 60)).padStart(2, '0')}:${String(total % 60).padStart(2, '0')}`;
}

/** Для проигрывателя: с сотыми долями */
export function fmtPrecise(sec: number): string {
  if (!Number.isFinite(sec) || sec < 0) sec = 0;
  const cs = Math.round(sec * 100);
  const c = cs % 100;
  const total = Math.floor(cs / 100);
  const s = total % 60;
  const m = Math.floor(total / 60);
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}.${String(c).padStart(2, '0')}`;
}

export function fmtBytes(n: number): string {
  if (n < 1024) return `${n} Б`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(0)} КБ`;
  return `${(n / 1024 / 1024).toFixed(1)} МБ`;
}

export function fmtElapsed(ms: number): string {
  const s = Math.max(0, Math.floor(ms / 1000));
  return `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`;
}
