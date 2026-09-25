import { FormEvent, useEffect, useRef, useState } from 'react';
import { Link, Navigate, Route, Routes, useLocation, useNavigate, useSearchParams } from 'react-router-dom';

import { AUTH_EVENT, DAMPAK_AUTH_EVENT, accreditationLogin, accreditationLogout, accreditationMe, accreditationRegister, dampakLogin, dampakLogout, dampakMe, dampakRegister, getAccreditation, getHomeSummary, getMetadata, getNews, getStory, searchAnalytics, type AccreditationResult, type AuthUser, type Metadata, type PillarDetail, type Story, type TopicOption } from './lib/api';
import { assetUrl, SiteShell, useInView } from './shell';
import { MultiSelect } from './multiselect';
import { ChartGrid, Insight, StoryTableView } from './story';
import { LaporanDampak, MataKuliahPanel } from './laporan';
import { Notice, PageHeader } from './ui';
import { AdminPage, ProfilePage } from './account';
import { AccreditationWorkspace } from './akreditasi';
import { SumberSection } from './sumber';
import { LaporanUnduh } from './laporan-unduh';
import { PembagianDampakChart } from './pembagian';
import { SdgPetaView, TagSdgManual } from './sdg';
import { PemetaanKepmenPanel, TagTemaManual } from './tema';

type FilterState = { yearFrom: string; yearTo: string; pillars: string[]; topics: string[]; sdgs: number[]; units: string[] };
const emptyFilters: FilterState = { yearFrom: '', yearTo: '', pillars: [], topics: [], sdgs: [], units: [] };

function AppShell({ children, plain }: { children: React.ReactNode; plain?: boolean }) { return <SiteShell plain={plain}>{children}</SiteShell>; }

/** Pesan kegagalan muat: pakai pesan asli dari API bila ada (mis. "Basis data tidak dapat
 *  dihubungi...") supaya pengguna tahu penyebabnya, bukan hanya "belum dapat dimuat". */
function pesanMuat(error: unknown, apa: string): string {
  const detail = error instanceof Error ? error.message : '';
  return detail && !/^\s*$/.test(detail) ? `${apa} gagal dimuat. ${detail}` : `${apa} belum dapat dimuat. Periksa koneksi API.`;
}

function queryFilters(metadata: Metadata): FilterState {
  const params = new URLSearchParams(window.location.search);
  const list = (key: string) => (params.get(key) ?? '').split(',').filter(Boolean);
  return { yearFrom: params.get('year_from') ?? metadata.years.min, yearTo: params.get('year_to') ?? metadata.years.max, pillars: list('pillars'), topics: list('topics'), sdgs: list('sdgs').map(Number).filter(value => value >= 1 && value <= 17), units: list('units') };
}

function updateUrl(filters: FilterState) {
  const params = new URLSearchParams({ year_from: filters.yearFrom, year_to: filters.yearTo });
  if (filters.pillars.length) params.set('pillars', filters.pillars.join(','));
  if (filters.topics.length) params.set('topics', filters.topics.join(','));
  if (filters.sdgs.length) params.set('sdgs', filters.sdgs.join(','));
  if (filters.units.length) params.set('units', filters.units.join(','));
  window.history.replaceState(null, '', `${window.location.pathname}?${params.toString()}`);
}


function Metric({ label, value }: { label: string; value: unknown }) { return <div className="metric"><div className="metric-label">{label}</div><div className="metric-value">{typeof value === 'number' ? value.toLocaleString('id-ID') : String(value ?? '-')}</div></div>; }

