import { useEffect, useRef, useState } from 'react';

import { getBeritaDampak, getSumber, type BeritaDampak, type JumlahPilar, type SumberData } from './lib/api';
import { Notice } from './ui';

/* Bagian "Sumber": menelusuri asal setiap angka, dari situs sumber sampai pecahan per dampak.
   Tiap jalur dibaca kiri ke kanan (HP: atas ke bawah): sumber -> cincin "diambil vs memuat
   konten dampak" -> tiga cincin per dampak.
   - Cincin utama = meter satu rasio (lingkaran penuh = diambil, busur emas = memuat konten dampak).
     Emas hanya dipakai di sini (satu aksen: angka yang dipakai laporan).
   - Per dampak sengaja TIGA cincin terpisah, bukan satu pie: satu berita bisa masuk >1 dampak,
     jadi jumlahnya > 100% dan irisan pie akan berbohong.
   - Warna pilar = slot 1-3 palet kategori mode gelap (#d95926, #3987e5, #199e70), tervalidasi
     all-pairs di kedua latar navy; teks angka tetap putih, identitas dari label yang tertulis. */

const fmt = (n: number) => n.toLocaleString('id-ID');
const persen = (bagian: number, total: number) => (total ? (100 * bagian) / total : 0);
const fmtPersen = (p: number) => `${p.toLocaleString('id-ID', { maximumFractionDigits: 1 })}%`;
const PILAR_KELAS: Record<string, string> = { Sosial: 'sosial', Ekonomi: 'ekonomi', Lingkungan: 'lingkungan' };

/** Cincin meter SVG: lintasan penuh + busur sepanjang `nilai/total`, mulai dari jam 12 searah jarum jam. */
function Cincin({ nilai, total, tebal, kelas, judul, children }: { nilai: number; total: number; tebal: number; kelas: string; judul: string; children: React.ReactNode }) {
  const r = 50 - tebal / 2 - 1;
  const keliling = 2 * Math.PI * r;
  const panjang = (Math.min(100, persen(nilai, total)) / 100) * keliling;
  return <div className={`ring ${kelas}`} role="img" aria-label={judul}>
    <svg viewBox="0 0 100 100" aria-hidden="true" focusable="false">
      <circle className="ring__track" cx="50" cy="50" r={r} strokeWidth={tebal} />
      <circle className="ring__arc" cx="50" cy="50" r={r} strokeWidth={tebal}
        strokeDasharray={`${panjang} ${keliling}`} transform="rotate(-90 50 50)"><title>{judul}</title></circle>
    </svg>
    <div className="ring__center">{children}</div>
  </div>;
}

function RasioDampak({ diambil, berdampak, satuan, label }: { diambil: number; berdampak: number; satuan: string; label: string }) {
  const p = persen(berdampak, diambil);
  return <div className="lineage__ratio">
    <Cincin nilai={berdampak} total={diambil} tebal={11} kelas="ring--hero"
      judul={`${fmt(berdampak)} dari ${fmt(diambil)} ${satuan} (${fmtPersen(p)}) memuat konten dampak`}>
      <strong>{fmtPersen(p)}</strong>
      <span>memuat konten dampak</span>
    </Cincin>
    <dl className="ring-legend">
      <div><dt><i className="ring-key ring-key--total" aria-hidden="true" />{label}</dt><dd>{fmt(diambil)} <small>{satuan}</small></dd></div>
      <div><dt><i className="ring-key ring-key--impact" aria-hidden="true" />Memuat konten dampak</dt><dd>{fmt(berdampak)} <small>{satuan}</small></dd></div>
      <div className="ring-legend__rest"><dt><i className="ring-key ring-key--rest" aria-hidden="true" />Belum memuat dampak</dt><dd>{fmt(diambil - berdampak)}</dd></div>
    </dl>
  </div>;
}

function PerDampak({ data, dari, satuan, catatan }: { data: JumlahPilar[]; dari: number; satuan: string; catatan: string }) {
  return <div className="lineage__pillars">
    <p className="lineage__stage-label">Per dampak <span>(dari yang memuat konten dampak)</span></p>
    <ul>
      {data.map(d => {
        const p = persen(d.jumlah, dari);
        return <li key={d.pilar}>
          <Cincin nilai={d.jumlah} total={dari} tebal={10} kelas={`ring--gauge ring--${PILAR_KELAS[d.pilar] ?? 'lain'}`}
            judul={`${d.pilar}: ${fmt(d.jumlah)} ${satuan}, ${fmtPersen(p)} dari yang memuat konten dampak`}>
            <strong>{Math.round(p)}%</strong>
          </Cincin>
          <p className="lineage__pillar-name"><i className={`ring-key ring-key--${PILAR_KELAS[d.pilar] ?? 'lain'}`} aria-hidden="true" />{d.pilar}</p>
          <p className="lineage__pillar-count">{fmt(d.jumlah)} {satuan}</p>
        </li>;
      })}
    </ul>
    <p className="lineage__caption">{catatan}</p>
  </div>;
}

