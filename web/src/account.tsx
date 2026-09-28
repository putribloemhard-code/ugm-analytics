import { Fragment, useEffect, useState, type ReactNode } from 'react';
import { Link, Navigate, useLocation } from 'react-router-dom';

import { aktivitasAdmin, kirimEmailUji, accreditationAdminAction, accreditationAdminUsers, accreditationMe, accreditationProfile, buatTautanReset, daftarPengajuanReset, dampakAdminAction, dampakAdminUsers, dampakMe, downloadAccreditationHistory, putuskanReset, simpanBlob, type AdminOverview, type DampakAdminOverview, type PengajuanReset, type Portal, type ProfileResult, type TautanReset } from './lib/api';
import { DaftarAktivitas } from './aktivitas';
import { Notice, PageHeader, ProgressLine } from './ui';

/** Gerbang halaman terproteksi: alihkan ke /akreditasi bila belum login. */
function useRequireUser() {
  const [state, setState] = useState<{ loading: boolean; user: { id: number; email: string; nama: string; is_admin: boolean } | null }>({ loading: true, user: null });
  useEffect(() => {
    let hidup = true;
    accreditationMe().then(user => { if (hidup) setState({ loading: false, user }); }).catch(() => { if (hidup) setState({ loading: false, user: null }); });
    return () => { hidup = false; };
  }, []);
  return state;
}

/** Unduh ulang laporan dari riwayat (padanan tombol unduh di page_profil.py lama). */
function UnduhRiwayat({ id }: { id: number }) {
  const [galat, setGalat] = useState('');
  const [sibuk, setSibuk] = useState(false);
  async function unduh() {
    setSibuk(true); setGalat('');
    try { const { blob, filename } = await downloadAccreditationHistory(id); simpanBlob(blob, filename); }
    catch (e) { setGalat(e instanceof Error ? e.message : 'Gagal mengunduh.'); }
    finally { setSibuk(false); }
  }
  return <>{galat ? <span className="field-hint">{galat}</span> : <button className="link-button" disabled={sibuk} onClick={unduh}>{sibuk ? 'Mengunduh…' : 'Unduh .docx'}</button>}</>;
}

/* Ikon garis sederhana untuk kotak statistik profil: menandai jenis angka (dokumen Word, file
   upload, laporan berjalan, riwayat), bukan hiasan. */
const IKON: Record<string, string> = {
  word: 'M7 3h7l5 5v13H7zM14 3v5h5M9.5 12l1.2 5 1.3-4 1.3 4 1.2-5',
  upload: 'M12 16V4m0 0-4 4m4-4 4 4M5 15v4h14v-4',
  laporan: 'M4 5h16v14H4zM8 9h8M8 13h5M16 16l2 2 3-4',
  riwayat: 'M3 12a9 9 0 1 0 3-6.7M3 4v4h4M12 7v5l3 3',
};
function Ikon({ nama }: { nama: keyof typeof IKON }) {
  return <svg viewBox="0 0 24 24" width="26" height="26" aria-hidden="true" focusable="false"><path d={IKON[nama]} fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" /></svg>;
}

function KotakStat({ ikon, label, nilai, catatan }: { ikon: keyof typeof IKON; label: string; nilai: number; catatan: string }) {
  return <div className="profil-stat">
    <span className="profil-stat__ikon"><Ikon nama={ikon} /></span>
    <div className="profil-stat__isi">
      <span className="profil-stat__label">{label}</span>
      <strong>{nilai.toLocaleString('id-ID')}</strong>
      <span className="profil-stat__catatan">{catatan}</span>
    </div>
  </div>;
}

function inisial(nama: string): string {
  return nama.split(/\s+/).filter(Boolean).slice(0, 2).map(k => k[0]?.toUpperCase() ?? '').join('') || '?';
}

