import { useEffect, useState } from 'react';
import type { AnalysisState, Violation } from '../lib/types';
import { PROCESSING_LIMIT_MS } from '../lib/config';
import { fmtBytes, fmtElapsed, fmtTimecode } from '../lib/format';
import { Icon } from './Icon';

interface Props {
  state: AnalysisState;
  sourceLabel: string;
  onSeek: (sec: number) => void;
  onOpenFrame: (v: Violation, index: number) => void;
  onRetry: () => void;
}

function useNow(active: boolean) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!active) return;
    const t = window.setInterval(() => setNow(Date.now()), 250);
    return () => window.clearInterval(t);
  }, [active]);
  return now;
}

function CopyButton({ text }: { text: string }) {
  const [done, setDone] = useState(false);
  return (
    <button
      type="button"
      className="icon-btn icon-btn--sm"
      title="Скопировать"
      aria-label="Скопировать"
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(text);
          setDone(true);
          window.setTimeout(() => setDone(false), 1400);
        } catch {
          /* буфер недоступен */
        }
      }}
    >
      <Icon name={done ? 'check' : 'copy'} size={14} />
    </button>
  );
}

function Stepper({ phase }: { phase: AnalysisState['phase'] }) {
  const order = ['uploading', 'processing', 'done'] as const;
  const idx = order.indexOf(phase as (typeof order)[number]);
  const steps = ['Загрузка видео', 'Анализ', 'Результат'];
  return (
    <ol className="stepper">
      {steps.map((s, i) => (
        <li key={s} className={i < idx ? 'is-done' : i === idx ? 'is-now' : ''}>
          <span className="stepper__dot">{i < idx ? <Icon name="check" size={12} /> : i + 1}</span>
          {s}
        </li>
      ))}
    </ol>
  );
}

function jsonFor(state: AnalysisState): string {
  const r = state.result;
  if (!r) return '';
  // base64 кадров — длинные; в просмотре JSON сокращаем, копирование отдаёт полный
  return JSON.stringify(r, (k, v) => (k === 'image_base64' && typeof v === 'string' ? `${v.slice(0, 24)}…(${v.length} симв.)` : v), 2);
}

