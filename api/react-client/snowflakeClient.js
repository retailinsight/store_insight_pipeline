// react-client/src/api/snowflakeClient.js
// Drop this file into your React app and import from it.
// Handles auth token management, automatic refresh, and SSE streaming.

const BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:3001';

// ─── Token Storage ────────────────────────────────────────────────────────────

const tokenStore = {
  get access()   { return localStorage.getItem('accessToken'); },
  get refresh()  { return localStorage.getItem('refreshToken'); },
  set(access, refresh) {
    localStorage.setItem('accessToken',  access);
    localStorage.setItem('refreshToken', refresh);
  },
  clear() {
    localStorage.removeItem('accessToken');
    localStorage.removeItem('refreshToken');
  },
};

// ─── Core Fetch Wrapper ───────────────────────────────────────────────────────

let isRefreshing = false;
let refreshQueue = [];

async function apiFetch(path, options = {}) {
  const headers = {
    'Content-Type': 'application/json',
    ...(tokenStore.access ? { Authorization: `Bearer ${tokenStore.access}` } : {}),
    ...options.headers,
  };

  let response = await fetch(`${BASE_URL}${path}`, { ...options, headers });

  // Attempt silent token refresh on 401
  if (response.status === 401 && tokenStore.refresh) {
    if (!isRefreshing) {
      isRefreshing = true;
      try {
        const refreshRes = await fetch(`${BASE_URL}/auth/refresh`, {
          method:  'POST',
          headers: { 'Content-Type': 'application/json' },
          body:    JSON.stringify({ refreshToken: tokenStore.refresh }),
        });

        if (refreshRes.ok) {
          const { accessToken, refreshToken } = await refreshRes.json();
          tokenStore.set(accessToken, refreshToken);
          refreshQueue.forEach((cb) => cb(accessToken));
        } else {
          tokenStore.clear();
          window.dispatchEvent(new Event('auth:logout'));
        }
      } finally {
        isRefreshing = false;
        refreshQueue = [];
      }
    } else {
      // Queue concurrent requests while refresh is in progress
      await new Promise((resolve) => refreshQueue.push(resolve));
    }

    // Retry the original request with the new token
    response = await fetch(`${BASE_URL}${path}`, {
      ...options,
      headers: { ...headers, Authorization: `Bearer ${tokenStore.access}` },
    });
  }

  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw Object.assign(new Error(body.error || `HTTP ${response.status}`), { status: response.status, body });
  }

  return response.json();
}

// ─── Auth ─────────────────────────────────────────────────────────────────────

export const auth = {
  async login(username, password) {
    const data = await apiFetch('/auth/login', {
      method: 'POST',
      body:   JSON.stringify({ username, password }),
    });
    tokenStore.set(data.accessToken, data.refreshToken);
    return data.user;
  },

  async register(username, password, role = 'viewer') {
    return apiFetch('/auth/register', {
      method: 'POST',
      body:   JSON.stringify({ username, password, role }),
    });
  },

  async logout() {
    await apiFetch('/auth/logout', {
      method: 'POST',
      body:   JSON.stringify({ refreshToken: tokenStore.refresh }),
    }).catch(() => {});
    tokenStore.clear();
  },

  isLoggedIn: () => Boolean(tokenStore.access),
};

// ─── Query ────────────────────────────────────────────────────────────────────

export const query = {
  /** Execute SQL and get all rows at once */
  async execute(sql, binds = []) {
    return apiFetch('/query/execute', {
      method: 'POST',
      body:   JSON.stringify({ sql, binds }),
    });
  },

  /**
   * Stream large results via SSE.
   * @param {string}   sql
   * @param {Array}    binds
   * @param {Function} onRow   - called for every row: (row) => void
   * @param {Function} onDone  - called when stream ends: ({ rowCount }) => void
   * @param {Function} onError - called on error: (error) => void
   * @returns {Function} cancel – call to abort the stream
   */
  stream(sql, binds = [], { onRow, onDone, onError } = {}) {
    const controller = new AbortController();

    (async () => {
      try {
        const res = await fetch(`${BASE_URL}/query/stream`, {
          method:  'POST',
          headers: {
            'Content-Type':  'application/json',
            Authorization:   `Bearer ${tokenStore.access}`,
          },
          body:   JSON.stringify({ sql, binds }),
          signal: controller.signal,
        });

        const reader  = res.body.getReader();
        const decoder = new TextDecoder();
        let   buffer  = '';

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop(); // keep incomplete line

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              try {
                const parsed = JSON.parse(line.slice(6));
                onRow?.(parsed);
              } catch { /* ignore parse errors */ }
            }
            if (line.startsWith('event: done')) {
              const dataLine = lines[lines.indexOf(line) + 1] || '';
              const meta = dataLine.startsWith('data: ') ? JSON.parse(dataLine.slice(6)) : {};
              onDone?.(meta);
            }
            if (line.startsWith('event: error')) {
              const dataLine = lines[lines.indexOf(line) + 1] || '';
              const err = dataLine.startsWith('data: ') ? JSON.parse(dataLine.slice(6)) : {};
              onError?.(err);
            }
          }
        }
      } catch (err) {
        if (err.name !== 'AbortError') onError?.(err);
      }
    })();

    return () => controller.abort();
  },
};

// ─── CRUD ─────────────────────────────────────────────────────────────────────

export const data = {
  list:     (table, params = {}) => apiFetch(`/data/${table}?${new URLSearchParams(params)}`),
  getById:  (table, id)          => apiFetch(`/data/${table}/${id}`),
  create:   (table, body)        => apiFetch(`/data/${table}`,    { method: 'POST',   body: JSON.stringify(body) }),
  update:   (table, id, body)    => apiFetch(`/data/${table}/${id}`, { method: 'PUT',    body: JSON.stringify(body) }),
  remove:   (table, id)          => apiFetch(`/data/${table}/${id}`, { method: 'DELETE' }),
};

export default { auth, query, data };
