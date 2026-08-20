"""Dashboard mata kuliah sustainability — topik resmi Kepmen 361/M/KEP/2025.

Fitur:
- Filter multi-fakultas di sidebar (kosong = semua fakultas).
- Bar chart SEMUA fakultas (termasuk yang 0), diwarnai persentase.
- Treemap fakultas → prodi → matkul.
- Heatmap topik × fakultas.
- Donut sebaran topik.
- Tren per tahun (stacked per fakultas).
- Tabel drill-down per prodi + daftar cek manual.

Jalankan:
    streamlit run dashboard_matkul_kepmen.py
"""
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title="Matkul Sustainability (Kepmen)", layout="wide")

WARNA_HIJAU = ['#e8f5e9', '#a5d6a7', '#66bb6a', '#2e7d32', '#1b5e20']
PALETTE = px.colors.qualitative.Set3

# ---------------------------------------------------------------- data
@st.cache_data
def muat_data():
    return (
        pd.read_csv('data/elok_matkul_kepmen.csv'),
        pd.read_csv('data/ringkasan_fakultas.csv'),
        pd.read_csv('data/ringkasan_prodi.csv'),
        pd.read_csv('data/ringkasan_topik.csv'),
        pd.read_csv('data/ringkasan_tahun.csv'),
    )

df, ringkasan_fak, ringkasan_prodi, ringkasan_topik, ringkasan_tahun = muat_data()

st.title("🌱 Mata Kuliah Terkait Sustainability — Topik Resmi Kepmen")
st.caption(
    "Indikator Kepmen 361/M/KEP/2025 — Dampak Lingkungan, Tema 5 (Pendidikan dan Penelitian). "
    "Keyword matching ke judul + deskripsi mata kuliah."
)

# ---------------------------------------------------------------- filter
with st.sidebar:
    st.header("🎛️ Filter")
    semua_fak = sorted(df['fakultas'].unique())
    fak_terpilih = st.multiselect(
        "Fakultas (kosong = semua)",
        options=semua_fak,
        default=[],
        help="Pilih satu atau lebih fakultas. Biarkan kosong untuk menampilkan seluruh fakultas.",
    )
    if fak_terpilih:
        df_f = df[df['fakultas'].isin(fak_terpilih)]
    else:
        df_f = df
        fak_terpilih = semua_fak
    st.caption(f"Menampilkan {len(fak_terpilih)} dari {len(semua_fak)} fakultas.")

st.warning(
    "⚠️ Data masih SAMPLE dari eLOK (bukan cakupan penuh seluruh mata kuliah UGM). "
    "41% deskripsi kosong dan sebagian terpotong, jadi angka ini lower-bound. "
    "Beberapa judul (mis. 'Pekerti') membawa deskripsi keliru dari eLOK — cek daftar manual di bawah."
)

# ---------------------------------------------------------------- metrics
n_match = int(df_f['terkait_sustainability'].sum())
c1, c2, c3, c4 = st.columns(4)
c1.metric("Mata kuliah (tampil)", len(df_f))
c2.metric("Terkait sustainability", n_match)
c3.metric("Cakupan", f"{n_match/len(df_f)*100:.1f}%" if len(df_f) else "-")
c4.metric("Fakultas dengan match > 0",
          int((df_f.groupby('fakultas')['terkait_sustainability'].sum() > 0).sum()))

# ---------------------------------------------------------------- 1. bar semua fakultas
st.subheader("1. Semua Fakultas — Jumlah & Persentase Matkul Sustainability")
ringkasan_f = (
    df_f.groupby('fakultas')
    .agg(total=('nama_normal', 'nunique'),
         sustain=('terkait_sustainability', 'sum'))
    .reset_index()
)
ringkasan_f['persen'] = (ringkasan_f['sustain'] / ringkasan_f['total'] * 100).round(1)
ringkasan_f = ringkasan_f.sort_values(['sustain', 'persen'], ascending=True)
ringkasan_f['label'] = ringkasan_f.apply(
    lambda r: f"{int(r['sustain'])}  ({r['persen']:.1f}%)", axis=1)

fig1 = px.bar(
    ringkasan_f, x='sustain', y='fakultas', orientation='h',
    text='label', color='persen',
    color_continuous_scale=WARNA_HIJAU,
    range_color=[0, 100],
    labels={'sustain': 'Jumlah matkul terkait sustainability', 'fakultas': '',
            'persen': '% terkait'},
    height=max(420, 34 * len(ringkasan_f)),
)
fig1.update_traces(textposition='outside', cliponaxis=False)
fig1.update_layout(coloraxis_colorbar=dict(title='%', len=0.5, y=0.75),
                   margin=dict(l=10, r=60, t=10, b=10))
st.plotly_chart(fig1, width='stretch')

# ---------------------------------------------------------------- 2. treemap
st.subheader("2. Peta Hierarki: Fakultas → Prodi → Mata Kuliah")
sub_sustain = df_f[df_f['terkait_sustainability']].copy()
sub_sustain['program'] = sub_sustain['program'].fillna('').replace('', '(tanpa program)')
if len(sub_sustain):
    fig2 = px.treemap(
        sub_sustain,
        path=[px.Constant('Semua Fakultas'), 'fakultas', 'program', 'nama_normal'],
        color='fakultas',
        color_discrete_sequence=PALETTE,
        hover_data={'nama_topik': True},
        height=560,
    )
    fig2.update_traces(textinfo='label+value', hovertemplate=
                       '<b>%{label}</b><br>Matkul: %{value}<br>Topik: %{customdata[0]}<extra></extra>')
    fig2.update_layout(margin=dict(l=0, r=0, t=30, b=0))
    st.plotly_chart(fig2, width='stretch')
