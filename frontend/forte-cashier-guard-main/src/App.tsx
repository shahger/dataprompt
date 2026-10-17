import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { TopBar } from './components/TopBar';
import { Hero } from './components/Hero';
import { UploadZone } from './components/UploadZone';
import { VideoMonitor, type MonitorHandle } from './components/VideoMonitor';
import { ResultPanel } from './components/ResultPanel';
import { FrameLightbox } from './components/FrameLightbox';
import { InfoCards } from './components/InfoCards';
import { SiteFooter } from './components/SiteFooter';
import { useAnalysis } from './hooks/useAnalysis';
import { validateVideo } from './lib/validate';
import type { Violation } from './lib/types';
import { fmtBytes } from './lib/format';

interface LightboxState {
  v: Violation;
  index: number;
}

export default function App() {
  const { state, start, reset } = useAnalysis();
  const [fileError, setFileError] = useState<string | null>(null);
  const [lightbox, setLightbox] = useState<LightboxState | null>(null);
  const monitor = useRef<MonitorHandle>(null);
  const consoleRef = useRef<HTMLDivElement>(null);

  const busy = state.phase === 'uploading' || state.phase === 'processing';

  const handleFile = useCallback(
    (file: File) => {
      const err = validateVideo(file);
      setFileError(err);
      if (!err) void start(file);
      // файл выбран из баннера — показываем рабочую область
      consoleRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    },
    [start],
  );

  // Если пользователь промахнулся мимо зоны — браузер не должен открывать видео вместо загрузки
  useEffect(() => {
    const stop = (e: DragEvent) => {
      if (e.dataTransfer?.types.includes('Files')) e.preventDefault();
    };
    window.addEventListener('dragover', stop);
    window.addEventListener('drop', stop);
    return () => {
      window.removeEventListener('dragover', stop);
      window.removeEventListener('drop', stop);
    };
  }, []);

  const violations = useMemo(() => state.result?.violations ?? [], [state.result]);
  const sourceLabel = 'Локальная обработка';

  const retry = () => {
    if (state.file) void start(state.file);
  };

  return (
    <div className="app">
      <TopBar />

      <main>
        <Hero phase={state.phase} disabled={busy} onFile={handleFile} />

        <section className="workspace" id="workspace">
          <div className="container">
            <div className="section-head">
              <div>
                <h2 className="section-title">Проверка видеозаписи</h2>
                <p className="section-sub">Загрузите запись кассы в формате .mov — результат появится в окне результата, события отмечены на таймлайне.</p>
              </div>
            </div>

            <div className="console" ref={consoleRef}>
              <section className="card stage" aria-label="Видеомонитор">
                <div className="card__head">
                  <h3 className="card-title">
                    <span className={`led ${state.file ? 'led--ok' : ''}`} /> Видеомонитор
                  </h3>
                  {state.file && (
                    <div className="head-actions">
                      <span className="file-info">
                        {state.file.name} · {fmtBytes(state.file.size)}
                      </span>
                      <UploadZone compact onFile={handleFile} disabled={busy} />
                    </div>
                  )}
                </div>

                {fileError && state.file && (
                  <div className="alert alert--bad alert--inline" role="alert">
                    {fileError}
                  </div>
                )}

                <div className="stage__body">
                  {state.file && state.videoUrl ? (
                    <VideoMonitor ref={monitor} url={state.videoUrl} file={state.file} violations={violations} />
                  ) : (
                    <UploadZone onFile={handleFile} error={fileError} disabled={busy} />
                  )}
                </div>
              </section>

              <ResultPanel
                state={state}
                sourceLabel={sourceLabel}
                onSeek={(t) => monitor.current?.seek(t)}
                onOpenFrame={(v, index) => setLightbox({ v, index })}
                onRetry={retry}
              />
            </div>
          </div>
        </section>

        <InfoCards />
      </main>

      <SiteFooter onReset={reset} canReset={state.phase !== 'idle'} />

      {lightbox && (
        <FrameLightbox
          title={lightbox.v.type}
          frames={lightbox.v.evidence_frames}
          index={lightbox.index}
          onIndex={(i) => setLightbox({ ...lightbox, index: i })}
          onClose={() => setLightbox(null)}
        />
      )}
    </div>
  );
}