export function ResultPanel({ state, sourceLabel, onSeek, onOpenFrame, onRetry }: Props) {
  const [tab, setTab] = useState<'events' | 'json'>('events');
  const busy = state.phase === 'uploading' || state.phase === 'processing';
  const now = useNow(busy);

  useEffect(() => {
    if (state.phase === 'uploading') setTab('events');
  }, [state.phase]);

  const result = state.result;
  const violations = result?.violations ?? [];
  const hasViolation = result?.verdict === 'violation';

  return (
    <section className="card result" aria-live="polite">
      <div className="card__head">
        <h3 className="card-title">Результат анализа</h3>
        <span className="source-chip">{sourceLabel}</span>
      </div>

      <dl className="meta">
        <div>
          <dt>job_id</dt>
          <dd className="mono">
            {state.jobId ?? '—'}
            {state.jobId && <CopyButton text={state.jobId} />}
          </dd>
        </div>
        <div>
          <dt>status</dt>
          <dd className="mono">
            {state.phase === 'idle' && '—'}
            {state.phase === 'uploading' && 'uploading'}
            {state.phase === 'processing' && 'processing'}
            {state.phase === 'done' && 'done'}
            {state.phase === 'failed' && 'failed'}
          </dd>
        </div>
        <div>
          <dt>verdict</dt>
          <dd className="mono">{result?.verdict ?? '—'}</dd>
        </div>
      </dl>

      <div className="card__body">
        {state.phase === 'idle' && (
          <div className="empty">
            <div className="empty__icon">
              <Icon name="film" size={28} />
            </div>
            <h3>Здесь появится результат</h3>
            <p>Загрузите видео — сервис покажет по каждому событию:</p>
            <ul>
              <li><b className="mono">job_id</b> задачи</li>
              <li>тип нарушения и описание</li>
              <li>правило и нормативный источник</li>
              <li>таймкод и кадры-доказательства</li>
            </ul>
          </div>
        )}

        {busy && (
          <div className="progress-card">
            <Stepper phase={state.phase} />
            {state.phase === 'uploading' && (
              <>
                <div className="bar" role="progressbar" aria-valuenow={Math.round(state.uploadPct * 100)} aria-valuemin={0} aria-valuemax={100}>
                  <i style={{ width: `${state.uploadPct * 100}%` }} />
                </div>
                <div className="progress-row mono">
                  <span>
                    {state.file ? fmtBytes(state.file.size * state.uploadPct) : ''} / {state.file ? fmtBytes(state.file.size) : ''}
                  </span>
                  <b>{Math.round(state.uploadPct * 100)}%</b>
                </div>
              </>
            )}
            {state.phase === 'processing' && state.processingStartedAt && (
              <>
                <div className="bar bar--indet" aria-label="Идёт анализ">
                  <i />
                </div>
                <div className="progress-row mono">
                  <span>Анализ видео… job_id {state.jobId}</span>
                  <b>{fmtElapsed(now - state.processingStartedAt)}</b>
                </div>
                <div className="limit mono">
                  <div className="limit__bar">
                    <i style={{ width: `${Math.min(100, ((now - state.processingStartedAt) / PROCESSING_LIMIT_MS) * 100)}%` }} />
                  </div>
                  <span>лимит {fmtElapsed(PROCESSING_LIMIT_MS)}</span>
                </div>
              </>
            )}
          </div>
        )}

        {state.phase === 'failed' && (
          <div className="alert alert--bad alert--block" role="alert">
            <Icon name="alert" size={20} />
            <div>
              <b>Не удалось получить результат</b>
              <p>{state.error}</p>
              <button type="button" className="btn btn--ghost" onClick={onRetry}>
                <Icon name="refresh" size={16} /> Повторить
              </button>
            </div>
          </div>
        )}

        {state.phase === 'done' && result && (
          <>
            <div className={`verdict ${hasViolation ? 'verdict--bad' : 'verdict--ok'}`}>
              <span className="verdict__icon">
                <Icon name={hasViolation ? 'alert' : 'check'} size={22} />
              </span>
              <div>
                <b>{hasViolation ? 'Обнаружены признаки возможных нарушений' : 'Нарушение не обнаружено'}</b>
                <span>
                  {hasViolation
                    ? `Событий: ${violations.length}. Это подсказка для проверки человеком, не итоговое заключение.`
                    : 'Видимых признаков нарушения в записи не найдено.'}
                </span>
              </div>
            </div>

            <div className="toggle" role="tablist">
              <button role="tab" aria-selected={tab === 'events'} className={tab === 'events' ? 'is-on' : ''} onClick={() => setTab('events')}>
                События <em>{violations.length}</em>
              </button>
              <button role="tab" aria-selected={tab === 'json'} className={tab === 'json' ? 'is-on' : ''} onClick={() => setTab('json')}>
                JSON
              </button>
            </div>

            {tab === 'events' && (
              <ul className="events">
                {violations.length === 0 && <li className="events__none">Список событий пуст — нарушений нет.</li>}
                {violations.map((v, i) => (
                  <li key={i} className="event">
                    <div className="event__top">
                      <span className="event__n mono">{String(i + 1).padStart(2, '0')}</span>
                      <h4>{v.type}</h4>
                      <button
                        type="button"
                        className="tc-btn mono"
                        onClick={() => onSeek(v.timecode_sec)}
                        title="Перейти к этому моменту в видео"
                      >
                        {fmtTimecode(v.timecode_sec)}
                        <small>{v.timecode_sec.toFixed(1)} c</small>
                      </button>
                    </div>
                    <p className="event__desc">{v.description}</p>

                    {v.rule && (
                      <div className={`rule ${v.rule.placeholder ? 'rule--ph' : ''}`}>
                        <div className="rule__head">
                          <Icon name="link" size={14} /> Правило и источник
                          {v.rule.placeholder && <span className="ph">плейсхолдер</span>}
                        </div>
                        <div className="rule__doc">{v.rule.document}</div>
                        <div className="rule__clause">{v.rule.clause}</div>
                        {v.rule.url && !v.rule.placeholder && (
                          <a href={v.rule.url} target="_blank" rel="noreferrer noopener">
                            Открыть источник
                          </a>
                        )}
                      </div>
                    )}

                    <div className="frames">
                      {v.evidence_frames.map((f, j) => (
                        <button key={j} type="button" className="frame" onClick={() => onOpenFrame(v, j)} aria-label={`Открыть кадр ${j + 1}`}>
                          <img src={`data:image/jpeg;base64,${f.image_base64}`} alt="" />
                          <span className="mono">{fmtTimecode(f.timestamp_sec)}</span>
                        </button>
                      ))}
                    </div>
                  </li>
                ))}
              </ul>
            )}

            {tab === 'json' && (
              <div className="json">
                <div className="json__bar">
                  <span className="json__title mono">GET /api/v1/jobs/{result.job_id}</span>
                  <CopyButton text={JSON.stringify(result, null, 2)} />
                </div>
                <pre className="mono">{jsonFor(state)}</pre>
              </div>
            )}
          </>
        )}
      </div>
    </section>
  );
}
