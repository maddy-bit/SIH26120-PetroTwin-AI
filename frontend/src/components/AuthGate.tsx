import React, { useEffect, useState } from 'react';
import { ApiError, api } from '../services/api';

type GateState = 'checking' | 'login' | 'ready' | 'error';

export function AuthGate({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<GateState>('checking');
  const [authRequired, setAuthRequired] = useState(false);
  const [user, setUser] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;
    const onUnauthorized = () => {
      if (active) {
        setUser(null);
        setState('login');
      }
    };
    window.addEventListener('petrotwin:unauthorized', onUnauthorized);
    api.getHealth().then(async (health) => {
      if (!active) return;
      setAuthRequired(health.auth_required);
      if (!health.auth_required) {
        setState('ready');
        return;
      }
      try {
        const result = await api.getCurrentUser();
        if (active) {
          setUser(result.user);
          setState('ready');
        }
      } catch (reason) {
        if (active) {
          if (reason instanceof ApiError && reason.status === 401) setState('login');
          else {
            setError(reason instanceof Error ? reason.message : 'Authentication service unavailable.');
            setState('error');
          }
        }
      }
    }).catch((reason: unknown) => {
      if (active) {
        setError(reason instanceof Error ? reason.message : 'Unable to reach the PETRO-TWIN API.');
        setState('error');
      }
    });
    return () => {
      active = false;
      window.removeEventListener('petrotwin:unauthorized', onUnauthorized);
    };
  }, []);

  const signOut = async () => {
    try { await api.logout(); } catch { /* local token is cleared even if the API is unreachable */ }
    setUser(null);
    setState('login');
  };

  if (state === 'checking') {
    return <main className="auth-screen"><section className="auth-panel" role="status">Checking API and session…</section></main>;
  }
  if (state === 'error') {
    return <main className="auth-screen"><section className="auth-panel">
      <h1>PETRO-TWIN unavailable</h1>
      <p role="alert">{error}</p>
      <button type="button" onClick={() => window.location.reload()}>Retry connection</button>
    </section></main>;
  }
  if (state === 'login') {
    return <LoginForm onSuccess={(authenticatedUser) => {
      setUser(authenticatedUser);
      setState('ready');
    }} />;
  }
  return <>
    {authRequired && user && <div className="auth-session-bar">
      <span>Signed in as <strong>{String(user.username)}</strong> · {String(user.role)}</span>
      <button type="button" onClick={signOut}>Sign out</button>
    </div>}
    {children}
  </>;
}

function LoginForm({ onSuccess }: { onSuccess: (user: Record<string, unknown>) => void }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const submit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setBusy(true);
    setError('');
    try {
      const user = await api.login(username.trim(), password);
      setPassword('');
      onSuccess(user);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Sign-in failed.');
    } finally {
      setBusy(false);
    }
  };

  return <main className="auth-screen">
    <form className="auth-panel" onSubmit={submit}>
      <div className="auth-eyebrow">SECURE ACCESS · SIH26120</div>
      <h1>PETRO-TWIN AI</h1>
      <p>Sign in using an account provisioned by a system administrator.</p>
      <label htmlFor="auth-username">Username</label>
      <input id="auth-username" autoComplete="username" value={username}
        onChange={(event) => setUsername(event.target.value)} required />
      <label htmlFor="auth-password">Password</label>
      <input id="auth-password" type="password" autoComplete="current-password"
        value={password} onChange={(event) => setPassword(event.target.value)} required />
      {error && <p role="alert" className="auth-error">{error}</p>}
      <button type="submit" disabled={busy || !username.trim() || !password}>
        {busy ? 'Signing in…' : 'Sign in'}
      </button>
    </form>
  </main>;
}
