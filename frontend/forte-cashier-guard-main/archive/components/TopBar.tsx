import { useEffect, useRef, useState } from 'react';
import markImg from '../assets/forte_mark.png';
import type { Scenario, Settings, Source } from '../lib/config';
import { Icon } from './Icon';

interface Props {
  settings: Settings;
  onSettings: (s: Settings) => void;
  /** во время загрузки/обработки переключать источник нельзя */
  locked: boolean;
}

const SITE = 'https://forte.kz/ru';

export function TopBar({ settings, onSettings, locked }: Props) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false);
    document.addEventListener('mousedown', onDown);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDown);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  const isMock = settings.source === 'mock';

  return (
    <header className="site-header">
      <div className="container header__inner">
        <a className="brand" href={SITE} target="_blank" rel="noopener noreferrer" aria-label="ForteBank — открыть forte.kz">
          <span className="logo-tile">
            <img src={markImg} alt="" />
          </span>
          <span className="brand__text">
            <b>Контроль кассовой дисциплины</b>
            <span>ForteBank</span>
          </span>
        </a>

        <div className="header__tools">
          <div className="popwrap" ref={ref}>
                <button
                  type="button"
                  className={`mode-pill ${isMock ? 'mode-pill--mock' : 'mode-pill--live'}`}
                  onClick={() => setOpen((v) => !v)}
                  aria-expanded={open}
                  aria-haspopup="dialog"
                >
                  <span className="dot" />
                  <span className="mode-pill__t">{isMock ? "Режим: заглушка API" : "API подключён"}</span>
                  <Icon name="gear" size={15} />
                </button>

                {open && (
                  <div className="popover" role="dialog" aria-label="Настройки источника данных">
                    <div className="popover__title">Источник данных</div>
                    <div className="seg">
                      {(['mock', 'api'] as Source[]).map((s) => (
                        <button
                          key={s}
                          type="button"
                          className={settings.source === s ? 'is-on' : ''}
                          disabled={locked}
                          onClick={() => onSettings({ ...settings, source: s })}
                        >
                          {s === 'mock' ? 'Заглушка' : 'Реальный API'}
                        </button>
                      ))}
                    </div>

                    {isMock ? (
                      <>
                        <div className="popover__title">Сценарий заглушки</div>
                        <div className="seg seg--col">
                          {(
                            [
                              ['violation', 'Нарушения найдены'],
                              ['no_violation', 'Нарушений нет'],
                              ['failed', 'Ошибка обработки'],
                            ] as [Scenario, string][]
                          ).map(([v, t]) => (
                            <button
                              key={v}
                              type="button"
                              className={settings.scenario === v ? 'is-on' : ''}
                              disabled={locked}
                              onClick={() => onSettings({ ...settings, scenario: v })}
                            >
                              {t}
                            </button>
                          ))}
                        </div>
                        <p className="hint">
                          Загрузка файла настоящая. Результат — плейсхолдер: таймкоды считаются от длительности вашего видео, кадры
                          вырезаются из него.
                        </p>
                      </>
                    ) : (
                      <p className="hint">
                        Запросы идут на <code>POST /api/v1/analyze</code> и <code>GET /api/v1/jobs/&#123;job_id&#125;</code>. Адрес и ключ — в{' '}
                        <code>.env</code> (<code>VITE_API_BASE</code>, <code>VITE_API_KEY</code>).
                      </p>
                    )}
                    {locked && <p className="hint hint--warn">Переключение недоступно во время обработки.</p>}
                  </div>
                )}
              </div>
        </div>
      </div>
    </header>
  );
}
