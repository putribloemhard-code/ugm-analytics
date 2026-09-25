import { useEffect, useRef, useState } from 'react';

import { batalkanTema, getBeritaTanpaTema, tandaiTema, type BeritaTanpaTema, type PemetaanKepmen, type PemetaanTema } from './lib/api';
import { Notice } from './ui';

const fmt = (n: number) => n.toLocaleString('id-ID');
const DAMPAK = ['Sosial', 'Ekonomi', 'Lingkungan'];
const HALAMAN = 5;

/* ------------------------------------------------------- pemetaan Kepmen ---- */
/** Pemetaan resmi 14 tema: terlipat sampai dibuka, lalu bisa disaring per dampak. */
export function PemetaanKepmenPanel({ data, mode }: { data: PemetaanKepmen; mode: string }) {
  // Bagian Dampak dan Dampak × SDGs tampil di halaman yang sama: id elemen diberi akhiran mode.
  const idJudul = `pemetaan-judul-${mode}`, idIsi = `pemetaan-isi-${mode}`;
  const [buka, setBuka] = useState(false);
  const [dampak, setDampak] = useState('');
  const tampil = data.rows.filter(r => !dampak || r.dampak === dampak);
  const jumlah = (d: string) => data.rows.filter(r => r.dampak === d).length;
  return <section className="story-block pemetaan" aria-labelledby={idJudul}>
    <div className="pemetaan__head">
      <div>
        <h3 id={idJudul}>Pemetaan resmi + indikator Kepmen ({data.rows.length} tema)</h3>
        <p className="section-note">Tema, klaster SDG, indikator, definisi, kriteria, formula, dan satuan resmi tiap tema.</p>
      </div>
      <button type="button" className="button secondary" aria-expanded={buka} aria-controls={idIsi} onClick={() => setBuka(b => !b)}>
        {buka ? 'Sembunyikan' : 'Tampilkan pemetaan'}
      </button>
    </div>
    {buka && <div id={idIsi}>
      <div className="pemetaan__filter" role="group" aria-label="Saring menurut dampak">
        <button type="button" aria-pressed={!dampak} className={!dampak ? 'is-on' : ''} onClick={() => setDampak('')}>Semua ({data.rows.length})</button>
        {DAMPAK.filter(d => jumlah(d)).map(d => <button key={d} type="button" aria-pressed={dampak === d}
          className={`pemetaan__chip--${d.toLowerCase()} ${dampak === d ? 'is-on' : ''}`} onClick={() => setDampak(d)}>{d} ({jumlah(d)})</button>)}
      </div>
      <ol className="pemetaan__list">{tampil.map(r => <KartuTema key={r.id} r={r} />)}</ol>
      <p className="chart-note">{data.note}</p>
    </div>}
  </section>;
}

function KartuTema({ r }: { r: PemetaanTema }) {
  return <li className="pemetaan__item">
    <div className="pemetaan__item-head">
      <span className={`pillar-tag pillar-tag--${r.dampak.toLowerCase()}`}>{r.dampak}</span>
      <h4>{r.tema_kepmen}</h4>
      {r.tema !== r.tema_kepmen && <span className="pemetaan__alias">di dashboard: {r.tema}</span>}
    </div>
    <p className="pemetaan__indikator"><b>Indikator:</b> {r.indikator}</p>
    <dl className="pemetaan__meta">
      <div><dt>Satuan</dt><dd>{r.satuan || '-'}</dd></div>
      <div><dt>Klaster SDG</dt><dd>{r.sdg}</dd></div>
    </dl>
    <details className="pemetaan__detail">
      <summary>Definisi, kriteria, dan formula</summary>
      <dl>
        <div><dt>Definisi</dt><dd>{r.definisi || '-'}</dd></div>
        <div><dt>Kriteria</dt><dd>{r.kriteria || '-'}</dd></div>
        <div><dt>Formula</dt><dd>{r.formula || '-'}</dd></div>
      </dl>
    </details>
  </li>;
}

/* --------------------------------------------------------- tag tema manual ---- */
type Filter = { year_from?: string; year_to?: string; units?: string[] };

