import { useCallback, useEffect, useRef, useState } from 'react';

import {
  ApiError, accreditationUpload, addAccreditationProgram, ajukanResetPin, buatLaporan, buatPinProdi, bukaProdi, downloadLaporanWord, hapusLaporan,
  generateAccreditationDocument, getAccreditationWorkspace, getDaftarLaporan, simpanBlob, startAccreditationExtraction,
  type AccreditationResult, type AuthUser, type DaftarLaporan, type Dokumen, type RiwayatEkstraksi, type Workspace, type WorkspaceItem, type WorkspaceUpload,
} from './lib/api';
import { Notice, PageHeader, ProgressLine, StatCard } from './ui';
import { pesan, useItemEditor, waktu } from './akreditasi-edit';
import { ReviewDokumen } from './akreditasi-dokumen';

type Mode = 'isi' | 'review' | 'download';
const MODE_LABEL: Record<Mode, string> = { isi: 'Isi data & upload', review: '1. Review dokumen', download: '2. Download Word' };

/* Ruang kerja akreditasi. Alur: Lingkup -> Fakultas & Prodi -> Dokumen (LED/LKPS) -> pilih laporan (tahun)
   dari riwayat atau buat baru, dibuka dengan PIN prodi -> Upload & ekstraksi -> isi item -> Generate Word.
   Staf satu prodi mengerjakan laporan yang sama; PIN prodi diminta lagi setiap login. */

const TAMBAH_PRODI = '__tambah__';
const JENJANG = ['Sarjana', 'Magister', 'Doktor', 'Profesi', 'Spesialis'];
const MAX_UPLOAD_MB = 25;
const STATE_LABEL: Record<WorkspaceItem['state'], string> = {
  otomatis: 'Tersedia otomatis', live: 'Data live', terisi: 'Terisi', kosong: 'Perlu input', belum_tersedia: 'Belum tersedia',
};
const STATUS_EKSTRAKSI: Record<RiwayatEkstraksi['status'], { label: string; hint: string }> = {
  ditambahkan: { label: 'Ditambahkan', hint: 'Masuk ke tabel data: mengisi kolom kosong atau menjadi baris baru.' },
  sudah_ada: { label: 'Sudah ada', hint: 'Nilai yang sama sudah ada di tabel data; tidak ditambahkan dua kali.' },
  tidak_menimpa: { label: 'Tidak menimpa', hint: 'Kolom ini sudah berisi nilai lain; isian yang ada dipertahankan.' },
  kolom_lain: { label: 'Di luar kolom', hint: 'Kolom ini tidak dibutuhkan item; tidak dipakai.' },
};
const RIWAYAT_PER_HALAMAN = 10;
// PIN prodi: angka saja, 6-12 digit (dicek ulang di server).
const PIN_MIN = 6;
const PIN_MAX = 12;
const pinValid = (pin: string) => new RegExp(`^[0-9]{${PIN_MIN},${PIN_MAX}}$`).test(pin);
const hanyaAngka = (v: string) => v.replace(/[^0-9]/g, '').slice(0, PIN_MAX);

/** Kolom PIN: tersamar, keyboard angka di ponsel, karakter selain angka dibuang saat diketik. */
function KolomPin({ id, label, value, onChange, baru }: { id: string; label: string; value: string; onChange: (v: string) => void; baru?: boolean }) {
  return <div className="field"><label htmlFor={id}>{label}</label>
    <input id={id} type="password" inputMode="numeric" autoComplete={baru ? 'new-password' : 'current-password'} maxLength={PIN_MAX}
      value={value} onChange={e => onChange(hanyaAngka(e.target.value))} /></div>;
}

/** Alasan tombol simpan PIN belum aktif, supaya tidak terasa "tombolnya tidak berfungsi". */
function syaratPin(pin: string, ulang: string): string | null {
  if (!pinValid(pin)) return `PIN harus ${PIN_MIN}–${PIN_MAX} angka (sekarang ${pin.length} angka).`;
  if (ulang !== pin) return ulang ? 'Kedua PIN belum sama.' : 'Ketik ulang PIN untuk konfirmasi.';
  return null;
}
// Narasi hasil AI bisa ratusan kata; di tabel cukup awalnya, sisanya dibuka per baris.
const NILAI_RINGKAS = 180;
const UPLOAD_LABEL: Record<WorkspaceUpload['status'], string> = {
  belum_diekstrak: 'Belum diekstrak', sedang_diekstrak: 'Sedang diekstrak', diekstrak: 'Sudah diekstrak',
  gagal_ekstrak: 'Gagal diekstrak', terhenti: 'Terhenti — bisa diulang',
};


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
  initialLaporan: number | null;
};

