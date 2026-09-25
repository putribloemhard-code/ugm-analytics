import { useEffect, useState } from 'react';
import { Link, Navigate, useLocation } from 'react-router-dom';

import { accreditationAdminAction, accreditationAdminUsers, accreditationMe, accreditationProfile, daftarPengajuanReset, downloadAccreditationHistory, putuskanReset, simpanBlob, type AdminOverview, type PengajuanReset, type ProfileResult } from './lib/api';
import { Notice, PageHeader, ProgressLine, StatCard } from './ui';

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
  return <section className="section">
    <div className="section-title-row"><div><p className="section-kicker">PIN prodi</p><h2>Pengajuan reset PIN</h2></div>{menunggu.length > 0 && <span className="status-pill">{menunggu.length} menunggu</span>}</div>
    <p className="section-note">Staf yang lupa PIN prodi mengajukan PIN baru di halaman Akreditasi. Setelah disetujui, PIN prodi diganti dan semua staf harus memakai PIN baru.</p>
    {pesan && <Notice type={pesan.type}>{pesan.text}</Notice>}
    {!data ? <div className="loading" role="status">Memuat pengajuan…</div>
      : data.length === 0 ? <p className="section-note">Belum ada pengajuan.</p>
        : <div className="data-table-wrap"><table className="data-table"><caption className="sr-only">Pengajuan reset PIN prodi</caption>
          <thead><tr><th scope="col">Program studi</th><th scope="col">Diajukan oleh</th><th scope="col">Waktu</th><th scope="col">Alasan</th><th scope="col">Status</th><th scope="col"><span className="sr-only">Aksi</span></th></tr></thead>
          <tbody>{data.map(r => <tr key={r.id}>
            <td>{r.nama_prodi ?? r.prodi_id}{r.fakultas && <small className="upload-summary">{r.fakultas}</small>}</td>
            <td>{r.nama_pengaju ?? '-'}<small className="upload-summary">{r.diajukan_oleh}</small></td>
            <td>{waktuLokal(r.created_at)}</td>
            <td>{r.alasan ?? '-'}</td>
            <td>{STATUS_RESET[r.status]}{r.diputus_oleh && <small className="upload-summary">oleh {r.diputus_oleh}, {waktuLokal(r.diputus_at)}</small>}</td>
            <td>{r.status === 'menunggu' && <div className="admin-card__actions">
              <button className="button" type="button" disabled={sibuk === r.id} onClick={() => putuskan(r.id, true)}>Setujui</button>
              <button className="button button--danger" type="button" disabled={sibuk === r.id} onClick={() => putuskan(r.id, false)}>Tolak</button>
            </div>}</td>
          </tr>)}</tbody>
        </table></div>}
  </section>;
}