function BarisTag({ row, tema, mode, onSimpan }: { row: BeritaTanpaTema; tema: PemetaanTema[]; mode: string; onSimpan: (row: BeritaTanpaTema, topiks: string[]) => Promise<void> }) {
  const [pilih, setPilih] = useState<string[]>([]);
  const [sibuk, setSibuk] = useState(false);
  // Pilihan 14 tema hanya dibuka untuk baris yang sedang ditandai, supaya daftar tetap ringkas.
  const [buka, setBuka] = useState(false);
  const toggle = (id: string) => setPilih(p => (p.includes(id) ? p.filter(x => x !== id) : [...p, id]));
  const kunci = `tema-tag-${mode}-${row.url.replace(/[^a-z0-9]/gi, '').slice(-24)}`;
  const nama = (id: string) => tema.find(t => t.id === id)?.tema ?? id;
  return <li className={`tema-tag__row ${buka ? 'is-open' : ''}`}>
    <div className="sdg-tag__news">
      <span className="sdg-tag__date">{row.tanggal || 'tanpa tanggal'}</span>
      {row.tautan ? <a className="table-link" href={row.tautan} target="_blank" rel="noopener noreferrer">{row.judul || row.url}<span className="sr-only"> (buka di tab baru)</span></a> : <span>{row.judul || row.url}</span>}
      {row.deskripsi && <span className="tema-tag__desc">{row.deskripsi}</span>}
    </div>
    {!buka && <button type="button" className="button secondary tema-tag__buka" aria-expanded={false} onClick={() => setBuka(true)}>Tandai tema</button>}
    {buka && <><div className="tema-tag__pick" role="group" aria-labelledby={`${kunci}-label`}>
      <span id={`${kunci}-label`} className="sr-only">Pilih tema untuk: {row.judul || row.url}</span>
      {DAMPAK.map(d => <div key={d} className="tema-tag__grup">
        <span className={`tema-tag__pilar pillar-tag pillar-tag--${d.toLowerCase()}`}>{d}</span>
        <div className="tema-tag__opsi">{tema.filter(t => t.dampak === d).map(t => <button key={t.id} type="button" aria-pressed={pilih.includes(t.id)}
          className={pilih.includes(t.id) ? 'is-on' : ''} title={t.tema_kepmen} onClick={() => toggle(t.id)}>{t.tema}</button>)}</div>
      </div>)}
    </div>
    <div className="tema-tag__aksi">
      <button type="button" className="button sdg-tag__save" disabled={!pilih.length || sibuk}
        onClick={async () => { setSibuk(true); try { await onSimpan(row, pilih); } finally { setSibuk(false); } }}>
        {sibuk ? 'Menyimpan…' : pilih.length ? `Simpan ${pilih.length} tema` : 'Pilih tema dulu'}
      </button>
      <button type="button" className="link-button" onClick={() => { setBuka(false); setPilih([]); }}>Batal</button>
      {pilih.length > 0 && <span className="field-hint">{pilih.map(nama).join(', ')}</span>}
    </div></>}
  </li>;
}

