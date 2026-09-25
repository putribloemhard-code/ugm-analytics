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
export type PillarDetail = { pillar: string; narrative: string; /** 'llm' = cache generate_narasi_llm.py (hanya filter default). */ narrative_source?: 'llm' | 'template'; metrics: StoryMetric[]; tabs: StoryTab[]; topic_options: TopicOption[]; selected_topic: string };
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
  /** Kurikulum terkait tema ini (ada bila data mata kuliah tersedia). */
  mata_kuliah?: KurikulumTema;
};
/** Ringkasan mata kuliah untuk satu tema Kepmen (sub-bab laporan). */
export type KurikulumTema = { jumlah: number; dasar: string; catatan: string; fakultas: number; tabel: StoryTable | null };
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
/** Blok data mata kuliah sustainability (kurasi kurikulum UGM, subproyek matkul-sustainability). */
export type MataKuliahBlok = {
  tersedia: boolean;
  sumber: string;
  total_penawaran: number;
  n_substansial: number;
  n_mk_unik: number;
  parsial: number;
  indikator_tema: string;
  /** Angka resmi Ringkasan Indikator Kepmen: jumlah MK unik per kriteria a-j. */
  kriteria_resmi: Record<string, number>;
  /** Catatan metode resmi (butir 1-7 Ringkasan Indikator Kepmen). */
  catatan_metode: string[];
  /** 'tema' = dipetakan ke 14 tema Kepmen (mode Dampak / Dampak x SDGs); 'sdg' = tagging SDG langsung. */
  mode: 'tema' | 'sdg';
  /** Rekap per tema dalam cakupan filter (kosong pada mode 'sdg'). */
  per_tema: { tema_id: string; tema: string; pilar: string; jumlah: number; dasar: string; catatan: string }[];
  note: string;
  metrics: StoryMetric[];
  charts: Chart[];
  tables: StoryTable[];
};
export type Story = {
  mode: string;
  filters: Record<string, unknown>;
  data_as_of: string | null;
  caveats: string[];
  executive: { metrics: StoryMetric[]; narrative: string; narrative_source?: 'llm' | 'template'; pembagian?: PembagianDampak };
  overview: { pillar: string; total: number; top_topic: string | null; top_topic_count: number }[];
  cross: { title: string; charts: Chart[]; tables: StoryTable[]; topic_options?: TopicOption[]; selected_topic?: string; pemetaan?: PemetaanKepmen };
  pillar_detail: PillarDetail | null;
  chapters: Chapter[];
  mata_kuliah?: MataKuliahBlok;
  tables: StoryTable[];
  /** Mode SDGs: peta sebaran 17 SDG + jumlah berita per keyword. */
  sdg_peta?: SdgPeta | null;
  /** Mode SDGs: jumlah berita (dalam filter) yang belum punya tanda SDG. */
  tanpa_sdg_total?: number;
};
export type SdgPeta = {
  ada_jumlah_keyword: boolean;
  catatan: string;
  tiles: { sdg: number; nama: string; jumlah: number; keywords: { keyword: string; jumlah: number | null }[] }[];
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
/* ---- Ruang kerja akreditasi (padanan page_akreditasi.py + dashboard_render.py lama) ---- */
export type Dokumen = 'LED' | 'LKPS';
export type ItemRow = Record<string, string>;
export type AiCell = { baris_ke: number; kolom: string; nilai: string; kutipan: string | null; nama_file: string };
export type ItemDraft = {
  rows: ItemRow[];
  ai_cells: AiCell[];
  conflicts: { baris_ke: number; kolom: string; opsi: { nilai: string; nama_file: string; kutipan: string | null }[] }[];
  skipped: AiCell[];
  ekstraksi_ids: number[];
};
export type WorkspaceItem = {
  id: string; nama: string; deskripsi: string; sumber_data: string; status: string; status_label: string;
  tipe: 'tabel' | 'narasi'; kolom: string[]; tabel_lkps: string | null; narasi: boolean; terisi: boolean;
  state: 'otomatis' | 'live' | 'terisi' | 'kosong' | 'belum_tersedia'; editable: boolean; rows: ItemRow[];
  diisi_oleh: string | null; updated_at: string | null; draft: ItemDraft | null;
  /** Status resmi dari data_source_map.json (bukan status_ketersediaan registry). */
  kategori: KategoriSumber; kategori_label: string; sumber_asli: string | null; catatan: string | null; sumber_tambahan: string | null;
  live: { kolom: string[]; rows: ItemRow[]; sumber: string[]; fetched_at: string | null } | null;
  pendukung: { judul: string; total: number; kolom: string[]; rows: string[][]; tautan: string[] | null } | null;
};
export type KategoriSumber = 'tersedia' | 'akses_data' | 'penyusunan';
export type PratinjauEkstraksi = {
  id: number; item_id: string; item_nama: string; grup: string; baris_ke: number; kolom: string; nilai: string;
  kutipan: string | null; nama_file: string; status: 'dipakai' | 'bentrok' | 'tidak_menimpa' | 'kolom_lain';
};
export type WorkspaceGroup = { key: string; label: string; items: WorkspaceItem[]; cuplikan: { id: string; tabel_lkps: string; nama: string; status: string; terisi: boolean }[] };
export type WorkspaceUpload = {
  id: number; nama_file: string; tipe_file: string; ukuran_bytes: number;
  status: 'belum_diekstrak' | 'sedang_diekstrak' | 'diekstrak' | 'gagal_ekstrak' | 'terhenti';
  diupload_oleh: string | null; uploaded_at: string | null; diekstrak_at: string | null;
  progres: { batch: number; total: number } | null;
  ringkasan: { n_item_ditemukan?: number; n_kolom_terisi?: number; n_batch?: number; waktu_llm_total?: number; error?: string | null } | null;
};
export type Workspace = {
  prodi: { slug: string; nama: string; jenjang: string | null; fakultas: string | null };
  dokumen: Dokumen;
  ringkasan: {
    total: number; lengkap: number; persen: number; terisi_manual: number;
    tersedia: { total: number; lengkap: number }; akses_data: { total: number; lengkap: number }; penyusunan: { total: number; lengkap: number };
  };
  groups: WorkspaceGroup[];
  uploads: WorkspaceUpload[];
  ekstraksi: { tersedia: boolean; item_menunggu_review: number; pratinjau: PratinjauEkstraksi[]; dokumen_lain: number };
};

export function getAccreditationWorkspace(prodiId: string, dokumen: Dokumen) {
  return kirim<Workspace>(`/analytics/accreditation/workspace?${toQuery({ prodi_id: prodiId, dokumen })}`, 'GET');
}
export function saveAccreditationItem(prodiId: string, itemId: string, rows: ItemRow[], ekstraksiIds: number[]) {
  return kirim<{ message: string; baris: number; sel: number }>(`/analytics/accreditation/workspace/items/${encodeURIComponent(itemId)}`, 'POST', { prodi_id: prodiId, rows, ekstraksi_ids: ekstraksiIds });
}
export function addAccreditationProgram(fakultasId: string, nama: string, jenjang: string) {
  return kirim<{ slug: string; nama: string }>('/analytics/accreditation/programs', 'POST', { fakultas_id: fakultasId, nama, jenjang });
}
export function startAccreditationExtraction(prodiId: string, dokumen: Dokumen) {
  return kirim<{ dimulai: number }>('/analytics/accreditation/extractions', 'POST', { prodi_id: prodiId, dokumen });
}

/** Unduh berkas dari endpoint ber-login; nama berkas diambil dari Content-Disposition. */
async function unduhBerkas(path: string, init: RequestInit, cadangan: string): Promise<{ blob: Blob; filename: string }> {
  const response = await fetch(`${API_BASE}${path}`, { credentials: 'include', ...init });
  if (!response.ok) throw new Error(await pesanError(response));
  const nama = /filename="([^"]+)"/.exec(response.headers.get('Content-Disposition') ?? '')?.[1];
  return { blob: await response.blob(), filename: nama ?? cadangan };
}
export function generateAccreditationDocument(prodiId: string, dokumen: Dokumen) {
  return unduhBerkas('/analytics/accreditation/generate', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ prodi_id: prodiId, dokumen }) }, `Laporan_Akreditasi_${dokumen}.docx`);
}
export function downloadAccreditationHistory(riwayatId: number) {
  return unduhBerkas(`/analytics/accreditation/history/${riwayatId}/file`, {}, 'Laporan_Akreditasi.docx');
}
/** Simpan blob sebagai berkas di perangkat pengguna. */
export function simpanBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = filename; document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/* ---- Update data berita (pipeline update_mingguan.py) -- padanan tombol Streamlit lama ---- */
export type RefreshStatus = {
  status: 'running' | 'finished' | 'idle' | 'stale_lock';
  updated_at: string | null;
  trigger_available: boolean;
  log_updated_at: string | null;
  last_exit: number | null;
  log_tail: string[];
};
export function getRefreshStatus() { return get<RefreshStatus>('/analytics/refresh-status'); }
export function startRefresh() { return kirim<{ pid: number; message: string }>('/analytics/refresh', 'POST'); }

