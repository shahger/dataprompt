import type { AnalyzeApi, JobResult, NormativeRef, Violation } from './types';
import type { Scenario } from './config';
import { probeVideo } from './frames';

// ───────────────────────── ЗАГЛУШКА API ─────────────────────────
// Повторяет контракт из ТЗ (раздел 10): submit → job_id, затем опрос статуса.
// Загрузка: файл реально читается кусками (прогресс настоящий).
// Результат: типы/описания/нормативка — ПЛЕЙСХОЛДЕРЫ; таймкоды считаются от
// реальной длительности вашего видео, кадры снимаются из вашего видео.
// ────────────────────────────────────────────────────────────────

const PROCESSING_MS = 7000;
const FAIL_AFTER_MS = 4000;
const UPLOAD_MS = 1800;

const ADILET = 'https://adilet.zan.kz';

const RULE_CASH_RULES: NormativeRef = {
  document: 'Правила ведения кассовых операций в банках РК (НБРК) — ПЛЕЙСХОЛДЕР, уточнить на adilet.zan.kz',
  clause: 'пункт / раздел: уточнить',
  url: ADILET,
  placeholder: true,
};
const RULE_PREMISES: NormativeRef = {
  document: 'Требования к организации и охране кассовых помещений банков (НБРК) — ПЛЕЙСХОЛДЕР, уточнить на adilet.zan.kz',
  clause: 'пункт / раздел: уточнить',
  url: ADILET,
  placeholder: true,
};
const RULE_COLLECTION: NormativeRef = {
  document: 'Правила инкассации наличных денег (НБРК) — ПЛЕЙСХОЛДЕР, уточнить на adilet.zan.kz',
  clause: 'пункт / раздел: уточнить',
  url: ADILET,
  placeholder: true,
};

interface Template {
  type: string;
  description: string;
  rule: NormativeRef;
  /** где в видео «происходит» событие (доля длительности) */
  at: number;
}

const TEMPLATES: Template[] = [
  {
    type: 'Посторонний в зоне кассира',
    description:
      '[Плейсхолдер] В кадре виден человек, не являющийся кассиром, на рабочей стороне кассовой стойки. Описание будет сформировано моделью по реальному фрагменту.',
    rule: RULE_PREMISES,
    at: 0.24,
  },
  {
    type: 'Наличные без присмотра',
    description:
      '[Плейсхолдер] Пачка банкнот остаётся на стойке, пока кассир отвлекается от рабочей зоны. Описание будет сформировано моделью по реальному фрагменту.',
    rule: RULE_CASH_RULES,
    at: 0.52,
  },
  {
    type: 'Передача наличных вне установленного порядка',
    description:
      '[Плейсхолдер] Наличные передаются между участниками без видимых признаков пересчёта и оформления. Описание будет сформировано моделью по реальному фрагменту.',
    rule: RULE_COLLECTION,
    at: 0.8,
  },
];

const sleep = (ms: number, signal: AbortSignal) =>
  new Promise<void>((resolve, reject) => {
    if (signal.aborted) return reject(new DOMException('Aborted', 'AbortError'));
    const t = window.setTimeout(resolve, ms);
    signal.addEventListener(
      'abort',
      () => {
        window.clearTimeout(t);
        reject(new DOMException('Aborted', 'AbortError'));
      },
      { once: true },
    );
  });

const newJobId = () =>
  Array.from(crypto.getRandomValues(new Uint8Array(4)))
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('');

const round1 = (n: number) => Math.round(n * 10) / 10;

async function buildResult(jobId: string, file: File, scenario: Scenario): Promise<JobResult> {
  if (scenario === 'no_violation') {
    return { job_id: jobId, status: 'done', verdict: 'no_violation', violations: [] };
  }
  const probe = await probeVideo(file);
  try {
    const duration = probe.duration ?? 60;
    const templates = duration < 20 ? TEMPLATES.slice(0, 2) : TEMPLATES;
    const violations: Violation[] = [];
    for (const tpl of templates) {
      const t = round1(duration * tpl.at);
      // 1–3 кадра: чуть до события, само событие, чуть после (по ТЗ)
      const stamps = [...new Set([round1(t - 0.6), t, round1(t + 0.6)])]
        .filter((x) => x >= 0 && x <= duration)
        .slice(0, 3);
      const images = await probe.capture(stamps);
      violations.push({
        type: tpl.type,
        timecode_sec: t,
        description: tpl.description,
        rule: tpl.rule,
        evidence_frames: stamps.map((ts, i) => ({ timestamp_sec: ts, image_base64: images[i] ?? '' })),
      });
    }
    return { job_id: jobId, status: 'done', verdict: 'violation', violations };
  } finally {
    probe.dispose();
  }
}

export function createMockApi(scenario: Scenario): AnalyzeApi {
  const jobs = new Map<string, { file: File; readyAt: number; result?: Promise<JobResult> }>();

  return {
    async submit(file, onProgress, signal) {
      const steps = Math.min(60, Math.max(12, Math.ceil(file.size / (1 << 20))));
      const chunk = Math.ceil(file.size / steps);
      for (let i = 0; i < steps; i++) {
        // Реально читаем файл — проверяем, что он доступен и не повреждён на уровне ФС
        await file.slice(i * chunk, (i + 1) * chunk).arrayBuffer();
        onProgress((i + 1) / steps);
        await sleep(UPLOAD_MS / steps, signal);
      }
      const id = newJobId();
      jobs.set(id, {
        file,
        readyAt: Date.now() + (scenario === 'failed' ? FAIL_AFTER_MS : PROCESSING_MS),
      });
      return id;
    },

    async getJob(jobId) {
      const job = jobs.get(jobId);
      if (!job) return { job_id: jobId, status: 'failed', error: 'Задача не найдена' };
      if (Date.now() < job.readyAt) return { job_id: jobId, status: 'processing' };
      if (scenario === 'failed') {
        return { job_id: jobId, status: 'failed', error: 'Заглушка: имитация ошибки обработки на сервере' };
      }
      job.result ??= buildResult(jobId, job.file, scenario);
      return job.result;
    },
  };
}