export function ProfilePage() {
  const { loading, user } = useRequireUser();
  const [profil, setProfil] = useState<ProfileResult | null>(null);
  const [error, setError] = useState('');
  useEffect(() => { if (!user) return; accreditationProfile().then(setProfil).catch(e => setError(e instanceof Error ? e.message : 'Profil belum dapat dimuat.')); }, [user]);
  if (loading) return <div className="content loading">Memuat profil...</div>;
  if (!user) return <Navigate to="/akreditasi" replace />;
  if (error) return <div className="content"><PageHeader title="Profil Saya" kicker="Akun akreditasi" /><Notice type="error">{error}</Notice></div>;
  if (!profil) return <div className="content loading">Memuat profil...</div>;
  const { user: identitas, stats, ongoing, riwayat } = profil;
  return <div className="content account-page profil">
    <PageHeader title="Profil Saya" kicker="Akun akreditasi" caption="Identitas akun, laporan yang sedang Anda kerjakan, dan riwayat dokumen Word." />

    <section className="profil-stats" aria-label="Ringkasan aktivitas">
      <KotakStat ikon="word" label="Dokumen digenerate" nilai={stats.dokumen_digenerate} catatan="laporan Word" />
      <KotakStat ikon="upload" label="Dokumen diupload" nilai={stats.dokumen_diupload} catatan="file pendukung" />
      <KotakStat ikon="laporan" label="Laporan berjalan" nilai={ongoing.length} catatan="yang Anda isi" />
      <KotakStat ikon="riwayat" label="Riwayat tersimpan" nilai={riwayat.total} catatan={`ditampilkan maks. ${riwayat.batas}`} />
    </section>

    <div className="profil-grid">
      <section className="profil-panel profil-akun" aria-labelledby="profil-akun-judul">
        <h2 className="profil-panel__head" id="profil-akun-judul">Informasi akun</h2>
        <div className="profil-akun__kepala">
          <span className="profil-avatar" aria-hidden="true">{inisial(identitas.nama)}</span>
          <div><b>{identitas.nama}</b><span>{identitas.is_admin ? 'Admin portal akreditasi' : 'Penyusun laporan'}</span></div>
        </div>
        <dl className="profil-kv">
          <div><dt>Email</dt><dd>{identitas.email}</dd></div>
          <div><dt>Peran</dt><dd>{identitas.is_admin ? 'Admin' : 'Penyusun'}</dd></div>
          <div><dt>Terdaftar sejak</dt><dd>{identitas.terdaftar ?? '-'}</dd></div>
          <div><dt>Login terakhir</dt><dd>{identitas.login_terakhir ?? '-'}</dd></div>
        </dl>
      </section>

      <section className="profil-panel" aria-labelledby="profil-laporan-judul">
        <h2 className="profil-panel__head" id="profil-laporan-judul">Laporan yang Anda isi</h2>
        {ongoing.length === 0
          ? <p className="profil-kosong">Belum ada. Laporan yang item-nya Anda simpan di halaman Akreditasi akan muncul di sini.</p>
          : <ul className="profil-laporan">{ongoing.map(k => <li key={k.laporan_id}>
            <div className="profil-laporan__atas">
              <div><b>{k.nama_prodi}</b><span>{k.nama_fakultas ?? 'Prodi tidak terhubung ke fakultas'}</span></div>
              <span className="status-pill">{k.nama_laporan}</span>
            </div>
            <ProgressLine value={k.lengkap} total={k.total} percent={k.persen} note={`${k.item_milik_user} item disimpan oleh Anda`} />
            <Link className="button profil-laporan__aksi" to={`/akreditasi?prodi=${encodeURIComponent(k.prodi_id)}&dokumen=${k.dokumen}&laporan=${k.laporan_id}`}>Lanjutkan</Link>
          </li>)}</ul>}
      </section>
    </div>

    <section className="profil-panel" aria-labelledby="profil-riwayat-judul">
      <h2 className="profil-panel__head" id="profil-riwayat-judul">Riwayat dokumen Word</h2>
      {riwayat.rows.length === 0
        ? <p className="profil-kosong">Belum ada laporan Word yang Anda buat.</p>
        : <>
          {riwayat.total > riwayat.batas && <p className="section-note">Menampilkan {riwayat.batas} dokumen terbaru dari {riwayat.total}.</p>}
          <ul className="profil-riwayat">{riwayat.rows.map(r => <li key={r.id}>
            <span className="profil-riwayat__dok">{r.jenis_dokumen}</span>
            <div><b>{r.nama_prodi}</b><span>Digenerate {r.digenerate ?? '-'}</span></div>
            <UnduhRiwayat id={r.id} />
          </li>)}</ul>
        </>}
    </section>
  </div>;
}

function waktuLokal(iso: string | null): string {
  if (!iso) return '-';
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString('id-ID', { dateStyle: 'medium', timeStyle: 'short' });
}

