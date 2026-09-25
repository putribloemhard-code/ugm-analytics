import { useState } from 'react';

import { setItemFinal, type Workspace, type WorkspaceGroup, type WorkspaceItem } from './lib/api';
import { Notice } from './ui';
import { pesan, useItemEditor, waktu } from './akreditasi-edit';

/* Review dokumen LED/LKPS: satu bagian (item) per halaman seperti dokumen, bisa diedit langsung di
   halaman atau lewat tabel isian ("Edit di tabel"). Keduanya menyimpan ke data laporan yang sama.
   Tiap bagian ditandai Draft/Final; menyimpan ulang mengembalikannya ke Draft (lihat backend). */

const PLACEHOLDER: Record<WorkspaceItem['kategori'], string> = {
  tersedia: '[DATA TIDAK TERSEDIA]',
  akses_data: '[DATA TIDAK TERSEDIA]',
  penyusunan: '[NARASI PERLU DISUSUN TIM PENYUSUN PRODI]',
};

function sumberIsian(item: WorkspaceItem): string {
  if (item.terisi) return item.diisi_oleh?.startsWith('AI: ') ? `Ekstraksi AI (${item.diisi_oleh.slice(4)})` : `Isian tim${item.diisi_oleh ? ` · ${item.diisi_oleh}` : ''}`;
  if (item.live) return 'Data live dari sumber resmi';
  return 'Belum ada isian';
}

type Bagian = { item: WorkspaceItem; grup: WorkspaceGroup };

/** Jenjang sering sudah ada di nama ("Magister Elektronika ..."), jangan diulang di kop. */
function namaProdi(p: Workspace['prodi']): string {
  return p.jenjang && !p.nama.toLowerCase().includes(p.jenjang.toLowerCase()) ? `${p.jenjang} ${p.nama}` : p.nama;
}