/* ---- Bagian "Sumber": asal data + daftar berita berdampak (api/app/services/sources.py) ---- */
export type JumlahPilar = { pilar: 'Sosial' | 'Ekonomi' | 'Lingkungan'; jumlah: number };
export type SumberData = {
  berita: {
    situs: string; sitemap: number; diambil: number; berdampak: number; rss: number;
    bahasa: { id: number; en: number }; tahun_awal: string | null; tahun_akhir: string | null;
    diperbarui: string | null; per_pilar: JumlahPilar[];
  };
  mata_kuliah: { tersedia: false } | {
    tersedia: true; baris: number; prodi: number; fakultas: number; mk_unik: number; mk_belum_dinilai: number;
    berdampak: number; indikator_resmi: number; per_pilar: JumlahPilar[];
  };
  internal: { nama: string; status: string; pengganti: string }[];
};
export type BeritaDampak = { judul: string; tautan: string | null; tanggal: string; bahasa: 'ID' | 'EN'; tema: string[]; pilar: string[] };
export function getSumber() { return get<SumberData>('/analytics/sources'); }
export function getBeritaDampak(params: { page: number; page_size: number; q?: string; pilar?: string }) {
  return get<{ page: number; page_size: number; total: number; rows: BeritaDampak[] }>(`/analytics/sources/news?${toQuery(params)}`);
}

