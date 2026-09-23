import { useState } from 'react';

import type { Chapter, ChapterSection, Story } from './lib/api';
import { ChartGrid, Insight, StoryTableView } from './story';

/* Komponen "Laporan dampak": tata letak mengikuti daftar isi resmi
 * LAPORAN DAMPAK SOSIAL, EKONOMI, DAN LINGKUNGAN UGM 2025 —
 * BAB II Dampak Sosial (4 tema), BAB III Dampak Ekonomi (5 tema),
 * BAB IV Dampak Lingkungan (5 tema); tiap tema = satu sub-bab bernomor
 * yang memuat indikator resmi Kepmen 361/M/KEP/2025 + analisis berita. */

const fmtValue = (value: unknown) => (typeof value === 'number' ? value.toLocaleString('id-ID') : String(value ?? '—'));
/** Nilai metrik pertama sub-bab selalu "Berita unik" (angka) — dipakai untuk cek ada/tidaknya data. */
const jumlahBerita = (section: ChapterSection) => {
  const value = section.metrics[0]?.value;
  return typeof value === 'number' ? value : Number(value) || 0;
};
const babId = (pillar: string) => `bab-${pillar.toLowerCase()}`;
const subId = (section: ChapterSection) => `sub-${section.number.replace('.', '-') || section.topic}`;