function HalamanItem({ bagian, nomor, total, workspace, onNav, onChange, onEditTabel }: {
  bagian: Bagian; nomor: number; total: number; workspace: Workspace;
  onNav: (arah: -1 | 1) => void; onChange: () => void; onEditTabel: () => void;
}) {
  const { item, grup } = bagian;
  const ed = useItemEditor(item, workspace.laporan.id, onChange);
  const [tujuan, setTujuan] = useState<-1 | 1 | null>(null);
  const [pesanFinal, setPesanFinal] = useState<{ type: 'info' | 'error'; text: string } | null>(null);
  const [sibukFinal, setSibukFinal] = useState(false);
  const placeholder = PLACEHOLDER[item.kategori];

  function pindah(arah: -1 | 1) { if (ed.dirty) setTujuan(arah); else onNav(arah); }
  async function simpanLalu(arah: -1 | 1) { if (await ed.simpan()) { setTujuan(null); onNav(arah); } }
  async function final(nilai: boolean) {
    setSibukFinal(true); setPesanFinal(null);
    try { const r = await setItemFinal(workspace.laporan.id, [item.id], nilai); setPesanFinal({ type: 'info', text: r.message }); onChange(); }
    catch (e) { setPesanFinal({ type: 'error', text: pesan(e, 'Status gagal diubah.') }); }
    finally { setSibukFinal(false); }
  }

  return <article className="review__doc" aria-labelledby="review-judul-item">
    <div className="review__toolbar">
      <div>
        <p className="review__posisi" id="review-judul-item">{nomor} / {total} · {item.nama}{item.tabel_lkps && ` (Tabel ${item.tabel_lkps})`}</p>
        <p className="review__status">Status: <span className={`state-badge ${item.final ? 'terisi' : 'kosong'}`}>{item.final ? 'Final' : 'Draft'}</span>
          {item.final && <small> oleh {item.final.oleh ?? '-'} · {waktu(item.final.waktu)}</small>}</p>
      </div>
      <div className="review__nav">
        <button type="button" className="button secondary" disabled={nomor <= 1} onClick={() => pindah(-1)}>‹ Prev</button>
        <button type="button" className="button secondary" disabled={nomor >= total} onClick={() => pindah(1)}>Next ›</button>
      </div>
    </div>
    {tujuan != null && <div className="review__konfirmasi" role="alertdialog" aria-label="Perubahan belum disimpan">
      <p>Ada perubahan di bagian ini yang belum disimpan.</p>
      <button type="button" className="button" disabled={ed.sibuk} onClick={() => simpanLalu(tujuan)}>Simpan & lanjut</button>
      <button type="button" className="button secondary" onClick={() => { ed.batal(); setTujuan(null); onNav(tujuan); }}>Buang perubahan</button>
      <button type="button" className="link-button" onClick={() => setTujuan(null)}>Tetap di sini</button>
    </div>}
    <div className="review__sumber">
      <span>Isi bagian ini</span>
      <span className={`state-badge ${item.terisi ? 'terisi' : item.live ? 'live' : 'kosong'}`}>{sumberIsian(item)}</span>
    </div>

    <div className="kertas__halaman review__halaman">
      <header className="review__kop">
        <p>{workspace.prodi.fakultas ?? 'Universitas Gadjah Mada'}</p>
        <p>{namaProdi(workspace.prodi)}</p>
        <hr />
        <p className="review__kop-judul">{workspace.dokumen === 'LED' ? 'LAPORAN EVALUASI DIRI' : 'LAPORAN KINERJA PROGRAM STUDI'}</p>
        <p>{workspace.laporan.nama}</p>
      </header>
      <p className="review__grup">{grup.label}</p>
      <h3 className="review__judul">{item.tabel_lkps ? `Tabel ${item.tabel_lkps} — ${item.nama}` : item.nama}</h3>
      {item.deskripsi && <p className="review__deskripsi">{item.deskripsi}</p>}

      {!item.terisi && item.live && !ed.dirty && <div className="review__live">
        <p>Belum diisi tim. Laporan Word memakai data live berikut; salin ke isian bila ingin mengeditnya.</p>
        <button type="button" className="link-button" onClick={ed.salinLive}>Salin data live ke isian</button>
      </div>}

      {item.tipe === 'narasi'
        ? <div className="review__narasi">{item.kolom.map(k => <div key={k} className="review__paragraf">
            <label htmlFor={`rv-${item.id}-${k}`}>{k}</label>
            <textarea id={`rv-${item.id}-${k}`} className="review__teks" rows={2} placeholder={placeholder}
              value={ed.rows[0]?.[k] ?? ''} onChange={e => ed.ubah(0, k, e.target.value)} disabled={!item.editable} />
          </div>)}</div>
        : <div className="review__tabel-wrap"><table className="review__tabel">
            <caption className="sr-only">{item.nama}</caption>
            <thead><tr><th scope="col">No</th>{item.kolom.map(k => <th key={k} scope="col">{k}</th>)}<th scope="col"><span className="sr-only">Aksi</span></th></tr></thead>
            <tbody>{ed.rows.map((r, i) => <tr key={i}>
              <td>{i + 1}</td>
              {item.kolom.map(k => <td key={k}>
                <textarea className="review__sel" rows={1} aria-label={`${k}, baris ${i + 1}`} placeholder={i === 0 && ed.rows.length === 1 ? placeholder : ''}
                  value={r[k] ?? ''} onChange={e => ed.ubah(i, k, e.target.value)} disabled={!item.editable} />
              </td>)}
              <td><button type="button" className="link-button" aria-label={`Hapus baris ${i + 1}`} onClick={() => ed.hapusBaris(i)}>Hapus</button></td>
            </tr>)}</tbody>
          </table>
          <button type="button" className="link-button review__tambah" onClick={ed.tambahBaris}>+ Tambah baris</button>
        </div>}
    </div>

    {ed.basi && <Notice type="warning">Bagian ini diubah di server (staf lain atau ekstraksi baru) saat Anda mengedit. Simpan untuk memakai isian Anda, atau <button className="link-button" onClick={ed.batal}>muat versi terbaru</button>.</Notice>}
    <div className="review__aksi">
      <button type="button" className="button" disabled={ed.sibuk || !ed.dirty} onClick={ed.simpan}>{ed.sibuk ? 'Menyimpan…' : 'Simpan perubahan'}</button>
      {ed.dirty && <button type="button" className="link-button" onClick={ed.batal}>Batalkan perubahan</button>}
      <button type="button" className="button secondary" onClick={onEditTabel}>Edit di tabel</button>
      {item.final
        ? <button type="button" className="button secondary" disabled={sibukFinal} onClick={() => final(false)}>Kembalikan ke draft</button>
        : <button type="button" className="button secondary" disabled={sibukFinal || ed.dirty} title={ed.dirty ? 'Simpan perubahan dulu' : undefined} onClick={() => final(true)}>Tandai final</button>}
    </div>
    {ed.status && <Notice type={ed.status.type}>{ed.status.text}</Notice>}
    {pesanFinal && <Notice type={pesanFinal.type}>{pesanFinal.text}</Notice>}
  </article>;
}