/* ---- Tag SDG manual untuk berita tanpa tanda SDG (api/app/services/sdg_manual.py) ---- */
export type BeritaTanpaSdg = { url: string; tautan: string | null; judul: string; tanggal: string };
export function getBeritaTanpaSdg(params: { page: number; page_size: number; q?: string; year_from?: string; year_to?: string; units?: string[] }) {
  return get<{ page: number; page_size: number; total: number; rows: BeritaTanpaSdg[] }>(`/analytics/sdg-manual/untagged?${toQuery(params)}`);
}
export function tandaiSdg(url: string, sdgs: number[]) { return kirim<{ url: string; sdgs: number[]; message: string }>('/analytics/sdg-manual', 'POST', { url, sdgs }); }
export function batalkanSdg(url: string) { return kirim<{ url: string; sdgs: number[]; message: string }>('/analytics/sdg-manual/delete', 'POST', { url }); }

/* ---- Pemetaan resmi 14 tema Kepmen + tag tema manual (api/app/services/tema_manual.py) ---- */
export type PemetaanTema = { id: string; tema: string; dampak: string; tema_kepmen: string; sdg: string; indikator: string; definisi: string; kriteria: string; formula: string; satuan: string };
export type PemetaanKepmen = { rows: PemetaanTema[]; note: string };
export type BeritaTanpaTema = { url: string; tautan: string | null; judul: string; tanggal: string; deskripsi: string };
export function getBeritaTanpaTema(params: { page: number; page_size: number; q?: string; year_from?: string; year_to?: string; units?: string[] }) {
  return get<{ page: number; page_size: number; total: number; rows: BeritaTanpaTema[] }>(`/analytics/tema-manual/untagged?${toQuery(params)}`);
}
export function tandaiTema(url: string, topiks: string[]) { return kirim<{ url: string; topiks: string[]; message: string }>('/analytics/tema-manual', 'POST', { url, topiks }); }
export function batalkanTema(url: string) { return kirim<{ url: string; topiks: string[]; message: string }>('/analytics/tema-manual/delete', 'POST', { url }); }

