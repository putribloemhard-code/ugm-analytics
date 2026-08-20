"""Tagging mata kuliah ke topik resmi Kepmen 361/M/KEP/2025 — Dampak Lingkungan, Tema 5 (Pendidikan dan Penelitian).

Cara kerja:
1. Baca data/elok_matkul_bersih.csv (hasil normalize_matkul.py).
2. Keyword matching (substring, case-insensitive) ke judul + deskripsi tiap matkul.
3. Matkul yang match >= 1 topik ditandai 'terkait_sustainability'.
4. Simpan hasil per-course + ringkasan per fakultas / prodi / topik / tahun.
"""
import os
import re

import pandas as pd

# 9 topik resmi (berdasarkan daftar topik Kepmen yang dipakai di dashboard)
# keyword pendek berisiko (mis. 'sda') dipisah ke 'boundary' -> pakai \b regex.
TOPIK_KEPMEN = {
    'pembangunan_berkelanjutan': {
        'nama': 'Pembangunan Berkelanjutan',
        'keywords': ['pembangunan berkelanjutan', 'sustainable development', 'keberlanjutan',
                     'sustainability', 'sdgs', 'tujuan pembangunan berkelanjutan'],
        'boundary': ['sdg'],
    },
    'perubahan_iklim': {
        'nama': 'Perubahan Iklim',
        'keywords': ['perubahan iklim', 'climate change', 'pemanasan global', 'global warming',
                     'mitigasi iklim', 'adaptasi iklim', 'krisis iklim', 'net zero',
                     'karbon'],
        'boundary': [],
    },
    'energi_terbarukan': {
        'nama': 'Energi Terbarukan',
        'keywords': ['energi terbarukan', 'renewable energy', 'energi bersih', 'energi surya',
                     'energi angin', 'solar energy', 'wind energy', 'biomassa', 'bioenergi',
                     'biofuel', 'energi alternatif', 'energi hijau', 'panas bumi', 'geothermal'],
        'boundary': [],
    },
    'pengelolaan_limbah': {
        'nama': 'Pengelolaan Limbah',
        'keywords': ['pengelolaan limbah', 'pengolahan limbah', 'limbah', 'waste management',
                     'waste treatment', 'wastewater', 'air limbah', 'limbah padat', 'limbah cair',
                     'limbah b3', 'sampah', 'polusi', 'pencemaran', 'emisi'],
        'boundary': [],
    },
    'ekonomi_sirkular': {
        'nama': 'Ekonomi Sirkular',
        'keywords': ['ekonomi sirkular', 'circular economy', 'daur ulang', 'recycling',
                     'recycle', 'upcycle', 'reuse', 'sirkular'],
        'boundary': [],
    },
    'konservasi_lingkungan': {
        'nama': 'Konservasi Lingkungan',
        'keywords': ['konservasi', 'conservation', 'pelestarian', 'perlindungan lingkungan',
                     'environmental protection', 'kawasan lindung', 'kawasan konservasi'],
        'boundary': [],
    },
    'keanekaragaman_hayati': {
        'nama': 'Keanekaragaman Hayati',
        'keywords': ['keanekaragaman hayati', 'biodiversitas', 'biodiversity', 'kehati',
                     'flora', 'fauna', 'satwa', 'satwa liar', 'habitat', 'ekologi',
                     'ecology', 'ekosistem', 'ecosystem', 'spesies', 'wildlife'],
        'boundary': [],
    },
    'rehabilitasi_restorasi': {
        'nama': 'Rehabilitasi/Restorasi Lingkungan',
        'keywords': ['rehabilitasi', 'restorasi', 'restoration', 'rehabilitasi lahan',
                     'reforestasi', 'reboisasi', 'revegetasi', 'penghijauan', 'reklamasi',
                     'pemulihan lingkungan', 'pemulihan ekosistem'],
        'boundary': [],
    },
    'pengelolaan_sda': {
        'nama': 'Pengelolaan Sumber Daya Alam',
        'keywords': ['sumber daya alam', 'natural resource', 'pengelolaan hutan', 'forest management',
                     'pengelolaan air', 'water management', 'pengelolaan lahan', 'land management',
                     'pengelolaan pesisir', 'kelautan', 'perikanan', 'pertambangan', 'mineral',
                     'batubara', 'migas', 'tata kelola air', 'watershed', 'daerah aliran sungai',
                     'air tanah', 'groundwater', 'kehutanan', 'forestry', 'hutan'],
        'boundary': ['sda'],
    },
}


def match_topik(judul: str, deskripsi: str) -> list[str]:
    """Kembalikan daftar id topik yang match ke judul/deskripsi."""
    teks_judul = str(judul).lower() if pd.notna(judul) else ''
    teks_desk = str(deskripsi).lower() if pd.notna(deskripsi) else ''
    teks = f'{teks_judul} {teks_desk}'
    hasil = []
    for topik_id, info in TOPIK_KEPMEN.items():
        match = any(kw in teks for kw in info['keywords'])
        if not match:
            match = any(re.search(rf'\b{re.escape(kw)}\b', teks) for kw in info['boundary'])
        if match:
            hasil.append(topik_id)
    return hasil


