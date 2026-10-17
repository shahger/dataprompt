import { REQUEST_TIMEOUT_MS } from './config';
import type { AnalyzeApi, JobResult, Violation } from './types';

export class ApiError extends Error {
  constructor(message: string, public status?: number, public retryable = false) { super(message); }
}

function statusMessage(status: number): string {
  if (status === 413) return 'Размер файла превышает допустимые 200 МБ.';
  if (status === 400 || status === 415 || status === 422) return 'Сервер не принял файл. Выберите непустое видео в формате .mov.';
  if (status === 404) return 'Задача не найдена. Попробуйте загрузить видео снова.';
  if (status === 401 || status === 403) return 'Доступ к сервису временно ограничен. Обратитесь к организаторам.';
  return 'Сервис временно недоступен. Повторите попытку позже.';
}

const object = (value: unknown): value is Record<string, unknown> => typeof value === 'object' && value !== null;
const seconds = (value: unknown): value is number => typeof value === 'number' && Number.isFinite(value) && value >= 0;
function isViolation(value: unknown): value is Violation {
  return object(value) && typeof value.type === 'string' && seconds(value.timecode_sec)
    && typeof value.description === 'string' && (value.rule === undefined || typeof value.rule === 'string')
    && Array.isArray(value.evidence_frames) && value.evidence_frames.length >= 1 && value.evidence_frames.length <= 3
    && value.evidence_frames.every((frame: unknown) => object(frame) && seconds(frame.timestamp_sec)
      && typeof frame.image_base64 === 'string' && /^[A-Za-z0-9+/]+={0,2}$/.test(frame.image_base64));
}
export function validateJob(value: unknown): JobResult {
  if (!object(value) || typeof value.job_id !== 'string') throw new ApiError('Сервер вернул некорректный ответ.');
  if (value.status === 'processing') return value as unknown as JobResult;
  if (value.status === 'failed' && typeof value.error === 'string') return value as unknown as JobResult;
  if (value.status === 'done' && (value.verdict === 'violation' || value.verdict === 'no_violation')
    && Array.isArray(value.violations) && value.violations.every(isViolation)
    && (value.verdict === 'violation' ? value.violations.length > 0 : value.violations.length === 0)) {
    return value as unknown as JobResult;
  }
  throw new ApiError('Сервер вернул некорректный результат анализа.');
}

export const httpApi: AnalyzeApi = {
  submit(file, onProgress, signal) {
    return new Promise<string>((resolve, reject) => {
      if (signal.aborted) return reject(new DOMException('Отменено', 'AbortError'));
      const xhr = new XMLHttpRequest();
      xhr.open('POST', '/ui/api/analyze');
      xhr.timeout = 90000;
      const abort = () => xhr.abort();
      const cleanup = () => signal.removeEventListener('abort', abort);
      xhr.upload.onprogress = (event) => {
        if (event.lengthComputable) onProgress(event.loaded / event.total);
      };
      xhr.onload = () => {
        cleanup();
        if (xhr.status < 200 || xhr.status >= 300) return reject(new ApiError(statusMessage(xhr.status), xhr.status));
        try {
          const data: unknown = JSON.parse(xhr.responseText);
          if (!object(data) || typeof data.job_id !== 'string' || !data.job_id) throw new Error();
          onProgress(1);
          resolve(data.job_id);
        } catch { reject(new ApiError('Сервер не вернул идентификатор задачи.')); }
      };
      xhr.onerror = () => { cleanup(); reject(new ApiError('Нет соединения с сервером. Проверьте подключение и повторите загрузку.')); };
      xhr.ontimeout = () => { cleanup(); reject(new ApiError('Загрузка заняла слишком много времени. Проверьте соединение и повторите попытку.')); };
      xhr.onabort = () => { cleanup(); reject(new DOMException('Отменено', 'AbortError')); };
      signal.addEventListener('abort', abort, { once: true });
      const body = new FormData();
      body.append('file', file);
      // No automatic POST retry: an interrupted upload may already have created a job.
      xhr.send(body);
    });
  },

  async getJob(jobId, signal) {
    const ctrl = new AbortController();
    const abort = () => ctrl.abort();
    signal.addEventListener('abort', abort, { once: true });
    if (signal.aborted) ctrl.abort();
    const timer = window.setTimeout(abort, REQUEST_TIMEOUT_MS);
    try {
      const response = await fetch(`/ui/api/jobs/${encodeURIComponent(jobId)}`, { signal: ctrl.signal });
      if (!response.ok) throw new ApiError(statusMessage(response.status), response.status, response.status >= 500);
      try { return validateJob(await response.json()); }
      catch (error) {
        if (ctrl.signal.aborted) throw error;
        if (error instanceof ApiError) throw error;
        throw new ApiError('Сервер вернул некорректный ответ.');
      }
    } catch (error) {
      if (signal.aborted) throw new DOMException('Отменено', 'AbortError');
      if (error instanceof ApiError) throw error;
      throw new ApiError('Не удалось получить состояние задачи. Проверьте соединение и повторите попытку.', undefined, true);
    } finally {
      window.clearTimeout(timer);
      signal.removeEventListener('abort', abort);
    }
  },
};
