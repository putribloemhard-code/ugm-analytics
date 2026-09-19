export type Metadata = {
  years: { min: string; max: string };
  pillars: string[];
  topics: { id: string; label: string; pillar: string; official_topic: string; sdgs: number[]; indicator: string; formula: string; unit: string }[];
  sdgs: { id: number; label: string }[];
  units: { id: string; label: string; category: string }[];
  updated_at: string | null;
};

export type AnalyticsResult = {
  mode: string;
  filters: Record<string, unknown>;
  data_as_of: string | null;
  summary: Record<string, string | number>;
  narrative: string;
  charts: Record<string, unknown[]>;
  tables: Record<string, unknown[]>;
  caveats: string[];
};

type QueryValue = string | number | string[] | number[] | undefined;
const API_BASE = import.meta.env.VITE_API_BASE_URL ?? `${import.meta.env.BASE_URL}api/v1`;

function toQuery(params: Record<string, QueryValue>) {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === '' || (Array.isArray(value) && value.length === 0)) continue;
    query.set(key, Array.isArray(value) ? value.join(',') : String(value));
  }
  return query.toString();
}

async function get<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`);
  if (!response.ok) throw new Error(`API request failed (${response.status})`);
  return response.json() as Promise<T>;
}

export type AccreditationResult = {
  summary: Record<string, number>;
  faculties: Record<string, unknown>[];
  programs: Record<string, unknown>[];
  manual: Record<string, unknown>[];
  publications: Record<string, unknown>[];
  uploads: Record<string, unknown>[];
  requirements: { led: Record<string, unknown>[]; lkps: Record<string, unknown>[] };
};

export function getMetadata() { return get<Metadata>('/analytics/metadata'); }
export function getAccreditation() { return get<AccreditationResult>('/analytics/accreditation'); }

export async function accreditationMe() { const response = await fetch(`${API_BASE}/analytics/accreditation/auth/me`, { credentials: 'include' }); if (!response.ok) return null; return (await response.json()).user as { id: number; email: string; nama: string; is_admin: boolean }; }
export async function accreditationLogin(email: string, password: string) { const response = await fetch(`${API_BASE}/analytics/accreditation/auth/login`, { method: 'POST', credentials: 'include', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email, password }) }); const body = await response.json(); if (!response.ok) throw new Error(body.detail ?? 'Login gagal'); return body.user; }
export async function accreditationRegister(email: string, name: string, password: string) { const response = await fetch(`${API_BASE}/analytics/accreditation/auth/register`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email, name, password }) }); const body = await response.json(); if (!response.ok) throw new Error(body.detail ?? 'Registrasi gagal'); return body; }
export async function accreditationLogout() { await fetch(`${API_BASE}/analytics/accreditation/auth/logout`, { method: 'POST', credentials: 'include' }); }
export async function accreditationUpload(prodiId: string, file: File) { const form = new FormData(); form.append('prodi_id', prodiId); form.append('file', file); const response = await fetch(`${API_BASE}/analytics/accreditation/uploads`, { method: 'POST', credentials: 'include', body: form }); const body = await response.json(); if (!response.ok) throw new Error(body.detail ?? 'Upload gagal'); return body; }
export function getHomeSummary() { return get<Record<string, string | number | null>>('/analytics/home-summary'); }
export function searchAnalytics(q: string) { return get<{ page: string; pillars: string[]; topics: string[]; sdgs: number[]; years: string[] | null; explanation: string }>(`/analytics/search?${toQuery({ q })}`); }
export function getImpact(params: Record<string, QueryValue>, mode: 'impact' | 'impact-sdgs') { return get<AnalyticsResult>(`/analytics/impact?${toQuery({ ...params, mode })}`); }
export function getSdgs(params: Record<string, QueryValue>) { return get<AnalyticsResult>(`/analytics/sdgs?${toQuery(params)}`); }
export function getNews(params: Record<string, QueryValue>, page: number, pageSize: number) { return get<{ rows: unknown[]; total: number; page: number; page_size: number }>(`/analytics/news?${toQuery({ ...params, page, page_size: pageSize })}`); }

export async function downloadReport(payload: Record<string, unknown>) {
  const response = await fetch(`${API_BASE}/analytics/reports`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
  if (!response.ok) throw new Error(`Report request failed (${response.status})`);
  return response.blob();
}
