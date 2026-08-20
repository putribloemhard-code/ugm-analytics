import pandas as pd

MATKUL_SDG_KEYWORD = {
    13: {'nama': 'Penanganan Perubahan Iklim',
         'keywords': ['perubahan iklim', 'climate change', 'pemanasan global',
                      'global warming', 'mitigasi iklim', 'adaptasi iklim']},
    7:  {'nama': 'Energi Bersih dan Terjangkau',
         'keywords': ['energi terbarukan', 'renewable energy', 'energi bersih',
                      'energi surya', 'energi angin', 'biomassa energi']},
    12: {'nama': 'Konsumsi dan Produksi Bertanggung Jawab',
         'keywords': ['pengelolaan limbah', 'waste management', 'ekonomi sirkular',
                      'circular economy', 'daur ulang', 'recycling',
                      'konsumsi berkelanjutan', 'produksi bersih']},
    15: {'nama': 'Ekosistem Daratan',
         'keywords': ['keanekaragaman hayati', 'biodiversitas', 'biodiversity',
                      'konservasi lingkungan', 'konservasi hutan', 'restorasi lahan',
                      'rehabilitasi lahan', 'ekosistem darat', 'flora fauna']},
    14: {'nama': 'Ekosistem Lautan',
         'keywords': ['ekosistem laut', 'konservasi laut', 'restorasi mangrove',
                      'pesisir', 'kelautan', 'marine ecosystem', 'terumbu karang']},
    6:  {'nama': 'Air Bersih dan Sanitasi',
         'keywords': ['pengelolaan air', 'water management', 'sanitasi',
                      'kualitas air', 'daur ulang air']},
    2:  {'nama': 'Tanpa Kelaparan',
         'keywords': ['ketahanan pangan', 'food security', 'pertanian berkelanjutan',
                      'sustainable agriculture']},
}


def map_matkul_ke_sdg(deskripsi_matkul):
    """Cek deskripsi mata kuliah, kembalikan daftar SDG yang match (bisa lebih dari 1)."""
    if pd.isna(deskripsi_matkul) or not str(deskripsi_matkul).strip():
        return []
    teks = str(deskripsi_matkul).lower()
    hasil = []
    for sdg_num, info in MATKUL_SDG_KEYWORD.items():
        if any(kw in teks for kw in info['keywords']):
            hasil.append(sdg_num)
    return hasil


if __name__ == '__main__':
    df = pd.read_csv('data/elok_matkul_bersih.csv')
    print(f"Total mata kuliah (setelah dedup/bersih): {len(df)}")
    df['sdg_list'] = df['deskripsi'].apply(map_matkul_ke_sdg)
    df['jumlah_sdg_match'] = df['sdg_list'].apply(len)
    matkul_dengan_sdg = df[df['jumlah_sdg_match'] > 0]
    print(f"Mata kuliah yang match ke minimal 1 SDG: {len(matkul_dengan_sdg)}")
    baris_sdg = []
    for _, row in matkul_dengan_sdg.iterrows():
        for sdg in row['sdg_list']:
            baris_sdg.append({
                'judul_course': row['nama_normal'],
                'fakultas': row['fakultas'],
                'sdg': sdg,
                'nama_sdg': MATKUL_SDG_KEYWORD[sdg]['nama'],
            })
    df_sdg = pd.DataFrame(baris_sdg)
    df_sdg.to_csv('data/elok_matkul_dengan_sdg.csv', index=False)
    print(f"Tersimpan di data/elok_matkul_dengan_sdg.csv ({len(df_sdg)} baris)")
    print("\nJumlah mata kuliah per SDG:")
    print(df_sdg.groupby(['sdg', 'nama_sdg']).size().sort_values(ascending=False))
    persentase = len(matkul_dengan_sdg) / len(df) * 100 if len(df) > 0 else 0
    print(f"\nCakupan: {persentase:.1f}% dari mata kuliah bersih match ke minimal 1 SDG")
