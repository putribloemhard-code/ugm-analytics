import { useEffect, useRef, useState } from 'react';

import { getBeritaDampak, getSumber, type BeritaDampak, type JumlahPilar, type SumberData } from './lib/api';
import { Notice } from './ui';

/* Bagian "Sumber": menelusuri asal setiap angka, dari situs sumber sampai pecahan per dampak.
   Diagram dibaca kiri ke kanan (HP: atas ke bawah): sumber -> diambil -> memuat konten dampak -> per pilar.
   Emas hanya untuk angka "memuat konten dampak" (satu aksen: angka yang dipakai laporan);
   warna pilar hanya penanda data, labelnya tetap tertulis. */

const fmt = (n: number) => n.toLocaleString('id-ID');
const persen = (bagian: number, total: number) => (total ? (100 * bagian) / total : 0);
const fmtPersen = (p: number) => `${p.toLocaleString('id-ID', { maximumFractionDigits: 1 })}%`;
const PILAR_KELAS: Record<string, string> = { Sosial: 'sosial', Ekonomi: 'ekonomi', Lingkungan: 'lingkungan' };

function Pecahan({ data, dari, catatan }: { data: JumlahPilar[]; dari: number; catatan: string }) {
  const terbesar = Math.max(1, ...data.map(d => d.jumlah));
  return <div className="lineage__leaves">
    <p className="lineage__stage-label">Per dampak</p>
    <ul>
      {data.map(d => <li key={d.pilar} className={`lineage__leaf lineage__leaf--${PILAR_KELAS[d.pilar]}`}>
        <span className="lineage__leaf-name">{d.pilar}</span>
        <span className="lineage__leaf-value">{fmt(d.jumlah)}</span>
        <span className="lineage__leaf-bar" aria-hidden="true"><span style={{ width: `${persen(d.jumlah, terbesar)}%` }} /></span>
        <span className="sr-only">, {fmtPersen(persen(d.jumlah, dari))} dari yang memuat konten dampak</span>
      </li>)}
    </ul>
    <p className="lineage__caption">{catatan}</p>
  </div>;
}

function Tahap({ label, nilai, satuan, keterangan, dampak, bagian }: { label: string; nilai: number; satuan: string; keterangan: string; dampak?: boolean; bagian?: { dari: number; teks: string } }) {
  const p = bagian ? persen(nilai, bagian.dari) : 0;
  return <div className={`lineage__stage ${dampak ? 'is-impact' : ''}`}>
    <p className="lineage__stage-label">{label}</p>
    <p className="lineage__number">{fmt(nilai)} <small>{satuan}</small></p>
    {bagian && <div className="lineage__share">
      <span className="lineage__share-track" aria-hidden="true"><span style={{ width: `${p}%` }} /></span>
      <span className="lineage__share-text">{fmtPersen(p)} {bagian.teks}</span>
    </div>}
    <p className="lineage__caption">{keterangan}</p>
  </div>;
}

function Jalur({ nomor, nama, sumber, catatan, children }: { nomor: string; nama: string; sumber: string; catatan?: string; children: React.ReactNode }) {
  return <li className="lineage__lane">
    <div className="lineage__source">
      <span className="lineage__index" aria-hidden="true">{nomor}</span>
      <h3>{nama}</h3>
      <p className="lineage__caption">{sumber}</p>
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
          catatan={`Bahasa Indonesia ${fmt(b.bahasa.id)} · English ${fmt(b.bahasa.en)}`}>
          <Tahap label="Berita diambil" nilai={b.diambil} satuan="berita"
            keterangan={`Terbit ${rentang}, dari ${fmt(b.sitemap)} URL di sitemap ${b.situs}.`} />
          <Tahap label="Memuat konten dampak" nilai={b.berdampak} satuan="berita" dampak
            bagian={{ dari: b.diambil, teks: 'dari berita yang diambil' }}
            keterangan="Cocok dengan minimal satu dari 14 tema Kepmen 361/M/KEP/2025 (keyword judul & deskripsi)." />
          <Pecahan data={b.per_pilar} dari={b.berdampak} catatan="Satu berita bisa masuk lebih dari satu dampak." />
        </Jalur>
        {mk.tersedia
          ? <Jalur nomor="02" nama="Mata kuliah" sumber={`Web kurikulum publik ${fmt(mk.prodi)} program studi · ${fmt(mk.fakultas)} fakultas/sekolah`}
            catatan="Data bersumber dari web setiap program studi (lebih dari 20 situs), dikurasi ke satu berkas.">
            <Tahap label="Mata kuliah diambil" nilai={mk.mk_unik} satuan="MK unik"
              keterangan={`Dari ${fmt(mk.baris)} baris penawaran; satu MK dihitung sekali walau ditawarkan di beberapa prodi.`} />
            <Tahap label="Memuat konten dampak" nilai={mk.berdampak} satuan="MK" dampak
              bagian={{ dari: mk.mk_unik, teks: 'dari mata kuliah yang diambil' }}
              keterangan={`Terpetakan ke minimal satu tema Kepmen. ${fmt(mk.indikator_resmi)} di antaranya indikator resmi (tema 4.5).`} />
            <Pecahan data={mk.per_pilar} dari={mk.berdampak} catatan="Satu mata kuliah bisa masuk lebih dari satu dampak." />
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
