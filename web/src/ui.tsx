import type { ReactNode } from 'react';

import { assetUrl } from './shell';

/** Judul halaman dengan ikon opsional — dipakai halaman Akreditasi, Profil, dan Admin.
 *  Ikon hanya boleh nama berkas yang benar-benar ada di web/public/logo/. */
export function PageHeader({ title, icon, kicker, caption }: { title: string; icon?: string; kicker?: string; caption?: string }) {
  return <header>{kicker && <p className="section-kicker">{kicker}</p>}<h1 className="page-heading">{icon && <img src={assetUrl(`logo/${icon}`)} alt="" />}{title}</h1>{caption && <p className="page-caption">{caption}</p>}</header>;
}

/** Kotak pesan standar (info/warning/error); error dibacakan sebagai alert. */
export function Notice({ type, children }: { type: 'info' | 'warning' | 'error'; children: ReactNode }) {
  return <div className={`notice ${type}`} role={type === 'error' ? 'alert' : 'status'}>{children}</div>;
}


/** Bar kelengkapan dengan teks persentase. */
export function ProgressLine({ value, total, percent, note }: { value: number; total: number; percent: number; note?: string }) {
  return <div className="completion-line"><div><b>Kelengkapan: {value}/{total} item ({percent}%)</b>{note && <span> · {note}</span>}</div><div className="progress-track"><div style={{ width: `${percent}%` }} /></div></div>;
}
