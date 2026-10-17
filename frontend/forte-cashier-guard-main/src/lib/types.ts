// Типы строго следуют разделу 10 ТЗ («API для проверки жюри»).
// Поле `rule` — дополнение для UI: ТЗ (раздел 4, п. 7) требует показывать правило и
// нормативный источник, а в схеме API оно не описано. Бэкенд может возвращать его
// опционально; если нет — UI просто скрывает блок.

export type Verdict = 'no_violation' | 'violation';
export type JobStatus = 'processing' | 'done' | 'failed';

export interface EvidenceFrame {
  timestamp_sec: number;
  /** JPEG в base64, без префикса data: */
  image_base64: string;
}

export interface Violation {
  type: string;
  timecode_sec: number;
  description: string;
  evidence_frames: EvidenceFrame[];
  rule?: string;
}

export interface JobResult {
  job_id: string;
  status: JobStatus;
  verdict?: Verdict;
  violations?: Violation[];
  error?: string;
}

export interface AnalyzeApi {
  /** Загружает видео, возвращает job_id. onProgress: 0..1 */
  submit(file: File, onProgress: (p: number) => void, signal: AbortSignal): Promise<string>;
  getJob(jobId: string, signal: AbortSignal): Promise<JobResult>;
}

export type Phase = 'idle' | 'uploading' | 'processing' | 'done' | 'failed';

export interface AnalysisState {
  phase: Phase;
  file: File | null;
  videoUrl: string | null;
  uploadPct: number;
  jobId: string | null;
  result: JobResult | null;
  error: string | null;
  technicalError: string | null;
  /** Date.now() начала загрузки */
  startedAt: number | null;
  /** Date.now() начала обработки (после получения job_id) */
  processingStartedAt: number | null;
}
