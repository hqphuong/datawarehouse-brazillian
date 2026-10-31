import React from 'react';

const P = {
  dashboard: <><rect x="3" y="3" width="7" height="9" rx="1"/><rect x="14" y="3" width="7" height="5" rx="1"/><rect x="14" y="12" width="7" height="9" rx="1"/><rect x="3" y="16" width="7" height="5" rx="1"/></>,
  dss: <path d="M13 2 3 14h9l-1 8 10-12h-9l1-8z"/>,
  olap: <><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18M3 15h18M9 3v18"/></>,
  etl: <><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M3 5v14a9 3 0 0 0 18 0V5M3 12a9 3 0 0 0 18 0"/></>,
  play: <polygon points="6 3 20 12 6 21 6 3"/>,
  alert: <path d="m21.7 18-8-14a2 2 0 0 0-3.4 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.7-3zM12 9v4M12 17h.01"/>,
  check: <path d="M20 6 9 17l-5-5"/>,
  x: <path d="M18 6 6 18M6 6l12 12"/>,
  sort: <path d="m7 15 5 5 5-5M7 9l5-5 5 5"/>,
  up: <path d="m18 15-6-6-6 6"/>,
  down: <path d="m6 9 6 6 6-6"/>,
  truck: <><path d="M10 17h4V5H2v12h3M20 17h2v-5l-3-4h-4v9h2"/><circle cx="7.5" cy="17.5" r="2.5"/><circle cx="17.5" cy="17.5" r="2.5"/></>,
  loader: <path d="M21 12a9 9 0 1 1-6.2-8.55"/>,
};

export const Icon = ({ n, size = 18, className = '' }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className={className}>
    {P[n]}
  </svg>
);