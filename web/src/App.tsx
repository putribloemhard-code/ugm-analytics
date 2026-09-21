import { FormEvent, useEffect, useRef, useState } from 'react';
import { Link, Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom';

import { accreditationLogin, accreditationLogout, accreditationMe, accreditationRegister, accreditationUpload, downloadReport, getAccreditation, getHomeSummary, getImpact, getMetadata, getNews, getSdgs, searchAnalytics, type AccreditationResult, type AnalyticsResult, type Metadata } from './lib/api';
import { assetUrl, CountUp, SiteShell, useInView } from './shell';

type FilterState = { yearFrom: string; yearTo: string; pillars: string[]; topics: string[]; sdgs: number[]; units: string[] };
const emptyFilters: FilterState = { yearFrom: '', yearTo: '', pillars: [], topics: [], sdgs: [], units: [] };

function AppShell({ children }: { children: React.ReactNode }) { return <SiteShell>{children}</SiteShell>; }

function PageHeader({ title, icon, caption }: { title: string; icon: string; caption?: string }) {
  return <header><h1 className="page-heading"><img src={assetUrl(`logo/${icon}`)} alt="" />{title}</h1>{caption && <p className="page-caption">{caption}</p>}</header>;
}

function Notice({ type, children }: { type: 'info' | 'warning' | 'error'; children: React.ReactNode }) {
  return <div className={`notice ${type}`} role={type === 'error' ? 'alert' : 'status'}>{children}</div>;
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
  return <section className="filter-panel" aria-label="Filter analisis"><div className="filter-heading"><div><p className="section-kicker">Kontrol analisis</p><h3>Filter data</h3></div><span className="filter-count">{activeCount ? `${activeCount} filter aktif` : 'Semua data'}</span></div><div className="year-range"><div className="range-label"><label htmlFor={`${idPrefix}-year-start`}>Rentang tahun</label><strong>{value.yearFrom} — {value.yearTo}</strong></div><div className="range-inputs"><input id={`${idPrefix}-year-start`} type="range" min={0} max={years.length - 1} value={startIndex} onChange={event => change({ ...value, yearFrom: years[Number(event.target.value)] })} /><input id={`${idPrefix}-year-end`} type="range" min={0} max={years.length - 1} value={endIndex} onChange={event => change({ ...value, yearTo: years[Math.max(startIndex, Number(event.target.value))] })} /></div></div><div className="filter-grid">{sdgMode ? <div className="field"><label htmlFor={`${idPrefix}-sdgs`}>SDG</label><select id={`${idPrefix}-sdgs`} multiple value={value.sdgs.map(String)} onChange={event => change({ ...value, sdgs: Array.from(event.target.selectedOptions).map(option => Number(option.value)) })}>{metadata.sdgs.map(sdg => <option key={sdg.id} value={sdg.id}>SDG {sdg.id} — {sdg.label}</option>)}</select></div> : <div className="field"><label htmlFor={`${idPrefix}-pillars`}>Dampak</label><select id={`${idPrefix}-pillars`} multiple value={value.pillars} onChange={event => change({ ...value, pillars: Array.from(event.target.selectedOptions).map(option => option.value) })}>{metadata.pillars.map(pillar => <option key={pillar}>{pillar}</option>)}</select></div>}{!sdgMode && <div className="field"><label htmlFor={`${idPrefix}-topics`}>Tema resmi Kepmen</label><select id={`${idPrefix}-topics`} multiple value={value.topics} onChange={event => change({ ...value, topics: Array.from(event.target.selectedOptions).map(option => option.value) })}>{topics.map(topic => <option key={topic.id} value={topic.id}>{topic.label} ({topic.pillar})</option>)}</select></div>}<div className="field"><label htmlFor={`${idPrefix}-units`}>Fakultas / Unit Kerja</label><select id={`${idPrefix}-units`} multiple value={value.units} onChange={event => change({ ...value, units: Array.from(event.target.selectedOptions).map(option => option.value) })}>{metadata.units.map(unit => <option key={unit.id} value={unit.id}>{unit.label}</option>)}</select></div></div><div className="action-row"><button className="button secondary" type="button" onClick={() => change({ yearFrom: metadata.years.min, yearTo: metadata.years.max, pillars: [], topics: [], sdgs: [], units: [] })}>Reset filter</button><span className="filter-hint">Pilih beberapa opsi dengan Cmd/Ctrl + klik.</span></div></section>;
}

function BarList({ title, rows, labelKey = 'label', valueKey = 'count', tone = 'navy' }: { title: string; rows: unknown[]; labelKey?: string; valueKey?: string; tone?: 'navy' | 'green' | 'orange' | 'blue' }) {
  const values = rows as Record<string, unknown>[];
  const max = Math.max(...values.map(row => Number(row[valueKey]) || 0), 1);
  return <section className="chart-card"><h3>{title}</h3>{values.length ? <div className="chart-list">{values.map((row, index) => <div className="chart-row" key={`${String(row[labelKey])}-${index}`}><span className="chart-label">{String(row[labelKey] ?? '-')}</span><div className={`chart-track ${tone}`} aria-label={`${String(row[labelKey])}: ${String(row[valueKey])}`}><div className="chart-bar" style={{ width: `${((Number(row[valueKey]) || 0) / max) * 100}%` }} /></div><span className="chart-value">{Number(row[valueKey] ?? 0).toLocaleString('id-ID')}</span></div>)}</div> : <Notice type="info">Belum ada data untuk bagian ini.</Notice>}</section>;
}

function LineChart({ title, rows }: { title: string; rows: unknown[] }) {
  const values = (rows as Record<string, unknown>[]).map(row => ({ label: String(row.year ?? row.month ?? ''), value: Number(row.count) || 0 }));
  const max = Math.max(...values.map(item => item.value), 1); const width = 640; const height = 210; const pad = 28;
  const points = values.map((item, index) => `${pad + (index * (width - pad * 2)) / Math.max(values.length - 1, 1)},${height - pad - (item.value / max) * (height - pad * 2)}`).join(' ');
  return <section className="chart-card chart-line-card"><h3>{title}</h3>{values.length ? <><svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={title}><polyline points={points} fill="none" stroke="var(--chart-primary)" strokeWidth="4" strokeLinecap="round" strokeLinejoin="round" />{values.map((item, index) => { const x = pad + (index * (width - pad * 2)) / Math.max(values.length - 1, 1); const y = height - pad - (item.value / max) * (height - pad * 2); return <g key={`${item.label}-${index}`}><circle cx={x} cy={y} r="5" fill="var(--gold)" /><title>{item.label}: {item.value.toLocaleString('id-ID')}</title><text x={x} y={height - 7} textAnchor="middle">{item.label}</text></g>; })}</svg><div className="chart-axis-note">Nilai maksimum: {max.toLocaleString('id-ID')}</div></> : <Notice type="info">Belum ada data untuk bagian ini.</Notice>}</section>;
}

function DonutChart({ title, rows }: { title: string; rows: unknown[] }) {
  const values = rows as Record<string, unknown>[]; const total = values.reduce((sum, row) => sum + (Number(row.count) || 0), 0); let offset = 0; const colors = ['var(--pillar-1)', 'var(--pillar-2)', 'var(--pillar-3)', 'var(--pillar-4)'];
  return <section className="chart-card donut-card"><h3>{title}</h3>{values.length && total ? <div className="donut-layout"><svg viewBox="0 0 120 120" role="img" aria-label={title}><circle cx="60" cy="60" r="43" fill="none" stroke="#e8edf3" strokeWidth="18" />{values.map((row, index) => { const pct = (Number(row.count) || 0) / total; const dash = pct * 270; const rotation = offset * 360 - 90; offset += pct; return <circle key={String(row.label ?? index)} cx="60" cy="60" r="43" fill="none" stroke={colors[index % colors.length]} strokeWidth="18" strokeDasharray={`${dash} ${270 - dash}`} transform={`rotate(${rotation} 60 60)`} />; })}<text x="60" y="57" textAnchor="middle" className="donut-total">{total.toLocaleString('id-ID')}</text><text x="60" y="70" textAnchor="middle" className="donut-caption">berita</text></svg><div className="donut-legend">{values.map((row, index) => <div key={String(row.label ?? index)}><i style={{ background: colors[index % colors.length] }} />{String(row.label ?? '-')} <b>{Number(row.count ?? 0).toLocaleString('id-ID')}</b></div>)}</div></div> : <Notice type="info">Belum ada data untuk bagian ini.</Notice>}</section>;
}

function ActivityHeatmap({ rows }: { rows: unknown[] }) {
  const values = rows as Record<string, unknown>[]; const grouped = new Map<string, number>(); values.forEach(row => grouped.set(String(row.month ?? ''), (grouped.get(String(row.month ?? '')) ?? 0) + (Number(row.count) || 0))); const max = Math.max(...grouped.values(), 1);
  return <section className="chart-card"><h3>Heatmap aktivitas per bulan</h3>{grouped.size ? <div className="heatmap">{Array.from(grouped.entries()).map(([month, count]) => <div key={month} className="heat-cell" style={{ opacity: .25 + count / max * .75 }} title={`${month}: ${count}`}><strong>{month}</strong><span>{count.toLocaleString('id-ID')}</span></div>)}</div> : <Notice type="info">Belum ada data bulanan.</Notice>}</section>;
}

function ChartGrid({ result }: { result: AnalyticsResult }) {
  const charts = result.charts as Record<string, unknown[]>;
  const yearly = (charts.yearly ?? []).slice().sort((a, b) => Number((a as Record<string, unknown>).year) - Number((b as Record<string, unknown>).year));
  const monthlyMap = new Map<string, number>();
  (charts.monthly ?? []).forEach(row => { const item = row as Record<string, unknown>; const month = String(item.month ?? ''); monthlyMap.set(month, (monthlyMap.get(month) ?? 0) + (Number(item.count) || 0)); });
  const monthly = Array.from(monthlyMap, ([month, count]) => ({ month, count }));
  return <div className="chart-grid"><DonutChart title="Komposisi pilar dampak" rows={charts.pillars ?? []} /><LineChart title="Tren berita tahunan" rows={yearly} /><BarList title="Ranking tema resmi Kepmen" rows={charts.topics ?? []} tone="blue" />{monthly.length > 0 && <><LineChart title="Tren aktivitas bulanan" rows={monthly} /><ActivityHeatmap rows={monthly} /></>}{result.mode !== 'impact' && <BarList title="Distribusi SDGs" rows={charts.sdgs ?? []} tone="green" />}</div>;
}

function Table({ title, rows }: { title: string; rows: unknown[] }) {
  const values = rows as Record<string, unknown>[];
  const columns = values.length ? Object.keys(values[0]) : [];
  return <section className="section"><h3>{title}</h3>{values.length ? <div className="data-table-wrap"><table><caption className="sr-only">{title}</caption><thead><tr>{columns.map(column => <th key={column}>{column.replaceAll('_', ' ')}</th>)}</tr></thead><tbody>{values.slice(0, 200).map((row, index) => <tr key={index}>{columns.map(column => <td key={column}>{Array.isArray(row[column]) ? row[column].join(', ') : String(row[column] ?? '')}</td>)}</tr>)}</tbody></table></div> : <Notice type="info">Tidak ada data untuk bagian ini.</Notice>}</section>;
}

function AnalyticsContent({ result }: { result: AnalyticsResult }) {
  const [tab, setTab] = useState('summary');
  const [news, setNews] = useState<{ rows: unknown[]; total: number } | null>(null);
  const [newsError, setNewsError] = useState('');
  const [page, setPage] = useState(1);
  const [reportError, setReportError] = useState('');
  const [reportBusy, setReportBusy] = useState(false);
  const tabs = Object.keys(result.tables);
  useEffect(() => { setPage(1); }, [result]);
  useEffect(() => { setNews(null); setNewsError(''); getNews({ mode: result.mode, year_from: result.filters.year_from as string, year_to: result.filters.year_to as string, pillars: result.filters.pillars as string[], topics: result.filters.topics as string[], sdgs: result.filters.sdgs as number[], units: result.filters.units as string[] }, page, 25).then(setNews).catch(() => setNewsError('Daftar berita belum dapat dimuat.')); }, [result, page]);
  const totalPages = news ? Math.max(1, Math.ceil(news.total / 25)) : 1;
  async function report() { setReportBusy(true); setReportError(''); try { const blob = await downloadReport({ mode: result.mode, ...result.filters }); const href = URL.createObjectURL(blob); const link = document.createElement('a'); link.href = href; link.download = `Laporan_UGM_Analytics_${result.mode}.docx`; link.click(); URL.revokeObjectURL(href); } catch { setReportError('Laporan belum dapat dibuat. Periksa koneksi API.'); } finally { setReportBusy(false); } }
  return <div className="analysis-dashboard"><section className="analysis-summary-grid">{Object.entries(result.summary).map(([label, value]) => <Metric key={label} label={label.replaceAll('_', ' ')} value={value} />)}</section><section className="insight insight--info"><div className="insight__label">Ringkasan analisis</div><p>{result.narrative}</p></section><div className="section tabs analysis-tabs" role="tablist" aria-label="Bagian analisis">{['summary', ...tabs].map(item => <button key={item} className={`tab ${tab === item ? 'active' : ''}`} role="tab" aria-selected={tab === item} onClick={() => setTab(item)}>{item === 'summary' ? 'Ringkasan' : item === 'news' ? 'Berita' : item.replaceAll('_', ' ')}</button>)}</div>{tab === 'summary' && <ChartGrid result={result} />}{tab !== 'summary' && <Table title={tab} rows={result.tables[tab] ?? []} />}<section className="section"><h3>Daftar berita</h3>{newsError ? <Notice type="error">{newsError}</Notice> : !news ? <div className="loading" role="status">Memuat daftar berita...</div> : <><Table title="Berita terpilih" rows={news.rows} /><div className="action-row"><button className="button secondary" disabled={page <= 1} onClick={() => setPage(current => current - 1)}>Halaman sebelumnya</button><span aria-live="polite">Halaman {page} dari {totalPages}</span><button className="button secondary" disabled={page >= totalPages} onClick={() => setPage(current => current + 1)}>Halaman berikutnya</button></div></>}</section><section className="section"><h3>Catatan metodologi</h3><ul>{result.caveats.map(caveat => <li key={caveat}>{caveat}</li>)}</ul></section><section className="section"><h3>Unduh laporan</h3><p className="section-note">Dokumen Word dibuat dari filter dan data yang divalidasi server.</p><button className="button" disabled={reportBusy} onClick={report}>{reportBusy ? 'Membuat laporan...' : 'Buat laporan Word'}</button>{reportError && <div className="section"><Notice type="error">{reportError}</Notice></div>}</section></div>;
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
      navigate(`/${result.page}?${params.toString()}`);
    } catch { setExplanation('Pencarian belum dapat diproses. Periksa koneksi API.'); }
  }
  const stats = summary ? [
    { label: 'Berita dianalisis', value: summary.total_berita },
    { label: 'Berita berdampak', value: summary.n_dampak },
    { label: 'Cakupan', value: `${Number(summary.cakupan_pct ?? 0).toFixed(1)}%` },
  ] : [];
  return <section className="cold-open" aria-labelledby="cold-open-title"><div className="cold-open__inner">
    <p className="eyebrow">Universitas Gadjah Mada · Kepmen 361/M/KEP/2025</p>
    {error ? <Notice type="error">{error}</Notice> : <ul className="cold-open__stats" aria-label="Ringkasan data">{summary ? stats.map(stat => <li key={stat.label}><span className="cold-open__number"><CountUp value={stat.value} /></span><span className="cold-open__label">{stat.label}</span></li>) : <li className="cold-open__loading" role="status">Memuat ringkasan data...</li>}</ul>}
    <h1 id="cold-open-title">Analisis <span>Dampak UGM</span></h1>
    <p className="cold-open__statement">Ruang baca untuk memeriksa jejak dampak sosial, ekonomi, dan lingkungan UGM melalui pemberitaan publik dan kerangka SDGs.</p>
    <form className="hero-search" onSubmit={search}><label className="sr-only" htmlFor="analysis-search">Mau analisis apa?</label><input id="analysis-search" value={query} onChange={event => setQuery(event.target.value)} placeholder="Contoh: energi, SDG 7, atau 2024" /><button type="submit">Cari analisis</button></form>
    <p className="hero-hint">Cari tema, pilar, SDG, atau tahun. Hasil akan membuka bagian analisis dengan filter terkait.</p>
    {explanation && <p className="hero-note" role="status">{explanation}</p>}
    {summary && <p className="cold-open__context">Data terakhir: {summary.updated_at ?? 'waktu pembaruan belum tersedia'}.</p>}
    <Link className="cold-open__continue" to={{ pathname: '/', hash: '#ringkasan' }}>Jelajahi laporan selengkapnya <span aria-hidden="true">↓</span></Link>
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
  const [result, setResult] = useState<AnalyticsResult | null>(null);
  const [error, setError] = useState('');
  useEffect(() => { if (metadata) setFilters(seeded ? queryFilters(metadata) : defaultFilters(metadata)); }, [metadata, seeded, seedKey]);
  useEffect(() => {
    if (!active || !metadata || !filters.yearFrom) return;
    let cancelled = false; setResult(null); setError('');
    const load = def.mode === 'sdgs' ? getSdgs({ year_from: filters.yearFrom, year_to: filters.yearTo, sdgs: filters.sdgs, units: filters.units }) : getImpact({ year_from: filters.yearFrom, year_to: filters.yearTo, pillars: filters.pillars, topics: filters.topics, sdgs: filters.sdgs, units: filters.units }, def.mode as 'impact' | 'impact-sdgs');
    load.then(value => { if (!cancelled) setResult(value); }).catch(() => { if (!cancelled) setError('Data analisis belum dapat dimuat. Periksa koneksi API.'); });
    return () => { cancelled = true; };
  }, [active, metadata, filters, def.mode]);
  const failure = metadataError || error;
  return <section ref={ref} id={def.id} className={`story-scene ${tint ? 'story-scene--tint' : ''}`} aria-labelledby={`${def.id}-title`}><div className="story-scene__inner">
    <header className="story-scene__header"><p className={`eyebrow eyebrow--${def.accent}`}><img src={assetUrl(`logo/${def.icon}`)} alt="" />{def.eyebrow}</p><h2 id={`${def.id}-title`}>{def.title}</h2><p className="story-scene__deck">{def.caption}</p></header>
    {failure ? <Notice type="error">{failure}</Notice> : !active || !metadata ? <div className="loading loading--scene" role="status">Bagian ini dimuat saat Anda menggulir ke sini...</div> : <>
      <Filters metadata={metadata} value={filters} onChange={setFilters} sdgMode={!!def.sdgMode} idPrefix={def.id} syncUrl={seeded} />
      {!result ? <div className="loading" role="status">Memuat hasil analisis...</div> : <><AnalyticsContent result={result} /><p className="footer-note">Data terakhir: {result.data_as_of ?? 'waktu pembaruan belum tersedia'}.</p></>}
    </>}
  </div></section>;
}

