import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import {
  accreditationUpload, addAccreditationProgram, generateAccreditationDocument, getAccreditationWorkspace,
  saveAccreditationItem, simpanBlob, startAccreditationExtraction,
  type AccreditationResult, type AuthUser, type Dokumen, type ItemRow, type PratinjauEkstraksi, type Workspace, type WorkspaceItem, type WorkspaceUpload,
} from './lib/api';
import { Notice, PageHeader, ProgressLine, StatCard } from './ui';

/* Ruang kerja akreditasi: pengganti dashboard Streamlit (dashboard_akreditasi.py / page_akreditasi.py).
   Alur sama: Lingkup -> Fakultas & Prodi -> Dokumen (LED/LKPS) -> Upload & ekstraksi -> isi item -> Generate Word. */

const TAMBAH_PRODI = '__tambah__';
const JENJANG = ['Sarjana', 'Magister', 'Doktor', 'Profesi', 'Spesialis'];
const MAX_UPLOAD_MB = 25;
const STATE_LABEL: Record<WorkspaceItem['state'], string> = {
  otomatis: 'Tersedia otomatis', live: 'Data live', terisi: 'Terisi', kosong: 'Perlu input', belum_tersedia: 'Belum tersedia',
};
const STATUS_PRATINJAU: Record<PratinjauEkstraksi['status'], { label: string; hint: string }> = {
  dipakai: { label: 'Siap dicek', hint: 'Mengisi sel kosong; tersimpan setelah Anda klik Simpan di item.' },
  bentrok: { label: 'Bentrok', hint: 'File berbeda memberi nilai berbeda; pilih sendiri di item.' },
  tidak_menimpa: { label: 'Tidak menimpa', hint: 'Sel ini sudah berisi isian tim; nilai AI tidak dipakai.' },
  kolom_lain: { label: 'Di luar kolom', hint: 'Kolom ini tidak dibutuhkan item; diabaikan saat disimpan.' },
};
const PRATINJAU_PER_HALAMAN = 10;
// Narasi hasil AI bisa ratusan kata; di tabel cukup awalnya, sisanya dibuka per baris.
const NILAI_RINGKAS = 180;
const UPLOAD_LABEL: Record<WorkspaceUpload['status'], string> = {
  belum_diekstrak: 'Belum diekstrak', sedang_diekstrak: 'Sedang diekstrak', diekstrak: 'Sudah diekstrak',
  gagal_ekstrak: 'Gagal diekstrak', terhenti: 'Terhenti — bisa diulang',
};

function waktu(iso: string | null): string {
  if (!iso) return '-';
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString('id-ID', { dateStyle: 'medium', timeStyle: 'short' });
}

function pesan(e: unknown, cadangan: string): string {
  return e instanceof Error && e.message ? e.message : cadangan;
}

/** Jenjang sering sudah terkandung di nama (mis. "Doktor Ilmu Fisika"), jangan diulang. */
function labelProdi(p: Record<string, unknown>): string {
  const nama = String(p.nama); const jenjang = p.jenjang ? String(p.jenjang) : '';
  return jenjang && !nama.toLowerCase().includes(jenjang.toLowerCase()) ? `${nama} — ${jenjang}` : nama;
}

/** Bagian LKPS dari nomor tabel ("3.C.1" -> "3") -- dipakai tombol "Buka di LKPS" pada cuplikan LED. */
function bagianLkps(tabel: string): string { return tabel.split('.')[0]; }

type Props = {
  catalog: AccreditationResult;
  user: AuthUser;
  onLogout: () => void;
  onCatalogChange: () => Promise<AccreditationResult>;
  initialProdi: string;
  initialDokumen: Dokumen;
};