function Jalur({ nomor, nama, sumber, catatan, detail, children }: { nomor: string; nama: string; sumber: string; catatan?: string; detail: string; children: React.ReactNode }) {
  return <li className="lineage__lane">
    <div className="lineage__source">
      <span className="lineage__index" aria-hidden="true">{nomor}</span>
      <h3>{nama}</h3>
      <p className="lineage__caption">{sumber}</p>
      <p className="lineage__detail">{detail}</p>
      {catatan && <p className="lineage__note">{catatan}</p>}
    </div>
    {children}
  </li>;
}

function Diagram({ data }: { data: SumberData }) {
  const b = data.berita;
  const mk = data.mata_kuliah;
  const rentang = b.tahun_awal && b.tahun_akhir ? `${b.tahun_awal}–${b.tahun_akhir}` : 'rentang tahun belum tersedia';
  return <div className="lineage">
    <div className="lineage__group">
      <p className="lineage__group-label">Sumber publik</p>
      <ol className="lineage__lanes">
        <Jalur nomor="01" nama="Berita UGM" sumber={`Scraping sitemap & RSS ${b.situs}`}
          detail={`Terbit ${rentang} · ${fmt(b.sitemap)} URL di sitemap`}
          catatan={`Bahasa Indonesia ${fmt(b.bahasa.id)} · English ${fmt(b.bahasa.en)}. Dampak = cocok dengan minimal satu dari 14 tema Kepmen 361/M/KEP/2025 (keyword judul & deskripsi).`}>
          <RasioDampak diambil={b.diambil} berdampak={b.berdampak} satuan="berita" label="Berita diambil" />
          <PerDampak data={b.per_pilar} dari={b.berdampak} satuan="berita"
            catatan="Satu berita bisa masuk lebih dari satu dampak, jadi jumlah ketiganya lebih dari 100%." />
        </Jalur>
        {mk.tersedia
          ? <Jalur nomor="02" nama="Mata kuliah" sumber={`Web kurikulum publik ${fmt(mk.prodi)} program studi · ${fmt(mk.fakultas)} fakultas/sekolah`}
            detail={`${fmt(mk.baris)} baris penawaran · dihitung per MK unik`}
            catatan={`Data bersumber dari web setiap program studi (lebih dari 20 situs), dikurasi ke satu berkas. ${fmt(mk.indikator_resmi)} MK di antaranya indikator resmi Kepmen (tema 4.5).`}>
            <RasioDampak diambil={mk.mk_unik} berdampak={mk.berdampak} satuan="MK" label="Mata kuliah diambil" />
            <PerDampak data={mk.per_pilar} dari={mk.berdampak} satuan="MK"
              catatan="Satu mata kuliah bisa masuk lebih dari satu dampak, jadi jumlah ketiganya lebih dari 100%." />
          </Jalur>
          : <li className="lineage__lane lineage__lane--missing"><Notice type="warning">Data mata kuliah belum tersedia di server ini.</Notice></li>}
      </ol>
    </div>
    <div className="lineage__group lineage__group--internal">
      <p className="lineage__group-label">Sumber internal</p>
      <ul className="lineage__internal">
        {data.internal.map(item => <li key={item.nama}>
          <h3>{item.nama}</h3>
          <p className="lineage__status">{item.status}</p>
          <p className="lineage__caption">Semestinya menjadi sumber data mata kuliah. Sementara diganti {item.pengganti.toLowerCase()} (jalur 02).</p>
        </li>)}
      </ul>
    </div>
  </div>;
}

const UKURAN_HALAMAN = 10;
const PILIHAN_PILAR = ['', 'Sosial', 'Ekonomi', 'Lingkungan'] as const;