function Filters({ metadata, value, onChange, sdgMode, idPrefix, syncUrl }: { metadata: Metadata; value: FilterState; onChange: (next: FilterState) => void; sdgMode: boolean; idPrefix: string; syncUrl: boolean }) {
  const topics = metadata.topics.filter(topic => value.pillars.length === 0 || value.pillars.includes(topic.pillar));
  const years = Array.from({ length: Number(metadata.years.max) - Number(metadata.years.min) + 1 }, (_, index) => String(Number(metadata.years.min) + index));
  const startIndex = Math.max(0, years.indexOf(value.yearFrom)); const endIndex = Math.max(startIndex, years.indexOf(value.yearTo));
  function change(next: FilterState) { const normalized = Number(next.yearFrom) > Number(next.yearTo) ? { ...next, yearTo: next.yearFrom } : next; if (syncUrl) updateUrl(normalized); onChange(normalized); }
  const activeCount = (value.pillars.length ? 1 : 0) + value.topics.length + value.sdgs.length + value.units.length;
  return <section className="filter-panel" aria-label="Filter analisis"><div className="filter-heading"><div><p className="section-kicker">Kontrol analisis</p><h3>Filter data</h3></div><span className="filter-count">{activeCount ? `${activeCount} filter aktif` : 'Semua data'}</span></div><div className="year-range"><div className="range-label"><label htmlFor={`${idPrefix}-year-start`}>Rentang tahun</label><strong>{value.yearFrom} — {value.yearTo}</strong></div><div className="range-inputs"><input id={`${idPrefix}-year-start`} type="range" min={0} max={years.length - 1} value={startIndex} onChange={event => change({ ...value, yearFrom: years[Number(event.target.value)] })} /><input id={`${idPrefix}-year-end`} type="range" min={0} max={years.length - 1} value={endIndex} onChange={event => change({ ...value, yearTo: years[Math.max(startIndex, Number(event.target.value))] })} /></div></div><div className="filter-grid">{sdgMode ? <MultiSelect id={`${idPrefix}-sdgs`} label="SDG" options={metadata.sdgs.map(sdg => ({ value: String(sdg.id), label: `SDG ${sdg.id}: ${sdg.label}` }))} selected={value.sdgs.map(String)} onChange={next => change({ ...value, sdgs: next.map(Number) })} searchable /> : <MultiSelect id={`${idPrefix}-pillars`} label="Dampak" options={metadata.pillars.map(pillar => ({ value: pillar, label: pillar }))} selected={value.pillars} onChange={next => change({ ...value, pillars: next })} />}{!sdgMode && <MultiSelect id={`${idPrefix}-topics`} label="Tema resmi Kepmen" options={topics.map(topic => ({ value: topic.id, label: `${topic.label} (${topic.pillar})` }))} selected={value.topics} onChange={next => change({ ...value, topics: next })} searchable />}<MultiSelect id={`${idPrefix}-units`} label="Fakultas / Unit Kerja" options={metadata.units.map(unit => ({ value: unit.id, label: unit.label }))} selected={value.units} onChange={next => change({ ...value, units: next })} searchable /></div><div className="action-row"><button className="button secondary" type="button" onClick={() => change({ yearFrom: metadata.years.min, yearTo: metadata.years.max, pillars: [], topics: [], sdgs: [], units: [] })}>Reset filter</button><span className="filter-hint">Centang beberapa opsi. Kosongkan untuk memakai semua.</span></div></section>;
}

function Table({ title, rows }: { title: string; rows: unknown[] }) {
  const values = rows as Record<string, unknown>[];
  const columns = values.length ? Object.keys(values[0]) : [];
  return <section className="section"><h3>{title}</h3>{values.length ? <div className="data-table-wrap"><table><caption className="sr-only">{title}</caption><thead><tr>{columns.map(column => <th key={column}>{column.replaceAll('_', ' ')}</th>)}</tr></thead><tbody>{values.slice(0, 200).map((row, index) => <tr key={index}>{columns.map(column => <td key={column}>{Array.isArray(row[column]) ? row[column].join(', ') : String(row[column] ?? '')}</td>)}</tr>)}</tbody></table></div> : <Notice type="info">Tidak ada data untuk bagian ini.</Notice>}</section>;
}

const NEWS_PAGE_SIZE = 5;

const pillarAccent: Record<string, string> = { Lingkungan: 'green', Ekonomi: 'orange', Sosial: 'blue' };
const fmtValue = (value: unknown) => (typeof value === 'number' ? value.toLocaleString('id-ID') : String(value ?? '-'));

function Executive({ story }: { story: Story }) {
  return <section className="story-block" aria-label="Ringkasan eksekutif">
    <h3>Ringkasan eksekutif</h3>
    <div className="analysis-summary-grid">{story.executive.metrics.map(metric => <div className="metric" key={metric.label} title={metric.help ?? undefined}><div className="metric-label">{metric.label}</div><div className="metric-value">{fmtValue(metric.value)}</div>{metric.note && <div className="metric-note">{metric.note}</div>}</div>)}</div>
    {story.executive.pembagian && <PembagianDampakChart data={story.executive.pembagian} />}
    <Insight label={story.executive.narrative_source === 'llm' ? 'Ringkasan analisis · dirangkai AI dari angka dashboard' : 'Ringkasan analisis'}>{story.executive.narrative}</Insight>
  </section>;
}

function Overview({ story, pillar, onPick }: { story: Story; pillar: string; onPick: (pillar: string) => void }) {
  return <section className="story-block" aria-label="Overview dampak">
    <h3>Overview dampak</h3>
    <p className="section-note">Pilih satu dampak untuk membaca rinciannya di bawah.</p>
    <div className="pillar-cards">{story.overview.map(item => <button type="button" key={item.pillar} aria-pressed={pillar === item.pillar} className={`pillar-card ${pillarAccent[item.pillar] ?? 'blue'} ${pillar === item.pillar ? 'is-selected' : ''}`} onClick={() => onPick(item.pillar)}>
      <span className="pillar-card__name">{item.pillar}</span>
      <strong>{item.total.toLocaleString('id-ID')}</strong><span className="pillar-card__unit">berita</span>
      {item.top_topic && <small>Tema terbanyak: {item.top_topic} ({item.top_topic_count.toLocaleString('id-ID')} berita)</small>}
    </button>)}</div>
  </section>;
}

