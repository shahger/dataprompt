// Клиентский захват кадров из загруженного видео — используется ТОЛЬКО заглушкой,
// чтобы в окне результата были настоящие кадры из вашего .mov. Когда подключите API,
// кадры придут с бэкенда (image_base64), и этот модуль не понадобится.

interface LoadedVideo {
  video: HTMLVideoElement;
  url: string;
  duration: number;
}

function waitFor(video: HTMLVideoElement, ok: string, ms: number): Promise<boolean> {
  return new Promise((resolve) => {
    const t = window.setTimeout(() => done(false), ms);
    const onOk = () => done(true);
    const onErr = () => done(false);
    function done(v: boolean) {
      window.clearTimeout(t);
      video.removeEventListener(ok, onOk);
      video.removeEventListener('error', onErr);
      resolve(v);
    }
    video.addEventListener(ok, onOk);
    video.addEventListener('error', onErr);
  });
}

export async function loadVideo(file: File): Promise<LoadedVideo | null> {
  const url = URL.createObjectURL(file);
  const video = document.createElement('video');
  video.muted = true;
  video.playsInline = true;
  video.preload = 'auto';
  video.src = url;
  const ok = await waitFor(video, 'loadeddata', 10_000);
  if (!ok || !Number.isFinite(video.duration) || video.videoWidth === 0) {
    URL.revokeObjectURL(url);
    return null;
  }
  return { video, url, duration: video.duration };
}

function seekTo(video: HTMLVideoElement, t: number): Promise<void> {
  return new Promise((resolve, reject) => {
    if (Math.abs(video.currentTime - t) < 0.001) return resolve();
    const timer = window.setTimeout(() => reject(new Error('seek timeout')), 5000);
    video.addEventListener(
      'seeked',
      () => {
        window.clearTimeout(timer);
        resolve();
      },
      { once: true },
    );
    video.currentTime = t;
  });
}

function toBase64(canvas: HTMLCanvasElement): string {
  return canvas.toDataURL('image/jpeg', 0.85).split(',')[1] ?? '';
}

/** Кадр-заглушка (тоже JPEG), если браузер не смог декодировать видео. */
export function placeholderFrame(t: number): string {
  const c = document.createElement('canvas');
  c.width = 960;
  c.height = 540;
  const g = c.getContext('2d');
  if (!g) return '';
  g.fillStyle = '#141821';
  g.fillRect(0, 0, c.width, c.height);
  g.strokeStyle = '#2a3142';
  g.lineWidth = 1;
  for (let x = 0; x < c.width; x += 48) {
    g.beginPath();
    g.moveTo(x, 0);
    g.lineTo(x, c.height);
    g.stroke();
  }
  for (let y = 0; y < c.height; y += 48) {
    g.beginPath();
    g.moveTo(0, y);
    g.lineTo(c.width, y);
    g.stroke();
  }
  g.fillStyle = '#8a93a6';
  g.font = '600 56px monospace';
  g.textAlign = 'center';
  g.fillText('КАДР-ЗАГЛУШКА', c.width / 2, c.height / 2 - 12);
  g.font = '400 40px monospace';
  g.fillText(`t = ${t.toFixed(1)} c`, c.width / 2, c.height / 2 + 48);
  return toBase64(c);
}


const fourcc = (v: DataView, o: number) =>
  String.fromCharCode(v.getUint8(o), v.getUint8(o + 1), v.getUint8(o + 2), v.getUint8(o + 3));

/**
 * Длительность из контейнера QuickTime (атом moov → mvhd) без декодирования видео.
 * Нужна, когда браузер не умеет воспроизвести кодек (например, Chromium без H.264).
 */
export async function readMovDuration(file: File): Promise<number | null> {
  const readAtoms = async (start: number, end: number, want: string): Promise<{ off: number; hdr: number; size: number } | null> => {
    let off = start;
    for (let guard = 0; guard < 10_000 && off + 8 <= end; guard++) {
      const v = new DataView(await file.slice(off, off + 16).arrayBuffer());
      if (v.byteLength < 8) return null;
      let size = v.getUint32(0);
      let hdr = 8;
      if (size === 1 && v.byteLength >= 16) {
        size = Number(v.getBigUint64(8));
        hdr = 16;
      } else if (size === 0) {
        size = end - off;
      }
      if (size < hdr) return null;
      if (fourcc(v, 4) === want) return { off, hdr, size };
      off += size;
    }
    return null;
  };

  try {
    const moov = await readAtoms(0, file.size, 'moov');
    if (!moov) return null;
    const mvhd = await readAtoms(moov.off + moov.hdr, moov.off + moov.size, 'mvhd');
    if (!mvhd) return null;
    const v = new DataView(await file.slice(mvhd.off + mvhd.hdr, mvhd.off + mvhd.hdr + 32).arrayBuffer());
    const version = v.getUint8(0);
    const timescale = version === 1 ? v.getUint32(20) : v.getUint32(12);
    const duration = version === 1 ? Number(v.getBigUint64(24)) : v.getUint32(16);
    if (!timescale || !duration) return null;
    return duration / timescale;
  } catch {
    return null;
  }
}

export interface Probe {
  duration: number | null;
  capture: (timestamps: number[]) => Promise<string[]>;
  dispose: () => void;
}

/** Открывает видео один раз: узнаёт длительность и умеет снимать кадры. */
export async function probeVideo(file: File): Promise<Probe> {
  const loaded = await loadVideo(file);
  if (!loaded) {
    return {
      duration: await readMovDuration(file),
      capture: async (ts) => ts.map(placeholderFrame),
      dispose: () => {},
    };
  }
  const { video, url, duration } = loaded;
  const maxW = Math.min(960, video.videoWidth);
  const canvas = document.createElement('canvas');
  canvas.width = maxW;
  canvas.height = Math.round((maxW * video.videoHeight) / video.videoWidth);
  const g = canvas.getContext('2d');

  return {
    duration,
    capture: async (timestamps) => {
      const out: string[] = [];
      for (const t of timestamps) {
        try {
          if (!g) throw new Error('no canvas');
          await seekTo(video, Math.min(Math.max(t, 0), Math.max(duration - 0.05, 0)));
          g.drawImage(video, 0, 0, canvas.width, canvas.height);
          out.push(toBase64(canvas));
        } catch {
          out.push(placeholderFrame(t));
        }
      }
      return out;
    },
    dispose: () => {
      video.removeAttribute('src');
      video.load();
      URL.revokeObjectURL(url);
    },
  };
}
