import { File } from 'expo-file-system';
import * as SecureStore from 'expo-secure-store';
import { Platform } from 'react-native';

const BASE = process.env.EXPO_PUBLIC_API_URL;
if (!BASE) throw new Error('Set EXPO_PUBLIC_API_URL in .env');

export type Session = {
  access_token: string;
  refresh_token: string;
  access_expires_in_seconds: number;
  member_status: 'PENDING' | 'ACTIVE' | 'REJECTED' | 'ARCHIVED';
};

// Keychain/Keystore on device; SecureStore has no web build, so the web preview falls back to localStorage.
export const store =
  Platform.OS === 'web'
    ? {
        get: async (k: string) => localStorage.getItem(k),
        set: async (k: string, v: string) => localStorage.setItem(k, v),
        del: async (k: string) => localStorage.removeItem(k),
      }
    : { get: SecureStore.getItemAsync, set: SecureStore.setItemAsync, del: SecureStore.deleteItemAsync };

// The access token lives in memory only (15 min); the refresh token (30 days) survives restarts.
let access: string | null = null;
let status: Session['member_status'] | null = null;

/** From the last login/refresh; the (app) layout lets only ACTIVE members past. */
export const memberStatus = () => status;

/** The backend serves uploads at relative /media/... paths. */
export const mediaUrl = (path: string | null) => (path ? `${BASE}${path}` : null);

/** expo-image source for endpoints behind the bearer token, e.g. matrimony photos. */
export const authedImage = (path: string) => ({ uri: `${BASE}${path}`, headers: { Authorization: `Bearer ${access}` } });

// Forms take DD/MM/YYYY; the API speaks ISO. The server rejects impossible dates.
export const isoDate = (dmy: string) => dmy.replace(/^(\d{2})\/(\d{2})\/(\d{4})$/, '$3-$2-$1');
export const dmyDate = (iso: string) => iso.replace(/^(\d{4})-(\d{2})-(\d{2})$/, '$3/$2/$1');
/** 'DD/MM/YYYY' as a birth date: null unless it is a real day between 1900 and today (31/02, 33/20/2000 are not). */
export function parseDmy(dmy: string): Date | null {
  const m = /^(\d{2})\/(\d{2})\/(\d{4})$/.exec(dmy);
  if (!m) return null;
  const [d, mo, y] = [Number(m[1]), Number(m[2]), Number(m[3])];
  const date = new Date(y, mo - 1, d);
  // the Date constructor rolls 31/02 over into March: a real date keeps its own day and month
  if (date.getDate() !== d || date.getMonth() !== mo - 1 || y < 1900 || date > new Date()) return null;
  return date;
}
const pad2 = (n: number) => String(n).padStart(2, '0');
export const toDmy = (d: Date) => `${pad2(d.getDate())}/${pad2(d.getMonth() + 1)}/${d.getFullYear()}`;

export async function saveSession(s: Session | null) {
  access = s?.access_token ?? null;
  status = s?.member_status ?? null;
  if (s) await store.set('refresh_token', s.refresh_token);
  else await store.del('refresh_token');
}

let refreshing: Promise<Session | null> | null = null;

/** Swap the stored refresh token for a fresh session; null = logged out. Concurrent callers share one request,
 *  because the server rotates the token and a second request with the old one would 401. */
export function restoreSession(): Promise<Session | null> {
  refreshing ??= (async () => {
    const refresh_token = await store.get('refresh_token');
    if (!refresh_token) return null;
    try {
      const s = await api<Session>('/member/auth/refresh', { method: 'POST', body: { refresh_token } }, false);
      await saveSession(s);
      return s;
    } catch {
      await saveSession(null);
      return null;
    }
  })().finally(() => (refreshing = null));
  return refreshing;
}

export async function logout() {
  const refresh_token = await store.get('refresh_token');
  await saveSession(null);
  if (refresh_token) await api('/member/auth/logout', { method: 'POST', body: { refresh_token } }, false).catch(() => {});
}

function detail(json: any, fallback: string): string {
  const d = json?.detail;
  if (typeof d === 'string') return d;
  if (Array.isArray(d)) return d.map((e) => e.msg.replace(/^Value error, /, '')).join('; ');
  return fallback;
}

/** fetch with the bearer token; a 401 refreshes once and retries. Throws Error(message from FastAPI's `detail`). */
export async function api<T = any>(
  path: string,
  { method = 'GET', body }: { method?: string; body?: unknown } = {},
  retry = true,
): Promise<T> {
  const headers: Record<string, string> = access ? { Authorization: `Bearer ${access}` } : {};
  // FormData sets its own multipart Content-Type with the boundary
  const form = body instanceof FormData;
  if (body !== undefined && !form) headers['Content-Type'] = 'application/json';
  // a server that accepts but never answers would otherwise hang the caller (blank start screen) forever
  const abort = new AbortController();
  const timer = setTimeout(() => abort.abort(), 15000);
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : form ? body : JSON.stringify(body),
      signal: abort.signal,
    });
  } catch (e) {
    if (__DEV__) console.warn(path, e); // the real cause; the message below covers bad requests too
    throw new Error('Cannot reach the server. Check your connection.');
  } finally {
    clearTimeout(timer);
  }
  if (res.status === 401 && retry && access && (await restoreSession())) return api(path, { method, body }, false);
  if (!res.ok)
    throw Object.assign(new Error(detail(await res.json().catch(() => null), `${res.status} ${res.statusText}`)), { status: res.status });
  return res.status === 204 ? (null as T) : res.json();
}

export type PickedFile = { uri: string; name: string; mimeType: string };

/** Sends one file as the multipart field `file`, which is what every backend upload expects. */
export async function upload<T = any>(path: string, method: string, file: PickedFile): Promise<T> {
  const body = new FormData();
  // web pickers hand back blob: URIs. Native: Expo's global fetch (expo/fetch) rejects RN's {uri, name, type}
  // parts and needs something with bytes(), which expo-file-system's File has.
  if (Platform.OS === 'web') body.append('file', await (await fetch(file.uri)).blob(), file.name);
  else body.append('file', new File(file.uri) as unknown as Blob, file.name);
  return api<T>(path, { method, body });
}
