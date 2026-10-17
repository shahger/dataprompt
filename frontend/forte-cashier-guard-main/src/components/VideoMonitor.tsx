import { forwardRef, useCallback, useEffect, useImperativeHandle, useRef, useState } from 'react';
import type { Violation } from '../lib/types';
import { fmtBytes, fmtPrecise, fmtTimecode } from '../lib/format';
import { Icon } from './Icon';

export interface MonitorHandle {
  seek: (sec: number) => void;
}

interface Props {
  url: string;
  file: File;
  violations: Violation[];
}

const FPS = 30; // по ТЗ у датасета FPS от 29
const NEAR = 0.6; // секунд — «мы на событии»

export const VideoMonitor = forwardRef<MonitorHandle, Props>(function VideoMonitor({ url, file, violations }, ref) {
  const video = useRef<HTMLVideoElement>(null);
  const raf = useRef(0);
  const [playing, setPlaying] = useState(false);
  const [time, setTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [dims, setDims] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);

  const sync = useCallback(() => {
    if (video.current) setTime(video.current.currentTime);
  }, []);

  const loop = useCallback(() => {
    sync();
    raf.current = requestAnimationFrame(loop);
  }, [sync]);

  useEffect(() => {
    if (playing) raf.current = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf.current);
  }, [playing, loop]);

  // новый файл — сбрасываем состояние
  useEffect(() => {
    setPlaying(false);
    setTime(0);
    setDuration(0);
    setDims(null);
    setFailed(false);
  }, [url]);

  const seek = useCallback(
    (sec: number) => {
      const v = video.current;
      if (!v || !Number.isFinite(v.duration)) return;
      v.currentTime = Math.min(Math.max(sec, 0), v.duration);
      sync();
    },
    [sync],
  );

  useImperativeHandle(ref, () => ({ seek }), [seek]);

  const toggle = () => {
    const v = video.current;
    if (!v) return;
    if (v.paused) void v.play().catch(() => setFailed(true));
    else v.pause();
  };

  const step = (frames: number) => {
    const v = video.current;
    if (!v) return;
    v.pause();
    seek(v.currentTime + frames / FPS);
  };

  const active = violations.find((x) => Math.abs(x.timecode_sec - time) <= NEAR);
  const pct = duration > 0 ? (time / duration) * 100 : 0;

  return (
    <div className="monitor">
      <div className="monitor__screen">
        <video
          ref={video}
          src={url}
          playsInline
          preload="auto"
          muted
          onLoadedMetadata={(e) => {
            const v = e.currentTarget;
            setDuration(v.duration);
            setDims(`${v.videoWidth}×${v.videoHeight}`);
          }}
          onPlay={() => setPlaying(true)}
          onPause={() => {
            setPlaying(false);
            sync();
          }}
          onEnded={() => setPlaying(false)}
          onSeeked={sync}
          onError={() => setFailed(true)}
          onClick={toggle}
        />

        <div className="osd osd--tl mono">
          <span className={`rec ${playing ? 'is-on' : ''}`} /> КАМЕРА 01 · КАССА
        </div>
        <div className="osd osd--tr mono">{fmtPrecise(time)}</div>
        <div className="osd osd--bl mono" title={file.name}>
          {file.name} · {fmtBytes(file.size)}
          {dims ? ` · ${dims}` : ''}
        </div>

        {active && (
          <div className="event-flag" role="status">
            <span className="led led--bad" /> Событие · {active.type}
          </div>
        )}

        {failed && (
          <div className="monitor__fail">
            <Icon name="alert" size={22} />
            <b>Предпросмотр недоступен</b>
            <span>
              Браузер не смог воспроизвести этот .mov (кодек). На загрузку и анализ это не влияет — файл отправляется как есть.
              Используйте браузер с поддержкой кодека вашего видео.
            </span>
          </div>
        )}
      </div>

      <div className="transport">
        <button type="button" className="icon-btn" onClick={() => step(-1)} aria-label="Кадр назад" title="Кадр назад">
          <Icon name="stepBack" />
        </button>
        <button type="button" className="icon-btn icon-btn--lg" onClick={toggle} aria-label={playing ? 'Пауза' : 'Воспроизвести'}>
          <Icon name={playing ? 'pause' : 'play'} size={22} />
        </button>
        <button type="button" className="icon-btn" onClick={() => step(1)} aria-label="Кадр вперёд" title="Кадр вперёд">
          <Icon name="stepFwd" />
        </button>

        <div className="scrub">
          <div className="scrub__track">
            <div className="scrub__fill" style={{ width: `${pct}%` }} />
            {duration > 0 &&
              violations.map((v, i) => (
                <span
                  key={i}
                  className="scrub__mark"
                  style={{ left: `${Math.min(100, (v.timecode_sec / duration) * 100)}%` }}
                  title={`${v.type} · ${fmtTimecode(v.timecode_sec)}`}
                />
              ))}
          </div>
          <input
            type="range"
            min={0}
            max={duration || 1}
            step={0.01}
            value={Math.min(time, duration || 1)}
            onChange={(e) => seek(Number(e.target.value))}
            aria-label="Позиция в видео"
            disabled={duration === 0}
          />
        </div>

        <span className="mono time">
          {fmtTimecode(time)} <i>/</i> {fmtTimecode(duration)}
        </span>
      </div>
    </div>
  );
});
