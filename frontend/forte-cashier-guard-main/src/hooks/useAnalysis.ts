import { useCallback, useEffect, useRef, useState } from 'react';
import type { AnalysisState } from '../lib/types';
import { POLL_INTERVAL_MS, PROCESSING_LIMIT_MS } from '../lib/config';
import { ApiError, httpApi } from '../lib/httpApi';

const initial: AnalysisState = {
  phase: 'idle', file: null, videoUrl: null, uploadPct: 0, jobId: null, result: null,
  error: null, technicalError: null, startedAt: null, processingStartedAt: null,
};
class JobFailedError extends Error {}
const isAbort = (error: unknown) => error instanceof DOMException && error.name === 'AbortError';

function sleep(ms: number, signal: AbortSignal) {
  return new Promise<void>((resolve, reject) => {
    const abort = () => { window.clearTimeout(timer); reject(new DOMException('Отменено', 'AbortError')); };
    const timer = window.setTimeout(() => { signal.removeEventListener('abort', abort); resolve(); }, ms);
    signal.addEventListener('abort', abort, { once: true });
    if (signal.aborted) { signal.removeEventListener('abort', abort); abort(); }
  });
}

export function useAnalysis() {
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
  const reset = useCallback(() => { cleanup(); setState(initial); }, [cleanup]);

  const start = useCallback(async (file: File) => {
    cleanup();
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    const url = URL.createObjectURL(file);
    urlRef.current = url;
    const startedAt = Date.now();
    let timedOut = false;
    const timer = window.setTimeout(() => { timedOut = true; ctrl.abort(); }, PROCESSING_LIMIT_MS);
    setState({ ...initial, phase: 'uploading', file, videoUrl: url, startedAt });
    try {
      const jobId = await httpApi.submit(file, (pct) => {
        if (!ctrl.signal.aborted) setState((s) => ({ ...s, uploadPct: pct }));
      }, ctrl.signal);
      if (ctrl.signal.aborted) throw new DOMException('Отменено', 'AbortError');
      setState((s) => ({ ...s, phase: 'processing', jobId, uploadPct: 1, processingStartedAt: Date.now() }));
      let failures = 0;
      for (;;) {
        await sleep(POLL_INTERVAL_MS, ctrl.signal);
        try {
          const result = await httpApi.getJob(jobId, ctrl.signal);
          failures = 0;
          if (result.status === 'done') {
            setState((s) => ({ ...s, phase: 'done', result }));
            return;
          }
          if (result.status === 'failed') throw new JobFailedError(result.error || 'Неизвестная ошибка обработки');
        } catch (error) {
          if (isAbort(error) || error instanceof JobFailedError) throw error;
          if (!(error instanceof ApiError) || !error.retryable || ++failures >= 3) throw error;
        }
      }
    } catch (error) {
      if (isAbort(error) && !timedOut) return;
      const jobFailed = error instanceof JobFailedError;
      setState((s) => ({ ...s, phase: 'failed',
        error: timedOut ? 'Превышено время ожидания — 5 минут с начала загрузки. Попробуйте позже или загрузите видео меньшего размера.'
          : jobFailed ? 'Не удалось обработать видео. Проверьте файл и повторите попытку.'
          : error instanceof ApiError ? error.message : 'Не удалось связаться с сервисом. Повторите попытку.',
        technicalError: jobFailed ? error.message : null,
      }));
    } finally { window.clearTimeout(timer); }
  }, [cleanup]);
  return { state, start, reset };
}