function TopicPicker({ id, options, value, onChange }: { id: string; options: TopicOption[]; value: string; onChange: (topic: string) => void }) {
  if (!options.length) return null;
  return <div className="field topic-picker"><label htmlFor={id}>Pilih tema (keyword)</label><select id={id} value={value} onChange={event => onChange(event.target.value)}>{options.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}</select></div>;
}

function PillarDetailView({ detail, topic, onTopic, busy }: { detail: PillarDetail; topic: string; onTopic: (topic: string) => void; busy: boolean }) {
  const [tabId, setTabId] = useState(detail.tabs[0]?.id ?? '');
  const active = detail.tabs.find(tab => tab.id === tabId) ?? detail.tabs[0];
  if (!active) return null;
  return <section className={`story-block ${busy ? 'is-busy' : ''}`} aria-label={`Detail dampak ${detail.pillar}`} aria-busy={busy}>
    <h3>Detail dampak: {detail.pillar}</h3>
    <Insight label={detail.narrative_source === 'llm' ? 'Narasi dampak · dirangkai AI dari angka dashboard' : 'Narasi dampak'}>{detail.narrative}</Insight>
    <div className="analysis-summary-grid analysis-summary-grid--3">{detail.metrics.map(metric => <div className="metric" key={metric.label} title={metric.help ?? undefined}><div className="metric-label">{metric.label}</div><div className="metric-value">{fmtValue(metric.value)}</div></div>)}</div>
    <div className="tabs analysis-tabs" role="tablist" aria-label={`Rincian dampak ${detail.pillar}`}>{detail.tabs.map(tab => <button key={tab.id} id={`tab-${tab.id}`} role="tab" type="button" aria-selected={tab.id === active.id} aria-controls={`panel-${tab.id}`} className={`tab ${tab.id === active.id ? 'active' : ''}`} onClick={() => setTabId(tab.id)}>{tab.label}</button>)}</div>
    <div role="tabpanel" id={`panel-${active.id}`} aria-labelledby={`tab-${active.id}`}>
      {active.id === 'kata_kunci' && <TopicPicker id="topic-picker-detail" options={detail.topic_options} value={topic || detail.selected_topic} onChange={onTopic} />}
      {active.note && <p className="chart-note">{active.note}</p>}
      <ChartGrid charts={active.charts} />
      {active.tables.map(table => <StoryTableView key={table.id} table={table} />)}
    </div>
  </section>;
}

function CrossSection({ story, topic, onTopic }: { story: Story; topic: string; onTopic: (topic: string) => void }) {
  if (!story.cross.charts.length && !story.cross.tables.length && !story.tables.length) return null;
  return <section className="story-block" aria-label={story.cross.title}>
    <h3>{story.cross.title}</h3>
    <TopicPicker id="topic-picker-cross" options={story.cross.topic_options ?? []} value={topic || story.cross.selected_topic || ''} onChange={onTopic} />
    <ChartGrid charts={story.cross.charts} />
    {[...story.cross.tables, ...story.tables].map(table => <StoryTableView key={table.id} table={table} />)}
  </section>;
}

