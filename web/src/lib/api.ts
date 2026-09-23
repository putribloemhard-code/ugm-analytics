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
  if (!response.ok) throw new Error(await pesanError(response));
  return response.json() as Promise<T>;
}

/** Ambil pesan `detail` dari API supaya penyebabnya terlihat di layar, bukan hanya kode status.
 *  Contoh: "Basis data tidak dapat dihubungi..." saat servis MySQL belum menyala. */
async function pesanError(response: Response): Promise<string> {
  try {
    const body = await response.json();
    if (typeof body?.detail === 'string' && body.detail) return body.detail;
  } catch { /* respons bukan JSON — pakai kode status saja */ }
  return `Permintaan ke API gagal (${response.status}).`;
}

/** Baca respons JSON endpoint auth/unggah; kalau gagal, lempar pesan `detail` dari API.
 *  Tanpa ini respons 500 berbadan teks (mis. crash server) memunculkan galat parse JSON yang
 *  membingungkan ("Unexpected token 'I'") alih-alih kode statusnya. */
async function kirimJson<T>(response: Response, pesanDefault: string): Promise<T> {
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(typeof body?.detail === 'string' && body.detail ? body.detail : `${pesanDefault} (${response.status}).`);
  return body as T;
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

/* ---- /analytics/story: seluruh chart + narasi insight dashboard lama (kontrak dibuat di api/app/services/story.py) ---- */
export type Chart = {
  id: string;
  kind: 'bar' | 'line' | 'stacked_bar' | 'heatmap' | 'combo';
  title: string;
  insight?: string | null;
  note?: string | null;
  orientation?: 'h' | 'v';
  data: unknown;
};
export type StoryTable = { id: string; title: string; note?: string | null; insight?: string | null; columns: { key: string; label: string }[]; rows: Record<string, unknown>[]; /** Baris per halaman jika tabel ber-paginasi (null = tampil utuh). */ page_size?: number | null };
export type StoryMetric = { label: string; value: string | number; note?: string | null; help?: string | null };
export type StoryTab = { id: string; label: string; note?: string | null; charts: Chart[]; tables: StoryTable[] };
export type TopicOption = { value: string; label: string };
export type PillarDetail = { pillar: string; narrative: string; metrics: StoryMetric[]; tabs: StoryTab[]; topic_options: TopicOption[]; selected_topic: string };
/** Sub-bab laporan = satu tema resmi Kepmen (mis. 2.1 Pendidikan Inklusif) beserta indikator resminya. */
export type ChapterSection = {
  id: string;
  number: string;
  topic: string;
  label: string;
  official_topic: string;
  /** Judul sub-bab persis daftar isi laporan resmi (bisa beda dari nama tema Kepmen). */
  report_title: string;
  pillar: string;
  indicator: string;
  definition: string;
  criteria: string;
  formula: string;
  unit: string;
  sdgs: number[];
  sdg_labels: { id: number; label: string }[];
  metrics: StoryMetric[];
  charts: Chart[];
  tables: StoryTable[];
};
/** Bab laporan (BAB II Sosial, BAB III Ekonomi, BAB IV Lingkungan) mengikuti daftar isi LAPORAN DAMPAK UGM 2025. */
export type Chapter = {
  pillar: string;
  chapter: string;
  title: string;
  total: number;
  charts: Chart[];
  metrics: StoryMetric[];
  subsections: ChapterSection[];
};
export type Story = {
  mode: string;
  filters: Record<string, unknown>;
  data_as_of: string | null;
  caveats: string[];
  executive: { metrics: StoryMetric[]; narrative: string };
  overview: { pillar: string; total: number; top_topic: string | null; top_topic_count: number }[];
  cross: { title: string; charts: Chart[]; tables: StoryTable[]; topic_options?: TopicOption[]; selected_topic?: string };
  pillar_detail: PillarDetail | null;
  chapters: Chapter[];
  tables: StoryTable[];
};
export function getStory(params: Record<string, QueryValue>) { return get<Story>(`/analytics/story?${toQuery(params)}`); }

export function getMetadata() { return get<Metadata>('/analytics/metadata'); }
export function getAccreditation() { return get<AccreditationResult>('/analytics/accreditation'); }

export type AuthUser = { id: number; email: string; nama: string; is_admin: boolean };
/** Header dan halaman Akreditasi sama-sama mendengarkan event ini untuk menyegarkan status login. */
export const AUTH_EVENT = 'ugm-auth-changed';
function notifyAuthChanged() { window.dispatchEvent(new Event(AUTH_EVENT)); }
export async function accreditationMe() { const response = await fetch(`${API_BASE}/analytics/accreditation/auth/me`, { credentials: 'include' }); if (!response.ok) return null; return (await response.json()).user as { id: number; email: string; nama: string; is_admin: boolean }; }
export async function accreditationLogin(email: string, password: string) { const response = await fetch(`${API_BASE}/analytics/accreditation/auth/login`, { method: 'POST', credentials: 'include', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email, password }) }); const body = await kirimJson<{ user: AuthUser }>(response, 'Login gagal'); notifyAuthChanged(); return body.user; }
export async function accreditationRegister(email: string, name: string, password: string) { const response = await fetch(`${API_BASE}/analytics/accreditation/auth/register`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email, name, password }) }); return kirimJson<{ message: string }>(response, 'Registrasi gagal'); }
export async function accreditationLogout() { await fetch(`${API_BASE}/analytics/accreditation/auth/logout`, { method: 'POST', credentials: 'include' }); notifyAuthChanged(); }
export async function accreditationUpload(prodiId: string, file: File) { const form = new FormData(); form.append('prodi_id', prodiId); form.append('file', file); const response = await fetch(`${API_BASE}/analytics/accreditation/uploads`, { method: 'POST', credentials: 'include', body: form }); return kirimJson<{ message?: string }>(response, 'Upload gagal'); }

