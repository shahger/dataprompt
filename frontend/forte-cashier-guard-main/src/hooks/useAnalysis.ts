import { useCallback, useEffect, useRef, useState } from 'react';
import type { AnalysisState } from '../lib/types';
import type { Settings } from '../lib/config';
import { POLL_INTERVAL_MS, PROCESSING_LIMIT_MS } from '../lib/config';
import { httpApi } from '../lib/httpApi';
import { createMockApi } from '../lib/mockApi';

const initial: AnalysisState = {
  phase: 'idle',
  file: null,
  videoUrl: null,
  uploadPct: 0,
  jobId: null,
  result: null,
  error: null,
  startedAt: null,
  processingStartedAt: null,
};

class JobFailedError extends Error {}

const isAbort = (e: unknown) => e instanceof DOMException && e.name === 'AbortError';

function sleep(ms: number, signal: AbortSignal) {
  return new Promise<void>((resolve, reject) => {
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
}

export function useAnalysis(settings: Settings) {
  const [state, setState] = useState<AnalysisState>(initial);
  const abortRef = useRef<AbortController | null>(null);
  const urlRef = useRef<string | null>(null);

  const cleanup = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    if (urlRef.current) URL.revokeObjectURL(urlRef.current);
    urlRef.current = null;
  }, []);

  useEffect(() => cleanup, [cleanup]);

  const reset = useCallback(() => {
    cleanup();
    setState(initial);
  }, [cleanup]);

  const start = useCallback(
    async (file: File) => {
      cleanup();
      const ctrl = new AbortController();
      abortRef.current = ctrl;
      const url = URL.createObjectURL(file);
      urlRef.current = url;

      setState({ ...initial, phase: 'uploading', file, videoUrl: url, startedAt: Date.now() });

      const api = settings.source === 'mock' ? createMockApi(settings.scenario) : httpApi;
      try {
        const jobId = await api.submit(
          file,
          (p) => setState((s) => ({ ...s, uploadPct: p })),
          ctrl.signal,
        );
        const t0 = Date.now();
        setState((s) => ({ ...s, phase: 'processing', jobId, uploadPct: 1, processingStartedAt: t0 }));

        let failures = 0;
        for (;;) {
          await sleep(POLL_INTERVAL_MS, ctrl.signal);
          if (Date.now() - t0 > PROCESSING_LIMIT_MS) {
            throw new Error('Превышен лимит обработки (5 минут). Видео считается необработанным.');
          }
          try {
            const r = await api.getJob(jobId, ctrl.signal);
            failures = 0;
            if (r.status === 'done') {
              setState((s) => ({ ...s, phase: 'done', result: r }));
              return;
            }
            if (r.status === 'failed') {
              throw new JobFailedError(r.error || 'Сервис не смог обработать это видео');
            }
          } catch (e) {
            if (isAbort(e)) throw e;
            // единичные сетевые сбои при опросе терпим, но не бесконечно
            if (e instanceof JobFailedError) throw e;
            if (++failures >= 3) throw e;
          }
        }
      } catch (e) {
        if (isAbort(e)) return;
        setState((s) => ({
          ...s,
          phase: 'failed',
          error: e instanceof Error ? e.message : 'Неизвестная ошибка',
        }));
      }
    },
    [cleanup, settings.source, settings.scenario],
  );

  return { state, start, reset };
}
