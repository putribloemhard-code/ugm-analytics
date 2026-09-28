import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';

import { cekResetPassword, lupaPassword, resetPassword, type Portal } from './lib/api';
import { Notice } from './ui';

/* Lupa password dua portal (Akreditasi & Analisis Dampak): minta tautan lewat email, lalu buat
   password baru dari tautan itu. Tautan juga bisa dibuat admin portal dari halaman Admin. */

const LOGIN: Record<Portal, { path: string; nama: string }> = {
  akreditasi: { path: '/akreditasi', nama: 'Portal Akreditasi' },
  dampak: { path: '/dampak', nama: 'Analisis Dampak' },
};

function pesan(e: unknown, cadangan: string) { return e instanceof Error && e.message ? e.message : cadangan; }

/** Isi di panel login saat user memilih "Lupa password?". */
export function LupaPasswordForm({ portal, emailAwal, onKembali }: { portal: Portal; emailAwal: string; onKembali: () => void }) {
  const [email, setEmail] = useState(emailAwal);
  const [sibuk, setSibuk] = useState(false);
  const [hasil, setHasil] = useState<{ type: 'info' | 'error'; text: string } | null>(null);
  const id = `lupa-${portal}`;
  async function kirim(e: React.FormEvent) {
    e.preventDefault(); setSibuk(true); setHasil(null);
    try { setHasil({ type: 'info', text: (await lupaPassword(portal, email)).message }); }
    catch (err) { setHasil({ type: 'error', text: pesan(err, 'Permintaan gagal.') }); }
    finally { setSibuk(false); }
  }
  return <form className="lupa-password" onSubmit={kirim}>
    <p className="section-note">Masukkan email akun {LOGIN[portal].nama} Anda. Kami kirim tautan untuk membuat password baru (berlaku 30 menit, sekali pakai).</p>
    <div className="field"><label htmlFor={`${id}-email`}>Email UGM</label>
      <input id={`${id}-email`} type="email" autoComplete="email" placeholder="nama@ugm.ac.id" value={email} onChange={e => setEmail(e.target.value)} required /></div>
    <button className="button auth-submit" type="submit" disabled={sibuk || !email.trim()}>{sibuk ? 'Mengirim…' : 'Kirim tautan reset'}</button>
    {hasil && <Notice type={hasil.type}>{hasil.text}</Notice>}
    <button className="link-button lupa-password__kembali" type="button" onClick={onKembali}>‹ Kembali ke Masuk</button>
  </form>;
}

/** Halaman /reset-password?portal=...&token=... dari tautan email atau dari admin. */
export function ResetPasswordPage() {
  const [params] = useSearchParams();
  const portal = (params.get('portal') === 'dampak' ? 'dampak' : 'akreditasi') as Portal;
  const token = params.get('token') ?? '';
  const [akun, setAkun] = useState<{ email: string; nama: string } | null>(null);
  const [galat, setGalat] = useState('');
  const [password, setPassword] = useState('');
  const [password2, setPassword2] = useState('');
  const [sibuk, setSibuk] = useState(false);
  const [selesai, setSelesai] = useState('');

  useEffect(() => {
    if (!token) { setGalat('Tautan reset tidak lengkap. Minta tautan baru dari halaman login.'); return; }
    cekResetPassword(portal, token).then(setAkun).catch(e => setGalat(pesan(e, 'Tautan reset tidak berlaku.')));
  }, [portal, token]);

  const syarat = password.length < 8 ? 'Password minimal 8 karakter.' : password !== password2 ? (password2 ? 'Kedua password belum sama.' : 'Ketik ulang password untuk konfirmasi.') : null;
  async function simpan(e: React.FormEvent) {
    e.preventDefault(); if (syarat) return;
    setSibuk(true); setGalat('');
    try { setSelesai((await resetPassword(portal, token, password)).message); }
    catch (err) { setGalat(pesan(err, 'Password gagal disimpan.')); }
    finally { setSibuk(false); }
  }

  return <div className="content reset-password">
    <section className="auth-panel reset-password__panel" aria-labelledby="reset-judul">
      <p className="section-kicker">{LOGIN[portal].nama}</p>
      <h1 id="reset-judul">Buat password baru</h1>
      {selesai
        ? <><Notice type="info">{selesai}</Notice><Link className="button auth-submit" to={LOGIN[portal].path}>Masuk ke {LOGIN[portal].nama}</Link></>
        : galat && !akun
          ? <><Notice type="error">{galat}</Notice><Link className="link-button" to={LOGIN[portal].path}>‹ Kembali ke halaman login untuk minta tautan baru</Link></>
          : !akun
            ? <div className="loading" role="status">Memeriksa tautan…</div>
            : <form onSubmit={simpan}>
              <p className="section-note">Untuk akun <b>{akun.email}</b> ({akun.nama}). Setelah disimpan, semua sesi login akun ini diakhiri dan tautan ini tidak bisa dipakai lagi.</p>
              <input type="email" autoComplete="username" value={akun.email} readOnly hidden />
              <div className="field"><label htmlFor="reset-pw">Password baru (min. 8 karakter)</label>
                <input id="reset-pw" type="password" autoComplete="new-password" value={password} onChange={e => setPassword(e.target.value)} /></div>
              <div className="field"><label htmlFor="reset-pw-2">Ulangi password baru</label>
                <input id="reset-pw-2" type="password" autoComplete="new-password" value={password2} onChange={e => setPassword2(e.target.value)} /></div>
              {syarat && <p className="field-hint" aria-live="polite">{syarat}</p>}
              <button className="button auth-submit" type="submit" disabled={sibuk || Boolean(syarat)}>{sibuk ? 'Menyimpan…' : 'Simpan password baru'}</button>
              {galat && <Notice type="error">{galat}</Notice>}
            </form>}
    </section>
  </div>;
}
