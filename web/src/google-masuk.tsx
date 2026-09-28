import { useEffect, useState } from 'react';
import { useLocation, useSearchParams } from 'react-router-dom';

import { googleLoginAktif, googleLoginUrl, type Portal } from './lib/api';
import { Notice } from './ui';

/* Tombol "Masuk dengan Google" di panel login kedua portal, di atas form email & password.
   Tombol hanya muncul bila server sudah diberi client ID Google; tanpa itu login password saja.
   Gagal login Google kembali ke halaman ini dengan ?google_error=... yang ditampilkan di sini. */

export function GoogleMasuk({ portal, next }: { portal: Portal; next?: string | null }) {
  const [aktif, setAktif] = useState(false);
  const [params, setParams] = useSearchParams();
  const location = useLocation();
  const [galat] = useState(() => params.get('google_error'));
  useEffect(() => { googleLoginAktif().then(setAktif); }, []);
  useEffect(() => {
    // Pesan cukup tampil sekali; buang dari URL supaya tidak muncul lagi saat halaman dimuat ulang.
    if (params.has('google_error')) { const p = new URLSearchParams(params); p.delete('google_error'); setParams(p, { replace: true }); }
  }, [params, setParams]);

  const sisa = new URLSearchParams(location.search); sisa.delete('google_error'); sisa.delete('next');
  const tujuan = next || location.pathname + (sisa.toString() ? `?${sisa}` : '');
  if (!galat && !aktif) return null;
  return <div className="google-masuk">
    {galat && <Notice type="error">{galat}</Notice>}
    {aktif && <>
      <a className="button google-masuk__tombol" href={googleLoginUrl(portal, tujuan)}>
        <svg aria-hidden="true" viewBox="0 0 48 48" width="20" height="20"><path fill="#FFC107" d="M43.6 20.5H42V20H24v8h11.3C33.7 32.7 29.2 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.3-.1-2.4-.4-3.5z"/><path fill="#FF3D00" d="m6.3 14.7 6.6 4.8C14.7 15.1 19 12 24 12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 16.3 4 9.7 8.3 6.3 14.7z"/><path fill="#4CAF50" d="M24 44c5.2 0 9.9-2 13.4-5.2l-6.2-5.2C29.2 35.1 26.7 36 24 36c-5.2 0-9.6-3.3-11.3-7.9l-6.5 5C9.5 39.6 16.2 44 24 44z"/><path fill="#1976D2" d="M43.6 20.5H42V20H24v8h11.3c-.8 2.2-2.2 4.2-4.1 5.6l6.2 5.2C37 39.2 44 34 44 24c0-1.3-.1-2.4-.4-3.5z"/></svg>
        Masuk dengan Google
      </a>
      <p className="google-masuk__atau"><span>atau pakai email &amp; password</span></p>
    </>}
  </div>;
}
