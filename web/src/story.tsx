import { useMemo, useState, type ReactNode } from 'react';

import type { Chart, StoryTable } from './lib/api';

/* ------------------------------------------------------------------ warna ---- */
const seriesColor = (index: number) => `var(--series-${(index % 8) + 1})`;
/** Warna tetap per dampak agar konsisten di semua chart; kategori lain mengikuti urutan kemunculan. */
const pillarColor: Record<string, string> = { Lingkungan: 'var(--series-2)', Ekonomi: 'var(--series-3)', Sosial: 'var(--series-4)' };
function groupColors(groups: (string | null | undefined)[]) {
  const map = new Map<string, string>(); let next = 0;
  for (const group of groups) { if (!group || map.has(group)) continue; map.set(group, pillarColor[group] ?? seriesColor(next++)); }
  return map;
}

const fmt = (value: unknown) => typeof value === 'number' ? value.toLocaleString('id-ID') : String(value ?? '');
const naturalSort = (a: string, b: string) => a.localeCompare(b, undefined, { numeric: true });

/* -------------------------------------------------- data tabel & CSV chart ---- */
type Column = { key: string; label: string };
type TableModel = { columns: Column[]; rows: Record<string, unknown>[] };

/** Bentuk tabel dari data chart -- dipakai untuk 'Lihat tabel data' (aksesibel) dan 'Unduh CSV'. */
export function chartToTable(chart: Chart): TableModel {
  const data = chart.data as any;
  switch (chart.kind) {
    case 'bar': {
      const grouped = (data as { group?: string | null }[]).some(row => row.group);
      return { columns: [{ key: 'label', label: 'Label' }, ...(grouped ? [{ key: 'group', label: 'Kelompok' }] : []), { key: 'value', label: 'Jumlah' }], rows: data as Record<string, unknown>[] };
    }
    case 'line': {
      const xs = [...new Set<string>((data.series as { points: { x: string }[] }[]).flatMap(series => series.points.map(point => point.x)))].sort(naturalSort);
      const rows = xs.map(x => { const row: Record<string, unknown> = { x }; for (const series of data.series) row[series.name] = series.points.find((point: { x: string; y: number }) => point.x === x)?.y ?? 0; return row; });
      return { columns: [{ key: 'x', label: 'Periode' }, ...data.series.map((series: { name: string }) => ({ key: series.name, label: series.name }))], rows };
    }
    case 'stacked_bar': {
      const rows = (data.x as string[]).map((x, i) => { const row: Record<string, unknown> = { x }; for (const series of data.series) row[series.name] = series.values[i] ?? 0; return row; });
      return { columns: [{ key: 'x', label: 'Periode' }, ...data.series.map((series: { name: string }) => ({ key: series.name, label: series.name }))], rows };
    }
    case 'heatmap': {
      const rows = (data.rows as string[]).map((label, i) => { const row: Record<string, unknown> = { label }; (data.cols as string[]).forEach((col, j) => { row[col] = data.values[i]?.[j] ?? 0; }); return row; });
      return { columns: [{ key: 'label', label: '' }, ...(data.cols as string[]).map(col => ({ key: col, label: col }))], rows };
    }
    case 'combo': {
      const rows = (data.x as string[]).map((x, i) => ({ x, bars: data.bars.values[i], line: data.line.values[i] }));
      return { columns: [{ key: 'x', label: 'Periode' }, { key: 'bars', label: data.bars.name }, { key: 'line', label: data.line.name }], rows };
    }
  }
}

function isEmpty(chart: Chart) {
  const data = chart.data as any;
  if (!data) return true;
  switch (chart.kind) {
    case 'bar': return data.length === 0;
    case 'line': return !data.series?.length;
    case 'stacked_bar': return !data.x?.length;
    case 'heatmap': return !data.rows?.length;
    case 'combo': return !data.x?.length;
  }
}

export function downloadCsv(filename: string, columns: Column[], rows: Record<string, unknown>[]) {
  const escape = (value: unknown) => { const text = String(value ?? ''); return /[",\r\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text; };
  // BOM di depan supaya Excel membaca UTF-8 dengan benar.
  const csv = '﻿' + [columns.map(column => escape(column.label)).join(','), ...rows.map(row => columns.map(column => escape(row[column.key])).join(','))].join('\r\n');
  const href = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }));
  const link = document.createElement('a'); link.href = href; link.download = filename; link.click(); URL.revokeObjectURL(href);
}