function ScrollReport({ target }: { target?: AnalysisDef['id'] }) {
  const location = useLocation();
  const [summary, setSummary] = useState<Record<string, string | number | null> | null>(null);
  const [summaryError, setSummaryError] = useState('');
  const [metadata, setMetadata] = useState<Metadata | null>(null);
  const [metadataError, setMetadataError] = useState('');
  useEffect(() => { getHomeSummary().then(setSummary).catch(() => setSummaryError('Ringkasan data belum dapat dimuat. Periksa koneksi API.')); getMetadata().then(setMetadata).catch(() => setMetadataError('Metadata filter belum dapat dimuat.')); }, []);
  useEffect(() => {
    const id = location.hash ? location.hash.slice(1) : target;
    if (!id) { window.scrollTo(0, 0); return; }
    // Instan, bukan smooth: bagian di antaranya dimuat lazy saat terlewati dan akan menggeser posisi tujuan.
    const timer = window.setTimeout(() => document.getElementById(id)?.scrollIntoView({ block: 'start' }), 60);
    return () => window.clearTimeout(timer);
  }, [location.key, location.hash, target]);
  return <AppShell><Hero summary={summary} error={summaryError} />
    <ChapterIntro id="ringkasan" number="Bagian I" title="Tiga Jalur untuk Membaca Dampak" description="Setiap jalur memakai sumber dan metode yang berbeda. Pilih jalur yang paling sesuai dengan pertanyaan Anda, bukan sekadar grafik yang ingin dilihat.">
      <div className="route-grid">{analysisSections.map(def => <Link className={`route-card ${def.accent}`} to={{ pathname: '/', hash: `#${def.id}` }} key={def.id}><div className="route-card-top"><img src={assetUrl(`logo/${def.icon}`)} alt="" /><span>{def.eyebrow}</span></div><h3>{routeTitle[def.id]}</h3><p>{def.description}</p><span className="route-action">Buka bagian ini <b aria-hidden="true">↓</b></span></Link>)}</div>
    </ChapterIntro>
    <ChapterIntro number="Bagian II" title="Analisis Data Berita" description="Tiap bagian punya filter sendiri. Angka, grafik, tabel, dan laporan Word mengikuti filter yang aktif." />
    {analysisSections.map((def, index) => <AnalysisScene key={def.id} def={def} metadata={metadata} metadataError={metadataError} seeded={target === def.id} seedKey={location.key} tint={index % 2 === 1} />)}
    <ChapterIntro id="metodologi" number="Bagian III" title="Data & Metodologi" description="Angka perlu konteks. Tag dampak adalah lower-bound berbasis keyword dan sumber yang tersedia. Pemetaan Dampak × SDGs mengikuti tema resmi Kepmen, sedangkan bagian SDGs menggunakan pencocokan langsung yang menjawab pertanyaan berbeda.">
      <p className="chapter-bridge">{summary ? `Data terakhir: ${summary.updated_at ?? 'waktu pembaruan belum tersedia'}.` : 'Memuat status data...'} Catatan metodologi rinci ditampilkan di bawah tiap bagian analisis.</p>
      <Link className="chapter-cta" to="/akreditasi">Buka Portal Akreditasi <span aria-hidden="true">›</span></Link>
    </ChapterIntro>
  </AppShell>;
}