/* ---- Login Analisis Dampak: akun terpisah total dari akun Akreditasi (tabel, cookie, dan
   event beda) supaya masuk ke satu portal tidak otomatis membuka portal yang lain. ---- */
export const DAMPAK_AUTH_EVENT = 'ugm-dampak-auth-changed';
function notifyDampakAuthChanged() { window.dispatchEvent(new Event(DAMPAK_AUTH_EVENT)); }
export async function dampakMe() { const response = await fetch(`${API_BASE}/analytics/dampak/auth/me`, { credentials: 'include' }); if (!response.ok) return null; return (await response.json()).user as AuthUser; }
export async function dampakLogin(email: string, password: string) { const response = await fetch(`${API_BASE}/analytics/dampak/auth/login`, { method: 'POST', credentials: 'include', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email, password }) }); const body = await kirimJson<{ user: AuthUser }>(response, 'Login gagal'); notifyDampakAuthChanged(); return body.user; }
export async function dampakRegister(email: string, name: string, password: string) { const response = await fetch(`${API_BASE}/analytics/dampak/auth/register`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email, name, password }) }); return kirimJson<{ message: string }>(response, 'Registrasi gagal'); }
export async function dampakLogout() { await fetch(`${API_BASE}/analytics/dampak/auth/logout`, { method: 'POST', credentials: 'include' }); notifyDampakAuthChanged(); }

/* ---- Profil Saya & Admin (padanan page_profil.py + page_admin.py dashboard lama) ---- */
export type ProfileUser = { id: number; email: string; nama: string; is_admin: boolean; created_at: string | null; last_login_at: string | null; terdaftar: string | null; login_terakhir: string | null };
export type OngoingWork = { prodi_id: string; nama_prodi: string; nama_fakultas: string | null; dokumen: string; item_milik_user: number; lengkap: number; total: number; persen: number };
export type RiwayatRow = { id: number; prodi_id: string; nama_prodi: string; jenis_dokumen: string; generated_at: string | null; digenerate: string | null };
export type ProfileResult = { user: ProfileUser; stats: { dokumen_digenerate: number; dokumen_diupload: number }; ongoing: OngoingWork[]; riwayat: { total: number; batas: number; rows: RiwayatRow[] } };
export type AdminUserRow = { id: number; nama: string; email: string; is_admin: boolean; is_blocked: boolean; terdaftar: string | null; login_terakhir: string | null; n_generate: number; diri_sendiri: boolean };
export type AdminOverview = { summary: { total_akun: number; admin: number; diblokir: number }; users: AdminUserRow[] };

async function kirim<T>(path: string, method: string, body?: unknown): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, { method, credentials: 'include', headers: body ? { 'Content-Type': 'application/json' } : undefined, body: body ? JSON.stringify(body) : undefined });
  const hasil = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(hasil.detail ?? `Permintaan gagal (${response.status})`);
  return hasil as T;
}

export function accreditationProfile() { return kirim<ProfileResult>('/analytics/accreditation/profile', 'GET'); }
export function accreditationAdminUsers() { return kirim<AdminOverview>('/analytics/accreditation/admin/users', 'GET'); }
export function accreditationAdminAction(targetId: number, action: 'blokir' | 'admin' | 'hapus', value?: boolean) {
  return kirim<{ message: string }>(`/analytics/accreditation/admin/users/${targetId}/action`, 'POST', { action, value });
}
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