export function getHomeSummary() { return get<Record<string, string | number | null>>('/analytics/home-summary'); }
export function searchAnalytics(q: string) { return get<{ page: string; pillars: string[]; topics: string[]; sdgs: number[]; years: string[] | null; explanation: string }>(`/analytics/search?${toQuery({ q })}`); }
export function getImpact(params: Record<string, QueryValue>, mode: 'impact' | 'impact-sdgs') { return get<AnalyticsResult>(`/analytics/impact?${toQuery({ ...params, mode })}`); }
export function getSdgs(params: Record<string, QueryValue>) { return get<AnalyticsResult>(`/analytics/sdgs?${toQuery(params)}`); }
export function getNews(params: Record<string, QueryValue>, page: number, pageSize: number) { return get<{ rows: unknown[]; total: number; page: number; page_size: number }>(`/analytics/news?${toQuery({ ...params, page, page_size: pageSize })}`); }

/* ---- Laporan dampak berkerangka LAPORAN DAMPAK UGM 2025 (api/app/services/laporan_dampak.py) ---- */
/** Pembagian berita dampak: irisan tanpa tumpang tindih (jumlahnya = total) + jumlah per pilar (bisa > total). */
export type PembagianDampak = {
  total: number;
  irisan: { kunci: string; label: string; pilar: string[]; jumlah: number; persen: number }[];
  per_pilar: { pilar: string; jumlah: number; persen: number }[];
};
export type LaporanBlok =
  | { type: 'heading'; level: 1 | 2 | 3; text: string; break_before?: boolean }
  | { type: 'paragraph'; text: string }
  | { type: 'list'; ordered: boolean; items: string[] }
  | { type: 'figure'; image: string; caption: string; source: string | null }
  | { type: 'table'; caption: string; columns: string[]; rows: string[][]; links: Record<string, number>; source: string | null; key_value: boolean };
export type Laporan = {
  title: string; subtitle: string; institution: string; period: string; mode: string; mode_label: string;
  filters: string[]; generated: string; data_as_of: string | null;
  toc: { level: number; text: string }[]; figures: string[]; tables: string[]; blocks: LaporanBlok[];
};
async function pesanGalat(response: Response, cadangan: string) {
  try { const body = await response.json(); if (typeof body?.detail === 'string') return body.detail; } catch { /* bukan JSON */ }
  return `${cadangan} (${response.status})`;
}
export async function getLaporanPreview(payload: Record<string, unknown>) {
  const response = await fetch(`${API_BASE}/analytics/reports/preview`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
  if (!response.ok) throw new Error(await pesanGalat(response, 'Pratinjau laporan gagal dibuat'));
  return response.json() as Promise<Laporan>;
}
export async function downloadReport(payload: Record<string, unknown>) {
  const response = await fetch(`${API_BASE}/analytics/reports`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
  if (!response.ok) throw new Error(await pesanGalat(response, 'Laporan gagal dibuat'));
  const nama = /filename="([^"]+)"/.exec(response.headers.get('Content-Disposition') ?? '')?.[1];
  return { blob: await response.blob(), nama };
}