function scrollTo(id: string) {
  document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

/* --------------------------------------------------------- panel daftar isi ---- */
function DaftarIsi({ chapters }: { chapters: Chapter[] }) {
  // Navigasi ringkas: nama dampak (tanpa label "BAB" + nomor) lalu daftar temanya
  // dengan panah. Nomor bab/sub-bab tetap ada di judul bagian isinya, bukan di sini.
  return <nav className="laporan-toc" aria-label="Daftar isi laporan dampak">
    <div className="laporan-toc__head">
      <p className="section-kicker">Mengikuti laporan resmi</p>
      <h3>Daftar isi</h3>
      <p className="section-note">Struktur mengikuti Laporan Dampak Sosial, Ekonomi, dan Lingkungan UGM 2025 — tiap tema resmi Kepmen menjadi satu bagian.</p>
    </div>
    <ol className="laporan-toc__list">
      {chapters.map(chapter => <li key={chapter.pillar}>
        <button type="button" className="laporan-toc__bab" onClick={() => scrollTo(babId(chapter.pillar))}>
          <span className="laporan-toc__bab-title">{chapter.title}</span>
          <span className="laporan-toc__count">{fmtValue(chapter.total)} berita</span>
        </button>
        <ul className="laporan-toc__subs">
          {chapter.subsections.map(section => <li key={section.id}>
            <button type="button" onClick={() => scrollTo(subId(section))}>
              <span className="laporan-toc__arrow" aria-hidden="true">→</span>
              {/* Judul persis daftar isi laporan (mis. "Kunjungan Akademik dan
                  Pengeluaran Pengunjung Nasional"), bukan label pendek dashboard. */}
              <span className="laporan-toc__sub-title">{section.report_title}</span>
              <span className="laporan-toc__count">{fmtValue(section.metrics[0]?.value ?? 0)}</span>
            </button>
          </li>)}
        </ul>
      </li>)}
    </ol>
  </nav>;
}

/* ------------------------------------------------- panel indikator resmi tema ---- */
function IndikatorPanel({ section }: { section: ChapterSection }) {
  const items: { label: string; value: string }[] = [
    { label: 'Indikator', value: section.indicator },
    { label: 'Definisi', value: section.definition },
    { label: 'Kriteria', value: section.criteria },
    { label: 'Formula', value: section.formula },
    { label: 'Satuan', value: section.unit },
  ];
  // Terbuka default: indikator penilaian adalah isi utama sub-bab, bukan lampiran tersembunyi.
  return <details className="laporan-indikator" open>
    <summary>Indikator penilaian resmi — Kepmen 361/M/KEP/2025</summary>
    <dl>
      {items.filter(item => item.value).map(item => <div key={item.label} className="laporan-indikator__row">
        <dt>{item.label}</dt><dd>{item.value}</dd>
      </div>)}
      {section.sdg_labels.length > 0 && <div className="laporan-indikator__row">
        <dt>Klaster SDGs</dt>
        <dd>{section.sdg_labels.map(sdg => <span key={sdg.id} className="sdg-chip" title={sdg.label}>SDG {sdg.id}</span>)}</dd>
      </div>}
    </dl>
  </details>;
}

/* ------------------------------------------------------------- satu sub-bab ---- */
function SubBab({ section, open, onToggle }: { section: ChapterSection; open: boolean; onToggle: () => void }) {
  const nBerita = jumlahBerita(section);
  const id = subId(section);
  return <article className={`laporan-sub ${open ? 'is-open' : ''}`} id={id}>
    <header className="laporan-sub__head">
      <button type="button" className="laporan-sub__toggle" aria-expanded={open} onClick={onToggle}>
        <span className="laporan-sub__number">{section.number}</span>
        <span className="laporan-sub__title">
          <strong>{section.label}</strong>
          <small>Tema resmi: {section.official_topic}</small>
        </span>
        <span className="laporan-sub__meta">{fmtValue(nBerita)} berita · satuan indikator: {section.unit || '—'}</span>
        <span className="laporan-sub__chevron" aria-hidden="true">{open ? '−' : '+'}</span>
      </button>
    </header>
    {open && <>
      <IndikatorPanel section={section} />
      {nBerita === 0
        ? <p className="chart-empty">Belum ada berita bertema ini pada filter saat ini — indikator resmi di atas tetap ditampilkan sebagai rujukan penilaian.</p>
        : <>
          <div className="analysis-summary-grid analysis-summary-grid--3">
            {section.metrics.map(metric => <div className="metric" key={metric.label}>
              <div className="metric-label">{metric.label}</div>
              <div className="metric-value">{fmtValue(metric.value)}</div>
            </div>)}
          </div>
          <ChartGrid charts={section.charts} />
          {section.tables.map(table => <StoryTableView key={table.id} table={table} />)}
        </>}
    </>}
  </article>;
}

/* ------------------------------------------------------------------- satu bab ---- */
function Bab({ chapter }: { chapter: Chapter }) {
  // Sub-bab terbuka secara default; yang ditutup disimpan per-id supaya tombol
  // "Tutup/Buka semua" dan klik satu sub-bab tidak saling menimpa.
  const [closed, setClosed] = useState<Set<string>>(new Set());
  const semuaTerbuka = closed.size === 0;
  const toggle = (id: string) => setClosed(current => {
    const next = new Set(current);
    if (next.has(id)) next.delete(id); else next.add(id);
    return next;
  });
  const adaData = chapter.subsections.some(section => jumlahBerita(section) > 0);
  return <section className={`laporan-bab laporan-bab--${chapter.pillar.toLowerCase()}`} id={babId(chapter.pillar)} aria-labelledby={`${babId(chapter.pillar)}-title`}>
    <header className="laporan-bab__head">
      <div>
        <h3 id={`${babId(chapter.pillar)}-title`}>{chapter.title}</h3>
      </div>
      <div className="analysis-summary-grid analysis-summary-grid--3 laporan-bab__metrics">
        {chapter.metrics.map(metric => <div className="metric" key={metric.label}>
          <div className="metric-label">{metric.label}</div>
          <div className="metric-value">{fmtValue(metric.value)}</div>
        </div>)}
      </div>
    </header>
    <ChartGrid charts={chapter.charts} />
    <div className="laporan-bab__actions">
      <span className="section-note">{adaData ? 'Buka tiap sub-bab untuk indikator resmi + analisis berita tema.' : 'Tidak ada berita pada tema mana pun di bab ini untuk filter saat ini.'}</span>
      <button type="button" className="button secondary" onClick={() => setClosed(semuaTerbuka ? new Set(chapter.subsections.map(subId)) : new Set())}>{semuaTerbuka ? 'Tutup semua sub-bab' : 'Buka semua sub-bab'}</button>
    </div>
    <div className="laporan-bab__subs">
      {chapter.subsections.map(section => <SubBab key={section.id} section={section} open={!closed.has(subId(section))} onToggle={() => toggle(subId(section))} />)}
    </div>
  </section>;
}

/* ------------------------------------------------------------- tampilan utama ---- */
export function LaporanDampak({ story }: { story: Story }) {
  if (!story.chapters.length) return null;
  return <section className="story-block laporan" aria-label="Laporan dampak per bab">
    <div className="laporan__intro">
      <h3>Laporan dampak</h3>
      <Insight label="Cara membaca">
        Bagian di bawah mengikuti struktur Laporan Dampak Sosial, Ekonomi, dan Lingkungan UGM 2025:
        Dampak Sosial (4 tema), Dampak Ekonomi (5 tema), dan Dampak Lingkungan (5 tema).
        Setiap tema menampilkan indikator penilaian resmi Kepmen 361/M/KEP/2025 di samping analisis
        pemberitaan publik untuk tema tersebut. Angka berita adalah lower-bound berbasis keyword —
        indikator resmi tetap menjadi rujukan penilaian, bukan angka pemberitaan.
      </Insight>
    </div>
    <DaftarIsi chapters={story.chapters} />
    <div className="laporan__bab-list">
      {story.chapters.map(chapter => <Bab key={chapter.pillar} chapter={chapter} />)}
    </div>
  </section>;
}
