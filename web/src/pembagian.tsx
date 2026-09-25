import { useState } from 'react';

import type { PembagianDampak } from './lib/api';

const fmt = (n: number) => n.toLocaleString('id-ID');
const persen = (n: number) => `${n.toLocaleString('id-ID', { maximumFractionDigits: 1 })}%`;
const KELAS: Record<string, string> = { Sosial: 'sosial', Ekonomi: 'ekonomi', Lingkungan: 'lingkungan', multi2: 'multi2', multi3: 'multi3' };

/** Donat irisan tanpa tumpang tindih (total = semua berita dampak) + batang jumlah per dampak.
 *  Pie biasa dari jumlah per dampak akan menyesatkan: satu berita bisa masuk beberapa dampak,
 *  sehingga ketiga angka itu dijumlahkan melebihi total. */
export function PembagianDampakChart({ data }: { data: PembagianDampak }) {
  const [aktif, setAktif] = useState<string | null>(null);
  if (!data.total) return null;
  const R = 70, KELILING = 2 * Math.PI * R, CELAH = 2;
  const irisan = data.irisan.filter(s => s.jumlah > 0);
  let mulai = 0;
  const busur = irisan.map(s => {
    const panjang = (s.jumlah / data.total) * KELILING;
    const b = { ...s, offset: -mulai, panjang: Math.max(panjang - (irisan.length > 1 ? CELAH : 0), 0.5) };
    mulai += panjang;
    return b;
  });
  const sorot = irisan.find(s => s.kunci === aktif);
  const puncakPilar = Math.max(...data.per_pilar.map(p => p.jumlah), 1);
  const jumlahPilar = data.per_pilar.reduce((a, p) => a + p.jumlah, 0);

  return <figure className="pembagian" aria-labelledby="pembagian-judul">
    <figcaption id="pembagian-judul" className="pembagian__judul">Pembagian berita dampak</figcaption>
    <div className="pembagian__grid">
      <div className="pembagian__donat-wrap">
        <div className="pembagian__donat">
          <svg viewBox="0 0 180 180" role="img" aria-label={`Donat pembagian ${fmt(data.total)} berita dampak: ${irisan.map(s => `${s.label} ${fmt(s.jumlah)}`).join(', ')}`}>
            <circle cx="90" cy="90" r={R} className="pembagian__lintasan" />
            {busur.map(s => <circle key={s.kunci} cx="90" cy="90" r={R}
              className={`pembagian__busur pembagian--${KELAS[s.kunci] ?? 'lain'} ${aktif && aktif !== s.kunci ? 'is-redup' : ''}`}
              strokeDasharray={`${s.panjang} ${KELILING}`} strokeDashoffset={s.offset} transform="rotate(-90 90 90)"
              onMouseEnter={() => setAktif(s.kunci)} onMouseLeave={() => setAktif(null)}>
              <title>{`${s.label}: ${fmt(s.jumlah)} berita (${persen(s.persen)})`}</title>
            </circle>)}
          </svg>
          <div className="pembagian__tengah" aria-hidden="true">
            {sorot
              ? <><strong>{persen(sorot.persen)}</strong><span>{sorot.label}</span></>
              : <><strong>{fmt(data.total)}</strong><span>berita dampak</span></>}
          </div>
        </div>
        <ul className="pembagian__legenda">
          {data.irisan.map(s => <li key={s.kunci} className={aktif === s.kunci ? 'is-aktif' : ''}
            onMouseEnter={() => setAktif(s.kunci)} onMouseLeave={() => setAktif(null)}>
            <i className={`pembagian__kunci pembagian--${KELAS[s.kunci] ?? 'lain'}`} aria-hidden="true" />
            <span className="pembagian__label">{s.label}</span>
            <span className="pembagian__angka">{fmt(s.jumlah)} <small>{persen(s.persen)}</small></span>
          </li>)}
        </ul>
      </div>
      <div className="pembagian__batang">
        <p className="pembagian__sub">Jumlah berita per dampak</p>
        <ul>
          {data.per_pilar.map(p => <li key={p.pilar}>
            <span className="pembagian__label">{p.pilar}</span>
            <span className="pembagian__bar" aria-hidden="true"><span className={`pembagian--${KELAS[p.pilar] ?? 'lain'}`} style={{ width: `${(100 * p.jumlah) / puncakPilar}%` }} /></span>
            <span className="pembagian__angka">{fmt(p.jumlah)} <small>{persen(p.persen)}</small></span>
          </li>)}
        </ul>
        <p className="chart-note">Persentase terhadap {fmt(data.total)} berita dampak. Jumlah ketiganya {fmt(jumlahPilar)}, lebih dari total, karena satu berita bisa masuk lebih dari satu dampak; donat memisahkan berita yang masuk satu, dua, atau tiga dampak.</p>
      </div>
    </div>
  </figure>;
}