function AnalyticsContent({ story, pillar, onPickPillar, topic, onTopic, busy, onDataChanged }: { story: Story; pillar: string; onPickPillar: (pillar: string) => void; topic: string; onTopic: (topic: string) => void; busy: boolean; onDataChanged: () => void }) {
  const [news, setNews] = useState<{ rows: unknown[]; total: number } | null>(null);
  const [newsError, setNewsError] = useState('');
  const [page, setPage] = useState(1);
  const filtersKey = JSON.stringify(story.filters);
  useEffect(() => { setPage(1); }, [filtersKey, story.mode]);
  useEffect(() => { setNews(null); setNewsError(''); const f = story.filters; getNews({ mode: story.mode, year_from: f.year_from as string, year_to: f.year_to as string, pillars: f.pillars as string[], topics: f.topics as string[], sdgs: f.sdgs as number[], units: f.units as string[] }, page, NEWS_PAGE_SIZE).then(setNews).catch(e => setNewsError(pesanMuat(e, 'Daftar berita'))); }, [filtersKey, story.mode, page]);
  const totalPages = news ? Math.max(1, Math.ceil(news.total / NEWS_PAGE_SIZE)) : 1;
  return <div className={`analysis-dashboard ${busy ? 'is-busy' : ''}`} aria-busy={busy}>
    <Executive story={story} />
    {/* Blok laporan berbab hanya di bagian "Analisis Dampak"; bagian "Dampak × SDGs" sudah
        punya tab SDG sendiri, jadi menaruhnya di sana akan menggandakan 14 sub-bab yang sama. */}
    {story.mode === 'impact' && <LaporanDampak story={story} />}
    {/* Data mata kuliah (sumber kedua, bukan berita): di mode Dampak panelnya ada di akhir laporan
        berbab (+ ringkasan per sub-bab); di Dampak × SDGs lewat klaster SDG tema; di SDGs lewat
        tagging SDG langsung dengan kamus yang sama dengan berita. */}
    {(story.mode === 'impact-sdgs' || story.mode === 'sdgs') && story.mata_kuliah && <MataKuliahPanel blok={story.mata_kuliah} />}
    {story.overview.length > 0 && <Overview story={story} pillar={pillar} onPick={onPickPillar} />}
    {story.pillar_detail && <PillarDetailView detail={story.pillar_detail} topic={topic} onTopic={onTopic} busy={busy} />}
    <CrossSection story={story} topic={topic} onTopic={onTopic} />
    {story.cross.pemetaan && <PemetaanKepmenPanel data={story.cross.pemetaan} mode={story.mode} />}
    {story.mode !== 'sdgs' && story.cross.pemetaan && <TagTemaManual tema={story.cross.pemetaan.rows} mode={story.mode} filter={{ year_from: story.filters.year_from as string, year_to: story.filters.year_to as string, units: story.filters.units as string[] }} onChanged={onDataChanged} />}
    {story.mode === 'sdgs' && story.sdg_peta && <SdgPetaView peta={story.sdg_peta} />}
    {story.mode === 'sdgs' && <TagSdgManual filter={{ year_from: story.filters.year_from as string, year_to: story.filters.year_to as string, units: story.filters.units as string[] }} onChanged={onDataChanged} />}
    <section className="story-block"><h3>Daftar berita</h3>{newsError ? <Notice type="error">{newsError}</Notice> : !news ? <div className="loading" role="status">Memuat daftar berita...</div> : <><Table title="Berita terpilih" rows={news.rows} /><div className="action-row"><button className="button secondary" disabled={page <= 1} onClick={() => setPage(current => current - 1)}>Halaman sebelumnya</button><span aria-live="polite">Halaman {page} dari {totalPages}</span><button className="button secondary" disabled={page >= totalPages} onClick={() => setPage(current => current + 1)}>Halaman berikutnya</button></div></>}</section>
    <section className="story-block"><h3>Catatan metodologi</h3><ul>{story.caveats.map(caveat => <li key={caveat}>{caveat}</li>)}</ul></section>
    <LaporanUnduh story={story} />
  </div>;
}

type AnalysisDef = { id: 'dampak' | 'dampak-sdgs' | 'sdgs'; mode: 'impact' | 'impact-sdgs' | 'sdgs'; title: string; icon: string; eyebrow: string; caption: string; description: string; accent: string; sdgMode?: boolean };
const analysisSections: AnalysisDef[] = [
  { id: 'dampak', mode: 'impact', title: 'Analisis Dampak Universitas', icon: 'dampak.png', eyebrow: 'Pilar Kepmen', caption: '3 dampak dan 14 tema resmi Kepmen 361/M/KEP/2025. Mode ini tidak menghitung SDG langsung.', description: 'Telaah Lingkungan, Ekonomi, dan Sosial melalui 14 tema resmi Kepmen.', accent: 'green' },
  { id: 'dampak-sdgs', mode: 'impact-sdgs', title: 'Analisis Dampak × SDGs', icon: 'dampakXsdgs.png', eyebrow: 'Peta keterkaitan', caption: 'Tema dampak Kepmen dipetakan ke klaster SDGs resmi. Ini berbeda dari pencocokan SDG langsung.', description: 'Lihat hubungan tema dampak Kepmen dengan klaster SDGs resminya.', accent: 'blue' },
  { id: 'sdgs', mode: 'sdgs', title: 'SDGs', icon: 'sdgs.png', eyebrow: 'Pencocokan langsung', caption: 'Mapping langsung seluruh URL sitemap ke 17 SDG, tanpa tema dampak Kepmen.', description: 'Telusuri 17 SDG pada URL sitemap dan teks berita yang tersedia.', accent: 'orange', sdgMode: true },
];
const routeTitle = { dampak: 'Dampak', 'dampak-sdgs': 'Dampak × SDGs', sdgs: 'SDGs' } as const;
const defaultFilters = (metadata: Metadata): FilterState => ({ ...emptyFilters, yearFrom: metadata.years.min, yearTo: metadata.years.max });