export function AdminPage() {
  const { loading, user } = useRequireUser();
  const [data, setData] = useState<AdminOverview | null>(null);
  const [message, setMessage] = useState<{ type: 'info' | 'error'; text: string } | null>(null);
  const [konfirmasi, setKonfirmasi] = useState<number | null>(null);
  const location = useLocation();

  const muat = () => { accreditationAdminUsers().then(setData).catch(e => setMessage({ type: 'error', text: e instanceof Error ? e.message : 'Data akun belum dapat dimuat.' })); };
  useEffect(() => { if (user?.is_admin) muat(); }, [user]);

  if (loading) return <div className="content loading">Memuat halaman admin...</div>;
  if (!user) return <Navigate to={`/akreditasi?next=${encodeURIComponent(location.pathname)}`} replace />;
  if (!user.is_admin) return <div className="content"><PageHeader title="Admin" kicker="Akun akreditasi" /><Notice type="error">Akses ditolak — halaman ini khusus admin.</Notice><p><Link className="button" to="/akreditasi">Kembali ke Akreditasi</Link></p></div>;
  if (!data) return <div className="content loading">Memuat data akun...</div>;

  async function aksi(targetId: number, action: 'blokir' | 'admin' | 'hapus', value?: boolean) {
    setMessage(null); setKonfirmasi(null);
    try {
      const hasil = await accreditationAdminAction(targetId, action, value);
      setMessage({ type: 'info', text: hasil.message });
      muat();
    } catch (e) { setMessage({ type: 'error', text: e instanceof Error ? e.message : 'Aksi gagal.' }); }
  }

  return <div className="content account-page">
    <PageHeader title="Admin" kicker="Akun akreditasi" caption="Kelola akun pengguna portal akreditasi. Akun Anda sendiri tidak bisa diblokir, dihapus, atau dicabut status adminnya." />
    {message && <Notice type={message.type}>{message.text}</Notice>}
    <section className="progress-overview">
      <StatCard label="Total akun" value={data.summary.total_akun} />
      <StatCard label="Admin" value={data.summary.admin} note="termasuk Anda" />
      <StatCard label="Diblokir" value={data.summary.diblokir} note="tidak bisa login" />
    </section>
    <ResetPasswordPanel />
    <section className="section">
      <div className="section-title-row"><div><p className="section-kicker">Semua pengguna</p><h2>Daftar akun</h2></div></div>
      <div className="data-table-wrap"><table className="data-table"><caption className="sr-only">Daftar akun portal akreditasi</caption>
        <thead><tr><th scope="col">Nama</th><th scope="col">Email</th><th scope="col">Terdaftar</th><th scope="col">Login terakhir</th><th scope="col">Status</th><th scope="col">Peran</th><th scope="col">Dokumen</th></tr></thead>
        <tbody>{data.users.map(u => <tr key={u.id}>
          <td>{u.nama}{u.diri_sendiri && <span className="tag">akun Anda</span>}</td>
          <td>{u.email}</td>
          <td>{u.terdaftar ?? '-'}</td>
          <td>{u.login_terakhir ?? '-'}</td>
          <td>{u.is_blocked ? 'Diblokir' : 'Aktif'}</td>
          <td>{u.is_admin ? 'Admin' : '—'}</td>
          <td>{u.n_generate}</td>
        </tr>)}</tbody>
      </table></div>
    </section>
    <section className="section">
      <div className="section-title-row"><div><p className="section-kicker">Kelola akun</p><h2>Aksi per akun</h2></div></div>
      <div className="admin-grid">{data.users.map(u => <article className={`admin-card ${u.is_blocked ? 'is-blocked' : ''}`} key={u.id}>
        <div className="admin-card__head"><b>{u.nama}</b>{u.is_admin && <span className="status-pill">Admin</span>}{u.diri_sendiri && <span className="status-pill">Akun Anda</span>}</div>
        <p className="section-note">{u.email} · {u.n_generate} dokumen digenerate</p>
        <div className="admin-card__actions">
          {u.is_blocked
            ? <button className="button" type="button" disabled={u.diri_sendiri} title={u.diri_sendiri ? 'Tidak berlaku untuk akun sendiri' : undefined} onClick={() => aksi(u.id, 'blokir', false)}>Buka blokir</button>
            : <button className="button" type="button" disabled={u.diri_sendiri} title={u.diri_sendiri ? 'Tidak berlaku untuk akun sendiri' : undefined} onClick={() => aksi(u.id, 'blokir', true)}>Blokir</button>}
          {u.is_admin
            ? <button className="button" type="button" disabled={u.diri_sendiri} title={u.diri_sendiri ? 'Tidak berlaku untuk akun sendiri' : undefined} onClick={() => aksi(u.id, 'admin', false)}>Cabut admin</button>
            : <button className="button" type="button" disabled={u.diri_sendiri} title={u.diri_sendiri ? 'Tidak berlaku untuk akun sendiri' : undefined} onClick={() => aksi(u.id, 'admin', true)}>Jadikan admin</button>}
          <button className="button button--danger" type="button" disabled={u.diri_sendiri} title={u.diri_sendiri ? 'Tidak berlaku untuk akun sendiri' : undefined} onClick={() => setKonfirmasi(u.id)}>Hapus</button>
        </div>
        {konfirmasi === u.id && <div className="admin-confirm">
          <p>Hapus akun <b>{u.email}</b> secara permanen? Riwayat laporannya ikut terhapus; data yang sudah ia konfirmasi tetap ada.</p>
          <button className="button button--danger" type="button" onClick={() => aksi(u.id, 'hapus')}>Ya, hapus</button>
          <button className="button" type="button" onClick={() => setKonfirmasi(null)}>Batal</button>
        </div>}
      </article>)}</div>
    </section>
  </div>;
}