const STATUS_RESET: Record<PengajuanReset['status'], string> = { menunggu: 'Menunggu', disetujui: 'Disetujui', ditolak: 'Ditolak', gugur: 'Gugur (PIN sudah diganti)' };

/** Pengajuan reset PIN prodi: admin melihat siapa yang mengajukan lalu menyetujui / menolak. */
function ResetPasswordPanel() {
  const [data, setData] = useState<PengajuanReset[] | null>(null);
  const [pesan, setPesan] = useState<{ type: 'info' | 'error'; text: string } | null>(null);
  const [sibuk, setSibuk] = useState<number | null>(null);
  const muat = () => { daftarPengajuanReset().then(r => setData(r.pengajuan)).catch(e => setPesan({ type: 'error', text: e instanceof Error ? e.message : 'Pengajuan belum dapat dimuat.' })); };
  useEffect(muat, []);
  async function putuskan(id: number, setujui: boolean) {
    setSibuk(id); setPesan(null);
    try { const r = await putuskanReset(id, setujui); setPesan({ type: 'info', text: r.message }); muat(); }
    catch (e) { setPesan({ type: 'error', text: e instanceof Error ? e.message : 'Keputusan gagal disimpan.' }); }
    finally { setSibuk(null); }
  }
  const menunggu = (data ?? []).filter(r => r.status === 'menunggu');
  const tabel = (baris: PengajuanReset[]) => <div className="data-table-wrap"><table className="data-table"><caption className="sr-only">Pengajuan reset PIN prodi</caption>
          <thead><tr><th scope="col">Program studi</th><th scope="col">Diajukan oleh</th><th scope="col">Waktu</th><th scope="col">Alasan</th><th scope="col">Status</th><th scope="col"><span className="sr-only">Aksi</span></th></tr></thead>
          <tbody>{baris.map(r => <tr key={r.id}>
            <td>{r.nama_prodi ?? r.prodi_id}{r.fakultas && <small className="upload-summary">{r.fakultas}</small>}</td>
            <td>{r.nama_pengaju ?? '-'}<small className="upload-summary">{r.diajukan_oleh}</small></td>
            <td>{waktuLokal(r.created_at)}</td>
            <td>{r.alasan ?? '-'}</td>
            <td>{STATUS_RESET[r.status]}{r.diputus_oleh && <small className="upload-summary">oleh {r.diputus_oleh}, {waktuLokal(r.diputus_at)}</small>}</td>
            <td>{r.status === 'menunggu' && <div className="akun-kelola">
              <button className="button" type="button" disabled={sibuk === r.id} onClick={() => putuskan(r.id, true)}>Setujui</button>
              <button className="button button--danger" type="button" disabled={sibuk === r.id} onClick={() => putuskan(r.id, false)}>Tolak</button>
            </div>}</td>
          </tr>)}</tbody>
        </table></div>;
  if (!data) return pesan ? <Notice type={pesan.type}>{pesan.text}</Notice> : null;
  const selesai = data.filter(r => r.status !== 'menunggu');
  return <>
    {pesan && <Notice type={pesan.type}>{pesan.text}</Notice>}
    {menunggu.length > 0 && <section className="section admin-perlu">
      <div className="section-title-row"><h2>Perlu keputusan Anda</h2><span className="status-pill">{menunggu.length} pengajuan reset PIN</span></div>
      <p className="section-note">Setelah disetujui, PIN prodi diganti dan semua staf prodi itu harus memakai PIN baru.</p>
      {tabel(menunggu)}
    </section>}
    {selesai.length > 0 && <details className="lipat">
      <summary>Riwayat pengajuan reset PIN ({selesai.length})</summary>
      {tabel(selesai)}
    </details>}
  </>;
}

/** Jalur cadangan lupa password tanpa server email: admin membuat tautan reset untuk satu akun
 *  lalu mengirimkannya sendiri (mis. lewat WA) ke pemilik akun. */
