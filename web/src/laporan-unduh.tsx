import { useEffect, useRef, useState } from 'react';

import { downloadReport, getLaporanPreview, type Laporan, type LaporanBlok, type Story } from './lib/api';
import { Notice } from './ui';

const NAMA_MODE: Record<string, string> = { impact: 'Dampak', 'impact-sdgs': 'Dampak_SDGs', sdgs: 'SDGs' };

function pesan(e: unknown, cadangan: string) {
  return e instanceof Error && e.message ? e.message : cadangan;
}

/** Satu blok dokumen. Blok yang sama dirender server ke Word, jadi pratinjau = isi file. */
function Blok({ blok }: { blok: LaporanBlok }) {
  switch (blok.type) {
    case 'heading':
      if (blok.level === 1) return <h2 className="kertas__bab">{blok.text}</h2>;
      if (blok.level === 2) return <h3 className="kertas__sub">{blok.text}</h3>;
      return <h4 className="kertas__subsub">{blok.text}</h4>;
    case 'paragraph':
      return <p className="kertas__p">{blok.text}</p>;
    case 'list': {
      const Tag = blok.ordered ? 'ol' : 'ul';
      return <Tag className="kertas__list">{blok.items.map(item => <li key={item}>{item}</li>)}</Tag>;
    }
    case 'figure':
      return <figure className="kertas__figure">
        <img src={`data:image/png;base64,${blok.image}`} alt={blok.caption} loading="lazy" />
        <figcaption><strong>{blok.caption}</strong>{blok.source && <span>Sumber: {blok.source}</span>}</figcaption>
      </figure>;
    case 'table': {
      const tautan = Object.fromEntries(Object.entries(blok.links).map(([k, v]) => [Number(k), v]));
      const kolomTautan = new Set(Object.values(tautan));
      const tampil = blok.columns.map((_, i) => i).filter(i => !kolomTautan.has(i));
      return <figure className="kertas__table">
        <figcaption><strong>{blok.caption}</strong></figcaption>
        <div className="kertas__table-wrap">
          <table className={blok.key_value ? 'is-kv' : ''}>
            {!blok.key_value && <thead><tr>{tampil.map(i => <th key={i} scope="col">{blok.columns[i]}</th>)}</tr></thead>}
            <tbody>{blok.rows.map((row, r) => <tr key={r}>{tampil.map(i => {
              const url = i in tautan ? row[tautan[i]] : '';
              const isi = /^https?:\/\//i.test(url)
                ? <a href={url} target="_blank" rel="noopener noreferrer">{row[i] || url}<span className="sr-only"> (buka di tab baru)</span></a>
                : row[i];
              return blok.key_value && i === 0 ? <th key={i} scope="row">{isi}</th> : <td key={i}>{isi}</td>;
            })}</tr>)}</tbody>
          </table>
        </div>
        {blok.source && <span className="kertas__source">Sumber: {blok.source}</span>}
      </figure>;
    }
  }
}

