import { useEffect, useRef, useState } from 'react';

import { batalkanSdg, getBeritaTanpaSdg, tandaiSdg, type BeritaTanpaSdg, type SdgPeta } from './lib/api';
import { downloadCsv } from './story';
import { Notice } from './ui';

const fmt = (n: number) => n.toLocaleString('id-ID');
const SDG = Array.from({ length: 17 }, (_, i) => i + 1);

/* ------------------------------------------------------------ peta sebaran ---- */
/** 17 petak SDG di posisi tetap (urut 1-17). Pekat petak = jumlah berita bertanda SDG itu
 *  (satu hue, sequential); kepekatan dibatasi 6-34% supaya teks tetap terbaca di kedua tema.
 *  Tiap petak: keyword teratas + jumlah beritanya; semua keyword bisa dibuka. */
export function SdgPetaView({ peta }: { peta: SdgPeta }) {
  const [buka, setBuka] = useState<number | null>(null);
  const maks = Math.max(1, ...peta.tiles.map(t => t.jumlah));
  function unduh() {
    const rows = peta.tiles.flatMap(t => t.keywords.map(k => ({ sdg: `SDG ${t.sdg}`, nama: t.nama, keyword: k.keyword, jumlah: k.jumlah ?? '' })));
    downloadCsv('keyword_per_sdg.csv', [{ key: 'sdg', label: 'SDG' }, { key: 'nama', label: 'Nama' }, { key: 'keyword', label: 'Keyword' }, { key: 'jumlah', label: 'Jumlah berita' }], rows);
  }
  return <section className="story-block sdg-map" aria-labelledby="sdg-map-title">
    <div className="sdg-map__head">
      <div>
        <h3 id="sdg-map-title">Peta sebaran keyword SDG</h3>
        <p className="section-note">Keyword yang menjadi dasar pencocokan tiap SDG, dengan jumlah berita yang memuatnya.</p>
      </div>
      <div className="sdg-map__legend" aria-hidden="true"><span>Sedikit berita</span><i /><span>Banyak berita</span></div>
    </div>
    {!peta.ada_jumlah_keyword && <Notice type="info">Jumlah per keyword belum dihitung. Jalankan <code>scripts/hitung_keyword_sdg.py</code> di folder berita-dampak, lalu muat ulang.</Notice>}
    <ol className="sdg-map__grid">
      {peta.tiles.map(t => {
        const kekuatan = Math.round(6 + 28 * (t.jumlah / maks));
        const puncak = Math.max(1, ...t.keywords.map(k => k.jumlah ?? 0));
        const terbuka = buka === t.sdg;
        return <li key={t.sdg} className={`sdg-tile ${terbuka ? 'is-open' : ''}`} style={{ ['--kekuatan' as string]: `${kekuatan}%` }}>
          <div className="sdg-tile__head">
            <span className="sdg-tile__no">SDG {t.sdg}</span>
            <span className="sdg-tile__total">{fmt(t.jumlah)} <small>berita</small></span>
          </div>
          <p className="sdg-tile__name">{t.nama}</p>
          <ul className="sdg-tile__kw">
            {(terbuka ? t.keywords : t.keywords.slice(0, 4)).map(k => <li key={k.keyword} title={k.jumlah == null ? k.keyword : `${k.keyword}: ${fmt(k.jumlah)} berita`}>
              <span className="sdg-tile__kw-name">{k.keyword}</span>
              <span className="sdg-tile__kw-value">{k.jumlah == null ? '' : fmt(k.jumlah)}</span>
              {k.jumlah != null && <span className="sdg-tile__kw-bar" aria-hidden="true"><span style={{ width: `${(100 * k.jumlah) / puncak}%` }} /></span>}
            </li>)}
          </ul>
          <button type="button" className="link-button sdg-tile__more" aria-expanded={terbuka} onClick={() => setBuka(terbuka ? null : t.sdg)}>
            {terbuka ? 'Ringkas' : `Lihat semua ${t.keywords.length} keyword`}
          </button>
        </li>;
      })}
    </ol>
    <p className="chart-note">{peta.catatan}</p>
    <div className="chart-frame__actions"><button type="button" className="link-button" onClick={unduh}>Unduh CSV keyword</button></div>
  </section>;
}

/* ------------------------------------------------------- tag SDG manual ---- */
type Filter = { year_from?: string; year_to?: string; units?: string[] };

function BarisTag({ row, onSimpan }: { row: BeritaTanpaSdg; onSimpan: (row: BeritaTanpaSdg, sdgs: number[]) => Promise<void> }) {
  const [pilih, setPilih] = useState<number[]>([]);
  const [sibuk, setSibuk] = useState(false);
  const toggle = (n: number) => setPilih(p => (p.includes(n) ? p.filter(x => x !== n) : [...p, n].sort((a, b) => a - b)));
  const id = `sdg-tag-${row.url.replace(/[^a-z0-9]/gi, '').slice(-24)}`;
  return <li className="sdg-tag__row">
    <div className="sdg-tag__news">
      <span className="sdg-tag__date">{row.tanggal || 'tanpa tanggal'}</span>
      {row.tautan ? <a className="table-link" href={row.tautan} target="_blank" rel="noopener noreferrer">{row.judul || row.url}<span className="sr-only"> (buka di tab baru)</span></a> : <span>{row.judul || row.url}</span>}
      {row.judul && <span className="sdg-tag__url">{row.url}</span>}
    </div>
    <div className="sdg-tag__pick" role="group" aria-labelledby={`${id}-label`}>
      <span id={`${id}-label`} className="sr-only">Pilih SDG untuk: {row.judul || row.url}</span>
      {SDG.map(n => <button key={n} type="button" aria-label={`SDG ${n}`} aria-pressed={pilih.includes(n)} className={pilih.includes(n) ? 'is-on' : ''} onClick={() => toggle(n)}>{n}</button>)}
    </div>
    <button type="button" className="button sdg-tag__save" disabled={!pilih.length || sibuk}
      onClick={async () => { setSibuk(true); try { await onSimpan(row, pilih); } finally { setSibuk(false); } }}>
      {sibuk ? 'Menyimpan…' : pilih.length ? `Simpan SDG ${pilih.join(', ')}` : 'Pilih SDG dulu'}
    </button>
  </li>;
}

