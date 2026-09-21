import { useEffect, useId, useMemo, useRef, useState } from 'react';

export type MultiOption = { value: string; label: string };

type Props = {
  id: string;
  label: string;
  options: MultiOption[];
  selected: string[];
  onChange: (next: string[]) => void;
  /** Teks tombol saat tidak ada yang dipilih (artinya: tanpa filter). */
  emptyLabel?: string;
  /** Tampilkan kolom cari; berguna untuk daftar panjang seperti unit kerja. */
  searchable?: boolean;
};

function summarize(options: MultiOption[], selected: string[], emptyLabel: string) {
  if (selected.length === 0) return emptyLabel;
  if (selected.length === 1) return options.find(option => option.value === selected[0])?.label ?? selected[0];
  return `${selected.length} dipilih`;
}

/** Dropdown pilihan-ganda berisi checkbox. Pengganti <select multiple> yang sulit dibaca dan dipakai. */
export function MultiSelect({ id, label, options, selected, onChange, emptyLabel = 'Semua', searchable = false }: Props) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const root = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const panelId = useId();
  const visible = useMemo(() => { const q = query.trim().toLowerCase(); return q ? options.filter(option => option.label.toLowerCase().includes(q)) : options; }, [options, query]);

  useEffect(() => {
    if (!open) return;
    function onPointerDown(event: PointerEvent) { if (root.current && !root.current.contains(event.target as Node)) setOpen(false); }
    document.addEventListener('pointerdown', onPointerDown);
    return () => document.removeEventListener('pointerdown', onPointerDown);
  }, [open]);
  useEffect(() => { if (!open) setQuery(''); }, [open]);

  function toggle(value: string) { onChange(selected.includes(value) ? selected.filter(item => item !== value) : [...selected, value]); }
  function close(returnFocus: boolean) { setOpen(false); if (returnFocus) trigger.current?.focus(); }

  // onBlur menutup hanya bila fokus pindah ke elemen lain di luar (Tab); klik di luar ditangani pointerdown di atas.
  // mousedown di panel dicegah mencuri fokus, kalau tidak klik pada label menutup panel sebelum klik tercatat.
  return <div className="field ms" ref={root} onKeyDown={event => { if (event.key === 'Escape' && open) { event.stopPropagation(); close(true); } }} onBlur={event => { const next = event.relatedTarget as Node | null; if (open && next && !root.current?.contains(next)) setOpen(false); }}>
    <label htmlFor={id}>{label}</label>
    <button ref={trigger} id={id} type="button" className={`ms__trigger ${selected.length ? 'has-value' : ''}`} aria-expanded={open} aria-controls={panelId} onClick={() => setOpen(current => !current)}>
      <span className="ms__summary">{summarize(options, selected, emptyLabel)}</span>
      <svg className="ms__chevron" viewBox="0 0 12 8" width="12" height="8" aria-hidden="true"><path d="M1 1.5 6 6.5 11 1.5" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" /></svg>
    </button>
    {open && <div className="ms__panel" id={panelId} role="group" aria-label={label} onMouseDown={event => { if (!(event.target as HTMLElement).closest('input[type="search"]')) event.preventDefault(); }}>
      {searchable && <input className="ms__search" type="search" autoFocus value={query} onChange={event => setQuery(event.target.value)} placeholder={`Cari ${label.toLowerCase()}...`} aria-label={`Cari ${label}`} />}
      <div className="ms__actions"><span aria-live="polite">{selected.length ? `${selected.length} dipilih` : emptyLabel}</span><button type="button" disabled={selected.length === 0} onClick={() => onChange([])}>Hapus pilihan</button></div>
      <ul className="ms__list">
        {visible.map(option => { const checked = selected.includes(option.value); return <li key={option.value}><label className={checked ? 'is-checked' : ''}><input type="checkbox" checked={checked} onChange={() => toggle(option.value)} /><span>{option.label}</span></label></li>; })}
        {visible.length === 0 && <li className="ms__empty">Tidak ada hasil.</li>}
      </ul>
    </div>}
  </div>;
}