function TabelBerita({ total }: { total: number }) {
  const [q, setQ] = useState('');
  const [cari, setCari] = useState('');
  const [pilar, setPilar] = useState<string>('');
  const [page, setPage] = useState(1);
  const [hasil, setHasil] = useState<{ total: number; rows: BeritaDampak[] } | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const permintaan = useRef(0);

  // Pencarian ditunda sebentar supaya API tidak dipanggil tiap ketukan tombol.
  useEffect(() => { const t = window.setTimeout(() => { setCari(q.trim()); setPage(1); }, 300); return () => window.clearTimeout(t); }, [q]);
  useEffect(() => {
    const id = ++permintaan.current;
    setLoading(true); setError('');
    getBeritaDampak({ page, page_size: UKURAN_HALAMAN, q: cari, pilar })
      .then(r => { if (id === permintaan.current) setHasil(r); })
      .catch(e => { if (id === permintaan.current) setError(e instanceof Error ? e.message : 'Daftar berita gagal dimuat.'); })
      .finally(() => { if (id === permintaan.current) setLoading(false); });
  }, [cari, pilar, page]);

  const jumlahHalaman = hasil ? Math.max(1, Math.ceil(hasil.total / UKURAN_HALAMAN)) : 1;
  return <div className="source-news">
    <div className="source-news__head">
      <div>
        <h3>Berita yang memuat konten dampak</h3>
        <p className="section-note">{fmt(total)} berita. Klik judul untuk membuka artikel aslinya di ugm.ac.id (tab baru).</p>
      </div>
    </div>
    <div className="source-news__controls">
      <div className="field">
        <label htmlFor="sumber-cari">Cari judul berita</label>
        <input id="sumber-cari" type="search" value={q} maxLength={100} placeholder="mis. energi, desa, beasiswa" onChange={e => setQ(e.target.value)} />
      </div>
      <div className="source-news__filter" role="group" aria-label="Saring menurut dampak">
        {PILIHAN_PILAR.map(p => <button key={p || 'semua'} type="button" aria-pressed={pilar === p} className={pilar === p ? 'is-on' : ''} onClick={() => { setPilar(p); setPage(1); }}>{p || 'Semua dampak'}</button>)}
      </div>
    </div>
    {error
      ? <Notice type="error">{error}</Notice>
      : !hasil
        ? <div className="loading" role="status">Memuat daftar berita…</div>
        : hasil.rows.length === 0
          ? <p className="chart-empty">Tidak ada berita berdampak yang judulnya memuat “{cari}”{pilar ? ` pada dampak ${pilar}` : ''}. Coba kata lain atau pilih “Semua dampak”.</p>
          : <div className={`data-table-wrap ${loading ? 'is-busy' : ''}`} aria-busy={loading}>
            <table className="data-table source-news__table">
              <caption className="sr-only">Berita ugm.ac.id yang memuat konten dampak, terbaru lebih dulu</caption>
              <thead><tr><th scope="col">Tanggal</th><th scope="col">Judul berita</th><th scope="col">Tema Kepmen</th><th scope="col">Dampak</th></tr></thead>
              <tbody>{hasil.rows.map((r, i) => <tr key={`${r.tautan ?? r.judul}-${i}`}>
                <td className="source-news__date">{r.tanggal}<small>{r.bahasa}</small></td>
                <td>{r.tautan
                  ? <a className="source-news__link" href={r.tautan} target="_blank" rel="noopener noreferrer">{r.judul}<span className="sr-only"> (buka di tab baru)</span></a>
                  : r.judul}</td>
                <td className="source-news__themes">{r.tema.join(', ')}</td>
                <td><span className="source-news__pillars">{r.pilar.map(p => <span key={p} className={`pillar-tag pillar-tag--${PILAR_KELAS[p] ?? 'lain'}`}>{p}</span>)}</span></td>
              </tr>)}</tbody>
            </table>
          </div>}
    {hasil && hasil.total > 0 && <div className="table-pager">
      <button type="button" className="link-button" disabled={page <= 1 || loading} onClick={() => setPage(p => p - 1)}>‹ Sebelumnya</button>
      <span className="table-pager__info" aria-live="polite">{fmt(hasil.total)} berita · halaman {fmt(page)} dari {fmt(jumlahHalaman)}</span>
      <button type="button" className="link-button" disabled={page >= jumlahHalaman || loading} onClick={() => setPage(p => p + 1)}>Berikutnya ›</button>
    </div>}
  </div>;
}

export function SumberSection() {
  const [data, setData] = useState<SumberData | null>(null);
  const [error, setError] = useState('');
  useEffect(() => { getSumber().then(setData).catch(e => setError(e instanceof Error ? e.message : 'Ringkasan sumber gagal dimuat.')); }, []);
  return <section className="sumber" id="sumber" aria-labelledby="sumber-title">
    <div className="sumber__inner">
      <header className="sumber__header">
        <p className="chapter-intro__number">Bagian I</p>
        <div className="chapter-intro__rule" aria-hidden="true" />
        <h2 id="sumber-title">Sumber Data</h2>
        <p className="chapter-intro__description">Setiap angka di laporan ini bisa ditelusuri ke asalnya. Diagram di bawah menunjukkan apa yang diambil dari tiap sumber, berapa yang memuat konten dampak, dan bagaimana angka itu terbagi ke tiga dampak Kepmen.</p>
      </header>
      {error ? <Notice type="error">{error}</Notice> : !data ? <div className="loading loading--scene" role="status">Memuat ringkasan sumber data…</div> : <>
        <Diagram data={data} />
        <p className="sumber__method">Tag dampak bersifat <em>lower-bound</em>: berbasis keyword pada teks yang tersedia, jadi berita atau mata kuliah yang tidak menyebut kata kuncinya tidak terhitung. Dampak × SDGs memakai pemetaan resmi tema Kepmen, sedangkan bagian SDGs memakai pencocokan langsung. {data.berita.diperbarui ? `Berita terakhir diperbarui ${data.berita.diperbarui.slice(0, 10)}.` : ''}</p>
        <TabelBerita total={data.berita.berdampak} />
      </>}
    </div>
  </section>;
}
