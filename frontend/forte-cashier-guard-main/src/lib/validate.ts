import { MAX_FILE_BYTES } from './config';
import { fmtBytes } from './format';

/** Возвращает текст ошибки или null, если файл подходит. */
export function validateVideo(file: File): string | null {
  const name = file.name.toLowerCase();
  const isMov = name.endsWith('.mov') || file.type === 'video/quicktime';
  if (!isMov) {
    return `Формат «${file.name.split('.').pop() ?? '?'}» не поддерживается. Сервис принимает только видео .mov`;
  }
  if (file.size === 0) return 'Файл пустой (0 байт)';
  if (file.size > MAX_FILE_BYTES) {
    return `Файл слишком большой (${fmtBytes(file.size)}). Максимум — ${fmtBytes(MAX_FILE_BYTES)}`;
  }
  return null;
}
