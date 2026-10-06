import { useRef, useState } from 'react';

import { bacaUploadTabel, downloadFormatTabel, simpanBlob, type ItemRow } from './lib/api';
import { pesan } from './akreditasi-edit';

/** "Unduh format" + "Upload data" untuk satu isian tabel. Format = kolom isian ini (format_tabel.json);
 *  server menolak file milik tabel lain, jadi baris tidak bisa masuk ke isian yang salah.
 *  Baris hasil upload diserahkan ke editor (onRows) dan baru tersimpan saat user menekan Simpan. */
export function FormatTabelAksi({ itemId, laporanId, disabled, onRows, onError }: {
  itemId: string; laporanId: number; disabled?: boolean;
  onRows: (rows: ItemRow[]) => void; onError: (teks: string) => void;
}) {
  const input = useRef<HTMLInputElement>(null);
  const [sibuk, setSibuk] = useState<'unduh' | 'upload' | null>(null);

  async function unduh() {
    setSibuk('unduh');
    try { const { blob, filename } = await downloadFormatTabel(itemId); simpanBlob(blob, filename); }
    catch (e) { onError(pesan(e, 'Format gagal diunduh.')); }
    finally { setSibuk(null); }
  }
  async function upload(file: File | undefined) {
    if (!file) return;
    setSibuk('upload');
    try { onRows((await bacaUploadTabel(itemId, laporanId, file)).rows); }
    catch (e) { onError(pesan(e, 'File gagal dibaca.')); }
    finally { setSibuk(null); if (input.current) input.current.value = ''; }
  }

  return <div className="format-tabel" role="group" aria-label="Format Excel tabel ini">
    <button type="button" className="button secondary" disabled={sibuk !== null} onClick={unduh}>
      {sibuk === 'unduh' ? 'Mengunduh…' : 'Unduh format'}
    </button>
    <button type="button" className="button secondary" disabled={disabled || sibuk !== null} onClick={() => input.current?.click()}>
      {sibuk === 'upload' ? 'Membaca file…' : 'Upload data'}
    </button>
    <input ref={input} type="file" hidden accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
      aria-label="Pilih file Excel isian tabel" onChange={e => upload(e.target.files?.[0])} />
  </div>;
}
