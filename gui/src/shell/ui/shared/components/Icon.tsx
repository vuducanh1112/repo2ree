interface SvgProps {
  d: string;
  size?: number;
  fill?: string;
  sw?: number;
  title?: string;
}

const Svg = ({ d, size = 15, fill = "none", sw = 1.6, title = "icon" }: SvgProps) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 24 24"
    fill={fill}
    stroke="currentColor"
    strokeWidth={sw}
    strokeLinecap="round"
    strokeLinejoin="round"
  >
    <title>{title}</title>
    <path d={d} />
  </svg>
);

export const Ic = {
  folder: (s = 15) => (
    <Svg
      size={s}
      d="M3 7a2 2 0 012-2h4l2 2h8a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V7z"
      fill="var(--tone-warning-line)"
      sw={0}
      title="Folder"
    />
  ),
  file: (s = 15) => (
    <Svg size={s} d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8l-6-6zm0 0v6h6" sw={1.4} />
  ),
  fileCode: (s = 15) => (
    <Svg
      size={s}
      sw={1.4}
      d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8l-6-6zm0 0v6h6M10 12l-2 2 2 2M14 12l2 2-2 2"
    />
  ),
  fileArchive: (s = 15) => (
    <Svg
      size={s}
      sw={1.4}
      d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8l-6-6zm0 0v6h6M11 12h2M11 15h2M11 18h2"
    />
  ),
  search: (s = 15) => <Svg size={s} d="M11 18a7 7 0 100-14 7 7 0 000 14zM21 21l-4.35-4.35" />,
  chevR: (s = 15) => <Svg size={s} d="M9 18l6-6-6-6" />,
  chevD: (s = 15) => <Svg size={s} d="M6 9l6 6 6-6" />,
  download: (s = 15) => (
    <Svg size={s} d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M7 10l5 5 5-5M12 15V3" />
  ),
  upload: (s = 15) => (
    <Svg size={s} d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M17 8l-5-5-5 5M12 3v12" />
  ),
  link: (s = 15) => (
    <Svg
      size={s}
      d="M10 13a5 5 0 007.54.54l3-3a5 5 0 00-7.07-7.07l-1.72 1.71M14 11a5 5 0 00-7.54-.54l-3 3a5 5 0 007.07 7.07l1.71-1.71"
    />
  ),
  star: (s = 15) => (
    <Svg
      size={s}
      d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"
      fill="currentColor"
      sw={0}
      title="Star"
    />
  ),
  check: (s = 15) => <Svg size={s} d="M20 6L9 17l-5-5" />,
  loader: (s = 15) => (
    <Svg
      size={s}
      d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"
    />
  ),
  archive: (s = 15) => <Svg size={s} d="M21 8v13H3V8M1 3h22v5H1zM10 12h4" />,
  cpu: (s = 15) => (
    <Svg
      size={s}
      d="M9 3H5a2 2 0 00-2 2v4m6-6h10a2 2 0 012 2v4M9 3v18m0 0h10a2 2 0 002-2V9M9 21H5a2 2 0 01-2-2V9m0 0h18"
    />
  ),
  shield: (s = 15) => <Svg size={s} d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />,
  layers: (s = 15) => <Svg size={s} d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" />,
  play: (s = 15) => <Svg size={s} d="M5 3l14 9-14 9V3z" fill="currentColor" sw={0} title="Play" />,
  plus: (s = 15) => <Svg size={s} d="M12 5v14M5 12h14" />,
  lock: (s = 15) => (
    <Svg
      size={s}
      d="M19 11H5a2 2 0 00-2 2v7a2 2 0 002 2h14a2 2 0 002-2v-7a2 2 0 00-2-2zM7 11V7a5 5 0 0110 0v4"
    />
  ),
  unlock: (s = 15) => (
    <Svg
      size={s}
      d="M19 11H5a2 2 0 00-2 2v7a2 2 0 002 2h14a2 2 0 002-2v-7a2 2 0 00-2-2zM7 11V7a5 5 0 019.9-1"
    />
  ),
  x: (s = 15) => <Svg size={s} d="M18 6L6 18M6 6l12 12" />,
  copy: (s = 15) => (
    <Svg
      size={s}
      d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"
    />
  ),
  externalLink: (s = 15) => (
    <Svg size={s} d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6M15 3h6v6M10 14L21 3" />
  ),
  info: (s = 15) => <Svg size={s} d="M12 16v-4m0-4h.01M12 2a10 10 0 100 20A10 10 0 0012 2z" />,
  package: (s = 15) => (
    <Svg
      size={s}
      d="M21 16V8a2 2 0 00-1-1.73l-7-4a2 2 0 00-2 0l-7 4A2 2 0 003 8v8a2 2 0 001 1.73l7 4a2 2 0 002 0l7-4A2 2 0 0021 16zM3.27 6.96L12 12.01l8.73-5.05M12 22.08V12"
    />
  ),
  globe: (s = 15) => (
    <Svg
      size={s}
      d="M12 2a10 10 0 100 20A10 10 0 0012 2zM2 12h20M12 2a15.3 15.3 0 010 20M12 2a15.3 15.3 0 000 20"
    />
  ),
  chip: (s = 15) => (
    <Svg
      size={s}
      d="M9 3H5a2 2 0 00-2 2v4m6-6h6m-6 0v18m6-18h4a2 2 0 012 2v4m-6-6v18m0 0H9m6 0h4a2 2 0 002-2v-4M3 9v6m18-6v6M3 15h6m12 0h-6"
    />
  ),
  arrowLeft: (s = 15) => <Svg size={s} d="M19 12H5M12 5l-7 7 7 7" />,
  terminal: (s = 15) => <Svg size={s} d="M4 17l6-6-6-6M12 19h8" />,
  refresh: (s = 15) => (
    <Svg
      size={s}
      d="M23 4v6h-6M1 20v-6h6M3.51 9a9 9 0 0114.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0020.49 15"
    />
  ),
  grid: (s = 15) => <Svg size={s} d="M3 3h7v7H3zM14 3h7v7h-7zM14 14h7v7h-7zM3 14h7v7H3z" />,
  files: (s = 15) => (
    <Svg size={s} d="M22 19a2 2 0 01-2 2H4a2 2 0 01-2-2V5a2 2 0 012-2h5l2 3h9a2 2 0 012 2z" />
  ),
  settings: (s = 15) => (
    <Svg
      size={s}
      d="M12 15a3 3 0 100-6 3 3 0 000 6zM19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 010-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 012.83-2.83l.06.06A1.65 1.65 0 009 4.68a1.65 1.65 0 001-1.51V3a2 2 0 014 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 2.83l-.06.06A1.65 1.65 0 0019.4 9a1.65 1.65 0 001.51 1H21a2 2 0 010 4h-.09a1.65 1.65 0 00-1.51 1z"
    />
  ),
  pen: (s = 15) => (
    <Svg size={s} d="M12 20h9M16.5 3.5a2.12 2.12 0 113 3L7 19l-4 1 1-4 12.5-12.5z" title="Pen" />
  ),
  menu: (s = 15) => <Svg size={s} d="M3 12h18M3 6h18M3 18h18" />,
};
