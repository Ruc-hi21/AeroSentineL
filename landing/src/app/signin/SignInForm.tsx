'use client';

import { useState } from 'react';
import Link from 'next/link';
import { Eye, EyeSlash, WarningCircle } from '@phosphor-icons/react';
import { DASHBOARD_URL } from '@/lib/site';

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;

export default function SignInForm() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [show, setShow] = useState(false);
  const [touched, setTouched] = useState({ email: false, password: false });
  const [submitted, setSubmitted] = useState(false);
  const [loading, setLoading] = useState(false);

  const emailError = !email ? 'Enter your work email.' : !EMAIL.test(email) ? 'That email address is missing something. Check the part after the @.' : '';
  const passwordError = !password ? 'Enter your password.' : password.length < 8 ? 'Passwords are at least 8 characters.' : '';
  const showEmailError = (touched.email || submitted) && emailError;
  const showPasswordError = (touched.password || submitted) && passwordError;

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitted(true);
    if (emailError || passwordError) return;
    setLoading(true);
    try {
      localStorage.setItem('aerosentinel.user', JSON.stringify({ email, at: Date.now() }));
    } catch {
      /* storage can be unavailable in private windows; sign in still works */
    }
    window.setTimeout(() => window.location.assign(DASHBOARD_URL), 900);
  }

  const field =
    'body-3 w-full rounded-lg border bg-base px-3 py-3 text-ink placeholder:text-faint transition-[border-color,box-shadow] duration-300 ease-[cubic-bezier(0.22,1,0.36,1)] focus:outline-none focus:ring-2 focus:ring-accent/40';

  return (
    <form noValidate onSubmit={onSubmit} className="mt-8 space-y-6" aria-describedby="signin-note">
      <div>
        <label htmlFor="email" className="title-4 text-ink">Work email</label>
        <input
          id="email"
          type="email"
          autoComplete="email"
          inputMode="email"
          placeholder="name@airline.example"
          value={email}
          onChange={(e) => setEmail(e.target.value.trim())}
          onBlur={() => setTouched((t) => ({ ...t, email: true }))}
          aria-invalid={!!showEmailError}
          aria-describedby={showEmailError ? 'email-error' : undefined}
          className={`${field} mt-2 ${showEmailError ? 'border-critical' : 'border-line-strong focus:border-accent'}`}
        />
        {showEmailError && (
          <p id="email-error" className="caption-2 mt-2 flex items-center gap-2 text-critical">
            <WarningCircle size={16} aria-hidden="true" /> {emailError}
          </p>
        )}
      </div>

      <div>
        <div className="flex items-center justify-between">
          <label htmlFor="password" className="title-4 text-ink">Password</label>
        </div>
        <div className="relative mt-2">
          <input
            id="password"
            type={show ? 'text' : 'password'}
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            onBlur={() => setTouched((t) => ({ ...t, password: true }))}
            aria-invalid={!!showPasswordError}
            aria-describedby={showPasswordError ? 'password-error' : undefined}
            className={`${field} pr-12 ${showPasswordError ? 'border-critical' : 'border-line-strong focus:border-accent'}`}
          />
          <button
            type="button"
            onClick={() => setShow((s) => !s)}
            aria-label={show ? 'Hide password' : 'Show password'}
            className="absolute right-2 top-1/2 grid h-8 w-8 -translate-y-1/2 place-items-center rounded-md text-faint transition-colors duration-300 hover:text-ink"
          >
            {show ? <EyeSlash size={18} /> : <Eye size={18} />}
          </button>
        </div>
        {showPasswordError && (
          <p id="password-error" className="caption-2 mt-2 flex items-center gap-2 text-critical">
            <WarningCircle size={16} aria-hidden="true" /> {passwordError}
          </p>
        )}
      </div>

      <button type="submit" disabled={loading} className="btn btn-primary btn-lg button-md relative w-full overflow-hidden disabled:cursor-progress">
        {loading ? 'Opening your console' : 'Sign in'}
        {loading && <span className="signin-progress absolute inset-x-0 bottom-0 h-0.5 bg-white/50" aria-hidden="true" />}
      </button>

      <p id="signin-note" className="caption-2 rounded-lg border border-line bg-surface p-3 text-muted">
        Team accounts are being set up for pilot teams. Until then, signing in opens the shared console with sample data.
      </p>

      <p className="body-6 text-center text-muted">
        Just looking?{' '}
        <Link href="/demo/" className="text-accent underline-offset-4 hover:underline">
          Try the live demo without an account
        </Link>
      </p>
    </form>
  );
}