function Hero({ summary, error }: { summary: Record<string, string | number | null> | null; error: string }) {
  const navigate = useNavigate();
  const [query, setQuery] = useState('');
  const [explanation, setExplanation] = useState('');
  async function search(event: FormEvent) {
    event.preventDefault();
    if (!query.trim()) { setExplanation('Ketik kata kunci yang ingin dianalisis.'); return; }
    try {
      const result = await searchAnalytics(query);
      setExplanation(result.explanation);
      const params = new URLSearchParams();
      if (result.years) { params.set('year_from', result.years[0]); params.set('year_to', result.years[1]); }
      if (result.pillars.length) params.set('pillars', result.pillars.join(','));
      if (result.topics.length) params.set('topics', result.topics.join(','));
      if (result.sdgs.length) params.set('sdgs', result.sdgs.join(','));
      // Semua hasil pencarian bermuara ke bagian dalam halaman Dampak (dulu halaman terpisah per pilar).
      navigate(`/dampak?${params.toString()}#${result.page}`);
    } catch { setExplanation('Pencarian belum dapat diproses. Periksa koneksi API.'); }
  }
  return <section className="cold-open" id="pembuka" aria-labelledby="cold-open-title"><div className="cold-open__inner">
    <p className="eyebrow">Universitas Gadjah Mada · Kepmen 361/M/KEP/2025</p>
    {error && <Notice type="error">{error}</Notice>}
    <h1 id="cold-open-title">Analisis <span>Dampak UGM</span></h1>
    <p className="cold-open__statement">Ruang baca untuk memeriksa jejak dampak sosial, ekonomi, dan lingkungan UGM melalui pemberitaan publik dan kerangka SDGs.</p>
    <form className="hero-search" onSubmit={search}><label className="sr-only" htmlFor="analysis-search">Mau analisis apa?</label><input id="analysis-search" value={query} onChange={event => setQuery(event.target.value)} placeholder="Contoh: energi, SDG 7, atau 2024" /><button type="submit">Cari analisis</button></form>
    <p className="hero-hint">Cari tema, pilar, SDG, atau tahun. Hasil akan membuka bagian analisis dengan filter terkait.</p>
    {explanation && <p className="hero-note" role="status">{explanation}</p>}
    {summary && <p className="cold-open__context">Data terakhir: {summary.updated_at ?? 'waktu pembaruan belum tersedia'}.</p>}
    <Link className="cold-open__continue" to={{ pathname: '/dampak', hash: '#sumber' }}>Lihat sumber data <span aria-hidden="true">↓</span></Link>
  </div></section>;
}

function ChapterIntro({ id, number, title, description, children }: { id?: string; number: string; title: string; description: string; children?: React.ReactNode }) {
  const titleId = `${id ?? number.replace(/\s+/g, '-').toLowerCase()}-title`;
  return <section className="chapter-intro" id={id} aria-labelledby={titleId}><div className="chapter-intro__inner"><p className="chapter-intro__number">{number}</p><div className="chapter-intro__rule" aria-hidden="true" /><h2 id={titleId}>{title}</h2><p className="chapter-intro__description">{description}</p>{children}</div></section>;
}

function AnalysisScene({ def, metadata, metadataError, seeded, seedKey, tint }: { def: AnalysisDef; metadata: Metadata | null; metadataError: string; seeded: boolean; seedKey: string; tint: boolean }) {
  const ref = useRef<HTMLElement>(null);
  const seen = useInView(ref);
  const active = seen || seeded;
  const [filters, setFilters] = useState(emptyFilters);
  const [story, setStory] = useState<Story | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [pillar, setPillar] = useState('Lingkungan');
  const [topic, setTopic] = useState('');
  // Naik setiap data berubah dari dalam bagian ini (mis. tag SDG manual) supaya story dimuat ulang.
  const [versi, setVersi] = useState(0);
  useEffect(() => { if (metadata) setFilters(seeded ? queryFilters(metadata) : defaultFilters(metadata)); }, [metadata, seeded, seedKey]);
  useEffect(() => {
    if (!active || !metadata || !filters.yearFrom) return;
    let cancelled = false; setLoading(true); setError('');
    // Data lama tetap tampil (redup) selama data baru dimuat, supaya halaman tidak melompat.
    getStory({ mode: def.mode, year_from: filters.yearFrom, year_to: filters.yearTo, pillars: filters.pillars, topics: filters.topics, sdgs: filters.sdgs, units: filters.units, pillar: def.mode === 'sdgs' ? undefined : pillar, topic: topic || undefined })
      .then(value => { if (!cancelled) { setStory(value); setLoading(false); } })
      .catch(e => { if (!cancelled) { setError(pesanMuat(e, 'Data analisis')); setLoading(false); } });
    return () => { cancelled = true; };
  }, [active, metadata, filters, def.mode, pillar, topic, versi]);
  const failure = metadataError || error;
  return <section ref={ref} id={def.id} className={`story-scene ${tint ? 'story-scene--tint' : ''}`} aria-labelledby={`${def.id}-title`}><div className="story-scene__inner">
    <header className="story-scene__header"><p className={`eyebrow eyebrow--${def.accent}`}><img src={assetUrl(`logo/${def.icon}`)} alt="" />{def.eyebrow}</p><h2 id={`${def.id}-title`}>{def.title}</h2><p className="story-scene__deck">{def.caption}</p></header>
    {failure ? <Notice type="error">{failure}</Notice> : !active || !metadata ? <div className="loading loading--scene" role="status">Bagian ini dimuat saat Anda menggulir ke sini...</div> : <>
      <Filters metadata={metadata} value={filters} onChange={setFilters} sdgMode={!!def.sdgMode} idPrefix={def.id} syncUrl={seeded} />
      {!story ? <div className="loading" role="status">Memuat hasil analisis...</div> : <><AnalyticsContent story={story} pillar={pillar} onPickPillar={value => { setPillar(value); setTopic(''); }} topic={topic} onTopic={setTopic} busy={loading} onDataChanged={() => setVersi(v => v + 1)} /><p className="footer-note">Data terakhir: {story.data_as_of ?? 'waktu pembaruan belum tersedia'}.</p></>}
    </>}
  </div></section>;
}