/* ------------------------------------------------------------- tabel data ---- */
export function DataTable({ title, columns, rows, note, caption }: { title?: string; columns: Column[]; rows: Record<string, unknown>[]; note?: string | null; caption?: string }) {
  return <div className="story-table">
    {title && <h4>{title}</h4>}
    {rows.length ? <div className="data-table-wrap"><table><caption className="sr-only">{caption ?? title}</caption><thead><tr>{columns.map(column => <th key={column.key}>{column.label}</th>)}</tr></thead><tbody>{rows.slice(0, 200).map((row, index) => <tr key={index}>{columns.map(column => <td key={column.key}>{fmt(row[column.key])}</td>)}</tr>)}</tbody></table></div> : <p className="chart-empty">Tidak ada data untuk bagian ini.</p>}
    {note && <p className="chart-note">{note}</p>}
  </div>;
}

export function StoryTableView({ table }: { table: StoryTable }) {
  const [open, setOpen] = useState(true);
  return <div className="story-table-block">
    <DataTable title={open ? table.title : undefined} columns={table.columns} rows={table.rows} note={open ? table.note : null} caption={table.title} />
    {table.insight && <Insight>{table.insight}</Insight>}
    <div className="chart-frame__actions"><button type="button" className="link-button" disabled={!table.rows.length} onClick={() => downloadCsv(`${table.id}.csv`, table.columns, table.rows)}>Unduh CSV</button></div>
  </div>;
}

/* -------------------------------------------------------------- legenda ---- */
function Legend({ items, hidden, onToggle }: { items: { name: string; color: string }[]; hidden?: Set<string>; onToggle?: (name: string) => void }) {
  return <ul className="chart-legend">{items.map(item => <li key={item.name}>{onToggle
    ? <button type="button" aria-pressed={!hidden?.has(item.name)} className={hidden?.has(item.name) ? 'is-off' : ''} onClick={() => onToggle(item.name)}><i style={{ background: item.color }} />{item.name}</button>
    : <span><i style={{ background: item.color }} />{item.name}</span>}</li>)}</ul>;
}

function useToggleSet() {
  const [hidden, setHidden] = useState<Set<string>>(new Set());
  return [hidden, (name: string) => setHidden(current => { const next = new Set(current); if (next.has(name)) next.delete(name); else next.add(name); return next; })] as const;
}

/* -------------------------------------------------------- sumbu skala SVG ---- */
function niceMax(value: number) {
  if (value <= 0) return 1;
  const exp = Math.pow(10, Math.floor(Math.log10(value))); const frac = value / exp;
  return (frac <= 1 ? 1 : frac <= 2 ? 2 : frac <= 5 ? 5 : 10) * exp;
}
const W = 720, H = 300, PAD = { l: 52, r: 16, t: 14, b: 40 };
const plotW = W - PAD.l - PAD.r, plotH = H - PAD.t - PAD.b;

function Axes({ max, labels, skip }: { max: number; labels: string[]; skip: number }) {
  const ticks = [0, .25, .5, .75, 1];
  return <g>
    {ticks.map(t => <g key={t}><line x1={PAD.l} x2={W - PAD.r} y1={PAD.t + plotH * (1 - t)} y2={PAD.t + plotH * (1 - t)} className="axis-grid" /><text x={PAD.l - 8} y={PAD.t + plotH * (1 - t) + 3} textAnchor="end" className="axis-label">{Math.round(max * t).toLocaleString('id-ID')}</text></g>)}
    {labels.map((label, i) => i % skip === 0 && <text key={i} x={PAD.l + (plotW * (i + .5)) / labels.length} y={H - PAD.b + 16} textAnchor="middle" className="axis-label">{label}</text>)}
  </g>;
}

/* ---------------------------------------------------------------- bar ---- */
function BarView({ chart }: { chart: Chart }) {
  const rows = chart.data as { label: string; value: number; group?: string | null; detail?: string | null }[];
  const colors = useMemo(() => groupColors(rows.map(row => row.group)), [rows]);
  const max = Math.max(...rows.map(row => row.value), 1);
  const color = (row: { group?: string | null }) => (row.group ? colors.get(row.group) : undefined) ?? 'var(--chart-primary)';
  const legend = [...colors].map(([name, value]) => ({ name, color: value }));
  if (chart.orientation === 'v') {
    return <div><div className="vbars" role="img" aria-label={chart.title}>{rows.map(row => <div className="vbars__col" key={row.label} title={`${row.detail ?? row.label}: ${fmt(row.value)}`}><span className="vbars__value">{fmt(row.value)}</span><div className="vbars__bar" style={{ height: `${(row.value / max) * 100}%`, background: color(row) }} /><span className="vbars__label">{row.label}</span></div>)}</div>{legend.length > 0 && <Legend items={legend} />}</div>;
  }
  return <div><div className="chart-list" role="img" aria-label={chart.title}>{rows.map((row, index) => <div className="chart-row" key={`${row.label}-${index}`}><span className="chart-label">{row.label}</span><div className="chart-track" title={`${row.detail ?? row.label}: ${fmt(row.value)}`}><div className="chart-bar" style={{ width: `${(row.value / max) * 100}%`, background: color(row) }} /></div><span className="chart-value">{fmt(row.value)}</span></div>)}</div>{legend.length > 0 && <Legend items={legend} />}</div>;
}