function AccreditationLogin({ onUser }: { onUser: (user: { id: number; email: string; nama: string; is_admin: boolean }) => void }) {
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [email, setEmail] = useState(''); const [name, setName] = useState(''); const [password, setPassword] = useState(''); const [message, setMessage] = useState('');
  async function submit() { setMessage(''); try { if (mode === 'register') { await accreditationRegister(email, name, password); setMode('login'); setMessage('Registrasi berhasil. Silakan masuk.'); } else onUser(await accreditationLogin(email, password)); } catch (e) { setMessage(e instanceof Error ? e.message : 'Autentikasi gagal'); } }
  return <div className="accreditation-gate"><section className="accreditation-hero"><div className="brand-chip"><img src={assetUrl('logo/LogoUGM.png')} alt="" /> Universitas Gadjah Mada</div><h1>Portal <span>Akreditasi</span></h1><p>Kelola kelengkapan data LED & LKPS, ekstrak dokumen pendukung, dan susun laporan akreditasi program studi dalam satu tempat.</p></section><section className="auth-panel"><p className="section-kicker">Selamat datang 👋</p><h2>Masuk untuk melanjutkan</h2><p className="section-note">Gunakan akun UGM Anda untuk mengelola dokumen akreditasi.</p><div className="auth-tabs"><button className={mode === 'login' ? 'active' : ''} onClick={() => setMode('login')}>Masuk</button><button className={mode === 'register' ? 'active' : ''} onClick={() => setMode('register')}>Daftar akun baru</button></div>{mode === 'register' && <div className="field"><label htmlFor="acc-name">Nama lengkap</label><input id="acc-name" value={name} onChange={e => setName(e.target.value)} /></div>}<div className="field"><label htmlFor="acc-email">Email UGM</label><input id="acc-email" type="email" placeholder="nama@ugm.ac.id" value={email} onChange={e => setEmail(e.target.value)} /></div><div className="field"><label htmlFor="acc-password">Password</label><input id="acc-password" type="password" value={password} onChange={e => setPassword(e.target.value)} /></div><button className="button auth-submit" onClick={submit}>{mode === 'login' ? 'Masuk' : 'Buat akun'}</button>{message && <Notice type={message.startsWith('Registrasi') ? 'info' : 'error'}>{message}</Notice>}</section></div>;
}

