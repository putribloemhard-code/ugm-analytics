import pandas as pd
import re

def normalisasi_nama_matkul(judul):
    """Hapus penanda kelas/dosen dari judul course eLOK, biar course yang sama tidak terhitung dobel."""
    nama = str(judul).strip()
    nama = re.sub(r'(Kelas\s*[A-Z])', '', nama, flags=re.IGNORECASE)
    nama = re.sub(r'Kelas\s*[A-Z]\b', '', nama, flags=re.IGNORECASE)
    nama = re.sub(r'\s+[A-Z]-[A-Z][a-z]+(\s+[A-Z][a-z]+)*$', '', nama)
    nama = re.sub(r'([A-Z]{2,5}\d{3,5})', '', nama)
    nama = re.sub(r'\s+', ' ', nama).strip()
    return nama

def gabungkan_duplikat_matkul(df):
    """Group course yang namanya sama (dalam fakultas+program yang sama) setelah normalisasi,
    ambil deskripsi paling lengkap."""
    df = df.copy()
    if 'program' not in df.columns:
        df['program'] = ''
    df['program'] = df['program'].fillna('')
    df['nama_normal'] = df['judul_course'].apply(normalisasi_nama_matkul)
    df['nama_normal_lower'] = df['nama_normal'].str.lower()
    df['panjang_deskripsi'] = df['deskripsi'].fillna('').astype(str).str.len()
    df = df.sort_values('panjang_deskripsi', ascending=False)
    df_unik = df.drop_duplicates(subset=['nama_normal_lower', 'fakultas', 'program'], keep='first')
    return df_unik[['nama_normal', 'deskripsi', 'fakultas', 'program']].reset_index(drop=True)

if __name__ == '__main__':
    df_mentah = pd.read_csv('data/elok_matkul_mentah.csv')
    print(f"Data mentah: {len(df_mentah)} baris")
    df_bersih = gabungkan_duplikat_matkul(df_mentah)
    print(f"Setelah dedup: {len(df_bersih)} baris")
    df_bersih.to_csv('data/elok_matkul_bersih.csv', index=False)
    print("Tersimpan di data/elok_matkul_bersih.csv")
    print("\nContoh 10 baris pertama:")
    print(df_bersih.head(10))