function Pratinjau({ laporan, sibuk, galat, onUnduh, onTutup }: { laporan: Laporan; sibuk: boolean; galat: string; onUnduh: () => void; onTutup: () => void }) {
  const dialog = useRef<HTMLDivElement>(null);
  const tutup = useRef(onTutup);
  tutup.current = onTutup;
  // Sekali saat dibuka: fokus ke dialog, kunci gulir halaman, Esc menutup; fokus kembali ke tombol saat ditutup.
  useEffect(() => {
    const kembali = document.activeElement as HTMLElement | null;
    dialog.current?.focus();
    const overflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    const tombol = (e: KeyboardEvent) => { if (e.key === 'Escape') tutup.current(); };
    window.addEventListener('keydown', tombol);
    return () => { window.removeEventListener('keydown', tombol); document.body.style.overflow = overflow; kembali?.focus(); };
  }, []);

  // Daftar isi/gambar/tabel disisipkan sebelum BAB I, sama dengan urutan di file Word.
  const indeksBab1 = laporan.blocks.findIndex(b => b.type === 'heading' && b.level === 1 && b.text.startsWith('BAB I '));
  const sebelum = indeksBab1 < 0 ? laporan.blocks : laporan.blocks.slice(0, indeksBab1);
  const sesudah = indeksBab1 < 0 ? [] : laporan.blocks.slice(indeksBab1);
  return <div className="pratinjau" role="dialog" aria-modal="true" aria-labelledby="pratinjau-judul" tabIndex={-1} ref={dialog}>
    <div className="pratinjau__bar">
      <div className="pratinjau__info">
        <strong id="pratinjau-judul">Pratinjau laporan {laporan.mode_label}</strong>
        <span>{laporan.toc.length} judul · {laporan.figures.length} gambar · {laporan.tables.length} tabel</span>
      </div>
      <div className="pratinjau__aksi">
        <button type="button" className="button" disabled={sibuk} onClick={onUnduh}>{sibuk ? 'Menyiapkan file…' : 'Unduh Word (.docx)'}</button>
        <button type="button" className="button secondary" onClick={onTutup}>Tutup</button>
      </div>
    </div>
    {galat && <div className="pratinjau__galat"><Notice type="error">{galat}</Notice></div>}
    <div className="pratinjau__scroll">
      <article className="kertas" aria-label="Isi laporan">
        <section className="kertas__halaman kertas__sampul">
          <p className="kertas__sampul-judul">{laporan.title}</p>
          <p>{laporan.subtitle}</p>
          <p>Periode data {laporan.period}</p>
          <div className="kertas__sampul-kaki"><strong>{laporan.institution}</strong><span>Yogyakarta</span><span>{laporan.generated}</span></div>
        </section>
        <section className="kertas__halaman">{sebelum.map((b, i) => <Blok key={i} blok={b} />)}</section>
        {indeksBab1 >= 0 && <section className="kertas__halaman">
          <h2 className="kertas__bab">DAFTAR ISI</h2>
          <ol className="kertas__toc">{laporan.toc.map((e, i) => <li key={i} className={e.level > 1 ? 'is-sub' : ''}>{e.text}</li>)}</ol>
          <h2 className="kertas__bab">DAFTAR GAMBAR</h2>
          <ol className="kertas__toc">{laporan.figures.map(g => <li key={g}>{g}</li>)}</ol>
          <h2 className="kertas__bab">DAFTAR TABEL</h2>
          <ol className="kertas__toc">{laporan.tables.map(t => <li key={t}>{t}</li>)}</ol>
        </section>}
        {sesudah.length > 0 && <section className="kertas__halaman">{sesudah.map((b, i) => <Blok key={i} blok={b} />)}</section>}
      </article>
    </div>
  </div>;
}

/** Bagian paling bawah analisis Dampak, Dampak × SDGs, dan SDGs: pratinjau dulu, lalu unduh Word. */
export function LaporanUnduh({ story }: { story: Story }) {
  const [laporan, setLaporan] = useState<Laporan | null>(null);
  const [memuat, setMemuat] = useState(false);
  const [mengunduh, setMengunduh] = useState(false);
  const [galat, setGalat] = useState('');
  const [galatUnduh, setGalatUnduh] = useState('');
  const payload = { mode: story.mode, ...story.filters };
  const filterKey = JSON.stringify(payload);
  useEffect(() => { setLaporan(null); setGalat(''); }, [filterKey]);

  async function pratinjau() {
    setMemuat(true); setGalat('');
    try { setLaporan(await getLaporanPreview(payload)); } catch (e) { setGalat(pesan(e, 'Pratinjau laporan gagal dibuat.')); } finally { setMemuat(false); }
  }
  async function unduh() {
    setMengunduh(true); setGalatUnduh('');
    try {
      const { blob, nama } = await downloadReport(payload);
      const href = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = href; link.download = nama ?? `Laporan_${NAMA_MODE[story.mode] ?? story.mode}_UGM.docx`;
      link.click(); URL.revokeObjectURL(href);
    } catch (e) { setGalatUnduh(pesan(e, 'Laporan gagal diunduh.')); } finally { setMengunduh(false); }
  }

  return <section className="story-block laporan-unduh" aria-labelledby={`laporan-unduh-${story.mode}`}>
    <h3 id={`laporan-unduh-${story.mode}`}>Laporan {story.mode === 'sdgs' ? 'kontribusi SDGs' : 'dampak'}</h3>
    <p className="section-note">
      Dokumen Word berkerangka <em>Laporan Dampak Sosial, Ekonomi, dan Lingkungan UGM 2025</em>: ringkasan eksekutif,
      lembar identifikasi, daftar isi, {story.mode === 'sdgs' ? 'sebaran dan profil per SDG' : 'BAB I sampai BAB V per tema Kepmen'},
      gambar dan tabel bernomor, referensi, serta lampiran metodologi. Isinya mengikuti filter yang sedang aktif.
    </p>
    <div className="laporan-unduh__aksi">
      <button type="button" className="button" disabled={memuat} onClick={pratinjau}>{memuat ? 'Menyusun laporan…' : 'Pratinjau laporan'}</button>
      {memuat && <span className="section-note" role="status">Menyusun bab dan menggambar grafik, bisa memakan waktu hingga 30 detik.</span>}
    </div>
    {galat && <Notice type="error">{galat}</Notice>}
    {laporan && <Pratinjau laporan={laporan} sibuk={mengunduh} galat={galatUnduh} onUnduh={unduh} onTutup={() => { setLaporan(null); setGalatUnduh(''); }} />}
  </section>;
}