export function AccreditationWorkspace({ catalog, user, onLogout, onCatalogChange, initialProdi, initialDokumen }: Props) {
  const [lingkup, setLingkup] = useState<'prodi' | 'universitas'>('prodi');
  const awal = catalog.programs.find(p => String(p.slug) === initialProdi);
  const [fakultas, setFakultas] = useState(awal ? String(awal.fakultas_id) : '');
  const [prodi, setProdi] = useState(awal ? initialProdi : '');
  const [dokumen, setDokumen] = useState<Dokumen>(initialDokumen);
  const [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [groupKey, setGroupKey] = useState('');
  const [fokus, setFokus] = useState('');
  const permintaan = useRef(0);

  const prodiDariFakultas = catalog.programs.filter(p => String(p.fakultas_id) === fakultas);
  const yatim = catalog.programs.filter(p => !p.fakultas_id || String(p.fakultas_id) === '').length;

  const muat = useCallback(async (diam = false) => {
    if (!prodi || prodi === TAMBAH_PRODI) { setWorkspace(null); return; }
    const id = ++permintaan.current;
    if (!diam) { setLoading(true); setError(''); }
    try {
      const hasil = await getAccreditationWorkspace(prodi, dokumen);
      if (id === permintaan.current) setWorkspace(hasil);
    } catch (e) {
      if (id === permintaan.current) setError(pesan(e, 'Data akreditasi gagal dimuat.'));
    } finally {
      if (id === permintaan.current && !diam) setLoading(false);
    }
  }, [prodi, dokumen]);

  useEffect(() => { muat(); }, [muat]);

  // Selama ada file yang sedang diekstrak, pantau status tiap 3 detik (ekstraksi berjalan di latar API).
  const sedangEkstrak = workspace?.uploads.some(u => u.status === 'sedang_diekstrak') ?? false;
  useEffect(() => {
    if (!sedangEkstrak) return;
    const t = window.setTimeout(() => { muat(true); }, 3000);
    return () => window.clearTimeout(t);
  }, [sedangEkstrak, workspace, muat]);

  function pilihFakultas(nilai: string) {
    setFakultas(nilai);
    const pertama = catalog.programs.find(p => String(p.fakultas_id) === nilai);
    setProdi(pertama ? String(pertama.slug) : TAMBAH_PRODI);
    setGroupKey('');
  }

  function bukaDiLkps(itemId: string, tabel: string) {
    setDokumen('LKPS'); setGroupKey(bagianLkps(tabel)); setFokus(itemId);
  }

  const groups = workspace?.groups ?? [];
  const activeGroup = groups.find(g => g.key === groupKey) ?? groups[0];

  return <div className="content accreditation-workspace">
    <div className="workspace-head">
      <PageHeader title="Akreditasi" icon="certificate.png" caption="Kelengkapan data LED & LKPS — instrumen akreditasi Program Studi (LAM-INFOKOM)." />
      <div className="user-chip">{user.nama}<button onClick={onLogout}>Keluar</button></div>
    </div>
    {yatim > 0 && <Notice type="error">{yatim} program studi belum terhubung ke fakultas mana pun, sehingga tidak muncul di pemilih. Perbaiki kolom fakultas_id pada tabel akreditasi_prodi.</Notice>}

    <section className="accreditation-selectors accreditation-selectors--4" aria-label="Pilihan dokumen akreditasi">
      <div className="field">
        <label htmlFor="ak-lingkup">Lingkup akreditasi</label>
        <select id="ak-lingkup" value={lingkup} onChange={e => setLingkup(e.target.value as 'prodi' | 'universitas')}>
          <option value="prodi">Akreditasi Program Studi</option>
          <option value="universitas">Akreditasi Universitas</option>
        </select>
      </div>
      <div className="field">
        <label htmlFor="ak-fakultas">Fakultas (wajib)</label>
        <select id="ak-fakultas" value={fakultas} onChange={e => pilihFakultas(e.target.value)} disabled={lingkup !== 'prodi'}>
          <option value="">Pilih fakultas…</option>
          {catalog.faculties.map(f => {
            const n = catalog.programs.filter(p => String(p.fakultas_id) === String(f.id)).length;
            return <option key={String(f.id)} value={String(f.id)}>{String(f.nama)}{n ? ` (${n} prodi)` : ' (belum ada prodi)'}</option>;
          })}
        </select>
        <small className="field-hint">Nama fakultas panjang bisa terpotong — buka daftar untuk melihat lengkap.</small>
      </div>
      <div className="field">
        <label htmlFor="ak-prodi">Program Studi (wajib)</label>
        <select id="ak-prodi" value={prodi} disabled={!fakultas || lingkup !== 'prodi'} onChange={e => { setProdi(e.target.value); setGroupKey(''); }}>
          {!fakultas && <option value="">Pilih fakultas dulu</option>}
          {prodiDariFakultas.map(p => <option key={String(p.id)} value={String(p.slug)}>{labelProdi(p)}</option>)}
          {fakultas && <option value={TAMBAH_PRODI}>+ Tambah prodi baru</option>}
        </select>
      </div>
      <div className="field">
        <label htmlFor="ak-dokumen">Dokumen</label>
        <select id="ak-dokumen" value={dokumen} disabled={lingkup !== 'prodi'} onChange={e => { setDokumen(e.target.value as Dokumen); setGroupKey(''); }}>
          <option value="LED">📘 LED — Laporan Evaluasi Diri</option>
          <option value="LKPS">📗 LKPS — Laporan Kinerja Program Studi</option>
        </select>
      </div>
    </section>

    {lingkup === 'universitas'
      ? <Notice type="info">Instrumen akreditasi Universitas (BAN-PT — LED APT/LKPT) berbeda struktur dari instrumen Program Studi (LAM-INFOKOM — LED/LKPS) yang sudah dibangun di sini. Dokumen requirement untuk instrumen institusi ini belum tersedia, jadi fitur ini akan dikembangkan setelah dokumen requirement LED APT/LKPT disiapkan.</Notice>
      : prodi === TAMBAH_PRODI && fakultas
        ? <AddProgram fakultasId={fakultas} fakultasNama={String(catalog.faculties.find(f => String(f.id) === fakultas)?.nama ?? '')}
            onAdded={async slug => { await onCatalogChange(); setProdi(slug); }} onCancel={() => { const p = prodiDariFakultas[0]; setProdi(p ? String(p.slug) : TAMBAH_PRODI); }} />
        : !prodi
          ? <Notice type="info">Pilih Fakultas dan Program Studi dulu untuk melihat kelengkapan data.</Notice>
          : error
            ? <Notice type="error">{error}</Notice>
            : !workspace || workspace.prodi.slug !== prodi || workspace.dokumen !== dokumen
              ? <div className="loading" role="status">Memuat kelengkapan data…</div>
              : <>
                <Ringkasan workspace={workspace} />
                <UploadPanel workspace={workspace} prodi={prodi} dokumen={dokumen} onChange={() => muat(true)} />
                <PratinjauPanel workspace={workspace} dokumen={dokumen} onBuka={(itemId, grup) => { setGroupKey(grup); setFokus(''); window.setTimeout(() => setFokus(itemId), 0); }}
                  onGantiDokumen={() => { setDokumen(dokumen === 'LED' ? 'LKPS' : 'LED'); setGroupKey(''); }} />
                <section className="section requirement-section">
                  <div className="section-title-row">
                    <div><p className="section-kicker">Kelengkapan Data {dokumen}</p><h2>{dokumen === 'LED' ? 'Narasi evaluatif per Kriteria' : 'Tabel data per Bagian'}</h2></div>
                    <span className="status-pill">{workspace.ringkasan.lengkap}/{workspace.ringkasan.total} lengkap</span>
                  </div>
                  <p className="section-note">{dokumen === 'LED'
                    ? 'Narasi evaluatif per Kriteria A–D (siklus PPEPP). Tiap Kriteria A/B/C1–C6 juga menampilkan tabel LKPS terkait sebagai bukti evaluasi.'
                    : 'Tabel data mentah per Bagian 1–6. Isi tabel lalu klik Simpan — tersimpan langsung sebagai data resmi prodi ini.'}</p>
                  <div className="accreditation-tabs" role="tablist" aria-label={dokumen === 'LED' ? 'Kriteria' : 'Bagian'}>
                    {groups.map(g => {
                      const lengkap = g.items.filter(i => i.state === 'terisi' || i.state === 'otomatis').length;
                      return <button key={g.key} role="tab" aria-selected={g.key === activeGroup?.key} className={g.key === activeGroup?.key ? 'active' : ''} onClick={() => setGroupKey(g.key)}>
                        {g.label} <span className="tab-count">{lengkap}/{g.items.length}</span>
                      </button>;
                    })}
                  </div>
                  {activeGroup && <div className="requirement-list" role="tabpanel">
                    {activeGroup.items.map(item => <ItemCard key={item.id} item={item} prodi={prodi} fokus={fokus === item.id} onSaved={() => muat(true)} />)}
                    {activeGroup.cuplikan.length > 0 && <div className="cuplikan">
                      <h3>Tabel LKPS terkait</h3>
                      <p className="section-note">Diisi dan dilihat lengkap di dokumen LKPS — ditampilkan di sini sebagai cuplikan bukti evaluasi.</p>
                      <ul>{activeGroup.cuplikan.map(c => <li key={c.id}>
                        <span className={`state-badge ${c.terisi ? 'terisi' : 'kosong'}`}>{c.terisi ? 'Terisi' : 'Perlu input'}</span>
                        <span>Tabel {c.tabel_lkps} — {c.nama}</span>
                        <button className="link-button" onClick={() => bukaDiLkps(c.id, c.tabel_lkps)}>Buka di LKPS</button>
                      </li>)}</ul>
                    </div>}
                  </div>}
                </section>
                <GeneratePanel prodi={prodi} dokumen={dokumen} />
              </>}
  </div>;
}

function Ringkasan({ workspace }: { workspace: Workspace }) {
  const r = workspace.ringkasan;
  // Kelompok mengikuti status resmi di data_source_map.json; "lengkap" = ada isian tim atau data live.
  return <>
    <section className="progress-overview" aria-label="Ringkasan kelengkapan">
      <StatCard label="Total item" value={r.total} note={`${workspace.dokumen} · ${workspace.prodi.nama}`} />
      <StatCard label="Tersedia dari sumber live" value={`${r.tersedia.lengkap}/${r.tersedia.total}`} note="ditarik pipeline dari situs resmi" />
      <StatCard label="Perlu akses data" value={`${r.akses_data.lengkap}/${r.akses_data.total}`} note="sumber ada, diisi tim (mis. SIMASTER)" />
      <StatCard label="Perlu disusun tim" value={`${r.penyusunan.lengkap}/${r.penyusunan.total}`} note="narasi & keputusan tim penyusun" />
    </section>
    <ProgressLine value={r.lengkap} total={r.total} percent={r.persen} note={`${r.terisi_manual} item diisi tim; sisanya dari data live`} />
  </>;
}

function AddProgram({ fakultasId, fakultasNama, onAdded, onCancel }: { fakultasId: string; fakultasNama: string; onAdded: (slug: string) => Promise<void>; onCancel: () => void }) {
  const [nama, setNama] = useState(''); const [jenjang, setJenjang] = useState('Sarjana');
  const [sibuk, setSibuk] = useState(false); const [galat, setGalat] = useState('');
  async function simpan() {
    setGalat(''); setSibuk(true);
    try { const hasil = await addAccreditationProgram(fakultasId, nama, jenjang); await onAdded(hasil.slug); }
    catch (e) { setGalat(pesan(e, 'Program studi gagal ditambahkan.')); }
    finally { setSibuk(false); }
  }
  return <section className="section requirement-section add-program">
    <p className="section-kicker">Program studi baru</p>
    <h2>Tambah program studi di {fakultasNama}</h2>
    <div className="add-program__fields">
      <div className="field"><label htmlFor="ak-prodi-baru">Nama Program Studi</label><input id="ak-prodi-baru" value={nama} maxLength={150} onChange={e => setNama(e.target.value)} placeholder="mis. Magister Kecerdasan Artifisial" /></div>
      <div className="field"><label htmlFor="ak-jenjang">Jenjang</label><select id="ak-jenjang" value={jenjang} onChange={e => setJenjang(e.target.value)}>{JENJANG.map(j => <option key={j}>{j}</option>)}</select></div>
    </div>
    <div className="action-row">
      <button className="button" disabled={sibuk || !nama.trim()} onClick={simpan}>{sibuk ? 'Menyimpan…' : 'Tambah prodi'}</button>
      <button className="button secondary" onClick={onCancel}>Batal</button>
    </div>
    {galat && <Notice type="error">{galat}</Notice>}
  </section>;
}

function UploadPanel({ workspace, prodi, dokumen, onChange }: { workspace: Workspace; prodi: string; dokumen: Dokumen; onChange: () => void }) {
  const [files, setFiles] = useState<File[]>([]);
  const [pesanUpload, setPesanUpload] = useState<{ type: 'info' | 'error'; text: string }[]>([]);
  const [sibuk, setSibuk] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  const bisaDiekstrak = workspace.uploads.filter(u => ['belum_diekstrak', 'gagal_ekstrak', 'terhenti'].includes(u.status));
  const sedang = workspace.uploads.filter(u => u.status === 'sedang_diekstrak');

  async function unggah() {
    setSibuk(true); setPesanUpload([]);
    const hasil: { type: 'info' | 'error'; text: string }[] = [];
    for (const f of files) {
      if (f.size > MAX_UPLOAD_MB * 1024 * 1024) { hasil.push({ type: 'error', text: `${f.name}: lebih dari ${MAX_UPLOAD_MB} MB.` }); continue; }
      try { await accreditationUpload(prodi, f); hasil.push({ type: 'info', text: `${f.name} tersimpan.` }); }
      catch (e) { hasil.push({ type: 'error', text: `${f.name}: ${pesan(e, 'upload gagal')}` }); }
    }
    setPesanUpload(hasil); setFiles([]); if (input.current) input.current.value = '';
    setSibuk(false); onChange();
  }

  async function ekstrak() {
    setSibuk(true); setPesanUpload([]);
    try {
      const { dimulai } = await startAccreditationExtraction(prodi, dokumen);
      setPesanUpload([{ type: 'info', text: dimulai ? `Ekstraksi ${dimulai} file dimulai (mode ${dokumen}). Proses berjalan di latar — halaman ini diperbarui otomatis.` : 'Tidak ada file yang perlu diekstrak.' }]);
    } catch (e) { setPesanUpload([{ type: 'error', text: pesan(e, 'Ekstraksi gagal dimulai.') }]); }
    setSibuk(false); onChange();
  }

  return <section className="upload-workflow upload-workflow--stack">
    <div>
      <p className="section-kicker">Dokumen pendukung</p>
      <h2>Upload & ekstraksi file</h2>
      <p>PDF, DOCX, atau XLSX — maks. {MAX_UPLOAD_MB} MB per file. Setelah diupload, klik <b>Ekstrak data</b> supaya AI mencoba mengambil nilai yang relevan. Hasilnya hanya <b>preview</b> yang perlu Anda cek dan konfirmasi di tiap item, bukan langsung data resmi.</p>
    </div>
    <div className="upload-controls">
      <label className="sr-only" htmlFor="ak-upload">Pilih file pendukung</label>
      <input id="ak-upload" ref={input} type="file" multiple accept=".pdf,.docx,.xlsx" onChange={e => setFiles(Array.from(e.target.files ?? []))} />
      <button className="button" disabled={sibuk || files.length === 0} onClick={unggah}>{sibuk && files.length ? 'Mengunggah…' : `Upload${files.length > 1 ? ` ${files.length} file` : ''}`}</button>
    </div>
    {pesanUpload.map((p, i) => <Notice key={i} type={p.type}>{p.text}</Notice>)}
    {workspace.uploads.length === 0
      ? <p className="section-note">Belum ada file yang diupload untuk prodi ini.</p>
      : <div className="data-table-wrap"><table className="data-table">
        <caption className="sr-only">File pendukung yang sudah diupload untuk prodi ini</caption>
        <thead><tr><th scope="col">Nama file</th><th scope="col">Tipe</th><th scope="col">Ukuran</th><th scope="col">Status</th><th scope="col">Diupload</th></tr></thead>
        <tbody>{workspace.uploads.map(u => <tr key={u.id}>
          <td>{u.nama_file}{u.ringkasan && <small className="upload-summary">{u.ringkasan.error
            ? `Kendala: ${u.ringkasan.error}`
            : `${u.ringkasan.n_item_ditemukan ?? 0} item ditemukan, ${u.ringkasan.n_kolom_terisi ?? 0} kolom terisi`}</small>}</td>
          <td>{u.tipe_file.toUpperCase()}</td>
          <td>{(u.ukuran_bytes / 1024).toFixed(1)} KB</td>
          <td><span className={`upload-status ${u.status}`}>{UPLOAD_LABEL[u.status]}{u.progres && u.progres.total ? ` — batch ${u.progres.batch}/${u.progres.total}` : ''}</span></td>
          <td>{waktu(u.uploaded_at)}</td>
        </tr>)}</tbody>
      </table></div>}
    <div className="action-row">
      <button className="button secondary" disabled={sibuk || bisaDiekstrak.length === 0 || !workspace.ekstraksi.tersedia} onClick={ekstrak}>
        {sedang.length ? `Mengekstrak ${sedang.length} file…` : `Ekstrak data dari ${bisaDiekstrak.length} file (mode ${dokumen})`}
      </button>
      {!workspace.ekstraksi.tersedia && <span className="field-hint">Ekstraksi AI nonaktif: isi OPENAI_API_KEY di .env lalu jalankan ulang API.</span>}
      {workspace.ekstraksi.tersedia && bisaDiekstrak.length > 0 && <span className="field-hint">Bisa makan beberapa menit per file (dipecah jadi beberapa panggilan AI kecil).</span>}
    </div>
  </section>;
}

/** Semua nilai hasil ekstraksi AI yang belum direview untuk dokumen aktif, dalam satu tabel. */
function PratinjauPanel({ workspace, dokumen, onBuka, onGantiDokumen }: { workspace: Workspace; dokumen: Dokumen; onBuka: (itemId: string, grup: string) => void; onGantiDokumen: () => void }) {
  const semua = workspace.ekstraksi.pratinjau;
  const [saring, setSaring] = useState<PratinjauEkstraksi['status'] | ''>('');
  const [cari, setCari] = useState('');
  const [halaman, setHalaman] = useState(1);
  const q = cari.trim().toLowerCase();
  const tampil = semua.filter(r => (!saring || r.status === saring)
    && (!q || `${r.item_nama} ${r.kolom} ${r.nilai}`.toLowerCase().includes(q)));
  const jumlahHalaman = Math.max(1, Math.ceil(tampil.length / PRATINJAU_PER_HALAMAN));
  const hal = Math.min(halaman, jumlahHalaman);
  const baris = tampil.slice((hal - 1) * PRATINJAU_PER_HALAMAN, hal * PRATINJAU_PER_HALAMAN);
  const per = (st: PratinjauEkstraksi['status']) => semua.filter(r => r.status === st).length;
  const nItem = new Set(semua.map(r => r.item_id)).size;
  useEffect(() => { setHalaman(1); }, [saring, cari, dokumen]);

  if (!semua.length) {
    if (!workspace.ekstraksi.dokumen_lain) return null;
    return <section className="section requirement-section ekstraksi-preview" aria-labelledby="ekstraksi-preview-title">
      <p className="section-kicker">Hasil ekstraksi</p>
      <h2 id="ekstraksi-preview-title">Pratinjau data hasil ekstraksi</h2>
      <Notice type="info">Belum ada hasil ekstraksi untuk {dokumen}. Ada <b>{workspace.ekstraksi.dokumen_lain} nilai</b> hasil ekstraksi untuk dokumen {dokumen === 'LED' ? 'LKPS' : 'LED'}. <button className="link-button" onClick={onGantiDokumen}>Buka {dokumen === 'LED' ? 'LKPS' : 'LED'}</button></Notice>
    </section>;
  }
  return <section className="section requirement-section ekstraksi-preview" aria-labelledby="ekstraksi-preview-title">
    <div className="section-title-row">
      <div><p className="section-kicker">Hasil ekstraksi · belum direview</p><h2 id="ekstraksi-preview-title">Pratinjau data hasil ekstraksi</h2></div>
      <span className="status-pill">{semua.length} nilai · {nItem} item</span>
    </div>
    <p className="section-note">Nilai yang diambil AI dari file upload, belum menjadi data resmi. Cek nilainya di sini, lalu buka item untuk mengedit dan klik <b>Simpan</b>. Setelah disimpan, nilainya pindah dari daftar ini ke isian item.</p>
    <div className="ekstraksi-preview__tools">
      <div className="ekstraksi-preview__chips" role="group" aria-label="Saring status">
        {([['', `Semua (${semua.length})`], ['dipakai', `Siap dicek (${per('dipakai')})`], ['bentrok', `Bentrok (${per('bentrok')})`], ['tidak_menimpa', `Tidak menimpa (${per('tidak_menimpa')})`], ['kolom_lain', `Di luar kolom (${per('kolom_lain')})`]] as const)
          .filter(([k]) => !k || per(k as PratinjauEkstraksi['status']) > 0)
          .map(([k, label]) => <button key={k} type="button" aria-pressed={saring === k} className={saring === k ? 'is-on' : ''} onClick={() => setSaring(k as PratinjauEkstraksi['status'] | '')}>{label}</button>)}
      </div>
      <div className="field">
        <label htmlFor="ekstraksi-cari">Cari item, kolom, atau nilai</label>
        <input id="ekstraksi-cari" type="search" value={cari} maxLength={100} onChange={e => setCari(e.target.value)} />
      </div>
    </div>
    {baris.length === 0
      ? <p className="section-note">Tidak ada nilai yang cocok dengan saringan ini.</p>
      : <div className="data-table-wrap"><table className="data-table ekstraksi-preview__table">
        <caption className="sr-only">Nilai hasil ekstraksi AI yang belum direview untuk {dokumen}</caption>
        <thead><tr><th scope="col">Item</th><th scope="col">Kolom</th><th scope="col">Nilai hasil AI</th><th scope="col">Sumber</th><th scope="col">Status</th><th scope="col"><span className="sr-only">Aksi</span></th></tr></thead>
        <tbody>{baris.map(r => <tr key={r.id}>
          <td data-label="Item">{r.item_nama}</td>
          <td data-label="Kolom">{r.kolom}<small className="ekstraksi-preview__baris">baris {r.baris_ke}</small></td>
          <td data-label="Nilai hasil AI" className="ekstraksi-preview__nilai">{r.nilai.length > NILAI_RINGKAS
            ? <details><summary>{r.nilai.slice(0, NILAI_RINGKAS).trimEnd()}… <span className="ekstraksi-preview__lagi">Selengkapnya</span></summary><p>{r.nilai}</p></details>
            : r.nilai}</td>
          <td data-label="Sumber">{r.nama_file}{r.kutipan && <details><summary>Kutipan</summary><p>{r.kutipan}</p></details>}</td>
          <td data-label="Status"><span className={`state-badge pratinjau-${r.status}`} title={STATUS_PRATINJAU[r.status].hint}>{STATUS_PRATINJAU[r.status].label}</span></td>
          <td><button type="button" className="link-button" onClick={() => onBuka(r.item_id, r.grup)}>Buka item<span className="sr-only"> {r.item_nama}</span></button></td>
        </tr>)}</tbody>
      </table></div>}
    {tampil.length > PRATINJAU_PER_HALAMAN && <div className="table-pager">
      <button type="button" className="link-button" disabled={hal <= 1} onClick={() => setHalaman(hal - 1)}>‹ Sebelumnya</button>
      <span className="table-pager__info" aria-live="polite">{tampil.length} nilai · halaman {hal} dari {jumlahHalaman}</span>
      <button type="button" className="link-button" disabled={hal >= jumlahHalaman} onClick={() => setHalaman(hal + 1)}>Berikutnya ›</button>
    </div>}
  </section>;
}

function DataLive({ live }: { live: NonNullable<WorkspaceItem['live']> }) {
  return <div className="data-live">
    <p className="data-live__title">Data live dari sumber resmi{live.fetched_at && <small> · diambil {waktu(live.fetched_at)}</small>}</p>
    <div className="data-table-wrap"><table className="data-table">
      <caption className="sr-only">Data live</caption>
      <thead><tr>{live.kolom.map(k => <th key={k} scope="col">{k}</th>)}</tr></thead>
      <tbody>{live.rows.map((r, i) => <tr key={i}>{live.kolom.map(k => <td key={k}>{r[k] || <span className="data-live__kosong">tidak tersedia</span>}</td>)}</tr>)}</tbody>
    </table></div>
    <p className="field-hint">Sumber: {live.sumber.map((u, i) => <span key={u}>{i > 0 && ', '}<a className="table-link" href={u} target="_blank" rel="noopener noreferrer">{u.replace(/^https?:\/\//, '')}<span className="sr-only"> (buka di tab baru)</span></a></span>)}. Data ini dipakai di laporan Word selama item belum diisi tim; isi form di bawah untuk menggantinya.</p>
  </div>;
}

function DataPendukung({ data, teks }: { data: NonNullable<WorkspaceItem['pendukung']>; teks: string | null }) {
  const kolomJudul = data.kolom.indexOf('Judul');
  return <details className="data-live data-live--pendukung">
    <summary>{data.judul} ({data.total}) — data pendukung, bukan pengganti isian resmi</summary>
    {teks && <p className="field-hint">{teks}</p>}
    <div className="data-table-wrap"><table className="data-table">
      <caption className="sr-only">{data.judul}</caption>
      <thead><tr>{data.kolom.map(k => <th key={k} scope="col">{k}</th>)}</tr></thead>
      <tbody>{data.rows.map((r, i) => <tr key={i}>{r.map((v, j) => {
        const url = j === kolomJudul ? data.tautan?.[i] : undefined;
        return <td key={j}>{url && /^https?:/.test(url) ? <a className="table-link" href={url} target="_blank" rel="noopener noreferrer">{v}<span className="sr-only"> (buka di tab baru)</span></a> : v}</td>;
      })}</tr>)}</tbody>
    </table></div>
    {data.total > data.rows.length && <p className="field-hint">Ditampilkan {data.rows.length} dari {data.total}.</p>}
  </details>;
}

function barisKosong(kolom: string[]): ItemRow { return Object.fromEntries(kolom.map(k => [k, ''])); }

function ItemCard({ item, prodi, fokus, onSaved }: { item: WorkspaceItem; prodi: string; fokus: boolean; onSaved: () => void }) {
  const sumber = item.draft?.rows ?? item.rows;
  // Tanda tangan data server: kalau berubah (simpan / hasil ekstraksi baru), editor dimuat ulang
  // -- kecuali user sedang mengedit, maka hanya diberi tahu supaya isiannya tidak hilang.
  const tanda = useMemo(() => JSON.stringify([item.updated_at, item.rows, item.draft?.ekstraksi_ids ?? []]), [item]);
  const [rows, setRows] = useState<ItemRow[]>(sumber);
  const [dirty, setDirty] = useState(false);
  const [basi, setBasi] = useState(false);
  const [open, setOpen] = useState(fokus);
  const [status, setStatus] = useState<{ type: 'info' | 'error'; text: string } | null>(null);
  const [sibuk, setSibuk] = useState(false);
  const tandaTerakhir = useRef(tanda);
  const el = useRef<HTMLElement>(null);

  useEffect(() => {
    if (tanda === tandaTerakhir.current) return;
    tandaTerakhir.current = tanda;
    if (dirty) setBasi(true); else setRows(item.draft?.rows ?? item.rows);
  }, [tanda]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { if (fokus) { setOpen(true); el.current?.scrollIntoView({ behavior: 'smooth', block: 'center' }); } }, [fokus]);

  const aiCells = new Map((item.draft?.ai_cells ?? []).map(c => [`${c.baris_ke}|${c.kolom}`, c]));
  const konflik = new Set((item.draft?.conflicts ?? []).map(c => `${c.baris_ke}|${c.kolom}`));

  function ubah(i: number, kolom: string, nilai: string) {
    setRows(rs => rs.map((r, j) => j === i ? { ...r, [kolom]: nilai } : r)); setDirty(true); setStatus(null);
  }
  function salinLive() {
    if (!item.live) return;
    const salinan = item.live.rows.map(r => Object.fromEntries(item.kolom.map(k => [k, r[k] ?? ''])));
    setRows(item.tipe === 'narasi' ? salinan.slice(0, 1) : salinan); setDirty(true); setStatus(null);
  }
  function tambahBaris() { setRows(rs => [...rs, barisKosong(item.kolom)]); setDirty(true); }
  function hapusBaris(i: number) { setRows(rs => rs.length > 1 ? rs.filter((_, j) => j !== i) : [barisKosong(item.kolom)]); setDirty(true); }
  function batal() { setRows(item.draft?.rows ?? item.rows); setDirty(false); setBasi(false); setStatus(null); }

  async function simpan() {
    setSibuk(true); setStatus(null);
    try {
      const hasil = await saveAccreditationItem(prodi, item.id, rows, item.draft?.ekstraksi_ids ?? []);
      setDirty(false); setBasi(false);
      setStatus({ type: 'info', text: hasil.sel ? `Tersimpan (${hasil.baris} baris).` : 'Tersimpan — item ini sekarang kosong.' });
      onSaved();
    } catch (e) { setStatus({ type: 'error', text: pesan(e, 'Gagal menyimpan.') }); }
    finally { setSibuk(false); }
  }

  const adaDraft = Boolean(item.draft);
  return <article ref={el} className={`requirement-card state-${item.state}${open ? ' is-open' : ''}`}>
    <button className="requirement-card__head" aria-expanded={open} onClick={() => setOpen(o => !o)}>
      <span className={`state-badge ${item.state}`}>{STATE_LABEL[item.state]}</span>
      <span className="requirement-card__title">{item.nama}{item.tabel_lkps && <small> · Tabel {item.tabel_lkps}</small>}</span>
      {adaDraft && <span className="state-badge ai">{item.narasi ? 'Draft AI' : 'Hasil ekstraksi AI'}</span>}
      {dirty && <span className="state-badge dirty">Belum disimpan</span>}
      <span className="requirement-card__chevron" aria-hidden="true">{open ? '−' : '+'}</span>
    </button>
    {open && <div className="requirement-card__body">
      <p className="section-note">{item.deskripsi}</p>
      <dl className="requirement-meta">
        <div><dt>Status sumber</dt><dd><span className={`state-badge kategori-${item.kategori}`}>{item.kategori_label}</span></dd></div>
        <div><dt>Sumber data</dt><dd>{item.sumber_asli ?? item.sumber_data}</dd></div>
        {item.diisi_oleh && <div><dt>Terakhir diisi</dt><dd>{item.diisi_oleh} · {waktu(item.updated_at)}</dd></div>}
      </dl>
      {item.kategori === 'akses_data' && item.catatan && <p className="field-hint"><b>Kenapa belum otomatis:</b> {item.catatan}</p>}
      {item.kategori === 'penyusunan' && <p className="field-hint">Item ini memang ditulis tim penyusun prodi (narasi/keputusan), bukan ditarik dari sistem.</p>}
      {item.live && <DataLive live={item.live} />}
      {item.pendukung && <DataPendukung data={item.pendukung} teks={item.sumber_tambahan} />}
      {!item.editable
        ? <Notice type="info">Belum ada pipeline/form untuk item ini. Sumber data seharusnya: <b>{item.sumber_data}</b>.</Notice>
        : <>
          {item.narasi && <Notice type="info"><b>Narasi ini perlu disesuaikan tim penyusun dengan kondisi &amp; evaluasi terkini</b> sebelum digunakan — termasuk bila ada draft dari dokumen yang diupload. Ini soal kesegaran dan relevansi narasi, bukan akurasi kutipan.</Notice>}
          {adaDraft && !item.narasi && <Notice type="warning"><b>Hasil ekstraksi AI — perlu diverifikasi.</b> Sel bertanda kuning diisi AI dari file yang diupload dan BELUM tersimpan sebagai data resmi. Cek kutipan sumbernya, edit bila perlu, lalu klik Simpan untuk mengonfirmasi.</Notice>}
          {adaDraft && item.narasi && <Notice type="warning"><b>Draft AI dari dokumen yang diupload</b> — belum tersimpan sebagai data resmi. Baca dan sesuaikan isinya sebelum klik Simpan.</Notice>}
          {basi && <Notice type="warning">Data item ini berubah di server (mis. hasil ekstraksi baru) saat Anda mengedit. Simpan untuk memakai isian Anda, atau <button className="link-button" onClick={batal}>muat versi terbaru</button>.</Notice>}
          {item.draft?.conflicts.map(c => <Notice key={`${c.baris_ke}|${c.kolom}`} type="warning">
            <b>{c.kolom}</b> (baris {c.baris_ke}): {c.opsi.length} nilai berbeda dari file berbeda — sengaja dikosongkan, pilih sendiri:
            <span className="conflict-options">{c.opsi.map((o, i) => <button key={i} className="button secondary" title={o.kutipan ?? undefined} onClick={() => ubah(c.baris_ke - 1, c.kolom, o.nilai)}>“{o.nilai}” <small>dari {o.nama_file}</small></button>)}</span>
          </Notice>)}
          {item.draft?.skipped.map(s => <p key={`${s.baris_ke}|${s.kolom}`} className="field-hint">AI menemukan “{s.nilai}” untuk <b>{s.kolom}</b> (baris {s.baris_ke}, dari {s.nama_file}), tetapi kolom ini sudah berisi data manual — tidak ditimpa.</p>)}

          {item.tipe === 'narasi'
            ? <div className="narasi-editor">{item.kolom.map(k => {
              const ai = aiCells.get(`1|${k}`);
              return <div className={`field${ai ? ' is-ai' : ''}`} key={k}>
                <label htmlFor={`${item.id}-${k}`}>{k}</label>
                <textarea id={`${item.id}-${k}`} rows={3} value={rows[0]?.[k] ?? ''} onChange={e => ubah(0, k, e.target.value)} />
                {ai && <small className="ai-source">Dari AI · {ai.nama_file}{ai.kutipan ? ` — “${ai.kutipan}”` : ''}</small>}
              </div>;
            })}</div>
            : <div className="data-table-wrap item-editor"><table>
              <caption className="sr-only">Isian {item.nama}</caption>
              <thead><tr><th scope="col" className="item-editor__no">#</th>{item.kolom.map(k => <th key={k} scope="col">{k}</th>)}<th scope="col"><span className="sr-only">Aksi</span></th></tr></thead>
              <tbody>{rows.map((r, i) => <tr key={i}>
                <td className="item-editor__no">{i + 1}</td>
                {item.kolom.map(k => {
                  const kunci = `${i + 1}|${k}`; const ai = aiCells.get(kunci);
                  return <td key={k} className={ai ? 'is-ai' : konflik.has(kunci) ? 'is-conflict' : undefined}>
                    <input aria-label={`${k}, baris ${i + 1}`} value={r[k] ?? ''} title={ai ? `Dari AI (${ai.nama_file})${ai.kutipan ? `: ${ai.kutipan}` : ''}` : undefined} onChange={e => ubah(i, k, e.target.value)} />
                  </td>;
                })}
                <td><button className="link-button" aria-label={`Hapus baris ${i + 1}`} onClick={() => hapusBaris(i)}>Hapus</button></td>
              </tr>)}</tbody>
            </table></div>}
          {item.tipe === 'tabel' && aiCells.size > 0 && <details className="ai-sources"><summary>Kutipan sumber nilai AI ({aiCells.size})</summary><ul>
            {[...aiCells.values()].map(c => <li key={`${c.baris_ke}|${c.kolom}`}><b>{c.kolom}</b> (baris {c.baris_ke}): “{c.nilai}” — {c.nama_file}{c.kutipan ? <>: <i>{c.kutipan}</i></> : null}</li>)}
          </ul></details>}
          <div className="action-row">
            {item.live && !item.terisi && <button className="button secondary" onClick={salinLive}>Salin data live ke isian</button>}
            {item.tipe === 'tabel' && <button className="button secondary" onClick={tambahBaris}>+ Tambah baris</button>}
            <button className="button" disabled={sibuk} onClick={simpan}>{sibuk ? 'Menyimpan…' : adaDraft ? 'Simpan & konfirmasi' : 'Simpan'}</button>
            {dirty && <button className="link-button" onClick={batal}>Batalkan perubahan</button>}
          </div>
          {status && <Notice type={status.type}>{status.text}</Notice>}
        </>}
    </div>}
  </article>;
}

function GeneratePanel({ prodi, dokumen }: { prodi: string; dokumen: Dokumen }) {
  const [sibuk, setSibuk] = useState(false);
  const [status, setStatus] = useState<{ type: 'info' | 'error'; text: string } | null>(null);
  async function generate() {
    setSibuk(true); setStatus(null);
    try {
      const { blob, filename } = await generateAccreditationDocument(prodi, dokumen);
      simpanBlob(blob, filename);
      setStatus({ type: 'info', text: `${filename} diunduh. Salinannya tersimpan di riwayat Profil Saya.` });
    } catch (e) { setStatus({ type: 'error', text: pesan(e, 'Dokumen gagal dibuat.') }); }
    finally { setSibuk(false); }
  }
  return <section className="section requirement-section">
    <p className="section-kicker">Dokumen Word</p>
    <h2>Generate laporan {dokumen}</h2>
    <p className="section-note">Satu dokumen .docx: cover dengan kelengkapan per status sumber, to-do item yang belum lengkap, lalu isi per {dokumen === 'LED' ? 'Kriteria (ditutup ringkasan tabel LKPS terkait)' : 'Bagian'}. Isi tiap item memakai isian tim yang sudah disimpan; kalau belum ada, data live dari sumber resmi. Item tanpa keduanya tetap dibuat dengan penanda <b>[DATA TIDAK TERSEDIA]</b> (sumber belum bisa diakses, disertai catatannya) atau <b>[NARASI PERLU DISUSUN TIM PENYUSUN PRODI]</b>. Hasil ekstraksi yang belum disimpan tidak ikut.</p>
    <div className="action-row"><button className="button" disabled={sibuk} onClick={generate}>{sibuk ? 'Membuat dokumen…' : `Generate & unduh ${dokumen} (Word)`}</button></div>
    {status && <Notice type={status.type}>{status.text}</Notice>}
  </section>;
}
