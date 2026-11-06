import { useEffect, useState } from 'react';
import { ApiClient, ApiError, errorMessage } from '../api';
import type { Page } from '../api';

export function checkProject(error: unknown, onMissing?: () => void) {
  if (error instanceof ApiError && (error.status === 404 || error.status === 403 && error.code === 'forbidden')) onMissing?.();
}
export function useRead<T>(api: ApiClient, path: string | undefined, onMissing?: () => void) {
  const [revision, setRevision] = useState(0);
  const [result, setResult] = useState<{ path?: string; data?: T; loading: boolean; error: string }>({ loading: false, error: '' });
  useEffect(() => {
    const controller = new AbortController();
    if (!path) { setResult({ loading: false, error: '' }); return () => controller.abort(); }
    setResult({ path, loading: true, error: '' });
    api.request<T>(path, { signal: controller.signal }).then(data => {
      if (!controller.signal.aborted) setResult({ path, data, loading: false, error: '' });
    }).catch(error => {
      if (controller.signal.aborted) return;
      setResult({ path, loading: false, error: errorMessage(error) }); checkProject(error, onMissing);
    });
    return () => controller.abort();
  }, [api, path, revision, onMissing]);
  return { data: result.path === path ? result.data : undefined, loading: !!path && (result.path !== path || result.loading),
    error: result.path === path ? result.error : '', reload: () => setRevision(value => value + 1) };
}

export function usePages<T extends { id: string }>(api: ApiClient, path: string, onMissing?: () => void) {
  const [revision, setRevision] = useState(0);
  const [page, setPage] = useState<{ path: string; items: T[]; cursor: string | null; next: string | null; loading: boolean; error: string }>(
    { path, items: [], cursor: null, next: null, loading: true, error: '' });
  const cursor = page.path === path ? page.cursor : null;
  useEffect(() => {
    const controller = new AbortController();
    setPage(previous => ({ path, items: previous.path === path ? previous.items : [], cursor,
      next: previous.path === path ? previous.next : null, loading: true, error: '' }));
    const query = cursor ? `${path.includes('?') ? '&' : '?'}cursor=${encodeURIComponent(cursor)}` : '';
    api.request<Page<T>>(path + query, { signal: controller.signal }).then(result => {
      if (controller.signal.aborted) return;
      setPage(previous => ({ path, cursor, next: result.next_cursor, loading: false, error: '',
        items: cursor && previous.path === path ? [...previous.items, ...result.items.filter(item => !previous.items.some(old => old.id === item.id))] : result.items }));
    }).catch(error => {
      if (controller.signal.aborted) return;
      setPage(previous => ({ ...previous, loading: false, error: errorMessage(error) })); checkProject(error, onMissing);
    });
    return () => controller.abort();
  }, [api, path, cursor, revision, onMissing]);
  return { items: page.path === path ? page.items : [], next: page.path === path ? page.next : null,
    loading: page.path !== path || page.loading, error: page.path === path ? page.error : '',
    more: () => setPage(previous => previous.next && !previous.loading ? { ...previous, cursor: previous.next } : previous),
    reload: () => { setPage({ path, items: [], cursor: null, next: null, loading: true, error: '' }); setRevision(value => value + 1); } };
}
