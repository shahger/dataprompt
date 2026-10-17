import { useEffect } from 'react';
import type { EvidenceFrame } from '../lib/types';
import { fmtPrecise } from '../lib/format';
import { Icon } from './Icon';

interface Props {
  title: string;
  frames: EvidenceFrame[];
  index: number;
  onIndex: (i: number) => void;
  onClose: () => void;
}

export function FrameLightbox({ title, frames, index, onIndex, onClose }: Props) {
  const frame = frames[index];

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
      if (e.key === 'ArrowLeft' && index > 0) onIndex(index - 1);
      if (e.key === 'ArrowRight' && index < frames.length - 1) onIndex(index + 1);
    };
    document.addEventListener('keydown', onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.removeEventListener('keydown', onKey);
      document.body.style.overflow = prev;
    };
  }, [index, frames.length, onClose, onIndex]);

  if (!frame) return null;

  return (
    <div className="lightbox" role="dialog" aria-modal="true" aria-label="Кадр-доказательство" onClick={onClose}>
      <div className="lightbox__body" onClick={(e) => e.stopPropagation()}>
        <div className="lightbox__bar">
          <div>
            <div className="label mono">КАДР-ДОКАЗАТЕЛЬСТВО · {index + 1}/{frames.length}</div>
            <b>{title}</b>
          </div>
          <span className="mono tc">{fmtPrecise(frame.timestamp_sec)}</span>
          <button type="button" className="icon-btn" onClick={onClose} aria-label="Закрыть" autoFocus>
            <Icon name="close" />
          </button>
        </div>
        <div className="lightbox__stage">
          <button
            type="button"
            className="icon-btn icon-btn--lg"
            disabled={index === 0}
            onClick={() => onIndex(index - 1)}
            aria-label="Предыдущий кадр"
          >
            <Icon name="chevL" size={22} />
          </button>
          <img src={`data:image/jpeg;base64,${frame.image_base64}`} alt={`Кадр на ${fmtPrecise(frame.timestamp_sec)}`} />
          <button
            type="button"
            className="icon-btn icon-btn--lg"
            disabled={index === frames.length - 1}
            onClick={() => onIndex(index + 1)}
            aria-label="Следующий кадр"
          >
            <Icon name="chevR" size={22} />
          </button>
        </div>
      </div>
    </div>
  );
}
