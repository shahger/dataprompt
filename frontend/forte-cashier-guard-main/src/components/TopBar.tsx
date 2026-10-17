import { useEffect, useState } from 'react';
import markImg from '../assets/forte_mark.png';

type Mode = 'checking' | 'stub' | 'demo' | 'ready' | 'error';
const labels: Record<Mode, string> = {
  checking: 'Проверка сервиса', stub: 'Модель не подключена', demo: 'Демонстрационный режим',
  ready: 'Сервис готов', error: 'Сервис недоступен',
};

export function TopBar() {
  const [mode, setMode] = useState<Mode>('checking');
  useEffect(() => {
    let alive = true;
    const ctrl = new AbortController();
    const timer = window.setTimeout(() => ctrl.abort(), 10000);
    fetch('/health', { signal: ctrl.signal }).then(async (response) => {
      if (!response.ok) throw new Error();
      const health = await response.json();
      if (alive) setMode(health.demo_mode ? 'demo' : health.model_loaded ? 'ready' : 'stub');
    }).catch(() => { if (alive) setMode('error'); })
      .finally(() => window.clearTimeout(timer));
    return () => { alive = false; ctrl.abort(); window.clearTimeout(timer); };
  }, []);
  return <>
    <header className="site-header">
      <div className="container header__inner">
        <a className="brand" href="/" aria-label="Главная страница — Форте Банк">
          <span className="logo-tile"><img src={markImg} alt="" /></span>
          <span className="brand__text"><b>Контроль кассовой дисциплины</b><span>Форте Банк</span></span>
        </a>
        <div className="header__tools">
          <span className={`mode-pill ${mode === 'ready' ? 'mode-pill--live' : 'mode-pill--mock'}`} role="status">
            <span className="dot" /><span>{labels[mode]}</span>
          </span>
        </div>
      </div>
    </header>
    {(mode === 'stub' || mode === 'demo') && <div className="container">
      <p className="alert alert--inline" role="status">{mode === 'demo'
        ? 'Демонстрационный режим: результат синтетический и не является настоящим анализом.'
        : 'Модель ещё не подключена. Текущий результат проверяет работу сервиса и не является анализом нарушений.'}</p>
    </div>}
  </>;
}
