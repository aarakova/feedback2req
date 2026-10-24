import { useEffect, useState } from 'react';
import { ApiClient, ApiError, errorMessage } from './api';
import type { Session } from './api';
import { AuthForm } from './AuthForm';
import { ProjectList } from './Projects';
import { ProjectLayout } from './ProjectLayout';
import { AppLayout } from './Layout';
import { parseRoute } from './routes';
import { Brand, ErrorNotice, Loading } from './ui';

export function App() {
  const [session, setSession] = useState<Session | null | undefined>(undefined);
  const [sessionError, setSessionError] = useState('');
  const [revision, setRevision] = useState(0);
  const [rechecking, setRechecking] = useState(false);
  const [accessRevision, setAccessRevision] = useState(0);
  const [logoutState, setLogoutState] = useState<'idle' | 'busy' | 'failed'>('idle');
  const [logoutError, setLogoutError] = useState('');
  const [hash, setHash] = useState(window.location.hash);
  const [api] = useState(() => new ApiClient(() => { setSession(null); setRechecking(false); }));

  useEffect(() => {
    const controller = new AbortController();
    api.getSession(controller.signal).then(session => {
      if (!controller.signal.aborted) setSession(session);
    }).catch(error => {
      if (controller.signal.aborted) return;
      if (error instanceof ApiError && error.status === 401) setSession(null);
      else setSessionError(errorMessage(error));
    });
    return () => controller.abort();
  }, [api, revision]);

  useEffect(() => {
    const changed = () => setHash(window.location.hash);
    window.addEventListener('hashchange', changed);
    return () => window.removeEventListener('hashchange', changed);
  }, []);

  // Recheck cookie ownership and current permissions after returning from another tab.
  useEffect(() => {
    let pending: AbortController | undefined;
    async function recheck() {
      if (document.visibilityState !== 'visible' || logoutState !== 'idle') return;
      if (!session) {
        setSession(undefined); setSessionError(''); setRevision(n => n + 1);
        return;
      }
      pending?.abort();
      const controller = new AbortController();
      pending = controller;
      setRechecking(true);
      try {
        const current = await api.getSession(controller.signal);
        if (controller.signal.aborted) return;
        setSession(current); setAccessRevision(n => n + 1);
      } catch (error) {
        if (controller.signal.aborted) return;
        if (!(error instanceof ApiError && error.status === 401)) setSessionError(errorMessage(error));
      } finally {
        if (!controller.signal.aborted) setRechecking(false);
      }
    }
    function restored(event: PageTransitionEvent) { if (event.persisted) recheck(); }
    window.addEventListener('focus', recheck);
    window.addEventListener('pageshow', restored);
    document.addEventListener('visibilitychange', recheck);
    return () => {
      pending?.abort();
      window.removeEventListener('focus', recheck);
      window.removeEventListener('pageshow', restored);
      document.removeEventListener('visibilitychange', recheck);
    };
  }, [api, logoutState, session?.user.id]);

  async function logout() {
    if (logoutState === 'busy') return;
    setLogoutState('busy'); setLogoutError(''); setRechecking(false);
    try {
      await api.logout();
      setSession(null);
      window.location.hash = '/projects';
      setLogoutState('idle');
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        setSession(null); setLogoutState('idle');
      } else {
        setLogoutError(errorMessage(error)); setLogoutState('failed');
      }
    }
  }

  if (logoutState !== 'idle') return <main className="centered"><Brand /><section className="panel status-panel">
    {logoutState === 'busy' ? <Loading>Завершаем сессию…</Loading> : <>
      <h1>Выход не подтверждён</h1><ErrorNotice message={logoutError} />
      <p className="muted">Сервер мог сохранить сессию. Повторите выход.</p>
      <button className="primary" onClick={logout}>Повторить выход</button>
    </>}
  </section></main>;

  if (sessionError || session === undefined) return <main className="centered"><Brand />
    <section className="panel status-panel">{sessionError ? <><ErrorNotice message={sessionError} />
      <button className="primary" onClick={() => { setSessionError(''); setRevision(n => n + 1); }}>Повторить проверку сессии</button>
    </> : <Loading>Проверяем сессию…</Loading>}</section></main>;

  if (session === null) return <AuthForm api={api} onLogin={setSession} />;

  const route = parseRoute(hash);
  return <>
    {rechecking && <main className="centered"><Loading>Проверяем сессию…</Loading></main>}
    <div style={{ display: rechecking ? 'none' : undefined }}>
      {route.kind === 'project' ? <ProjectLayout key={`${session.user.id}/${route.id}`}
        api={api} user={session.user} onLogout={logout} id={route.id} accessRevision={accessRevision}
        section={route.section} selected={route.selected} />
        : <AppLayout user={session.user} onLogout={logout} listRoute={route.kind === 'projects'}>
          {route.kind === 'projects' ? <ProjectList key={`${session.user.id}/${accessRevision}`} api={api} />
            : <section className="panel empty"><h1>Страница не найдена</h1>
                <a href="#/projects">Вернуться к проектам</a></section>}
        </AppLayout>}
  </div></>;
}
