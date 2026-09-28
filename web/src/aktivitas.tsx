import { useEffect, useState } from 'react';

import type { Aktivitas } from './lib/api';

/* Daftar "siapa melakukan apa, kapan" (services/aktivitas.py). Dipakai di Riwayat perubahan
   laporan akreditasi dan di Aktivitas terbaru halaman Admin kedua portal. */

const PER_HALAMAN = 10;

function waktu(iso: string) {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString('id-ID', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });
}

export function DaftarAktivitas({ muat, kosong, kunci }: { muat: () => Promise<{ aktivitas: Aktivitas[] }>; kosong: string; kunci?: unknown }) {
  const [data, setData] = useState<Aktivitas[] | null>(null);
  const [galat, setGalat] = useState('');
  const [tampil, setTampil] = useState(PER_HALAMAN);
  useEffect(() => {
    let hidup = true;
    setGalat('');
    muat().then(r => { if (hidup) setData(r.aktivitas); }).catch(e => { if (hidup) setGalat(e instanceof Error ? e.message : 'Riwayat belum dapat dimuat.'); });
    return () => { hidup = false; };
    // `kunci` berubah = muat ulang (mis. setelah laporan disimpan).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [kunci]);

  if (galat) return <p className="field-hint" role="alert">{galat}</p>;
  if (!data) return <p className="loading" role="status">Memuat riwayat…</p>;
  if (data.length === 0) return <p className="section-note">{kosong}</p>;
  return <>
    <ol className="aktivitas">
      {data.slice(0, tampil).map(a => <li key={a.id}>
        <time dateTime={a.created_at}>{waktu(a.created_at)}</time>
        <span className="aktivitas__isi"><b>{a.pelaku_nama || a.pelaku_email}</b> {a.keterangan}</span>
      </li>)}
    </ol>
    {data.length > tampil && <button type="button" className="link-button" onClick={() => setTampil(t => t + PER_HALAMAN)}>
      Tampilkan {Math.min(PER_HALAMAN, data.length - tampil)} lagi
    </button>}
  </>;
}