else:
    st.info("Tidak ada matkul terkait sustainability pada fakultas terpilih.")

# ---------------------------------------------------------------- 3. heatmap topik x fakultas
st.subheader("3. Heatmap: Topik Kepmen × Fakultas")
baris_hm = []
for _, r in sub_sustain.iterrows():
    for topik in str(r['nama_topik']).split('; '):
        if topik:
            baris_hm.append({'fakultas': r['fakultas'], 'topik': topik})
hm = pd.DataFrame(baris_hm)
if len(hm):
    pivot = hm.pivot_table(index='topik', columns='fakultas', aggfunc='size', fill_value=0)
    pivot = pivot.reindex(sorted(pivot.columns, key=lambda c: -pivot[c].sum()), axis=1)
    pivot = pivot.loc[pivot.sum(axis=1).sort_values(ascending=False).index]
    fig3 = px.imshow(
        pivot, text_auto=True, aspect='auto',
        color_continuous_scale=WARNA_HIJAU,
        labels=dict(x='Fakultas', y='Topik', color='Jumlah matkul'),
        height=max(360, 70 * len(pivot)),
    )
    fig3.update_layout(margin=dict(l=10, r=10, t=30, b=10))
    fig3.update_xaxes(tickangle=45)
    st.plotly_chart(fig3, width='stretch')
else:
    st.info("Tidak ada data untuk heatmap.")

# ---------------------------------------------------------------- 4. donut + tren
kol_kiri, kol_kanan = st.columns([1, 1.4])
with kol_kiri:
    st.subheader("4. Sebaran per Topik")
    fig4 = px.pie(
        ringkasan_topik, names='topik', values='jumlah_matkul', hole=0.5,
        color_discrete_sequence=PALETTE,
    )
    fig4.update_traces(textinfo='label+value')
    fig4.update_layout(showlegend=False, height=380, margin=dict(l=10, r=10, t=30, b=10))
    st.plotly_chart(fig4, width='stretch')

with kol_kanan:
    st.subheader("5. Tren per Tahun (Stacked per Fakultas)")
    df_tren = sub_sustain[sub_sustain['tahun'].notna()].copy()
    st.caption(
        f"Tahun diekstrak dari JUDUL matkul (mis. 'Gasal 2024/2025'). "
        f"Hanya {len(df_tren)} dari {len(df_f)} matkul punya tahun di judul — indikasi kasar, bukan data resmi."
    )
    if len(df_tren):
        tren = (
            df_tren.groupby(['tahun', 'fakultas']).size()
            .reset_index(name='jumlah')
            .sort_values('tahun')
        )
        fig5 = px.bar(
            tren, x='tahun', y='jumlah', color='fakultas',
            color_discrete_sequence=PALETTE,
            labels={'tahun': 'Tahun (dari judul)', 'jumlah': 'Matkul terkait'},
        )
        fig5.update_layout(height=380, legend=dict(orientation='h', y=-0.25),
                           margin=dict(l=10, r=10, t=30, b=10))
        fig5.update_xaxes(dtick=1)
        st.plotly_chart(fig5, width='stretch')
    else:
        st.info("Tidak ada data tahun untuk fakultas terpilih.")

# ---------------------------------------------------------------- 6. drill-down tabel
st.subheader("6. Drill-down: Mata Kuliah per Prodi")
fak_pilihan = st.selectbox(
    "Pilih fakultas untuk detail (default: semua):",
    ['— Semua Fakultas —'] + sorted(df_f['fakultas'].unique()),
    index=0,
)
if fak_pilihan == '— Semua Fakultas —':
    sub = df_f
else:
    sub = df_f[df_f['fakultas'] == fak_pilihan]
st.markdown(f"**{fak_pilihan}** — {int(sub['terkait_sustainability'].sum())} dari "
            f"{len(sub)} matkul terkait sustainability.")
detail = sub[sub['terkait_sustainability']][['fakultas', 'program', 'nama_normal', 'nama_topik', 'tahun']]
detail['program'] = detail['program'].fillna('').replace('', '(tanpa program)')
detail = detail.sort_values(['fakultas', 'program', 'nama_normal'])
st.dataframe(detail, width='stretch', height=min(600, 35 * (len(detail) + 1)))

with st.expander("➕ Ringkasan semua prodi (terfilter)"):
    rp = ringkasan_prodi[ringkasan_prodi['fakultas'].isin(fak_terpilih)]
    st.dataframe(rp, width='stretch')

with st.expander("ℹ️ Matkul yang TIDAK match topik manapun (cek manual)"):
    tidak_match = df_f[~df_f['terkait_sustainability']]
    st.write(f"{len(tidak_match)} matkul tidak match. Deskripsi kosong/terpotong adalah penyebab utama.")
    st.dataframe(tidak_match[['nama_normal', 'fakultas', 'program', 'deskripsi']], width='stretch')
