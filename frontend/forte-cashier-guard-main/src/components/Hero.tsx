import { useRef } from 'react';
import logo from '../assets/forte_logo.png';
import type { Phase } from '../lib/types';
import { Icon } from './Icon';

interface Props {
  phase: Phase;
  disabled: boolean;
  onFile: (file: File) => void;
}

const STEPS = ['Загрузка видео', 'Анализ', 'Результат'];

function activeStep(phase: Phase): number {
  if (phase === 'done') return 2;
  if (phase === 'processing' || phase === 'failed') return 1;
  return 0;
}

export function Hero({ phase, disabled, onFile }: Props) {
  const input = useRef<HTMLInputElement>(null);
  const step = activeStep(phase);

  return (
    <div className="container hero-wrap">
      <section className="hero" aria-label="О сервисе">
        <div className="hero__text">
          <div className="lockup">
            <img src={logo} alt="Forte" />
            <span className="lockup__sep" />
            <span className="lockup__name">Дататон 26</span>
          </div>

          <h2 className="hero__title">Контроль кассовой дисциплины по видео</h2>

          <div className="hero__cols">
            <p>Загрузите запись кассы в формате .mov — сервис проверит признаки возможных нарушений</p>
            <p>Таймкод, кадры-доказательства, правило и нормативный источник по каждому событию</p>
          </div>

          <div className="hero__cta">
            <input
              ref={input}
              type="file"
              accept=".mov,video/quicktime"
              hidden
              data-testid="hero-file-input"
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) onFile(f);
                e.target.value = '';
              }}
            />
            <button type="button" className="btn btn--primary btn--lg" disabled={disabled} onClick={() => input.current?.click()}>
              <Icon name="upload" size={18} /> Загрузить видео
            </button>
            <span className="hero__note">Обработка полностью локальная — без облачных сервисов искусственного интеллекта</span>
          </div>
        </div>

        <HeroArt />
      </section>

      <div className="pager" role="group" aria-label="Этапы проверки">
        <div className="pager__dots" aria-hidden="true">
          {STEPS.map((_, i) => (
            <i key={i} className={i === step ? 'is-on' : i < step ? 'is-past' : ''} />
          ))}
        </div>
        <span className="pager__label" aria-live="polite">
          {step + 1} из {STEPS.length} · {STEPS[step]}
        </span>
      </div>
    </div>
  );
}

/** Иллюстрация: фирменные дуги + «камера» с найденным событием. Нарисовано с нуля. */
function HeroArt() {
  return (
    <div className="hero__art" aria-hidden="true">
      <svg className="hero__arcs" viewBox="0 0 600 400" preserveAspectRatio="xMidYMid slice">
        <defs>
          <linearGradient id="warm" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stopColor="#f1e3d3" />
            <stop offset="1" stopColor="#dcbf9f" />
          </linearGradient>
        </defs>
        <rect width="600" height="400" fill="url(#warm)" />
        <circle cx="560" cy="-30" r="150" fill="none" stroke="#a31550" strokeWidth="86" />
        <circle cx="610" cy="470" r="150" fill="none" stroke="#a31550" strokeWidth="64" />
        <circle cx="610" cy="470" r="236" fill="none" stroke="#a31550" strokeWidth="40" />
      </svg>

      <div className="cam">
        <div className="cam__screen">
          <div className="cam__grid" />
          <span className="cam__rec">
            <i /> КАМЕРА 01
          </span>
          <div className="cam__box">
            <span>Событие</span>
          </div>
          <span className="cam__time">00:00</span>
        </div>
        <div className="cam__bar">
          <span className="cam__play" />
          <span className="cam__track">
            <i />
            <b />
          </span>
        </div>
      </div>

      <div className="chip-float chip-float--a">
        <Icon name="check" size={14} /> Кадр-доказательство
      </div>
      <div className="chip-float chip-float--b">
        <Icon name="link" size={14} /> Норматив РК
      </div>
    </div>
  );
}
