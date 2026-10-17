import { useRef, useState } from 'react';
import { Icon } from './Icon';

interface Props {
  onFile: (file: File) => void;
  /** компактный вид: кнопка «загрузить другое видео» */
  compact?: boolean;
  disabled?: boolean;
  error?: string | null;
}

export function UploadZone({ onFile, compact, disabled, error }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);
  const depth = useRef(0);

  const pick = (files: FileList | null) => {
    const f = files?.[0];
    if (f) onFile(f);
    // позволяет выбрать тот же файл повторно
    if (inputRef.current) inputRef.current.value = '';
  };

  const input = (
    <input
      ref={inputRef}
      type="file"
      accept=".mov,video/quicktime"
      hidden
      onChange={(e) => pick(e.target.files)}
      data-testid="file-input"
    />
  );

  if (compact) {
    return (
      <>
        {input}
        <button type="button" className="btn btn--ghost" disabled={disabled} onClick={() => inputRef.current?.click()}>
          <Icon name="upload" size={16} /> Загрузить другое видео
        </button>
      </>
    );
  }

  return (
    <div
      className={`dropzone ${over ? 'is-over' : ''} ${disabled ? 'is-disabled' : ''}`}
      onDragEnter={(e) => {
        e.preventDefault();
        depth.current++;
        setOver(true);
      }}
      onDragOver={(e) => e.preventDefault()}
      onDragLeave={() => {
        depth.current = Math.max(0, depth.current - 1);
        if (depth.current === 0) setOver(false);
      }}
      onDrop={(e) => {
        e.preventDefault();
        depth.current = 0;
        setOver(false);
        if (!disabled) pick(e.dataTransfer.files);
      }}
    >
      {input}

      <div className="dropzone__icon">
        <Icon name="film" size={34} />
      </div>
      <h3>{over ? 'Отпустите файл для загрузки' : 'Перетащите видео сюда'}</h3>
      <p>Запись кассовой зоны в формате <b>.mov</b>, обычно до 30 МБ. Или нажмите кнопку, чтобы выбрать файл.</p>
      <button type="button" className="btn btn--primary" disabled={disabled} onClick={() => inputRef.current?.click()}>
        <Icon name="upload" size={16} /> Выбрать файл
      </button>

      {error && (
        <div className="alert alert--bad" role="alert">
          <Icon name="alert" size={16} /> <span>{error}</span>
        </div>
      )}
      <div className="dropzone__foot">Анализ на компьютере сервиса · анализ строго визуальный</div>
    </div>
  );
}