function TautanResetAdmin({ portal, userId, email }: { portal: Portal; userId: number; email: string }) {
  const [hasil, setHasil] = useState<TautanReset | null>(null);
  const [galat, setGalat] = useState('');
  const [tersalin, setTersalin] = useState(false);
  async function buat() {
    setGalat(''); setTersalin(false);
    try { setHasil(await buatTautanReset(portal, userId)); } catch (e) { setGalat(e instanceof Error ? e.message : 'Tautan gagal dibuat.'); }
  }
  async function salin() {
    if (!hasil) return;
    try { await navigator.clipboard.writeText(hasil.tautan); setTersalin(true); } catch { setGalat('Salin manual tautan di atas.'); }
  }
  return <div className="tautan-reset">
    {!hasil && <button className="button secondary" type="button" onClick={buat}>Buat tautan reset password</button>}
    {hasil && <>
      <p className="field-hint">{hasil.message}</p>
      <label className="sr-only" htmlFor={`tautan-${portal}-${userId}`}>Tautan reset untuk {email}</label>
      <input id={`tautan-${portal}-${userId}`} className="tautan-reset__isi" readOnly value={hasil.tautan} onFocus={e => e.target.select()} />
      <button className="button" type="button" onClick={salin}>{tersalin ? 'Tersalin' : 'Salin tautan'}</button>
    </>}
    {galat && <p className="field-hint" role="alert">{galat}</p>}
  </div>;
}

type BarisAkun = { id: number; nama: string; email: string; is_admin: boolean; is_blocked: boolean; terdaftar: string | null; login_terakhir: string | null; diri_sendiri: boolean; jumlah: number };
type AksiAkun = 'blokir' | 'admin' | 'hapus';

/** Satu baris ringkas: jumlah akun, admin, diblokir (pengganti tiga kotak statistik besar). */
function RingkasAkun({ summary }: { summary: { total_akun: number; admin: number; diblokir: number } }) {
  return <p className="admin-ringkas">
    <span><b>{summary.total_akun}</b> akun</span>
    <span><b>{summary.admin}</b> admin</span>
    <span className={summary.diblokir ? 'is-waspada' : ''}><b>{summary.diblokir}</b> diblokir</span>
  </p>;
}

/** Satu tabel akun; aksi (blokir, admin, tautan reset, hapus) dibuka per baris lewat "Kelola". */
function TabelAkun({ portal, users, labelJumlah, catatanHapus, onAksi }: {
  portal: Portal; users: BarisAkun[]; labelJumlah: string; catatanHapus: string; onAksi: (id: number, aksi: AksiAkun, nilai?: boolean) => Promise<void>;
}) {
  const [buka, setBuka] = useState<number | null>(null);
  const [konfirmasi, setKonfirmasi] = useState<number | null>(null);
  async function jalankan(id: number, aksi: AksiAkun, nilai?: boolean) {
    setKonfirmasi(null);
    await onAksi(id, aksi, nilai);
    if (aksi === 'hapus') setBuka(null);
  }
  return <div className="data-table-wrap akun-tabel"><table className="data-table">
    <caption className="sr-only">Daftar akun</caption>
    <thead><tr><th scope="col">Akun</th><th scope="col">Status</th><th scope="col">Login terakhir</th><th scope="col">{labelJumlah}</th><th scope="col"><span className="sr-only">Aksi</span></th></tr></thead>
    <tbody>{users.map(u => <Fragment key={u.id}>
      <tr className={u.is_blocked ? 'is-diblokir' : ''}>
        <td data-label="Akun"><b>{u.nama}</b>{u.diri_sendiri && <span className="tag">akun Anda</span>}<small className="akun-tabel__email">{u.email}</small></td>
        <td data-label="Status"><span className="akun-status">{u.is_blocked ? 'Diblokir' : 'Aktif'}{u.is_admin && ' · Admin'}</span></td>
        <td data-label="Login terakhir">{u.login_terakhir ?? '-'}</td>
        <td data-label={labelJumlah}>{u.jumlah}</td>
        <td className="akun-tabel__aksi">
          {!u.diri_sendiri && <button type="button" className="button secondary" aria-expanded={buka === u.id} aria-controls={`kelola-${portal}-${u.id}`}
              onClick={() => { setBuka(buka === u.id ? null : u.id); setKonfirmasi(null); }}>{buka === u.id ? 'Tutup' : 'Kelola'}</button>}
        </td>
      </tr>
      {buka === u.id && <tr className="akun-tabel__kelola" id={`kelola-${portal}-${u.id}`}><td colSpan={5}>
        <div className="akun-kelola">
          <button className="button secondary" type="button" onClick={() => jalankan(u.id, 'blokir', !u.is_blocked)}>{u.is_blocked ? 'Buka blokir' : 'Blokir'}</button>
          <button className="button secondary" type="button" onClick={() => jalankan(u.id, 'admin', !u.is_admin)}>{u.is_admin ? 'Cabut admin' : 'Jadikan admin'}</button>
          {!u.is_blocked && <TautanResetAdmin portal={portal} userId={u.id} email={u.email} />}
          <button className="button button--danger-outline" type="button" onClick={() => setKonfirmasi(u.id)}>Hapus akun</button>
        </div>
        {konfirmasi === u.id && <div className="admin-confirm" role="alertdialog" aria-label={`Konfirmasi hapus ${u.email}`}>
          <p>Hapus akun <b>{u.email}</b> secara permanen? {catatanHapus}</p>
          <button className="button button--danger" type="button" onClick={() => jalankan(u.id, 'hapus')}>Ya, hapus</button>
          <button className="button secondary" type="button" onClick={() => setKonfirmasi(null)}>Batal</button>
        </div>}
      </td></tr>}
    </Fragment>)}</tbody>
  </table></div>;
}