export function AccreditationWorkspace({ catalog, user, onLogout, onCatalogChange, initialProdi, initialDokumen, initialLaporan }: Props) {
  const [lingkup, setLingkup] = useState<'prodi' | 'universitas'>('prodi');
  const awal = catalog.programs.find(p => String(p.slug) === initialProdi);
  const [fakultas, setFakultas] = useState(awal ? String(awal.fakultas_id) : '');
  const [prodi, setProdi] = useState(awal ? initialProdi : '');
  const [dokumen, setDokumen] = useState<Dokumen>(initialDokumen);
  const [laporanId, setLaporanId] = useState<number | null>(null);
  // Laporan yang diminta lewat tautan (?laporan= dari Profil) atau yang sesinya habis: daftar laporan
  // + formulir PIN ditampilkan dulu, lalu laporan ini dibuka otomatis begitu PIN prodi benar.
  const [laporanTarget, setLaporanTarget] = useState<number | null>(awal ? initialLaporan : null);
  // "Buka di LKPS" dari laporan LED: buka laporan LKPS tahun yang sama bila sudah ada.
  const [tahunTarget, setTahunTarget] = useState<number | null>(null);
  const [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [groupKey, setGroupKey] = useState('');
  const [fokus, setFokus] = useState('');
  const [mode, setMode] = useState<Mode>('isi');
  const permintaan = useRef(0);

  const prodiDariFakultas = catalog.programs.filter(p => String(p.fakultas_id) === fakultas);
  const yatim = catalog.programs.filter(p => !p.fakultas_id || String(p.fakultas_id) === '').length;

  const muat = useCallback(async (diam = false) => {
    if (!laporanId) { setWorkspace(null); return; }
    const id = ++permintaan.current;
    if (!diam) { setLoading(true); setError(''); }
    try {
      const hasil = await getAccreditationWorkspace(laporanId);
      if (id === permintaan.current) setWorkspace(hasil);
    } catch (e) {
      if (id !== permintaan.current) return;
      if (e instanceof ApiError && e.status === 403) {  // PIN prodi belum/tidak lagi dibuka di sesi ini
        setLaporanTarget(laporanId); setLaporanId(null); setWorkspace(null);
      } else setError(pesan(e, 'Data akreditasi gagal dimuat.'));
    } finally {
      if (id === permintaan.current && !diam) setLoading(false);
    }
  }, [laporanId]);

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
    setGroupKey(''); setLaporanId(null);
  }

  function bukaDiLkps(itemId: string, tabel: string) {
    setTahunTarget(workspace?.laporan.tahun ?? null);
    setDokumen('LKPS'); setLaporanId(null); setGroupKey(bagianLkps(tabel)); setFokus(itemId);
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
        <select id="ak-prodi" value={prodi} disabled={!fakultas || lingkup !== 'prodi'} onChange={e => { setProdi(e.target.value); setGroupKey(''); setLaporanId(null); }}>
          {!fakultas && <option value="">Pilih fakultas dulu</option>}
          {prodiDariFakultas.map(p => <option key={String(p.id)} value={String(p.slug)}>{labelProdi(p)}</option>)}
          {fakultas && <option value={TAMBAH_PRODI}>+ Tambah prodi baru</option>}
        </select>
      </div>
      <div className="field">
        <label htmlFor="ak-dokumen">Dokumen</label>
        <select id="ak-dokumen" value={dokumen} disabled={lingkup !== 'prodi'} onChange={e => { setDokumen(e.target.value as Dokumen); setGroupKey(''); setLaporanId(null); setTahunTarget(null); }}>
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
          : !laporanId
            ? <PilihLaporan prodi={prodi} dokumen={dokumen} tahunTarget={tahunTarget} laporanTarget={laporanTarget}
                onPilih={id => { setLaporanId(id); setTahunTarget(null); setLaporanTarget(null); setMode('isi'); }} />
            : error
              ? <div className="laporan-galat"><Notice type="error">{error}</Notice><button className="button secondary" onClick={() => { setError(''); setLaporanId(null); }}>Kembali ke daftar laporan</button></div>
              : !workspace || workspace.laporan.id !== laporanId
                ? <div className="loading" role="status">Memuat kelengkapan data…</div>
                : <>
                <div className="laporan-bar">
                  <div><p className="section-kicker">Laporan yang sedang dikerjakan</p><h2>{workspace.laporan.nama}</h2><p className="section-note">{workspace.prodi.nama} · dikerjakan bersama staf prodi yang memegang PIN prodi.</p></div>
                  <button className="button secondary" onClick={() => { setLaporanId(null); setWorkspace(null); }}>Ganti laporan</button>
                </div>
                <nav className="ruang-mode" aria-label="Tahap pengerjaan laporan">
                  {(Object.keys(MODE_LABEL) as Mode[]).map(m => <button key={m} type="button" aria-current={mode === m ? 'step' : undefined}
                    className={mode === m ? 'is-on' : ''} onClick={() => setMode(m)}>{MODE_LABEL[m]}</button>)}
                </nav>
                {mode === 'review' && <ReviewDokumen workspace={workspace} onChange={() => muat(true)} onLanjut={() => setMode('download')}
                  onEditTabel={(itemId, grup) => { setMode('isi'); setGroupKey(grup); setFokus(''); window.setTimeout(() => setFokus(itemId), 0); }} />}
                {mode === 'download' && <>
                  {workspace.ringkasan.final < workspace.ringkasan.total && <Notice type="info">{workspace.ringkasan.final} dari {workspace.ringkasan.total} bagian sudah ditandai final. Word tetap bisa diunduh; bagian yang masih draft ikut dengan isi terakhirnya. <button className="link-button" onClick={() => setMode('review')}>Kembali ke review</button></Notice>}
                  <GeneratePanel workspace={workspace} onChange={() => muat(true)} />
                </>}
                {mode === 'isi' && <>
                <Ringkasan workspace={workspace} />
                <UploadPanel workspace={workspace} dokumen={dokumen} onChange={() => muat(true)} />
                <RiwayatEkstraksiPanel workspace={workspace} onBuka={(itemId, grup) => { setGroupKey(grup); setFokus(''); window.setTimeout(() => setFokus(itemId), 0); }} />
                <section className="section requirement-section">
                  <div className="section-title-row">
                    <div><p className="section-kicker">Kelengkapan Data {dokumen}</p><h2>{dokumen === 'LED' ? 'Narasi evaluatif per Kriteria' : 'Tabel data per Bagian'}</h2></div>
                    <span className="status-pill">{workspace.ringkasan.lengkap}/{workspace.ringkasan.total} lengkap</span>
                  </div>
                  <p className="section-note">{dokumen === 'LED'
                    ? 'Narasi evaluatif per Kriteria A–D (siklus PPEPP). Tiap Kriteria A/B/C1–C6 juga menampilkan tabel LKPS terkait sebagai bukti evaluasi.'
                    : 'Tabel data mentah per Bagian 1–6. Isi tabel lalu klik Simpan — tersimpan langsung sebagai data resmi laporan ini.'}</p>
                  <div className="accreditation-tabs" role="tablist" aria-label={dokumen === 'LED' ? 'Kriteria' : 'Bagian'}>
                    {groups.map(g => {
                      const lengkap = g.items.filter(i => i.state === 'terisi' || i.state === 'otomatis').length;
                      return <button key={g.key} role="tab" aria-selected={g.key === activeGroup?.key} className={g.key === activeGroup?.key ? 'active' : ''} onClick={() => setGroupKey(g.key)}>
                        {g.label} <span className="tab-count">{lengkap}/{g.items.length}</span>
                      </button>;
                    })}
                  </div>
                  {activeGroup && <div className="requirement-list" role="tabpanel">
                    {activeGroup.items.map(item => <ItemCard key={item.id} item={item} laporanId={workspace.laporan.id} fokus={fokus === item.id} onSaved={() => muat(true)} />)}
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
                <div className="ruang-mode__lanjut">
                  <p>Selesai mengisi? Periksa laporan seperti dokumen, tandai tiap bagian final, lalu unduh Word.</p>
                  <button className="button" onClick={() => { setMode('review'); window.scrollTo({ top: 0, behavior: 'smooth' }); }}>Review dokumen ›</button>
                </div>
                </>}
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

function UploadPanel({ workspace, dokumen, onChange }: { workspace: Workspace; dokumen: Dokumen; onChange: () => void }) {
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
      try { await accreditationUpload(workspace.laporan.id, f); hasil.push({ type: 'info', text: `${f.name} tersimpan.` }); }
      catch (e) { hasil.push({ type: 'error', text: `${f.name}: ${pesan(e, 'upload gagal')}` }); }
    }
    setPesanUpload(hasil); setFiles([]); if (input.current) input.current.value = '';
    setSibuk(false); onChange();
  }

  async function ekstrak() {
    setSibuk(true); setPesanUpload([]);
    try {
      const { dimulai } = await startAccreditationExtraction(workspace.laporan.id);
      setPesanUpload([{ type: 'info', text: dimulai ? `Ekstraksi ${dimulai} file dimulai (mode ${dokumen}). Proses berjalan di latar; hasilnya langsung masuk ke tabel data dan halaman ini diperbarui otomatis.` : 'Tidak ada file yang perlu diekstrak.' }]);
    } catch (e) { setPesanUpload([{ type: 'error', text: pesan(e, 'Ekstraksi gagal dimulai.') }]); }
    setSibuk(false); onChange();
  }

  return <section className="upload-workflow upload-workflow--stack">
    <div>
      <p className="section-kicker">Dokumen pendukung</p>
      <h2>Upload & ekstraksi file</h2>
      <p>PDF, DOCX, atau XLSX — maks. {MAX_UPLOAD_MB} MB per file. Setelah diupload, klik <b>Ekstrak data</b>: nilai yang ditemukan AI <b>langsung masuk ke tabel data</b> laporan ini. Isian yang sudah ada tidak pernah ditimpa: kolom kosong diisi, baris baru ditambahkan, dan setiap file baru menambah detail. Periksa hasilnya di riwayat ekstraksi di bawah.</p>
    </div>
    <div className="upload-controls">
      <label className="sr-only" htmlFor="ak-upload">Pilih file pendukung</label>
      <input id="ak-upload" ref={input} type="file" multiple accept=".pdf,.docx,.xlsx" onChange={e => setFiles(Array.from(e.target.files ?? []))} />
      <button className="button" disabled={sibuk || files.length === 0} onClick={unggah}>{sibuk && files.length ? 'Mengunggah…' : `Upload${files.length > 1 ? ` ${files.length} file` : ''}`}</button>
    </div>
    {pesanUpload.map((p, i) => <Notice key={i} type={p.type}>{p.text}</Notice>)}
    {workspace.uploads.length === 0
      ? <p className="section-note">Belum ada file yang diupload untuk laporan ini.</p>
      : <div className="data-table-wrap"><table className="data-table">
        <caption className="sr-only">File pendukung yang sudah diupload untuk laporan ini</caption>
        <thead><tr><th scope="col">Nama file</th><th scope="col">Tipe</th><th scope="col">Ukuran</th><th scope="col">Status</th><th scope="col">Diupload</th></tr></thead>
        <tbody>{workspace.uploads.map(u => <tr key={u.id}>
          <td>{u.nama_file}{u.diupload_oleh && <small className="upload-summary">oleh {u.diupload_oleh}</small>}{u.ringkasan && <small className="upload-summary">{u.ringkasan.error
            ? `Kendala: ${u.ringkasan.error}`
            : `${u.ringkasan.n_item_ditemukan ?? 0} item ditemukan${u.ringkasan.diterapkan ? `, ${u.ringkasan.diterapkan.ditambahkan} nilai masuk tabel` : ''}`}</small>}</td>
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

/** Semua nilai hasil ekstraksi AI laporan ini dan apa yang terjadi saat diterapkan ke tabel data. */
function RiwayatEkstraksiPanel({ workspace, onBuka }: { workspace: Workspace; onBuka: (itemId: string, grup: string) => void }) {
  const semua = workspace.ekstraksi.riwayat;
  const [saring, setSaring] = useState<RiwayatEkstraksi['status'] | ''>('');
  const [cari, setCari] = useState('');
  const [halaman, setHalaman] = useState(1);
  const q = cari.trim().toLowerCase();
  const tampil = semua.filter(r => (!saring || r.status === saring)
    && (!q || `${r.item_nama} ${r.kolom} ${r.nilai} ${r.nama_file}`.toLowerCase().includes(q)));
  const jumlahHalaman = Math.max(1, Math.ceil(tampil.length / RIWAYAT_PER_HALAMAN));
  const hal = Math.min(halaman, jumlahHalaman);
  const baris = tampil.slice((hal - 1) * RIWAYAT_PER_HALAMAN, hal * RIWAYAT_PER_HALAMAN);
  const per = (st: RiwayatEkstraksi['status']) => semua.filter(r => r.status === st).length;
  const nFile = new Set(semua.map(r => r.nama_file)).size;
  useEffect(() => { setHalaman(1); }, [saring, cari]);
  if (!semua.length) return null;
  return <section className="section requirement-section ekstraksi-preview" aria-labelledby="ekstraksi-preview-title">
    <div className="section-title-row">
      <div><p className="section-kicker">Hasil ekstraksi</p><h2 id="ekstraksi-preview-title">Riwayat data hasil ekstraksi</h2></div>
      <span className="status-pill">{per('ditambahkan')} nilai masuk tabel · {nFile} file</span>
    </div>
    <p className="section-note">Setiap nilai yang ditemukan AI dan apa yang terjadi padanya. Nilai berstatus <b>Ditambahkan</b> sudah masuk tabel data (bisa diedit di item). Nilai yang sama atau yang bertentangan dengan isian yang ada tidak menimpa apa pun, tetapi tetap tercatat di sini.</p>
    <div className="ekstraksi-preview__tools">
      <div className="ekstraksi-preview__chips" role="group" aria-label="Saring status">
        {([['', `Semua (${semua.length})`], ['ditambahkan', `Ditambahkan (${per('ditambahkan')})`], ['sudah_ada', `Sudah ada (${per('sudah_ada')})`], ['tidak_menimpa', `Tidak menimpa (${per('tidak_menimpa')})`], ['kolom_lain', `Di luar kolom (${per('kolom_lain')})`]] as const)
          .filter(([k]) => !k || per(k as RiwayatEkstraksi['status']) > 0)
          .map(([k, label]) => <button key={k} type="button" aria-pressed={saring === k} className={saring === k ? 'is-on' : ''} onClick={() => setSaring(k as RiwayatEkstraksi['status'] | '')}>{label}</button>)}
      </div>
      <div className="field">
        <label htmlFor="ekstraksi-cari">Cari item, kolom, nilai, atau file</label>
        <input id="ekstraksi-cari" type="search" value={cari} maxLength={100} onChange={e => setCari(e.target.value)} />
      </div>
    </div>
    {baris.length === 0
      ? <p className="section-note">Tidak ada nilai yang cocok dengan saringan ini.</p>
      : <div className="data-table-wrap"><table className="data-table ekstraksi-preview__table">
        <caption className="sr-only">Riwayat nilai hasil ekstraksi AI laporan ini</caption>
        <thead><tr><th scope="col">Item</th><th scope="col">Kolom</th><th scope="col">Nilai hasil AI</th><th scope="col">Sumber</th><th scope="col">Status</th><th scope="col"><span className="sr-only">Aksi</span></th></tr></thead>
        <tbody>{baris.map(r => <tr key={r.id}>
          <td data-label="Item">{r.item_nama}</td>
          <td data-label="Kolom">{r.kolom}<small className="ekstraksi-preview__baris">baris {r.baris_ke} di file</small></td>
          <td data-label="Nilai hasil AI" className="ekstraksi-preview__nilai">{r.nilai.length > NILAI_RINGKAS
            ? <details><summary>{r.nilai.slice(0, NILAI_RINGKAS).trimEnd()}… <span className="ekstraksi-preview__lagi">Selengkapnya</span></summary><p>{r.nilai}</p></details>
            : r.nilai}</td>
          <td data-label="Sumber">{r.nama_file}{r.kutipan && <details><summary>Kutipan</summary><p>{r.kutipan}</p></details>}</td>
          <td data-label="Status"><span className={`state-badge pratinjau-${r.status}`} title={STATUS_EKSTRAKSI[r.status].hint}>{STATUS_EKSTRAKSI[r.status].label}</span></td>
          <td><button type="button" className="link-button" onClick={() => onBuka(r.item_id, r.grup)}>Buka item<span className="sr-only"> {r.item_nama}</span></button></td>
        </tr>)}</tbody>
      </table></div>}
    {tampil.length > RIWAYAT_PER_HALAMAN && <div className="table-pager">
      <button type="button" className="link-button" disabled={hal <= 1} onClick={() => setHalaman(hal - 1)}>‹ Sebelumnya</button>
      <span className="table-pager__info" aria-live="polite">{tampil.length} nilai · halaman {hal} dari {jumlahHalaman}</span>
      <button type="button" className="link-button" disabled={hal >= jumlahHalaman} onClick={() => setHalaman(hal + 1)}>Berikutnya ›</button>
    </div>}
  </section>;
}

/** Data live pipeline. Kalau item sudah diisi tim, isian tim yang dipakai di Word, jadi data live
 *  hanya dilipat sebagai pembanding supaya sel kosongnya tidak terbaca seperti isian yang hilang. */
function DataLive({ live, terisi }: { live: NonNullable<WorkspaceItem['live']>; terisi: boolean }) {
  const tabel = <>
    <div className="data-table-wrap"><table className="data-table">
      <caption className="sr-only">Data live</caption>
      <thead><tr>{live.kolom.map(k => <th key={k} scope="col">{k}</th>)}</tr></thead>
      <tbody>{live.rows.map((r, i) => <tr key={i}>{live.kolom.map(k => <td key={k}>{r[k] || <span className="data-live__kosong">tidak ditemukan di sumber</span>}</td>)}</tr>)}</tbody>
    </table></div>
    <p className="field-hint">Sumber: {live.sumber.map((u, i) => <span key={u}>{i > 0 && ', '}<a className="table-link" href={u} target="_blank" rel="noopener noreferrer">{u.replace(/^https?:\/\//, '')}<span className="sr-only"> (buka di tab baru)</span></a></span>)}.{' '}
      {terisi ? 'Item ini sudah diisi tim, jadi laporan Word memakai isian tim di bawah, bukan data live ini.' : 'Data ini dipakai di laporan Word selama item belum diisi tim; isi form di bawah untuk menggantinya.'}</p>
  </>;
  const waktuAmbil = live.fetched_at && <small> · diambil {waktu(live.fetched_at)}</small>;
  if (terisi) {
    return <details className="data-live data-live--pendukung">
      <summary>Bandingkan dengan data live dari sumber resmi{waktuAmbil}</summary>
      {tabel}
    </details>;
  }
  return <div className="data-live">
    <p className="data-live__title">Data live dari sumber resmi{waktuAmbil}</p>
    {tabel}
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


function ItemCard({ item, laporanId, fokus, onSaved }: { item: WorkspaceItem; laporanId: number; fokus: boolean; onSaved: () => void }) {
  const { rows, dirty, basi, status, sibuk, ubah, salinLive, tambahBaris, hapusBaris, batal, simpan } = useItemEditor(item, laporanId, onSaved);
  const [open, setOpen] = useState(fokus);
  const el = useRef<HTMLElement>(null);

  useEffect(() => { if (fokus) { setOpen(true); el.current?.scrollIntoView({ behavior: 'smooth', block: 'center' }); } }, [fokus]);

  const dariAi = Boolean(item.diisi_oleh?.startsWith('AI: '));
  return <article ref={el} className={`requirement-card state-${item.state}${open ? ' is-open' : ''}`}>
    <button className="requirement-card__head" aria-expanded={open} onClick={() => setOpen(o => !o)}>
      <span className={`state-badge ${item.state}`}>{STATE_LABEL[item.state]}</span>
      <span className="requirement-card__title">{item.nama}{item.tabel_lkps && <small> · Tabel {item.tabel_lkps}</small>}</span>
      {dariAi && <span className="state-badge ai">Dari ekstraksi AI</span>}
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
      {item.live && <DataLive live={item.live} terisi={item.terisi} />}
      {item.pendukung && <DataPendukung data={item.pendukung} teks={item.sumber_tambahan} />}
      {!item.editable
        ? <Notice type="info">Belum ada pipeline/form untuk item ini. Sumber data seharusnya: <b>{item.sumber_data}</b>.</Notice>
        : <>
          {item.narasi && <Notice type="info"><b>Narasi ini perlu disesuaikan tim penyusun dengan kondisi &amp; evaluasi terkini</b> sebelum digunakan — termasuk bila isinya berasal dari ekstraksi dokumen yang diupload.</Notice>}
          {dariAi && <p className="field-hint">Sebagian isian item ini berasal dari ekstraksi AI ({item.diisi_oleh?.slice(4)}). Periksa lalu klik Simpan untuk mengonfirmasi atas nama Anda.</p>}
          {basi && <Notice type="warning">Data item ini berubah di server (mis. disimpan staf lain atau hasil ekstraksi baru) saat Anda mengedit. Simpan untuk memakai isian Anda, atau <button className="link-button" onClick={batal}>muat versi terbaru</button>.</Notice>}

          {item.tipe === 'narasi'
            ? <div className="narasi-editor">{item.kolom.map(k => <div className="field" key={k}>
                <label htmlFor={`${item.id}-${k}`}>{k}</label>
                <textarea id={`${item.id}-${k}`} rows={3} value={rows[0]?.[k] ?? ''} onChange={e => ubah(0, k, e.target.value)} />
              </div>)}</div>
            : <div className="data-table-wrap item-editor"><table>
              <caption className="sr-only">Isian {item.nama}</caption>
              <thead><tr><th scope="col" className="item-editor__no">#</th>{item.kolom.map(k => <th key={k} scope="col">{k}</th>)}<th scope="col"><span className="sr-only">Aksi</span></th></tr></thead>
              <tbody>{rows.map((r, i) => <tr key={i}>
                <td className="item-editor__no">{i + 1}</td>
                {item.kolom.map(k => <td key={k}>
                  <input aria-label={`${k}, baris ${i + 1}`} value={r[k] ?? ''} onChange={e => ubah(i, k, e.target.value)} />
                </td>)}
                <td><button className="link-button" aria-label={`Hapus baris ${i + 1}`} onClick={() => hapusBaris(i)}>Hapus</button></td>
              </tr>)}</tbody>
            </table></div>}
          <div className="action-row">
            {item.live && !item.terisi && <button className="button secondary" onClick={salinLive}>Salin data live ke isian</button>}
            {item.tipe === 'tabel' && <button className="button secondary" onClick={tambahBaris}>+ Tambah baris</button>}
            <button className="button" disabled={sibuk} onClick={simpan}>{sibuk ? 'Menyimpan…' : 'Simpan'}</button>
            {dirty && <button className="link-button" onClick={batal}>Batalkan perubahan</button>}
          </div>
          {status && <Notice type={status.type}>{status.text}</Notice>}
        </>}
    </div>}
  </article>;
}

function GeneratePanel({ workspace, onChange }: { workspace: Workspace; onChange: () => void }) {
  const [sibuk, setSibuk] = useState(false);
  const [status, setStatus] = useState<{ type: 'info' | 'error'; text: string } | null>(null);
  const { dokumen, laporan } = workspace;
  async function generate() {
    setSibuk(true); setStatus(null);
    try {
      const { blob, filename } = await generateAccreditationDocument(laporan.id, dokumen);
      simpanBlob(blob, filename);
      setStatus({ type: 'info', text: `${filename} diunduh dan tersimpan di riwayat laporan ini.` });
      onChange();
    } catch (e) { setStatus({ type: 'error', text: pesan(e, 'Dokumen gagal dibuat.') }); }
    finally { setSibuk(false); }
  }
  async function unduhUlang(id: number) {
    try { const { blob, filename } = await downloadLaporanWord(laporan.id, id); simpanBlob(blob, filename); }
    catch (e) { setStatus({ type: 'error', text: pesan(e, 'Dokumen gagal diunduh.') }); }
  }
  return <section className="section requirement-section">
    <p className="section-kicker">Dokumen Word</p>
    <h2>Generate {laporan.nama}</h2>
    <p className="section-note">Satu dokumen .docx: cover dengan kelengkapan per status sumber, to-do item yang belum lengkap, lalu isi per {dokumen === 'LED' ? 'Kriteria (ditutup ringkasan tabel LKPS terkait)' : 'Bagian'}. Isi tiap item memakai isian tim dan hasil ekstraksi yang sudah masuk tabel; kalau belum ada, data live dari sumber resmi. Item tanpa keduanya tetap dibuat dengan penanda <b>[DATA TIDAK TERSEDIA]</b> (sumber belum bisa diakses, disertai catatannya) atau <b>[NARASI PERLU DISUSUN TIM PENYUSUN PRODI]</b>.</p>
    <div className="action-row"><button className="button" disabled={sibuk} onClick={generate}>{sibuk ? 'Membuat dokumen…' : `Generate & unduh ${laporan.nama} (Word)`}</button></div>
    {status && <Notice type={status.type}>{status.text}</Notice>}
    {workspace.riwayat_word.length > 0 && <div className="riwayat-word">
      <h3>Riwayat Word laporan ini</h3>
      <ul>{workspace.riwayat_word.map(r => <li key={r.id}>
        <span>{waktu(r.waktu)} · oleh {r.oleh}</span>
        <button className="link-button" onClick={() => unduhUlang(r.id)}>Unduh</button>
      </li>)}</ul>
    </div>}
  </section>;
}

/** Riwayat laporan prodi + dokumen: lanjutkan draft, hapus, atau buat laporan baru; dibuka dengan PIN prodi. */
function PilihLaporan({ prodi, dokumen, tahunTarget, laporanTarget, onPilih }: { prodi: string; dokumen: Dokumen; tahunTarget: number | null; laporanTarget: number | null; onPilih: (id: number) => void }) {
  const [data, setData] = useState<DaftarLaporan | null>(null);
  const [galat, setGalat] = useState('');
  const [pesanInfo, setPesanInfo] = useState('');
  const [sibuk, setSibuk] = useState(false);
  const [pin, setPin] = useState('');
  const [pin2, setPin2] = useState('');
  const [alasan, setAlasan] = useState('');
  const [modeReset, setModeReset] = useState(false);
  const [hapusId, setHapusId] = useState<number | null>(null);
  const [tahun, setTahun] = useState(String(new Date().getFullYear()));
  const [nama, setNama] = useState('');
  const permintaan = useRef(0);

  const muat = useCallback(async () => {
    const id = ++permintaan.current;
    try { const d = await getDaftarLaporan(prodi, dokumen); if (id === permintaan.current) { setData(d); setGalat(''); } }
    catch (e) { if (id === permintaan.current) setGalat(pesan(e, 'Daftar laporan gagal dimuat.')); }
  }, [prodi, dokumen]);
  useEffect(() => { setData(null); setPin(''); setPin2(''); setModeReset(false); setHapusId(null); setPesanInfo(''); muat(); }, [muat]);
  useEffect(() => {
    if (!data?.terbuka) return;
    const cocok = data.laporan.find(l => (laporanTarget != null ? l.id === laporanTarget : l.tahun === tahunTarget));
    if (cocok && (laporanTarget != null || tahunTarget != null)) onPilih(cocok.id);
  }, [data, tahunTarget, laporanTarget]); // eslint-disable-line react-hooks/exhaustive-deps
  const namaTarget = data?.laporan.find(l => l.id === laporanTarget)?.nama;

  async function jalankan(aksi: () => Promise<unknown>, sukses?: string) {
    setSibuk(true); setGalat(''); setPesanInfo('');
    try { await aksi(); if (sukses) setPesanInfo(sukses); setPin(''); setPin2(''); await muat(); }
    catch (e) { setGalat(pesan(e, 'Permintaan gagal.')); }
    finally { setSibuk(false); }
  }
  const syarat = syaratPin(pin, pin2);

  if (!data) return galat ? <Notice type="error">{galat}</Notice> : <div className="loading" role="status">Memuat riwayat laporan…</div>;
  return <section className="section requirement-section pilih-laporan" aria-labelledby="pilih-laporan-judul">
    <div className="section-title-row">
      <div><p className="section-kicker">Riwayat laporan · {data.prodi.nama}</p><h2 id="pilih-laporan-judul">Laporan {dokumen}</h2></div>
      <span className={`status-pill ${data.terbuka ? '' : 'is-locked'}`}>{!data.terkunci ? 'Belum ada PIN prodi' : data.terbuka ? 'Terbuka untuk sesi ini' : 'Terkunci'}</span>
    </div>
    <p className="section-note">Semua staf prodi mengerjakan laporan yang sama. Pilih laporan untuk melanjutkan draft, atau buat laporan tahun baru. Isi laporan hanya bisa dibuka dengan PIN prodi, dan PIN diminta lagi setiap kali login.</p>
    {namaTarget && !data.terbuka && <Notice type="info">Masukkan PIN prodi di bawah untuk melanjutkan <b>{namaTarget}</b>; laporan akan langsung terbuka.</Notice>}

    {data.laporan.length === 0
      ? <p className="chart-empty">Belum ada laporan {dokumen} untuk prodi ini.</p>
      : <ul className="laporan-list">{data.laporan.map(l => <li key={l.id} className="laporan-list__item">
        <div className="laporan-list__info">
          <strong>{l.nama}</strong>
          <span>{l.terakhir_diubah ? `Terakhir diubah ${waktu(l.terakhir_diubah)} oleh ${l.terakhir_oleh ?? '-'}` : 'Belum ada isian'}{l.dibuat_oleh ? ` · dibuat oleh ${l.dibuat_oleh}` : ''}</span>
          <ProgressLine value={l.lengkap} total={l.total} percent={l.persen} />
        </div>
        <div className="laporan-list__aksi">
          <button className="button" disabled={!data.terbuka} onClick={() => onPilih(l.id)} title={data.terbuka ? undefined : 'Masukkan PIN prodi dulu'}>{data.terbuka ? 'Lanjutkan' : data.terkunci ? 'Terkunci' : 'Buat PIN dulu'}</button>
          {data.terbuka && <button className="button button--danger" onClick={() => setHapusId(l.id)} aria-expanded={hapusId === l.id}>Hapus</button>}
        </div>
        {hapusId === l.id && <div className="admin-confirm laporan-list__konfirmasi" role="alertdialog" aria-label={`Hapus ${l.nama}`}>
          <p>Hapus <b>{l.nama}</b> secara permanen? Semua isian ({l.lengkap} item terisi), file upload, riwayat ekstraksi, dan riwayat Word laporan ini ikut terhapus untuk semua staf prodi, dan tidak bisa dibatalkan.</p>
          <button className="button button--danger" disabled={sibuk} onClick={() => jalankan(async () => { const r = await hapusLaporan(l.id); setHapusId(null); setPesanInfo(r.message); })}>{sibuk ? 'Menghapus…' : 'Ya, hapus laporan'}</button>
          <button className="button secondary" onClick={() => setHapusId(null)}>Batal</button>
        </div>}
      </li>)}</ul>}

    {galat && <Notice type="error">{galat}</Notice>}
    {pesanInfo && <Notice type="info">{pesanInfo}</Notice>}

    {!data.terkunci && <form className="laporan-form" onSubmit={e => { e.preventDefault(); if (!syarat) jalankan(() => buatPinProdi(prodi, pin), 'PIN prodi dibuat. Bagikan ke staf prodi yang ikut menyusun laporan.'); }}>
      <h3>Buat PIN prodi</h3>
      <p className="section-note">Prodi ini belum punya PIN. PIN ({PIN_MIN}–{PIN_MAX} angka) mengunci semua laporan prodi (LED dan LKPS, tahun berapa pun). Bagikan hanya ke staf prodi yang ikut menyusun.</p>
      <div className="laporan-form__fields">
        <KolomPin id="pin-baru" label={`PIN prodi (${PIN_MIN}–${PIN_MAX} angka)`} value={pin} onChange={setPin} baru />
        <KolomPin id="pin-baru-2" label="Ulangi PIN" value={pin2} onChange={setPin2} baru />
      </div>
      {syarat && <p className="field-hint" aria-live="polite">{syarat}</p>}
      <button className="button" type="submit" disabled={sibuk || Boolean(syarat)}>{sibuk ? 'Menyimpan…' : 'Buat PIN'}</button>
    </form>}

    {data.terkunci && !data.terbuka && !modeReset && <form className="laporan-form" onSubmit={e => { e.preventDefault(); if (pinValid(pin)) jalankan(() => bukaProdi(prodi, pin)); }}>
      <h3>Buka laporan prodi</h3>
      <div className="laporan-form__fields"><KolomPin id="pin-buka" label="PIN prodi" value={pin} onChange={setPin} /></div>
      {pin && !pinValid(pin) && <p className="field-hint" aria-live="polite">PIN terdiri dari {PIN_MIN}–{PIN_MAX} angka.</p>}
      <div className="action-row">
        <button className="button" type="submit" disabled={sibuk || !pinValid(pin)}>{sibuk ? 'Memeriksa…' : 'Buka'}</button>
        <button className="link-button" type="button" onClick={() => { setModeReset(true); setGalat(''); setPin(''); }}>Lupa PIN?</button>
      </div>
      {data.reset_menunggu && <p className="field-hint">Pengajuan reset PIN Anda sedang menunggu persetujuan admin.</p>}
    </form>}

    {data.terkunci && !data.terbuka && modeReset && <form className="laporan-form" onSubmit={e => { e.preventDefault(); if (!syarat) jalankan(async () => { await ajukanResetPin(prodi, pin, alasan); setModeReset(false); setAlasan(''); }, 'Pengajuan terkirim. PIN baru berlaku setelah disetujui admin.'); }}>
      <h3>Ajukan reset PIN prodi</h3>
      <p className="section-note">Tentukan PIN baru. PIN lama tetap berlaku sampai admin menyetujui pengajuan ini; setelah disetujui, semua staf memakai PIN baru.</p>
      <div className="laporan-form__fields">
        <KolomPin id="pin-reset" label={`PIN baru (${PIN_MIN}–${PIN_MAX} angka)`} value={pin} onChange={setPin} baru />
        <KolomPin id="pin-reset-2" label="Ulangi PIN baru" value={pin2} onChange={setPin2} baru />
        <div className="field laporan-form__wide"><label htmlFor="pin-alasan">Alasan (opsional)</label><input id="pin-alasan" maxLength={500} value={alasan} onChange={e => setAlasan(e.target.value)} placeholder="mis. staf yang memegang PIN sudah pindah tugas" /></div>
      </div>
      {syarat && <p className="field-hint" aria-live="polite">{syarat}</p>}
      <div className="action-row">
        <button className="button" type="submit" disabled={sibuk || Boolean(syarat)}>{sibuk ? 'Mengirim…' : 'Kirim pengajuan'}</button>
        <button className="link-button" type="button" onClick={() => { setModeReset(false); setPin(''); setPin2(''); }}>Batal</button>
      </div>
    </form>}

    {data.terbuka && <form className="laporan-form" onSubmit={e => { e.preventDefault(); jalankan(async () => { const baru = await buatLaporan(prodi, dokumen, Number(tahun), nama); setNama(''); onPilih(baru.id); }); }}>
      <h3>Buat laporan baru</h3>
      <div className="laporan-form__fields">
        <div className="field"><label htmlFor="lap-tahun">Tahun laporan</label><input id="lap-tahun" type="number" inputMode="numeric" min={2000} max={2100} value={tahun} onChange={e => setTahun(e.target.value)} /></div>
        <div className="field laporan-form__wide"><label htmlFor="lap-nama">Nama laporan (opsional)</label><input id="lap-nama" maxLength={150} value={nama} onChange={e => setNama(e.target.value)} placeholder={`${dokumen} ${tahun}`} /></div>
      </div>
      <button className="button" type="submit" disabled={sibuk || !/^\d{4}$/.test(tahun)}>{sibuk ? 'Membuat…' : 'Buat laporan'}</button>
    </form>}
  </section>;
}
