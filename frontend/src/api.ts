export interface User { id: string; login: string }
export interface Session { user: User; csrf_token: string }
export interface Project {
  id: string;
  owner_id: string;
  name: string;
  execution_mode: string;
  permissions: { is_owner: boolean; is_member: boolean; can_approve: boolean };
}
export interface Page<T> { items: T[]; next_cursor: string | null }
export interface TextSource { id: string; state_id: string; kind: 'text'; text: string }
export interface ProductDocument { id: string; state_id: string; title: string; text: string }
export type Material = TextSource | ProductDocument;
export type MaterialKind = 'sources' | 'documents';

export class ApiError extends Error {
  constructor(public status: number, public code: string, public requestId?: string) {
    super(code);
  }
}

// Credentials and CSRF live in memory. The HttpOnly session cookie belongs to the browser.
export class ApiClient {
  private csrf: string | null = null;
  constructor(private onUnauthorized: () => void) {}

  clearSession() { this.csrf = null; }

  async request<T>(path: string, options: {
    method?: string; body?: unknown; signal?: AbortSignal; anonymous?: boolean;
  } = {}): Promise<T> {
    const method = options.method ?? 'GET';
    const headers: Record<string, string> = { Accept: 'application/json' };
    if (options.body !== undefined) headers['Content-Type'] = 'application/json';
    if (method !== 'GET' && !options.anonymous && this.csrf) {
      headers['X-CSRF-Token'] = this.csrf;
    }
    const response = await fetch(`/api/v1${path}`, {
      method, headers, credentials: 'same-origin', cache: 'no-store',
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
      signal: options.signal,
    });
    if (options.signal?.aborted) throw new DOMException('Aborted', 'AbortError');
    if (!response.ok) {
      if (response.status === 401 && !options.anonymous) {
        this.clearSession();
        this.onUnauthorized();
      }
      const data = await response.json().catch(() => null);
      throw new ApiError(response.status, data?.error?.code ?? 'http_error',
        data?.error?.request_id);
    }
    if (response.status === 204) return undefined as T;
    return response.json() as Promise<T>;
  }

  async getSession(signal?: AbortSignal) {
    const session = await this.request<Session>('/auth/session', { signal });
    this.csrf = session.csrf_token;
    return session;
  }

  async login(login: string, password: string, signal?: AbortSignal) {
    const session = await this.request<Session>('/auth/session', {
      method: 'POST', body: { login, password }, anonymous: true, signal,
    });
    this.csrf = session.csrf_token;
    return session;
  }

  register(login: string, password: string, signal?: AbortSignal) {
    return this.request<User>('/auth/register', {
      method: 'POST', body: { login, password }, anonymous: true, signal,
    });
  }

  async logout() {
    await this.request<void>('/auth/session', { method: 'DELETE' });
    this.clearSession();
  }
}

export function errorMessage(error: unknown): string {
  if (!(error instanceof ApiError)) return 'Не удалось связаться с сервером. Проверьте соединение и повторите запрос.';
  const messages: Record<string, string> = {
    invalid_credentials: 'Неверный логин или пароль.',
    login_unavailable: 'Этот логин уже занят. Выберите другой.',
    invalid_login: 'Логин должен содержать от 1 до 128 символов после нормализации, без управляющих символов.',
    invalid_request: 'Проверьте заполнение полей и допустимую длину значений.',
    csrf_rejected: 'Не удалось подтвердить запрос. Перезагрузите страницу и повторите действие.',
    origin_rejected: 'Адрес приложения не разрешён сервером. Проверьте настройку F2R_ALLOWED_ORIGIN.',
    rate_limited: 'Слишком много попыток. Подождите немного и попробуйте снова.',
    body_too_large: 'Объём запроса превышает допустимый предел.',
    text_too_large: 'Текст превышает допустимый на сервере объём. Содержимое формы сохранено; сократите его перед отправкой.',
    invalid_text: 'Введите непустой текст без недопустимых символов. Проверьте также название документа.',
  };
  return messages[error.code] ?? (error.status === 401
    ? 'Сессия завершена. Войдите снова.'
    : error.status === 404 ? 'Проект не найден или доступ к нему отозван.'
    : error.status === 403 ? 'Недостаточно прав для этого действия.'
    : 'Сервер не смог выполнить запрос. Попробуйте ещё раз.');
}

export function projectUnavailable(error: unknown): boolean {
  return error instanceof ApiError && (error.status === 404 ||
    (error.status === 403 && error.code === 'forbidden'));
}
