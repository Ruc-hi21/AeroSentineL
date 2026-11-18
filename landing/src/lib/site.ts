// The deployed Streamlit console. Set NEXT_PUBLIC_DASHBOARD_URL at build time.
export const DASHBOARD_URL =
  (process.env.NEXT_PUBLIC_DASHBOARD_URL || 'http://localhost:8501').replace(/\/$/, '');

export const REPO_URL = 'https://github.com/Ruc-hi21/AeroSentineL';

export const NAV = [
  { href: '#problem', label: 'Problem', id: 'problem' },
  { href: '#answers', label: 'What you get', id: 'answers' },
  { href: '#how', label: 'How it works', id: 'how' },
  { href: '#components', label: 'Components', id: 'components' },
  { href: '#evaluation', label: 'Evaluation', id: 'evaluation' },
  { href: '#faq', label: 'FAQ', id: 'faq' },
] as const;

/** Base motion curve, shared by Motion and CSS. */
export const EASE: [number, number, number, number] = [0.22, 1, 0.36, 1];