/** Berita tanpa match tema: 5 per halaman, bisa dicari, ditandai tema langsung, tersimpan ke basis data. */
export function TagTemaManual({ tema, filter, mode, onChanged }: { tema: PemetaanTema[]; filter: Filter; mode: string; onChanged: () => void }) {
  const idJudul = `tema-tag-title-${mode}`, idCari = `tema-tag-cari-${mode}`;
  const [q, setQ] = useState('');
  const [cari, setCari] = useState('');
  const [page, setPage] = useState(1);
  const [hasil, setHasil] = useState<{ total: number; rows: BeritaTanpaTema[] } | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [terakhir, setTerakhir] = useState<BeritaTanpaTema | null>(null);
  const [pesan, setPesan] = useState<{ type: 'info' | 'error'; text: string } | null>(null);
  const [muatUlang, setMuatUlang] = useState(0);
  const permintaan = useRef(0);
  const filterKey = JSON.stringify(filter);

  useEffect(() => { const t = window.setTimeout(() => { setCari(q.trim()); setPage(1); }, 300); return () => window.clearTimeout(t); }, [q]);
  useEffect(() => { setPage(1); }, [filterKey]);
  useEffect(() => {
    const id = ++permintaan.current;
    setLoading(true); setError('');
    getBeritaTanpaTema({ page, page_size: HALAMAN, q: cari, ...filter })
      .then(r => { if (id === permintaan.current) setHasil(r); })
      .catch(e => { if (id === permintaan.current) setError(e instanceof Error ? e.message : 'Daftar berita gagal dimuat.'); })
      .finally(() => { if (id === permintaan.current) setLoading(false); });
  }, [cari, page, filterKey, muatUlang]); // eslint-disable-line react-hooks/exhaustive-deps

  async function simpan(row: BeritaTanpaTema, topiks: string[]) {
    setPesan(null);
    try {
      const r = await tandaiTema(row.url, topiks);
      setTerakhir(row);
      setPesan({ type: 'info', text: `“${row.judul || row.url}”: ${r.message.charAt(0).toLowerCase()}${r.message.slice(1)}` });
      setMuatUlang(n => n + 1); onChanged();
    } catch (e) { setPesan({ type: 'error', text: e instanceof Error ? e.message : 'Gagal menyimpan tema.' }); }
  }
  async function batalkan() {
    if (!terakhir) return;
    try {
      await batalkanTema(terakhir.url);
      setPesan({ type: 'info', text: `Tag tema untuk “${terakhir.judul || terakhir.url}” dibatalkan.` });
      setTerakhir(null); setMuatUlang(n => n + 1); onChanged();
    } catch (e) { setPesan({ type: 'error', text: e instanceof Error ? e.message : 'Gagal membatalkan tag.' }); }
  }

  const jumlahHalaman = hasil ? Math.max(1, Math.ceil(hasil.total / HALAMAN)) : 1;
  return <section className="story-block sdg-tag tema-tag" aria-labelledby={idJudul}>
    <h3 id={idJudul}>Berita tanpa match tema (cek manual)</h3>
    <p className="section-note">Berita yang tidak memuat keyword tema Kepmen mana pun. Buka beritanya, pilih tema yang sesuai, lalu simpan: tag tersimpan di basis data (tabel terpisah dari tag otomatis) dan langsung ikut dihitung di angka dampak, termasuk klaster SDG temanya di Dampak × SDGs.</p>
    <div className="field sdg-tag__search">
      <label htmlFor={idCari}>Cari judul atau URL</label>
      <input id={idCari} type="search" value={q} maxLength={100} placeholder="mis. seminar, kerja sama" onChange={e => setQ(e.target.value)} />
    </div>
    {pesan && <div className="sdg-tag__msg"><Notice type={pesan.type}>{pesan.text}{pesan.type === 'info' && terakhir && <> <button type="button" className="link-button" onClick={batalkan}>Batalkan</button></>}</Notice></div>}
    {error
      ? <Notice type="error">{error}</Notice>
      : !hasil
        ? <div className="loading" role="status">Memuat berita tanpa tema…</div>
        : hasil.rows.length === 0
          ? <p className="chart-empty">{cari ? `Tidak ada berita tanpa tema yang memuat “${cari}”.` : 'Semua berita dalam filter ini sudah bertema.'}</p>
          : <ol className={`sdg-tag__list ${loading ? 'is-busy' : ''}`} aria-busy={loading}>{hasil.rows.map(row => <BarisTag key={row.url} row={row} tema={tema} mode={mode} onSimpan={simpan} />)}</ol>}
    {hasil && hasil.total > 0 && <div className="table-pager">
      <button type="button" className="link-button" disabled={page <= 1 || loading} onClick={() => setPage(p => p - 1)}>‹ Sebelumnya</button>
      <span className="table-pager__info" aria-live="polite">{fmt(hasil.total)} berita · halaman {fmt(Math.min(page, jumlahHalaman))} dari {fmt(jumlahHalaman)}</span>
      <button type="button" className="link-button" disabled={page >= jumlahHalaman || loading} onClick={() => setPage(p => p + 1)}>Berikutnya ›</button>
    </div>}
  </section>;
}
