export type Source = 'mock' | 'api';
export type Scenario = 'violation' | 'no_violation' | 'failed';

export interface Settings {
  source: Source;
  scenario: Scenario;
}

export const API_BASE = (import.meta.env.VITE_API_BASE ?? '').replace(/\/$/, '');
export const API_KEY = import.meta.env.VITE_API_KEY ?? '';

/** Лимит обработки по ТЗ: 5 минут */
export const PROCESSING_LIMIT_MS = 5 * 60 * 1000;
/** По ТЗ файлы ~29 МБ; жёсткий предел с запасом */
export const MAX_FILE_BYTES = 200 * 1024 * 1024;
export const POLL_INTERVAL_MS = 1500;

const KEY = 'forte-guard-settings';
const defaults: Settings = {
  source: import.meta.env.VITE_USE_MOCK === 'false' ? 'api' : 'mock',
  scenario: 'violation',
};

export function loadSettings(): Settings {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return defaults;
    const p = JSON.parse(raw) as Partial<Settings>;
    return {
      source: p.source === 'api' || p.source === 'mock' ? p.source : defaults.source,
      scenario:
        p.scenario === 'no_violation' || p.scenario === 'failed' || p.scenario === 'violation'
          ? p.scenario
          : defaults.scenario,
    };
  } catch {
    return defaults;
  }
}

export function saveSettings(s: Settings): void {
  try {
    localStorage.setItem(KEY, JSON.stringify(s));
  } catch {
    /* storage недоступен — не критично */
  }
}