/* --------------------------------------------------------------- line ---- */
function LineView({ chart }: { chart: Chart }) {
  const series = (chart.data as { series: { name: string; points: { x: string; y: number }[] }[] }).series;
  const [hidden, toggle] = useToggleSet();
  const xs = useMemo(() => [...new Set(series.flatMap(item => item.points.map(point => point.x)))].sort(naturalSort), [series]);
  const visible = series.filter(item => !hidden.has(item.name));
  const max = niceMax(Math.max(...visible.flatMap(item => item.points.map(point => point.y)), 1));
  const xAt = (x: string) => PAD.l + (plotW * (xs.indexOf(x) + .5)) / xs.length;
  const yAt = (y: number) => PAD.t + plotH * (1 - y / max);
  return <div>
    <svg viewBox={`0 0 ${W} ${H}`} className="chart-svg" role="img" aria-label={chart.title}>
      <Axes max={max} labels={xs} skip={Math.ceil(xs.length / 12)} />
      {series.map((item, index) => hidden.has(item.name) ? null : <g key={item.name} style={{ color: seriesColor(index) }}>
        <polyline fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinejoin="round" strokeLinecap="round" points={[...item.points].sort((a, b) => naturalSort(a.x, b.x)).map(point => `${xAt(point.x)},${yAt(point.y)}`).join(' ')} />
        {item.points.map(point => <circle key={point.x} cx={xAt(point.x)} cy={yAt(point.y)} r="3.5" fill="currentColor"><title>{`${item.name} — ${point.x}: ${fmt(point.y)}`}</title></circle>)}
      </g>)}
    </svg>
    {series.length > 1 && <Legend items={series.map((item, index) => ({ name: item.name, color: seriesColor(index) }))} hidden={hidden} onToggle={toggle} />}
  </div>;
}

/* ------------------------------------------------------- stacked & combo ---- */
function StackedView({ chart }: { chart: Chart }) {
  const data = chart.data as { x: string[]; series: { name: string; values: number[] }[] };
  const [hidden, toggle] = useToggleSet();
  const visible = data.series.filter(item => !hidden.has(item.name));
  const totals = data.x.map((_, i) => visible.reduce((sum, item) => sum + (item.values[i] ?? 0), 0));
  const max = niceMax(Math.max(...totals, 1));
  const slot = plotW / data.x.length, bar = Math.min(slot * .7, 46);
  return <div>
    <svg viewBox={`0 0 ${W} ${H}`} className="chart-svg" role="img" aria-label={chart.title}>
      <Axes max={max} labels={data.x} skip={Math.ceil(data.x.length / 12)} />
      {data.x.map((x, i) => { let acc = 0; return <g key={x}>{data.series.map((item, index) => { if (hidden.has(item.name)) return null; const v = item.values[i] ?? 0; const h = (v / max) * plotH; const y = PAD.t + plotH - acc - h; acc += h; return v > 0 ? <rect key={item.name} x={PAD.l + slot * i + (slot - bar) / 2} y={y} width={bar} height={h} fill={seriesColor(index)}><title>{`${item.name} — ${x}: ${fmt(v)}`}</title></rect> : null; })}</g>; })}
    </svg>
    <Legend items={data.series.map((item, index) => ({ name: item.name, color: seriesColor(index) }))} hidden={hidden} onToggle={toggle} />
  </div>;
}

