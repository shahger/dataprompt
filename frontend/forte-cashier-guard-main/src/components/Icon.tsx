const paths: Record<string, string> = {
  play: 'M8 5v14l11-7z',
  pause: 'M6 5h4v14H6zM14 5h4v14h-4z',
  stepBack: 'M6 5h2v14H6zM20 5v14L9 12z',
  stepFwd: 'M16 5h2v14h-2zM4 5l11 7L4 19z',
  upload: 'M12 3l5 5h-3.5v6h-3V8H7l5-5zM5 17h14v3H5z',
  copy: 'M9 3h10a2 2 0 012 2v12h-2V5H9V3zM5 7h10a2 2 0 012 2v10a2 2 0 01-2 2H5a2 2 0 01-2-2V9a2 2 0 012-2zm0 2v10h10V9H5z',
  check: 'M9.5 16.2L5.3 12l-1.4 1.4 5.6 5.6L20.1 8.4 18.7 7z',
  alert: 'M12 3L2 21h20L12 3zm1 14h-2v-2h2v2zm0-4h-2V9h2v4z',
  close: 'M6.4 5L5 6.4 10.6 12 5 17.6 6.4 19 12 13.4 17.6 19 19 17.6 13.4 12 19 6.4 17.6 5 12 10.6z',
  chevL: 'M15.4 6.4L14 5l-7 7 7 7 1.4-1.4L9.8 12z',
  chevR: 'M8.6 6.4L10 5l7 7-7 7-1.4-1.4L14.2 12z',
  gear: 'M19.4 13a7.5 7.5 0 000-2l2-1.5-2-3.4-2.4 1a7.6 7.6 0 00-1.7-1L15 3.5h-4l-.4 2.6a7.6 7.6 0 00-1.7 1l-2.4-1-2 3.4 2 1.5a7.5 7.5 0 000 2l-2 1.5 2 3.4 2.4-1c.5.4 1.1.7 1.7 1l.4 2.6h4l.4-2.6c.6-.3 1.2-.6 1.7-1l2.4 1 2-3.4-2-1.5zM13 15.5a3.5 3.5 0 110-7 3.5 3.5 0 010 7z',
  film: 'M4 4h16a1 1 0 011 1v14a1 1 0 01-1 1H4a1 1 0 01-1-1V5a1 1 0 011-1zm1 2v2h2V6H5zm0 4v2h2v-2H5zm0 4v2h2v-2H5zm12-8v2h2V6h-2zm0 4v2h2v-2h-2zm0 4v2h2v-2h-2zM9 6v12h6V6H9z',
  shield: 'M12 2l8 3v6c0 5-3.4 9.4-8 11-4.6-1.6-8-6-8-11V5l8-3zm-1 14l6-6-1.4-1.4L11 13.2 8.4 10.6 7 12l4 4z',
  link: 'M10.6 13.4a3 3 0 004.2 0l3-3a3 3 0 00-4.2-4.2l-1 1 1.4 1.4 1-1a1 1 0 011.4 1.4l-3 3a1 1 0 01-1.4 0l-1.4 1.4zm2.8-2.8a3 3 0 00-4.2 0l-3 3a3 3 0 004.2 4.2l1-1-1.4-1.4-1 1a1 1 0 01-1.4-1.4l3-3a1 1 0 011.4 0l1.4-1.4z',
  refresh: 'M17.6 6.4A8 8 0 104 12h2a6 6 0 111.8 4.2L10 14H4v6l2.4-2.4A8 8 0 1017.6 6.4z',
};

export type IconName = keyof typeof paths;

export function Icon({ name, size = 18 }: { name: IconName; size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor" aria-hidden="true" focusable="false">
      <path d={paths[name]} />
    </svg>
  );
}
