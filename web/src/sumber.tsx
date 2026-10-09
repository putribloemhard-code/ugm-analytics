import { useEffect, useState } from 'react';

import { getSumber, type JumlahPilar, type SumberData } from './lib/api';
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

/** Satu jalur sumber: kepala (nomor, nama, asal, fakta ringkas) lalu dua panel angka berdampingan. */
function Jalur({ nomor, nama, sumber, catatan, fakta, children }: { nomor: string; nama: string; sumber: string; catatan?: string; fakta: string[]; children: React.ReactNode }) {
  return <li className="lineage__lane">
    <header className="lineage__source">
      <span className="lineage__index" aria-hidden="true">{nomor}</span>
      <div className="lineage__title">
        <h3>{nama}</h3>
        <p className="lineage__caption">{sumber}</p>
      </div>
      <ul className="lineage__facts" aria-label={`Fakta ${nama}`}>{fakta.map(f => <li key={f}>{f}</li>)}</ul>
    </header>
    <div className="lineage__body">{children}</div>
    {catatan && <p className="lineage__note">{catatan}</p>}
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
          fakta={[`Terbit ${rentang}`, `${fmt(b.sitemap)} URL di sitemap`, `Indonesia ${fmt(b.bahasa.id)} · English ${fmt(b.bahasa.en)}`]}
          catatan="Dampak = cocok dengan minimal satu dari 14 tema Kepmen 361/M/KEP/2025 (keyword judul & deskripsi).">
          <RasioDampak diambil={b.diambil} berdampak={b.berdampak} satuan="berita" label="Berita diambil" />
          <PerDampak data={b.per_pilar} dari={b.berdampak} satuan="berita"
            catatan="Satu berita bisa masuk lebih dari satu dampak, jadi jumlah ketiganya lebih dari 100%." />
        </Jalur>
        {mk.tersedia
          ? <Jalur nomor="02" nama="Mata kuliah" sumber="Web kurikulum publik tiap program studi (lebih dari 20 situs), dikurasi ke satu berkas"
            fakta={[`${fmt(mk.prodi)} program studi`, `${fmt(mk.fakultas)} fakultas/sekolah`, `${fmt(mk.baris)} MK ditawarkan`, `${fmt(mk.mk_unik)} MK unik`]}
            catatan={`Dihitung per MK unik. ${fmt(mk.indikator_resmi)} MK di antaranya indikator resmi Kepmen (tema 4.5).`}>
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
        <p className="chapter-intro__description">Setiap angka di laporan ini bisa ditelusuri ke asalnya. Tiap sumber di bawah menunjukkan berapa data yang diambil, berapa yang memuat konten dampak, dan bagaimana angka itu terbagi ke tiga dampak Kepmen.</p>
      </header>
      {error ? <Notice type="error">{error}</Notice> : !data ? <div className="loading loading--scene" role="status">Memuat ringkasan sumber data…</div> : <>
        <Diagram data={data} />
        <p className="sumber__method">Tag dampak bersifat <em>lower-bound</em>: berbasis keyword pada teks yang tersedia, jadi berita atau mata kuliah yang tidak menyebut kata kuncinya tidak terhitung. Dampak × SDGs memakai pemetaan resmi tema Kepmen, sedangkan bagian SDGs memakai pencocokan langsung. {data.berita.diperbarui ? `Berita terakhir diperbarui ${data.berita.diperbarui.slice(0, 10)}.` : ''}</p>
      </>}
    </div>
  </section>;
}