function AccreditationPage() {
  const [data, setData] = useState<AccreditationResult | null>(null); const [user, setUser] = useState<{ id: number; email: string; nama: string; is_admin: boolean } | null>(null); const [error, setError] = useState('');
  const [prodi, setProdi] = useState(''); const [document, setDocument] = useState<'LED' | 'LKPS'>('LED'); const [group, setGroup] = useState(''); const [file, setFile] = useState<File | null>(null); const [uploadMessage, setUploadMessage] = useState('');
  useEffect(() => { getAccreditation().then(d => { setData(d); if (d.programs[0]) setProdi(String(d.programs[0].slug)); }).catch(() => setError('Data akreditasi belum dapat dimuat.')); accreditationMe().then(setUser); }, []);
  if (error) return <AppShell><div className="content"><Notice type="error">{error}</Notice></div></AppShell>;
  if (!data) return <AppShell><div className="content loading">Memuat portal akreditasi...</div></AppShell>;
  if (!user) return <AppShell><div className="content"><PageHeader title="Akreditasi" icon="certificate.png" caption="Portal kelengkapan data LED & LKPS." /><AccreditationLogin onUser={setUser} /></div></AppShell>;
  const items = document === 'LED' ? data.requirements.led : data.requirements.lkps; const groups = [...new Set(items.map(item => String(item.group)))]; const activeGroup = group || groups[0] || ''; const visible = items.filter(item => String(item.group) === activeGroup); const filled = new Set(data.manual.filter(row => String(row.prodi_id) === prodi).map(row => String(row.item_id))); const done = items.filter(item => filled.has(String(item.id))).length; const percent = items.length ? Math.round(done / items.length * 100) : 0;
  async function upload() { if (!file || !prodi) return; try { await accreditationUpload(prodi, file); setUploadMessage('File berhasil disimpan.'); setFile(null); } catch (e) { setUploadMessage(e instanceof Error ? e.message : 'Upload gagal'); } }
  return <AppShell><div className="content accreditation-workspace"><div className="workspace-head"><div><PageHeader title="Akreditasi" icon="certificate.png" caption="Kelengkapan data LED & LKPS — instrumen akreditasi Program Studi." /></div><div className="user-chip">{user.nama}<button onClick={async () => { await accreditationLogout(); setUser(null); }}>Keluar</button></div></div><section className="accreditation-selectors"><div className="field"><label>Fakultas & Program Studi</label><select value={prodi} onChange={e => setProdi(e.target.value)}>{data.programs.map(p => <option key={String(p.id)} value={String(p.slug)}>{String(p.fakultas)} — {String(p.nama)}</option>)}</select></div><div className="field"><label>Dokumen</label><select value={document} onChange={e => { setDocument(e.target.value as 'LED' | 'LKPS'); setGroup(''); }}><option value="LED">📘 LED — Laporan Evaluasi Diri</option><option value="LKPS">📗 LKPS — Laporan Kinerja Program Studi</option></select></div></section><section className="progress-overview"><div className="progress-card"><span>Total item</span><strong>{items.length}</strong><small>{document}</small></div><div className="progress-card"><span>Terisi</span><strong>{done}/{items.length}</strong><small>{percent}% kelengkapan</small></div><div className="progress-card"><span>Perlu verifikasi</span><strong>{items.length - done}</strong><small>review manual</small></div><div className="progress-card"><span>Upload</span><strong>{data.uploads.filter(row => String(row.prodi_id) === prodi).length}</strong><small>dokumen tersimpan</small></div></section><div className="completion-line"><div><b>Kelengkapan keseluruhan: {done}/{items.length} item ({percent}%)</b><span> · sumber data resmi tersimpan setelah konfirmasi</span></div><div className="progress-track"><div style={{ width: `${percent}%` }} /></div></div><section className="upload-workflow"><div><p className="section-kicker">Dokumen pendukung</p><h2>Upload File Pendukung</h2><p>PDF, DOCX, atau XLSX — maksimal 25 MB per file. Hasil ekstraksi akan menjadi preview dan tetap perlu diverifikasi sebelum menjadi data resmi.</p></div><div className="upload-controls"><input type="file" accept=".pdf,.docx,.xlsx" onChange={e => setFile(e.target.files?.[0] ?? null)} /><button className="button" disabled={!file} onClick={upload}>Upload</button>{uploadMessage && <span role="status">{uploadMessage}</span>}</div></section><section className="section requirement-section"><div className="section-title-row"><div><p className="section-kicker">Kelengkapan Data {document}</p><h2>Struktur dokumen akreditasi</h2></div><span className="status-pill">{done}/{items.length} terisi</span></div><div className="accreditation-tabs">{groups.map(g => <button key={g} className={g === activeGroup ? 'active' : ''} onClick={() => setGroup(g)}>{document === 'LED' ? `Kriteria ${g}` : `Bagian ${g}`}</button>)}</div><div className="requirement-list">{visible.map(item => <article className={`requirement-row ${filled.has(String(item.id)) ? 'complete' : ''}`} key={String(item.id)}><div className="requirement-status">{filled.has(String(item.id)) ? '✓' : '!'}</div><div><h3>{String(item.name)}</h3><p>{String(item.description)}</p><small>{String(item.type)} · {String(item.status)}</small></div><span className="requirement-action">{filled.has(String(item.id)) ? 'Tersimpan' : 'Perlu input'}</span></article>)}</div></section><Notice type="info">Fase ini sudah mengikuti alur referensi: selector dokumen, progress, upload, dan checklist per Kriteria/Bagian. Ekstraksi AI, tabel editable, review kutipan, dan generate Word menjadi tahap berikutnya.</Notice></div></AppShell>;
}

export default function App() { return <Routes><Route path="/" element={<ScrollReport />} /><Route path="/dampak" element={<ScrollReport target="dampak" />} /><Route path="/dampak-sdgs" element={<ScrollReport target="dampak-sdgs" />} /><Route path="/sdgs" element={<ScrollReport target="sdgs" />} /><Route path="/akreditasi" element={<AccreditationPage />} /><Route path="*" element={<Navigate to="/" replace />} /></Routes>; }