function ScrollReport({ target }: { target?: AnalysisDef['id'] }) {
  const location = useLocation();
  const [summary, setSummary] = useState<Record<string, string | number | null> | null>(null);
  const [summaryError, setSummaryError] = useState('');
  const [metadata, setMetadata] = useState<Metadata | null>(null);
  const [metadataError, setMetadataError] = useState('');
  useEffect(() => { getHomeSummary().then(setSummary).catch(e => setSummaryError(pesanMuat(e, 'Ringkasan data'))); getMetadata().then(setMetadata).catch(e => setMetadataError(pesanMuat(e, 'Metadata filter'))); }, []);
  useEffect(() => {
    const dariHash = location.hash ? location.hash.slice(1) : target;
    const id = dariHash === 'metodologi' ? 'sumber' : dariHash;
    if (!id) { window.scrollTo(0, 0); return; }
    // Instan, bukan smooth: bagian di antaranya dimuat lazy saat terlewati dan akan menggeser posisi tujuan.
    const timer = window.setTimeout(() => document.getElementById(id)?.scrollIntoView({ block: 'start' }), 60);
    return () => window.clearTimeout(timer);
  }, [location.key, location.hash, target]);
  return <AppShell><Hero summary={summary} error={summaryError} />
    <SumberSection />
    <ChapterIntro id="ringkasan" number="Bagian II" title="Tiga Jalur untuk Membaca Dampak" description="Setiap jalur memakai sumber dan metode yang berbeda. Pilih jalur yang paling sesuai dengan pertanyaan Anda, bukan sekadar grafik yang ingin dilihat.">
      <div className="route-grid">{analysisSections.map(def => <Link className={`route-card ${def.accent}`} to={{ pathname: '/dampak', hash: `#${def.id}` }} key={def.id}><div className="route-card-top"><img src={assetUrl(`logo/${def.icon}`)} alt="" /><span>{def.eyebrow}</span></div><h3>{routeTitle[def.id]}</h3><p>{def.description}</p><span className="route-action">Buka bagian ini <b aria-hidden="true">↓</b></span></Link>)}</div>
    </ChapterIntro>
    <ChapterIntro number="Bagian III" title="Analisis Data Berita" description="Tiap bagian punya filter sendiri. Angka, grafik, tabel, dan laporan Word mengikuti filter yang aktif." />
    {analysisSections.map((def, index) => <AnalysisScene key={def.id} def={def} metadata={metadata} metadataError={metadataError} seeded={target === def.id} seedKey={location.key} tint={index % 2 === 1} />)}
  </AppShell>;
}

function LandingPage() {
  return <AppShell>
    <section className="cold-open cold-open--landing" aria-labelledby="landing-title"><div className="cold-open__inner">
      <p className="eyebrow">Universitas Gadjah Mada</p>
      <h1 id="landing-title">UGM <span>Analytics</span></h1>
      <p className="cold-open__statement">Satu pintu untuk dua layanan: membaca jejak dampak sosial, ekonomi, dan lingkungan UGM lewat pemberitaan publik dan kerangka SDGs, serta mengelola kelengkapan data akreditasi Program Studi (LED & LKPS). Pilih salah satu untuk memulai.</p>
      <a className="cold-open__continue" href="#pilihan">Pilih menu untuk mulai <span aria-hidden="true">↓</span></a>
    </div></section>
    <ChapterIntro id="pilihan" number="Mulai dari sini" title="Pilih Jalur Anda" description="Analisis Dampak dan Akreditasi memakai akun masing-masing yang terpisah. Anda akan diminta masuk atau daftar akun saat membuka salah satu di bawah.">
      <div className="route-grid route-grid--pair">
        <Link className="route-card green" to="/dampak">
          <div className="route-card-top"><img src={assetUrl('logo/dampak.png')} alt="" /><span>Analisis data</span></div>
          <h3>Analisis Dampak</h3>
          <p>Telaah dampak Lingkungan, Ekonomi, dan Sosial UGM lewat pemberitaan publik dan kerangka SDGs resmi Kepmen 361/M/KEP/2025.</p>
          <span className="route-action">Buka Analisis Dampak <b aria-hidden="true">→</b></span>
        </Link>
        <Link className="route-card orange" to="/akreditasi">
          <div className="route-card-top"><img src={assetUrl('logo/certificate.png')} alt="" /><span>Akreditasi</span></div>
          <h3>Portal Akreditasi</h3>
          <p>Kelola kelengkapan data LED & LKPS, ekstrak dokumen pendukung, dan susun laporan akreditasi Program Studi.</p>
          <span className="route-action">Buka Akreditasi <b aria-hidden="true">→</b></span>
        </Link>
      </div>
    </ChapterIntro>
  </AppShell>;
}

