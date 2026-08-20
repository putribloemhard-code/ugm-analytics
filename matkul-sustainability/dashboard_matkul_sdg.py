import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Dampak Lingkungan - Mata Kuliah Sustainability", layout="wide")
st.title("🌱 Dampak Lingkungan: Integrasi Kurikulum Sustainability")
st.caption("Indikator resmi Kepmen 361/M/KEP/2025 — Dampak Lingkungan, Tema 5 (Pendidikan dan Penelitian)")

st.warning(
    "⚠️ Data ini masih SAMPLE dari eLOK (bukan cakupan penuh seluruh mata kuliah UGM), "
    "karena tergantung preferensi dosen menggunakan eLOK atau tidak. "
    "Angka di bawah TIDAK merepresentasikan total mata kuliah UGM secara resmi."
)

df_mentah = pd.read_csv('data/elok_matkul_mentah.csv')
df_bersih = pd.read_csv('data/elok_matkul_bersih.csv')
df_sdg = pd.read_csv('data/elok_matkul_dengan_sdg.csv')

col1, col2, col3, col4 = st.columns(4)
col1.metric("Data Mentah (sebelum dedup)", len(df_mentah))
col2.metric("Data Bersih (setelah dedup)", len(df_bersih))
col3.metric("Match ke Minimal 1 SDG", df_sdg['judul_course'].nunique())
col4.metric("Jumlah SDG Berbeda Terdeteksi", df_sdg['sdg'].nunique())

st.subheader("Jumlah Mata Kuliah per SDG")
ringkasan_sdg = df_sdg.groupby(['sdg', 'nama_sdg']).size().reset_index(name='jumlah')
ringkasan_sdg['label'] = 'SDG ' + ringkasan_sdg['sdg'].astype(str) + ' - ' + ringkasan_sdg['nama_sdg']
ringkasan_sdg = ringkasan_sdg.sort_values('jumlah', ascending=True)
fig1 = px.bar(ringkasan_sdg, x='jumlah', y='label', orientation='h', height=400)
st.plotly_chart(fig1, use_container_width=True)

st.subheader("Jumlah Mata Kuliah Terkait Sustainability per Fakultas")
per_fakultas = df_sdg.groupby('fakultas')['judul_course'].nunique().reset_index(name='jumlah_matkul')
per_fakultas = per_fakultas.sort_values('jumlah_matkul', ascending=True)
fig2 = px.bar(per_fakultas, x='jumlah_matkul', y='fakultas', orientation='h', height=400)
st.plotly_chart(fig2, use_container_width=True)

st.subheader("Detail Mata Kuliah per SDG")
sdg_pilihan = st.selectbox("Pilih SDG:", sorted(df_sdg['nama_sdg'].unique()))
detail = df_sdg[df_sdg['nama_sdg'] == sdg_pilihan][['judul_course', 'fakultas']].drop_duplicates()
st.dataframe(detail, use_container_width=True)

with st.expander("ℹ️ Mata kuliah yang TIDAK match ke SDG manapun (buat dicek manual)"):
    judul_match = set(df_sdg['judul_course'])
    tidak_match = df_bersih[~df_bersih['nama_normal'].isin(judul_match)]
    st.write(f"{len(tidak_match)} dari {len(df_bersih)} mata kuliah bersih tidak match ke SDG manapun")
    st.dataframe(tidak_match[['nama_normal', 'fakultas', 'deskripsi']], use_container_width=True)