/** Periksa server email dari halaman Admin: kirim satu email uji ke alamat admin sendiri. */
function EmailUji({ portal, email }: { portal: Portal; email: string }) {
  const [hasil, setHasil] = useState<{ terkirim: boolean; message: string } | null>(null);
  const [sibuk, setSibuk] = useState(false);
  async function kirimUji() {
    setSibuk(true); setHasil(null);
    try { setHasil(await kirimEmailUji(portal)); }
    catch (e) { setHasil({ terkirim: false, message: e instanceof Error ? e.message : 'Email uji gagal.' }); }
    finally { setSibuk(false); }
  }
  return <div className="admin-email">
    <p className="section-note">Email dipakai untuk tautan lupa password dan pemberitahuan pengajuan reset PIN. Kirim email uji ke <b>{email}</b> untuk memastikan pengaturannya benar.</p>
    <button className="button secondary" type="button" disabled={sibuk} onClick={kirimUji}>{sibuk ? 'Mengirim…' : 'Kirim email uji'}</button>
    {hasil && <Notice type={hasil.terkirim ? 'info' : 'error'}>{hasil.message}</Notice>}
  </div>;
}

/** Kerangka halaman Admin kedua portal: ringkasan, (pengajuan PIN), akun, aktivitas, email. */
function HalamanAdmin({ portal, judul, kicker, keterangan, summary, users, labelJumlah, catatanJumlah, catatanHapus, onAksi, pesan, sebelumAkun }: {
  portal: Portal; judul: string; kicker: string; keterangan: string; summary: { total_akun: number; admin: number; diblokir: number };
  users: BarisAkun[]; labelJumlah: string; catatanJumlah: string; catatanHapus: string; onAksi: (id: number, aksi: AksiAkun, nilai?: boolean) => Promise<void>;
  pesan: { type: 'info' | 'error'; text: string } | null; sebelumAkun?: ReactNode;
}) {
  const [versi, setVersi] = useState(0);
  const diri = users.find(u => u.diri_sendiri);
  return <div className="content account-page admin-halaman">
    <PageHeader title={judul} kicker={kicker} caption={keterangan} />
    <RingkasAkun summary={summary} />
    {pesan && <Notice type={pesan.type}>{pesan.text}</Notice>}
    {sebelumAkun}
    <section className="section">
      <div className="section-title-row"><h2>Akun</h2></div>
      <TabelAkun portal={portal} users={users} labelJumlah={labelJumlah} catatanHapus={catatanHapus}
        onAksi={async (id, aksi, nilai) => { await onAksi(id, aksi, nilai); setVersi(v => v + 1); }} />
      <p className="section-note">{catatanJumlah} Akun Anda sendiri tidak bisa diblokir, dihapus, atau dicabut status adminnya.</p>
    </section>
    <section className="section">
      <div className="section-title-row"><h2>Aktivitas terbaru</h2></div>
      <DaftarAktivitas muat={() => aktivitasAdmin(portal)} kunci={versi} kosong="Belum ada aktivitas yang tercatat." />
    </section>
    <details className="lipat">
      <summary>Pengaturan email</summary>
      <EmailUji portal={portal} email={diri?.email ?? ''} />
    </details>
  </div>;
}