function ComboView({ chart }: { chart: Chart }) {
  const data = chart.data as { x: string[]; bars: { name: string; values: number[] }; line: { name: string; values: number[] } };
  const max = niceMax(Math.max(...data.bars.values, ...data.line.values, 1));
  const slot = plotW / data.x.length, bar = Math.min(slot * .7, 46);
  const yAt = (v: number) => PAD.t + plotH * (1 - v / max);
  return <div>
    <svg viewBox={`0 0 ${W} ${H}`} className="chart-svg" role="img" aria-label={chart.title}>
      <Axes max={max} labels={data.x} skip={Math.ceil(data.x.length / 12)} />
      {data.bars.values.map((v, i) => <rect key={i} x={PAD.l + slot * i + (slot - bar) / 2} y={yAt(v)} width={bar} height={(v / max) * plotH} fill="var(--series-1)" opacity=".35"><title>{`${data.bars.name} — ${data.x[i]}: ${fmt(v)}`}</title></rect>)}
      <polyline fill="none" stroke="var(--series-3)" strokeWidth="2.5" strokeLinejoin="round" points={data.line.values.map((v, i) => `${PAD.l + slot * (i + .5)},${yAt(v)}`).join(' ')} />
      {data.line.values.map((v, i) => <circle key={i} cx={PAD.l + slot * (i + .5)} cy={yAt(v)} r="3.5" fill="var(--series-3)"><title>{`${data.line.name} — ${data.x[i]}: ${fmt(v)}`}</title></circle>)}
    </svg>
    <Legend items={[{ name: data.bars.name, color: 'var(--series-1)' }, { name: data.line.name, color: 'var(--series-3)' }]} />
  </div>;
}

/* ------------------------------------------------------------- heatmap ---- */
function HeatmapView({ chart }: { chart: Chart }) {
  const data = chart.data as { rows: string[]; cols: string[]; values: number[][] };
  const max = Math.max(...data.values.flat(), 1);
  return <div className="heatmap-scroll" role="img" aria-label={chart.title}><table className="heatmap-table"><thead><tr><th />{data.cols.map(col => <th key={col}>{col}</th>)}</tr></thead><tbody>{data.rows.map((row, i) => <tr key={row}><th scope="row">{row}</th>{data.cols.map((col, j) => { const v = data.values[i]?.[j] ?? 0; const pct = Math.round((v / max) * 100); return <td key={col} title={`${row} × ${col}: ${fmt(v)}`} style={{ background: v ? `color-mix(in srgb, var(--chart-primary) ${Math.max(pct, 8)}%, var(--surface-card))` : undefined, color: pct > 55 ? '#fff' : undefined }}>{v ? fmt(v) : ''}</td>; })}</tr>)}</tbody></table></div>;
}

/* --------------------------------------------------- bingkai chart utama ---- */
export function Insight({ label = 'Insight', children }: { label?: string; children: ReactNode }) {
  return <aside className="insight insight--info"><div className="insight__label">{label}</div><p>{children}</p></aside>;
}

export function ChartFrame({ chart }: { chart: Chart }) {
  const [asTable, setAsTable] = useState(false);
  const empty = isEmpty(chart);
  const table = useMemo(() => (empty ? null : chartToTable(chart)), [chart, empty]);
  const wide = chart.kind !== 'bar' || (chart.orientation === 'v' && (chart.data as unknown[]).length > 6);
  return <figure className={`chart-frame ${wide ? 'chart-frame--wide' : ''}`}>
    <figcaption><h4>{chart.title}</h4></figcaption>
    {empty ? <p className="chart-empty">Belum ada data untuk filter ini.</p> : <>
      <div className="chart-frame__plot">{chart.kind === 'bar' ? <BarView chart={chart} /> : chart.kind === 'line' ? <LineView chart={chart} /> : chart.kind === 'stacked_bar' ? <StackedView chart={chart} /> : chart.kind === 'heatmap' ? <HeatmapView chart={chart} /> : <ComboView chart={chart} />}</div>
      {chart.insight && <Insight>{chart.insight}</Insight>}
      {chart.note && <p className="chart-note">{chart.note}</p>}
      <div className="chart-frame__actions">
        <button type="button" className="link-button" aria-expanded={asTable} onClick={() => setAsTable(value => !value)}>{asTable ? 'Sembunyikan tabel data' : 'Lihat tabel data'}</button>
        <button type="button" className="link-button" onClick={() => table && downloadCsv(`${chart.id}.csv`, table.columns, table.rows)}>Unduh CSV</button>
      </div>
      {asTable && table && <DataTable columns={table.columns} rows={table.rows} caption={`Data: ${chart.title}`} />}
    </>}
  </figure>;
}

export function ChartGrid({ charts }: { charts: Chart[] }) {
  return <div className="story-charts">{charts.map(chart => <ChartFrame key={chart.id} chart={chart} />)}</div>;
}
