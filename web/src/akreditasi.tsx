import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import {
  accreditationUpload, addAccreditationProgram, generateAccreditationDocument, getAccreditationWorkspace,
  saveAccreditationItem, simpanBlob, startAccreditationExtraction,
  type AccreditationResult, type AuthUser, type Dokumen, type ItemRow, type Workspace, type WorkspaceItem, type WorkspaceUpload,
} from './lib/api';
import { Notice, PageHeader, ProgressLine, StatCard } from './ui';

/* Ruang kerja akreditasi: pengganti dashboard Streamlit (dashboard_akreditasi.py / page_akreditasi.py).
   Alur sama: Lingkup -> Fakultas & Prodi -> Dokumen (LED/LKPS) -> Upload & ekstraksi -> isi item -> Generate Word. */

const TAMBAH_PRODI = '__tambah__';
const JENJANG = ['Sarjana', 'Magister', 'Doktor', 'Profesi', 'Spesialis'];
const MAX_UPLOAD_MB = 25;
const STATE_LABEL: Record<WorkspaceItem['state'], string> = {
  otomatis: 'Tersedia otomatis', terisi: 'Terisi', kosong: 'Perlu input', belum_tersedia: 'Belum tersedia',
};
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
                {workspace.ekstraksi.item_menunggu_review > 0 && <Notice type="warning">Ada hasil ekstraksi AI untuk <b>{workspace.ekstraksi.item_menunggu_review} item</b> yang belum direview. Buka item bertanda <b>Draft AI</b>, cek kutipan sumbernya, lalu klik Simpan untuk mengonfirmasi.</Notice>}
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
  return <>
    <section className="progress-overview" aria-label="Ringkasan kelengkapan">
      <StatCard label="Total item" value={r.total} note={`${workspace.dokumen} · ${workspace.prodi.nama}`} />
      <StatCard label="Tersedia otomatis" value={r.tersedia_otomatis} note="dari pipeline data" />
      <StatCard label="Input manual terisi" value={`${r.perlu_manual_terisi}/${r.perlu_manual_total}`} note="dikonfirmasi penyusun" />
      <StatCard label="Belum tersedia" value={r.belum_tersedia} note="belum ada sumber data" />
    </section>
    <ProgressLine value={r.lengkap} total={r.total} percent={r.persen} note={r.narasi_total ? `termasuk ${r.narasi_terisi}/${r.narasi_total} item narasi` : undefined} />
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
        <div><dt>Sumber data</dt><dd>{item.sumber_data}</dd></div>
        <div><dt>Status</dt><dd>{item.status_label}</dd></div>
        {item.diisi_oleh && <div><dt>Terakhir diisi</dt><dd>{item.diisi_oleh} · {waktu(item.updated_at)}</dd></div>}
      </dl>
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
    <p className="section-note">Satu dokumen .docx: cover, ringkasan &amp; to-do item yang belum lengkap, lalu isi per {dokumen === 'LED' ? 'Kriteria (ditutup ringkasan tabel LKPS terkait)' : 'Bagian'}. Bagian yang datanya belum ada tetap dibuat dan ditandai “Data belum tersedia”, jadi dokumen selalu berupa template lengkap. Yang dipakai hanya data yang sudah disimpan.</p>
    <div className="action-row"><button className="button" disabled={sibuk} onClick={generate}>{sibuk ? 'Membuat dokumen…' : `Generate & unduh ${dokumen} (Word)`}</button></div>
    {status && <Notice type={status.type}>{status.text}</Notice>}
  </section>;
}