function DampakLogin({ onUser, next }: { onUser: (user: AuthUser) => void; next?: string | null }) {
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [email, setEmail] = useState(''); const [name, setName] = useState(''); const [password, setPassword] = useState(''); const [message, setMessage] = useState('');
  const navigate = useNavigate();
  async function submit() {
    setMessage('');
    try {
      if (mode === 'register') {
        try { await dampakRegister(email, name, password); }
        catch (e) {
          // Akun Analisis Dampak terpisah dari portal lain: email yang sama bisa sudah terdaftar di sini.
          if (e instanceof Error && e.message.includes('sudah terdaftar')) { setMode('login'); setMessage('Email ini sudah punya akun Analisis Dampak. Silakan masuk dengan password akun tersebut; kalau lupa, minta admin menghapus akunnya lalu daftar ulang.'); return; }
          throw e;
        }
        setMode('login'); setMessage('Registrasi berhasil. Silakan masuk.'); return;
      }
      onUser(await dampakLogin(email, password));
      if (next && next.startsWith('/')) navigate(next, { replace: true });
    } catch (e) { setMessage(e instanceof Error ? e.message : 'Autentikasi gagal'); }
  }
  return <div className="accreditation-gate"><section className="accreditation-hero dampak"><div className="brand-chip"><img src={assetUrl('logo/LogoUGM.png')} alt="" /> Universitas Gadjah Mada</div><h1>Analisis <span>Dampak UGM</span></h1><p>Telaah jejak dampak sosial, ekonomi, dan lingkungan UGM melalui pemberitaan publik dan kerangka SDGs resmi Kepmen 361/M/KEP/2025.</p></section><section className="auth-panel"><p className="section-kicker">Selamat datang</p><h2>Masuk untuk melanjutkan</h2><p className="section-note">Akun Analisis Dampak terpisah dari akun Akreditasi.</p><div className="auth-tabs"><button className={mode === 'login' ? 'active' : ''} onClick={() => setMode('login')}>Masuk</button><button className={mode === 'register' ? 'active' : ''} onClick={() => setMode('register')}>Daftar akun baru</button></div>{mode === 'register' && <div className="field"><label htmlFor="dp-name">Nama lengkap</label><input id="dp-name" value={name} onChange={e => setName(e.target.value)} /></div>}<div className="field"><label htmlFor="dp-email">Email UGM</label><input id="dp-email" type="email" placeholder="nama@ugm.ac.id" aria-describedby="dp-email-hint" value={email} onChange={e => setEmail(e.target.value)} /><small id="dp-email-hint" className="field-hint">Hanya email @ugm.ac.id atau @mail.ugm.ac.id.</small></div><div className="field"><label htmlFor="dp-password">Password</label><input id="dp-password" type="password" value={password} onChange={e => setPassword(e.target.value)} /></div><button className="button auth-submit" onClick={submit}>{mode === 'login' ? 'Masuk' : 'Buat akun'}</button>{message && <Notice type={/^(Registrasi|Email ini sudah)/.test(message) ? 'info' : 'error'}>{message}</Notice>}</section></div>;
}

function DampakPage() {
  const [user, setUser] = useState<AuthUser | null | undefined>(undefined);
  const [params] = useSearchParams();
  useEffect(() => {
    const refresh = () => { dampakMe().then(setUser).catch(() => setUser(null)); };
    refresh();
    window.addEventListener(DAMPAK_AUTH_EVENT, refresh);
    return () => window.removeEventListener(DAMPAK_AUTH_EVENT, refresh);
  }, []);
  if (user === undefined) return <AppShell plain><div className="content loading">Memuat...</div></AppShell>;
  if (!user) return <AppShell plain><div className="content"><DampakLogin onUser={setUser} next={params.get('next')} /></div></AppShell>;
  return <ScrollReport />;
}