def ekstrak_tahun(judul: str):
    """Tahun dari judul (mis. '... 2024'). None kalau tidak ada."""
    m = re.search(r'(19|20)\d{2}', str(judul))
    return int(m.group(0)) if m else None


def main():
    os.makedirs('data', exist_ok=True)
    df = pd.read_csv('data/elok_matkul_bersih.csv')
    print(f'Mata kuliah bersih: {len(df)} baris')

    df['topik_list'] = [match_topik(j, d) for j, d in zip(df['nama_normal'], df['deskripsi'])]
    df['jumlah_topik'] = df['topik_list'].apply(len)
    df['terkait_sustainability'] = df['jumlah_topik'] > 0
    df['tahun'] = df['nama_normal'].apply(ekstrak_tahun)

    n_match = int(df['terkait_sustainability'].sum())
    print(f'Terkait sustainability: {n_match} ({n_match/len(df)*100:.1f}%)')

    # --- per-course ---
    df_out = df.copy()
    df_out['nama_topik'] = df_out['topik_list'].apply(
        lambda ids: '; '.join(TOPIK_KEPMEN[i]['nama'] for i in ids))
    df_out[['nama_normal', 'fakultas', 'program', 'deskripsi', 'tahun',
            'nama_topik', 'jumlah_topik', 'terkait_sustainability']].to_csv(
        'data/elok_matkul_kepmen.csv', index=False)
    print('Tersimpan data/elok_matkul_kepmen.csv')

    # --- ringkasan per fakultas ---
    per_fak = (
        df_out.groupby('fakultas')
        .agg(total_matkul=('nama_normal', 'nunique'),
             matkul_sustainability=('terkait_sustainability', 'sum'))
        .reset_index()
    )
    per_fak['persen'] = (per_fak['matkul_sustainability'] / per_fak['total_matkul'] * 100).round(1)
    per_fak = per_fak.sort_values('matkul_sustainability', ascending=False)
    per_fak.to_csv('data/ringkasan_fakultas.csv', index=False)
    print(f'\n--- Per fakultas ({len(per_fak)}) ---')
    print(per_fak.to_string(index=False))

    # --- ringkasan per prodi (drill-down) ---
    per_prodi = (
        df_out.groupby(['fakultas', 'program'])
        .agg(total_matkul=('nama_normal', 'nunique'),
             matkul_sustainability=('terkait_sustainability', 'sum'))
        .reset_index()
    )
    per_prodi['program'] = per_prodi['program'].replace('', '(tanpa program)')
    per_prodi['persen'] = (per_prodi['matkul_sustainability'] / per_prodi['total_matkul'] * 100).round(1)
    per_prodi = per_prodi.sort_values(['matkul_sustainability', 'fakultas'], ascending=[False, True])
    per_prodi.to_csv('data/ringkasan_prodi.csv', index=False)
    print(f'\n--- Per prodi ({len(per_prodi)}) ---')
    print(per_prodi.to_string(index=False))

    # --- ringkasan per topik ---
    baris_topik = []
    for _, row in df_out[df_out['terkait_sustainability']].iterrows():
        for tid in row['topik_list']:
            baris_topik.append({'topik': TOPIK_KEPMEN[tid]['nama'],
                                'judul_course': row['nama_normal'],
                                'fakultas': row['fakultas']})
    df_topik = pd.DataFrame(baris_topik)
    ringkasan_topik = (
        df_topik.groupby('topik')
        .agg(jumlah_matkul=('judul_course', 'nunique'))
        .reset_index()
        .sort_values('jumlah_matkul', ascending=False)
    )
    ringkasan_topik.to_csv('data/ringkasan_topik.csv', index=False)
    print(f'\n--- Per topik ---')
    print(ringkasan_topik.to_string(index=False))

    # --- tren per tahun (kalau tersedia) ---
    df_tahun = df_out[df_out['tahun'].notna()].copy()
    print(f'\nJudul dengan tahun: {len(df_tahun)} / {len(df_out)}')
    if not df_tahun.empty:
        ringkasan_tahun = (
            df_tahun.groupby('tahun')
            .agg(total_matkul=('nama_normal', 'nunique'),
                 matkul_sustainability=('terkait_sustainability', 'sum'))
            .reset_index()
            .sort_values('tahun')
        )
        ringkasan_tahun.to_csv('data/ringkasan_tahun.csv', index=False)
        print(ringkasan_tahun.to_string(index=False))
    else:
        print('Tren tidak tersedia: tidak ada informasi tahun di data.')


if __name__ == '__main__':
    main()