/** Langkah 1 "Review": halaman dokumen per bagian + panel status & kelengkapan. */
export function ReviewDokumen({ workspace, onChange, onEditTabel, onLanjut }: {
  workspace: Workspace; onChange: () => void; onEditTabel: (itemId: string, grup: string) => void; onLanjut: () => void;
}) {
  const bagian: Bagian[] = workspace.groups.flatMap(g => g.items.map(item => ({ item, grup: g })));
  const [idx, setIdx] = useState(0);
  const [pesanSemua, setPesanSemua] = useState<{ type: 'info' | 'error'; text: string } | null>(null);
  const [sibuk, setSibuk] = useState(false);
  const aktif = bagian[Math.min(idx, bagian.length - 1)];
  const r = workspace.ringkasan;
  const siapFinal = bagian.filter(b => !b.item.final && (b.item.terisi || b.item.live)).map(b => b.item.id);

  async function finalSemua() {
    setSibuk(true); setPesanSemua(null);
    try { const hasil = await setItemFinal(workspace.laporan.id, siapFinal, true); setPesanSemua({ type: 'info', text: hasil.message }); onChange(); }
    catch (e) { setPesanSemua({ type: 'error', text: pesan(e, 'Finalisasi gagal.') }); }
    finally { setSibuk(false); }
  }
  if (!aktif) return <Notice type="info">Dokumen ini belum punya bagian.</Notice>;
  return <div className="review">
    <HalamanItem key={aktif.item.id} bagian={aktif} nomor={idx + 1} total={bagian.length} workspace={workspace}
      onNav={arah => setIdx(i => Math.max(0, Math.min(bagian.length - 1, i + arah)))} onChange={onChange}
      onEditTabel={() => onEditTabel(aktif.item.id, aktif.grup.key)} />
    <aside className="review__side" aria-label="Status dan kelengkapan">
      <section className="profil-panel">
        <h2 className="profil-panel__head">Bagian ini</h2>
        <div className="review__side-isi">
          <span className={`state-badge kategori-${aktif.item.kategori}`}>{aktif.item.kategori_label}</span>
          <p className="review__side-sumber"><b>Sumber data:</b> {aktif.item.sumber_asli ?? aktif.item.sumber_data}</p>
          {aktif.item.kategori === 'akses_data' && aktif.item.catatan && <p className="field-hint">{aktif.item.catatan}</p>}
        </div>
      </section>
      <section className="profil-panel">
        <h2 className="profil-panel__head">Kelengkapan per bagian</h2>
        <ul className="review__bar-list">{workspace.groups.map(g => {
          const n = g.items.filter(i => i.terisi || i.live).length;
          const f = g.items.filter(i => i.final).length;
          const pertama = bagian.findIndex(b => b.grup.key === g.key);
          return <li key={g.key}>
            <button type="button" className={`review__bar ${aktif.grup.key === g.key ? 'is-aktif' : ''}`} onClick={() => setIdx(pertama)} title={g.label}>
              <span className="review__bar-nama">{g.label}</span>
              <span className="review__bar-track" aria-hidden="true"><span style={{ width: `${(100 * n) / g.items.length}%` }} /></span>
              <span className="review__bar-angka">{n}/{g.items.length}{f ? ` · ${f} final` : ''}</span>
            </button>
          </li>;
        })}</ul>
      </section>
      <section className="profil-panel review__final">
        <p><b>{r.final}</b> dari {r.total} bagian difinalisasi</p>
        <button type="button" className="button secondary" disabled={sibuk || siapFinal.length === 0} onClick={finalSemua}>
          {sibuk ? 'Memproses…' : `Finalisasi semua yang terisi (${siapFinal.length})`}
        </button>
        {pesanSemua && <Notice type={pesanSemua.type}>{pesanSemua.text}</Notice>}
        <button type="button" className="button" onClick={onLanjut}>Lanjut ke Download ›</button>
      </section>
    </aside>
  </div>;
}
