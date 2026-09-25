import { useEffect, useState } from 'react';
import { Link, Navigate, useLocation } from 'react-router-dom';

import { accreditationAdminAction, accreditationAdminUsers, accreditationMe, accreditationProfile, daftarPengajuanReset, downloadAccreditationHistory, getRefreshStatus, putuskanReset, simpanBlob, startRefresh, type AdminOverview, type PengajuanReset, type ProfileResult, type RefreshStatus } from './lib/api';
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
  return <div className="content account-page">
    <PageHeader title="Profil Saya" kicker="Akun akreditasi" caption="Identitas akun, pekerjaan yang sedang berjalan, dan riwayat laporan yang pernah dibuat." />
    <section className="profile-identity">
      <div className="field"><span className="field__label">Nama</span><b>{identitas.nama}</b></div>
      <div className="field"><span className="field__label">Email</span><b>{identitas.email}</b></div>
      <div className="field"><span className="field__label">Terdaftar sejak</span><b>{identitas.terdaftar ?? '-'}</b></div>
      <div className="field"><span className="field__label">Login terakhir</span><b>{identitas.login_terakhir ?? '-'}</b></div>
    </section>
    <section className="progress-overview">
      <StatCard label="Dokumen digenerate" value={stats.dokumen_digenerate} note="laporan Word" />
      <StatCard label="Dokumen diupload" value={stats.dokumen_diupload} note="file pendukung" />
      <StatCard label="Pekerjaan berjalan" value={ongoing.length} note="laporan yang Anda isi" />
      <StatCard label="Riwayat tersimpan" value={riwayat.total} note={`ditampilkan maks. ${riwayat.batas}`} />
    </section>
    <section className="section">
      <div className="section-title-row"><div><p className="section-kicker">Sedang dikerjakan</p><h2>Laporan yang Anda isi</h2></div>{identitas.is_admin && <span className="status-pill">Admin</span>}</div>
      {ongoing.length === 0
        ? <Notice type="info">Belum ada pekerjaan. Laporan yang item-nya Anda simpan di halaman Akreditasi akan muncul di sini.</Notice>
        : <div className="ongoing-list">{ongoing.map(k => <article className="ongoing-card" key={k.laporan_id}>
          <div className="ongoing-card__head"><b>{k.nama_prodi}</b><span className="status-pill">{k.nama_laporan}</span></div>
          <p className="section-note">{k.nama_fakultas ?? 'Prodi tidak terhubung ke fakultas.'}</p>
          <ProgressLine value={k.lengkap} total={k.total} percent={k.persen} note={`${k.item_milik_user} item disimpan oleh Anda`} />
          <Link className="button" to={`/akreditasi?prodi=${encodeURIComponent(k.prodi_id)}&dokumen=${k.dokumen}&laporan=${k.laporan_id}`}>Lanjutkan</Link>
        </article>)}</div>}
    </section>
    <section className="section">
      <div className="section-title-row"><div><p className="section-kicker">Riwayat dokumen</p><h2>Laporan yang pernah dibuat</h2></div></div>
      {riwayat.rows.length === 0
        ? <Notice type="info">Belum ada laporan yang Anda buat.</Notice>
        : <>
          {riwayat.total > riwayat.batas && <p className="section-note">Menampilkan {riwayat.batas} laporan terbaru dari {riwayat.total}.</p>}
          <div className="data-table-wrap"><table className="data-table"><caption className="sr-only">Riwayat laporan akreditasi milik Anda</caption>
            <thead><tr><th scope="col">Program studi</th><th scope="col">Dokumen</th><th scope="col">Digenerate</th><th scope="col"><span className="sr-only">Unduh</span></th></tr></thead>
            <tbody>{riwayat.rows.map(r => <tr key={r.id}><td>{r.nama_prodi}</td><td>{r.jenis_dokumen}</td><td>{r.digenerate ?? '-'}</td><td><UnduhRiwayat id={r.id} /></td></tr>)}</tbody>
          </table></div>
        </>}
    </section>
  </div>;
}

function waktuLokal(iso: string | null): string {
  if (!iso) return '-';
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString('id-ID', { dateStyle: 'medium', timeStyle: 'short' });
}

const REFRESH_LABEL: Record<RefreshStatus['status'], string> = {
  running: 'Sedang berjalan', finished: 'Selesai', idle: 'Belum pernah dijalankan dari web', stale_lock: 'Terhenti (lock lama akan dibersihkan)',
};

/** Tombol update data berita (padanan "🔄 Update Berita Terbaru" dashboard Streamlit lama). */
function UpdateDataPanel() {
  const [st, setSt] = useState<RefreshStatus | null>(null);
  const [pesan, setPesan] = useState<{ type: 'info' | 'error'; text: string } | null>(null);
  const [sibuk, setSibuk] = useState(false);
  const muat = () => getRefreshStatus().then(setSt).catch(e => setPesan({ type: 'error', text: e instanceof Error ? e.message : 'Status update belum dapat dimuat.' }));
  useEffect(() => { muat(); }, []);
  // Selama pipeline berjalan, pantau status + log tiap 5 detik.
  useEffect(() => {
    if (st?.status !== 'running') return;
    const t = window.setTimeout(muat, 5000);
    return () => window.clearTimeout(t);
  }, [st]);
  async function mulai() {
    setSibuk(true); setPesan(null);
    try { const r = await startRefresh(); setPesan({ type: 'info', text: `${r.message} (PID ${r.pid})` }); await muat(); }
    catch (e) { setPesan({ type: 'error', text: e instanceof Error ? e.message : 'Update gagal dimulai.' }); }
    finally { setSibuk(false); }
  }
  return <section className="section">
    <div className="section-title-row"><div><p className="section-kicker">Data berita ugm.ac.id</p><h2>Update data</h2></div>
      {st && <span className="status-pill">{REFRESH_LABEL[st.status]}</span>}</div>
    <p className="section-note">Menjalankan seluruh pipeline (sitemap → RSS → ambil berita baru → normalisasi → tagging → narasi → laporan) di latar belakang, ±10 menit. Cron mingguan tetap berjalan setiap Sabtu 06:00; keduanya tidak akan jalan bersamaan.</p>
    {st && <dl className="requirement-meta">
      <div><dt>Data terakhir</dt><dd>{waktuLokal(st.updated_at)}</dd></div>
      <div><dt>Log update web terakhir</dt><dd>{waktuLokal(st.log_updated_at)}{st.last_exit !== null && (st.last_exit === 0 ? ' · berhasil' : ' · gagal, cek log')}</dd></div>
    </dl>}
    <div className="action-row">
      <button className="button" type="button" disabled={sibuk || !st?.trigger_available || st?.status === 'running'} onClick={mulai}>{st?.status === 'running' ? 'Update sedang berjalan…' : 'Update berita terbaru'}</button>
      {st && !st.trigger_available && <span className="field-hint">Tidak tersedia di server ini: venv pipeline tidak ditemukan (set UGM_ANALYTICS_PYTHON).</span>}
    </div>
    {pesan && <Notice type={pesan.type}>{pesan.text}</Notice>}
    {st && st.log_tail.length > 0 && <details className="update-log" open={st.status === 'running'}><summary>Log terakhir</summary><pre>{st.log_tail.join('\n')}</pre></details>}
  </section>;
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
    <UpdateDataPanel />
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