export function TagSdgManual({ filter, onChanged }: { filter: Filter; onChanged: () => void }) {
  const [q, setQ] = useState('');
  const [cari, setCari] = useState('');
  const [page, setPage] = useState(1);
  const [hasil, setHasil] = useState<{ total: number; rows: BeritaTanpaSdg[] } | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [terakhir, setTerakhir] = useState<{ row: BeritaTanpaSdg; sdgs: number[] } | null>(null);
  const [pesan, setPesan] = useState<{ type: 'info' | 'error'; text: string } | null>(null);
  const [muatUlang, setMuatUlang] = useState(0);
  const permintaan = useRef(0);
  const filterKey = JSON.stringify(filter);

  useEffect(() => { const t = window.setTimeout(() => { setCari(q.trim()); setPage(1); }, 300); return () => window.clearTimeout(t); }, [q]);
  useEffect(() => { setPage(1); }, [filterKey]);
  useEffect(() => {
    const id = ++permintaan.current;
    setLoading(true); setError('');
    getBeritaTanpaSdg({ page, page_size: 5, q: cari, ...filter })
      .then(r => { if (id === permintaan.current) setHasil(r); })
      .catch(e => { if (id === permintaan.current) setError(e instanceof Error ? e.message : 'Daftar berita gagal dimuat.'); })
      .finally(() => { if (id === permintaan.current) setLoading(false); });
  }, [cari, page, filterKey, muatUlang]); // eslint-disable-line react-hooks/exhaustive-deps

  async function simpan(row: BeritaTanpaSdg, sdgs: number[]) {
    setPesan(null);
    try {
      const r = await tandaiSdg(row.url, sdgs);
      setTerakhir({ row, sdgs: r.sdgs });
      setPesan({ type: 'info', text: `“${row.judul || row.url}” ${r.message.charAt(0).toLowerCase()}${r.message.slice(1)}` });
      setMuatUlang(n => n + 1); onChanged();
    } catch (e) { setPesan({ type: 'error', text: e instanceof Error ? e.message : 'Gagal menyimpan tag.' }); }
  }
  async function batalkan() {
    if (!terakhir) return;
    try {
      await batalkanSdg(terakhir.row.url);
      setPesan({ type: 'info', text: `Tag SDG untuk “${terakhir.row.judul || terakhir.row.url}” dibatalkan.` });
      setTerakhir(null); setMuatUlang(n => n + 1); onChanged();
    } catch (e) { setPesan({ type: 'error', text: e instanceof Error ? e.message : 'Gagal membatalkan tag.' }); }
  }

  const jumlahHalaman = hasil ? Math.max(1, Math.ceil(hasil.total / 5)) : 1;
  return <section className="story-block sdg-tag" aria-labelledby="sdg-tag-title">
    <h3 id="sdg-tag-title">Berita tanpa tanda SDG (cek manual)</h3>
    <p className="section-note">Berita yang tidak memuat keyword SDG mana pun. Buka beritanya, pilih SDG yang sesuai, lalu simpan: tag tersimpan di basis data (tabel terpisah dari tag otomatis) dan langsung ikut dihitung di angka SDG di atas.</p>
    <div className="field sdg-tag__search">
      <label htmlFor="sdg-tag-cari">Cari judul atau URL</label>
      <input id="sdg-tag-cari" type="search" value={q} maxLength={100} placeholder="mis. wisuda, seminar" onChange={e => setQ(e.target.value)} />
    </div>
    {pesan && <div className="sdg-tag__msg"><Notice type={pesan.type}>{pesan.text}{pesan.type === 'info' && terakhir && <> <button type="button" className="link-button" onClick={batalkan}>Batalkan</button></>}</Notice></div>}
    {error
      ? <Notice type="error">{error}</Notice>
      : !hasil
        ? <div className="loading" role="status">Memuat berita tanpa tanda SDG…</div>
        : hasil.rows.length === 0
          ? <p className="chart-empty">{cari ? `Tidak ada berita tanpa tanda SDG yang memuat “${cari}”.` : 'Semua berita dalam filter ini sudah bertanda SDG.'}</p>
          : <ol className={`sdg-tag__list ${loading ? 'is-busy' : ''}`} aria-busy={loading}>{hasil.rows.map(row => <BarisTag key={row.url} row={row} onSimpan={simpan} />)}</ol>}
    {hasil && hasil.total > 0 && <div className="table-pager">
      <button type="button" className="link-button" disabled={page <= 1 || loading} onClick={() => setPage(p => p - 1)}>‹ Sebelumnya</button>
      <span className="table-pager__info" aria-live="polite">{fmt(hasil.total)} berita · halaman {fmt(Math.min(page, jumlahHalaman))} dari {fmt(jumlahHalaman)}</span>
      <button type="button" className="link-button" disabled={page >= jumlahHalaman || loading} onClick={() => setPage(p => p + 1)}>Berikutnya ›</button>
    </div>}
  </section>;
}
