import { API_BASE, API_KEY } from './config';
import type { AnalyzeApi, JobResult } from './types';

export class ApiError extends Error {
  constructor(
    message: string,
    public status?: number,
  ) {
    super(message);
  }
}

function statusMessage(status: number): string {
  if (status === 401 || status === 403) return 'Сервер отклонил запрос: неверный или отсутствующий API-ключ';
  if (status === 413) return 'Сервер отклонил файл: слишком большой размер';
  if (status === 415 || status === 422) return 'Сервер не принял файл: проверьте, что это корректный .mov';
  if (status >= 500) return `Ошибка на стороне сервера (${status})`;
  return `Ошибка запроса (${status})`;
}

// Контракт — раздел 10 ТЗ:
//   POST /api/v1/analyze        multipart, поле `file` (.mov)  →  { job_id }
//   GET  /api/v1/jobs/{job_id}  →  { job_id, status, verdict?, violations? }
export const httpApi: AnalyzeApi = {
  submit(file, onProgress, signal) {
    return new Promise<string>((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open('POST', `${API_BASE}/api/v1/analyze`);
      if (API_KEY) xhr.setRequestHeader('X-API-Key', API_KEY);

      xhr.upload.onprogress = (e) => {
        if (e.lengthComputable) onProgress(e.loaded / e.total);
      };
      xhr.onload = () => {
        if (xhr.status < 200 || xhr.status >= 300) {
          return reject(new ApiError(statusMessage(xhr.status), xhr.status));
        }
        try {
          const data = JSON.parse(xhr.responseText) as { job_id?: string | number };
          if (data.job_id === undefined || data.job_id === null || data.job_id === '') throw new Error();
          onProgress(1);
          resolve(String(data.job_id));
        } catch {
          reject(new ApiError('Сервер не вернул job_id'));
        }
      };
      xhr.onerror = () => reject(new ApiError('Нет соединения с сервером'));
      xhr.ontimeout = () => reject(new ApiError('Тайм-аут при загрузке файла'));
      xhr.onabort = () => reject(new DOMException('Aborted', 'AbortError'));
      signal.addEventListener('abort', () => xhr.abort(), { once: true });

      const body = new FormData();
      body.append('file', file);
      xhr.send(body);
    });
  },

  async getJob(jobId, signal) {
    let res: Response;
    try {
      res = await fetch(`${API_BASE}/api/v1/jobs/${encodeURIComponent(jobId)}`, {
        headers: API_KEY ? { 'X-API-Key': API_KEY } : undefined,
        signal,
      });
    } catch (e) {
      if (e instanceof DOMException && e.name === 'AbortError') throw e;
      throw new ApiError('Нет соединения с сервером');
    }
    if (!res.ok) throw new ApiError(statusMessage(res.status), res.status);
    return (await res.json()) as JobResult;
  },
};
