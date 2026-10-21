import { useEffect, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { ApiClient, errorMessage } from './api';
import type { Session } from './api';
import { Brand, ErrorNotice } from './ui';

export function AuthForm({ api, onLogin }: { api: ApiClient; onLogin: (session: Session) => void }) {
  const [registering, setRegistering] = useState(false);
  const [login, setLogin] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const pending = useRef<AbortController | null>(null);
  useEffect(() => () => pending.current?.abort(), []);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    if (registering && [...password].length < 12) {
      setError('Пароль должен содержать не менее 12 символов.');
      return;
    }
    setBusy(true); setError(''); setNotice('');
    const controller = new AbortController();
    pending.current = controller;
    try {
      if (registering) {
        const user = await api.register(login, password, controller.signal);
        if (controller.signal.aborted) return;
        setLogin(user.login);
        setPassword('');
        setRegistering(false);
        setNotice('Учётная запись создана. Введите пароль, чтобы войти.');
      } else {
        const session = await api.login(login, password, controller.signal);
        if (controller.signal.aborted) return;
        setPassword('');
        onLogin(session);
      }
    } catch (error) { if (!controller.signal.aborted) setError(errorMessage(error)); }
    finally { if (!controller.signal.aborted) setBusy(false); }
  }

  return <main className="auth-layout">
    <section className="auth-intro">
      <Brand />
      <div><p className="eyebrow">Обратная связь → требования</p>
        <h1>Работа над продуктом<br /><span className="accent">начинается с людей.</span></h1>
        <p className="muted">Ваши проекты, материалы и решения — в одном рабочем пространстве.</p>
      </div>
      <p className="muted small">feedback2req</p>
    </section>
    <section className="auth-panel panel" aria-labelledby="auth-title">
      <p className="eyebrow">Рабочее пространство</p>
      <h2 id="auth-title">{registering ? 'Регистрация' : 'Вход в аккаунт'}</h2>
      <p className="muted">{registering ? 'Создайте локальную учётную запись.' : 'Войдите, чтобы открыть доступные проекты.'}</p>
      {notice && <p className="success-notice" role="status">{notice}</p>}
      {error && <ErrorNotice message={error} />}
      <form onSubmit={submit} className="stack">
        <label>Логин<input name="login" autoComplete="username" required maxLength={256}
          value={login} onChange={e => setLogin(e.target.value)} disabled={busy} /></label>
        <label>Пароль<input name="password" type="password" required maxLength={1024}
          autoComplete={registering ? 'new-password' : 'current-password'}
          aria-describedby={registering ? 'password-help' : undefined}
          value={password} onChange={e => setPassword(e.target.value)} disabled={busy} /></label>
        {registering && <p id="password-help" className="muted small">От 12 до 1024 символов. Пробелы в пароле сохраняются.</p>}
        <button className="primary" disabled={busy}>{busy ? 'Подождите…' : registering ? 'Создать аккаунт' : 'Войти'}</button>
      </form>
      <button className="text-button" disabled={busy} onClick={() => {
        setRegistering(!registering); setPassword(''); setError(''); setNotice('');
      }}>{registering ? 'Уже есть аккаунт? Войти' : 'Нет аккаунта? Зарегистрироваться'}</button>
    </section>
  </main>;
}