function AccreditationLogin({ onUser, next }: { onUser: (user: { id: number; email: string; nama: string; is_admin: boolean }) => void; next?: string | null }) {
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [email, setEmail] = useState(''); const [name, setName] = useState(''); const [password, setPassword] = useState(''); const [message, setMessage] = useState('');
  const navigate = useNavigate();
  async function submit() {
    setMessage('');
    try {
      if (mode === 'register') {
        try { await accreditationRegister(email, name, password); }
        catch (e) {
          // Akun Akreditasi terpisah dari portal lain: email yang sama bisa sudah terdaftar di sini.
          if (e instanceof Error && e.message.includes('sudah terdaftar')) { setMode('login'); setMessage('Email ini sudah punya akun Akreditasi. Silakan masuk dengan password akun tersebut; kalau lupa, minta admin menghapus akunnya lalu daftar ulang.'); return; }
          throw e;
        }
        setMode('login'); setMessage('Registrasi berhasil. Silakan masuk.'); return;
      }
      onUser(await accreditationLogin(email, password));
      // Kembali ke halaman yang tadi diminta (mis. /admin) setelah login berhasil.
      if (next && next.startsWith('/')) navigate(next, { replace: true });
    } catch (e) { setMessage(e instanceof Error ? e.message : 'Autentikasi gagal'); }
  }
  return <div className="accreditation-gate"><section className="accreditation-hero akreditasi"><div className="brand-chip"><img src={assetUrl('logo/LogoUGM.png')} alt="" /> Universitas Gadjah Mada</div><h1>Portal <span>Akreditasi</span></h1><p>Kelola kelengkapan data LED & LKPS, ekstrak dokumen pendukung, dan susun laporan akreditasi program studi dalam satu tempat.</p></section><section className="auth-panel"><p className="section-kicker">Selamat datang</p><h2>Masuk untuk melanjutkan</h2><p className="section-note">Gunakan akun UGM Anda untuk mengelola dokumen akreditasi.</p><div className="auth-tabs"><button className={mode === 'login' ? 'active' : ''} onClick={() => setMode('login')}>Masuk</button><button className={mode === 'register' ? 'active' : ''} onClick={() => setMode('register')}>Daftar akun baru</button></div>{mode === 'register' && <div className="field"><label htmlFor="acc-name">Nama lengkap</label><input id="acc-name" value={name} onChange={e => setName(e.target.value)} /></div>}<div className="field"><label htmlFor="acc-email">Email UGM</label><input id="acc-email" type="email" placeholder="nama@ugm.ac.id" aria-describedby="acc-email-hint" value={email} onChange={e => setEmail(e.target.value)} /><small id="acc-email-hint" className="field-hint">Hanya email @ugm.ac.id atau @mail.ugm.ac.id.</small></div><div className="field"><label htmlFor="acc-password">Password</label><input id="acc-password" type="password" value={password} onChange={e => setPassword(e.target.value)} /></div><button className="button auth-submit" onClick={submit}>{mode === 'login' ? 'Masuk' : 'Buat akun'}</button>{message && <Notice type={/^(Registrasi|Email ini sudah)/.test(message) ? 'info' : 'error'}>{message}</Notice>}</section></div>;
}

function AccreditationPage() {
  const [data, setData] = useState<AccreditationResult | null>(null); const [user, setUser] = useState<AuthUser | null | undefined>(undefined); const [error, setError] = useState('');
  // ?prodi=&dokumen= datang dari tombol "Lanjutkan" di halaman Profil Saya.
  const [params] = useSearchParams();
  const muatKatalog = () => getAccreditation().then(d => { setData(d); return d; });
  useEffect(() => {
    muatKatalog().catch(e => setError(pesanMuat(e, 'Data akreditasi')));
    const refresh = () => { accreditationMe().then(setUser).catch(() => setUser(null)); }; refresh(); window.addEventListener(AUTH_EVENT, refresh); return () => window.removeEventListener(AUTH_EVENT, refresh);
  }, []);
  if (error) return <AppShell><div className="content"><Notice type="error">{error}</Notice></div></AppShell>;
  if (!data || user === undefined) return <AppShell><div className="content loading">Memuat portal akreditasi...</div></AppShell>;
  if (!user) return <AppShell><div className="content"><AccreditationLogin onUser={setUser} next={params.get('next')} /></div></AppShell>;
  return <AppShell><AccreditationWorkspace catalog={data} user={user} onLogout={async () => { await accreditationLogout(); setUser(null); }} onCatalogChange={muatKatalog}
    initialProdi={params.get('prodi') ?? ''} initialDokumen={params.get('dokumen') === 'LKPS' ? 'LKPS' : 'LED'} /></AppShell>;
}

export default function App() {
  return <Routes>
    <Route path="/" element={<LandingPage />} />
    <Route path="/dampak" element={<DampakPage />} />
    {/* Route lama tetap hidup supaya tautan/bookmark lama tidak mati, tapi dialihkan ke
        anchor bagian di dalam halaman Dampak — dulu ini halaman terpisah, kini satu halaman. */}
    <Route path="/dampak-sdgs" element={<Navigate to={{ pathname: '/dampak', hash: '#dampak-sdgs' }} replace />} />
    <Route path="/sdgs" element={<Navigate to={{ pathname: '/dampak', hash: '#sdgs' }} replace />} />
    <Route path="/akreditasi" element={<AccreditationPage />} />
    <Route path="/profil" element={<AppShell><ProfilePage /></AppShell>} />
    <Route path="/admin" element={<AppShell><AdminPage /></AppShell>} />
    <Route path="*" element={<Navigate to="/" replace />} />
  </Routes>;
}