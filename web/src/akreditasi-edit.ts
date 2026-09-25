import { useEffect, useMemo, useRef, useState } from 'react';

import { saveAccreditationItem, type ItemRow, type WorkspaceItem } from './lib/api';

/* Bagian bersama ruang kerja akreditasi: dipakai editor tabel (kartu item) dan review dokumen,
   supaya keduanya menyimpan ke data yang sama dengan aturan yang sama. */

export function waktu(iso: string | null): string {
  if (!iso) return '-';
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString('id-ID', { dateStyle: 'medium', timeStyle: 'short' });
}

export function pesan(e: unknown, cadangan: string): string {
  return e instanceof Error && e.message ? e.message : cadangan;
}

export function barisKosong(kolom: string[]): ItemRow { return Object.fromEntries(kolom.map(k => [k, ''])); }

/** State edit satu item laporan: baris isian, tanda belum disimpan, dan simpan ke server.
 *  Kalau data server berubah (disimpan staf lain / hasil ekstraksi baru) saat user sedang
 *  mengedit, isian user tidak ditimpa -- hanya ditandai `basi` supaya user memilih sendiri. */
export function useItemEditor(item: WorkspaceItem, laporanId: number, onSaved: () => void) {
  const tanda = useMemo(() => JSON.stringify([item.updated_at, item.rows]), [item]);
  const [rows, setRows] = useState<ItemRow[]>(item.rows);
  const [dirty, setDirty] = useState(false);
  const [basi, setBasi] = useState(false);
  const [status, setStatus] = useState<{ type: 'info' | 'error'; text: string } | null>(null);
  const [sibuk, setSibuk] = useState(false);
  const tandaTerakhir = useRef(tanda);

  useEffect(() => {
    if (tanda === tandaTerakhir.current) return;
    tandaTerakhir.current = tanda;
    if (dirty) setBasi(true); else setRows(item.rows);
  }, [tanda]); // eslint-disable-line react-hooks/exhaustive-deps

  function ubah(i: number, kolom: string, nilai: string) {
    setRows(rs => rs.map((r, j) => j === i ? { ...r, [kolom]: nilai } : r)); setDirty(true); setStatus(null);
  }
  function salinLive() {
    if (!item.live) return;
    const salinan = item.live.rows.map(r => Object.fromEntries(item.kolom.map(k => [k, r[k] ?? ''])));
    setRows(item.tipe === 'narasi' ? salinan.slice(0, 1) : salinan); setDirty(true); setStatus(null);
  }
  function tambahBaris() { setRows(rs => [...rs, barisKosong(item.kolom)]); setDirty(true); }
  function hapusBaris(i: number) { setRows(rs => rs.length > 1 ? rs.filter((_, j) => j !== i) : [barisKosong(item.kolom)]); setDirty(true); }
  function batal() { setRows(item.rows); setDirty(false); setBasi(false); setStatus(null); }

  /** true bila tersimpan (dipakai "Simpan & lanjut" supaya tidak pindah halaman saat gagal). */
  async function simpan(): Promise<boolean> {
    setSibuk(true); setStatus(null);
    try {
      const hasil = await saveAccreditationItem(laporanId, item.id, rows);
      setDirty(false); setBasi(false);
      setStatus({ type: 'info', text: hasil.sel ? `Tersimpan (${hasil.baris} baris).` : 'Tersimpan — item ini sekarang kosong.' });
      onSaved();
      return true;
    } catch (e) { setStatus({ type: 'error', text: pesan(e, 'Gagal menyimpan.') }); return false; }
    finally { setSibuk(false); }
  }

  return { rows, dirty, basi, status, sibuk, ubah, salinLive, tambahBaris, hapusBaris, batal, simpan };
}