export function AdminPage() {
  const { loading, user } = useRequireUser();
  const [data, setData] = useState<AdminOverview | null>(null);
  const [message, setMessage] = useState<{ type: 'info' | 'error'; text: string } | null>(null);
  const location = useLocation();

  const muat = () => { accreditationAdminUsers().then(setData).catch(e => setMessage({ type: 'error', text: e instanceof Error ? e.message : 'Data akun belum dapat dimuat.' })); };
  useEffect(() => { if (user?.is_admin) muat(); }, [user]);

  if (loading) return <div className="content loading">Memuat halaman admin...</div>;
  if (!user) return <Navigate to={`/akreditasi?next=${encodeURIComponent(location.pathname)}`} replace />;
  if (!user.is_admin) return <div className="content"><PageHeader title="Admin" kicker="Akun akreditasi" /><Notice type="error">Akses ditolak — halaman ini khusus admin.</Notice><p><Link className="button" to="/akreditasi">Kembali ke Akreditasi</Link></p></div>;
  if (!data) return <div className="content loading">{message ? <Notice type={message.type}>{message.text}</Notice> : 'Memuat data akun...'}</div>;

  async function aksi(targetId: number, action: AksiAkun, value?: boolean) {
    setMessage(null);
    try { const hasil = await accreditationAdminAction(targetId, action, value); setMessage({ type: 'info', text: hasil.message }); muat(); }
    catch (e) { setMessage({ type: 'error', text: e instanceof Error ? e.message : 'Aksi gagal.' }); }
  }
  return <HalamanAdmin portal="akreditasi" judul="Admin" kicker="Portal Akreditasi"
    keterangan="Kelola akun, setujui reset PIN prodi, dan pantau aktivitas portal akreditasi."
    summary={data.summary} users={data.users.map(u => ({ ...u, jumlah: u.n_generate }))} labelJumlah="Word dibuat"
    catatanJumlah="Word dibuat = laporan Word yang pernah diunduh akun itu."
    catatanHapus="Riwayat laporannya ikut terhapus; data yang sudah ia isi tetap ada." onAksi={aksi} pesan={message}
    sebelumAkun={<ResetPasswordPanel />} />;
}

/** Halaman Admin portal Analisis Dampak: kelola akun Dampak (terpisah dari akun Akreditasi). */
export function DampakAdminPage() {
  const [user, setUser] = useState<{ id: number; email: string; nama: string; is_admin: boolean } | null | undefined>(undefined);
  const [data, setData] = useState<DampakAdminOverview | null>(null);
  const [message, setMessage] = useState<{ type: 'info' | 'error'; text: string } | null>(null);
  useEffect(() => { dampakMe().then(setUser).catch(() => setUser(null)); }, []);
  const muat = () => { dampakAdminUsers().then(setData).catch(e => setMessage({ type: 'error', text: e instanceof Error ? e.message : 'Data akun belum dapat dimuat.' })); };
  useEffect(() => { if (user?.is_admin) muat(); }, [user]);

  if (user === undefined) return <div className="content loading">Memuat halaman admin...</div>;
  if (!user) return <Navigate to="/dampak" replace />;
  if (!user.is_admin) return <div className="content"><PageHeader title="Admin Analisis Dampak" kicker="Akun Analisis Dampak" /><Notice type="error">Akses ditolak — halaman ini khusus admin Analisis Dampak.</Notice><p><Link className="button" to="/dampak">Kembali ke Analisis Dampak</Link></p></div>;
  if (!data) return <div className="content loading">{message ? <Notice type={message.type}>{message.text}</Notice> : 'Memuat data akun...'}</div>;

  async function aksi(targetId: number, action: AksiAkun, value?: boolean) {
    setMessage(null);
    try { const hasil = await dampakAdminAction(targetId, action, value); setMessage({ type: 'info', text: hasil.message }); muat(); }
    catch (e) { setMessage({ type: 'error', text: e instanceof Error ? e.message : 'Aksi gagal.' }); }
  }
  return <HalamanAdmin portal="dampak" judul="Admin Analisis Dampak" kicker="Analisis Dampak"
    keterangan="Kelola akun portal Analisis Dampak dan pantau aktivitasnya. Akun ini terpisah dari akun Akreditasi."
    summary={data.summary} users={data.users.map(u => ({ ...u, jumlah: u.n_tag }))} labelJumlah="Tag manual"
    catatanJumlah="Tag manual = berita yang ditandai SDG atau tema secara manual oleh akun itu."
    catatanHapus="Tag manual yang pernah ia simpan tetap ada." onAksi={aksi} pesan={message} />;
}
