"""Generate laporan HTML statis (tanpa streamlit) dari hasil tagging Kepmen.

Plotly.js di-embed inline (include_plotlyjs=True) supaya chart tetap render
saat dibuka OFFLINE. Output: laporan_matkul_kepmen.html — buka langsung di browser.
"""
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

df = pd.read_csv('data/elok_matkul_kepmen.csv')
ringkasan_fak = pd.read_csv('data/ringkasan_fakultas.csv')
ringkasan_prodi = pd.read_csv('data/ringkasan_prodi.csv')
ringkasan_topik = pd.read_csv('data/ringkasan_topik.csv')
ringkasan_tahun = pd.read_csv('data/ringkasan_tahun.csv')

n_match = int(df['terkait_sustainability'].sum())
PALETTE = px.colors.qualitative.Set3
WARNA_HIJAU = ['#e8f5e9', '#a5d6a7', '#66bb6a', '#2e7d32', '#1b5e20']

# 1. Bar semua fakultas (termasuk yang 0)
fak = (df.groupby('fakultas')
       .agg(total=('nama_normal', 'nunique'), sustain=('terkait_sustainability', 'sum'))
       .reset_index())
fak['persen'] = (fak['sustain'] / fak['total'] * 100).round(1)
fak = fak.sort_values(['sustain', 'persen'])
fak['label'] = fak.apply(lambda r: f"{int(r['sustain'])}  ({r['persen']:.1f}%)", axis=1)
fig1 = px.bar(fak, x='sustain', y='fakultas', orientation='h', text='label',
              color='persen', color_continuous_scale=WARNA_HIJAU, range_color=[0, 100],
              labels={'sustain': 'Jumlah matkul terkait sustainability', 'fakultas': '',
                      'persen': '% terkait'},
              height=max(420, 34 * len(fak)),
              title='Semua Fakultas — Jumlah & Persentase Matkul Sustainability')
fig1.update_traces(textposition='outside', cliponaxis=False)
fig1.update_layout(margin=dict(l=10, r=60, t=60, b=10))

# 2. Treemap fakultas -> prodi -> matkul
sub = df[df['terkait_sustainability']].copy()
sub['program'] = sub['program'].fillna('').replace('', '(tanpa program)')
fig2 = px.treemap(sub, path=[px.Constant('Semua Fakultas'), 'fakultas', 'program', 'nama_normal'],
                  color='fakultas', color_discrete_sequence=PALETTE,
                  hover_data={'nama_topik': True}, height=560,
                  title='Peta Hierarki: Fakultas → Prodi → Mata Kuliah')
fig2.update_traces(textinfo='label+value',
                   hovertemplate='<b>%{label}</b><br>Topik: %{customdata[0]}<extra></extra>')
fig2.update_layout(margin=dict(l=0, r=0, t=60, b=0))

# 3. Heatmap topik x fakultas
baris_hm = []
for _, r in sub.iterrows():
    for topik in str(r['nama_topik']).split('; '):
        if topik:
            baris_hm.append({'fakultas': r['fakultas'], 'topik': topik})
hm = pd.DataFrame(baris_hm)
pivot = hm.pivot_table(index='topik', columns='fakultas', aggfunc='size', fill_value=0)
pivot = pivot.reindex(sorted(pivot.columns, key=lambda c: -pivot[c].sum()), axis=1)
pivot = pivot.loc[pivot.sum(axis=1).sort_values(ascending=False).index]
fig3 = px.imshow(pivot, text_auto=True, aspect='auto', color_continuous_scale=WARNA_HIJAU,
                 labels=dict(x='Fakultas', y='Topik', color='Jumlah matkul'),
                 height=max(360, 70 * len(pivot)), title='Heatmap: Topik Kepmen × Fakultas')
fig3.update_xaxes(tickangle=45)
fig3.update_layout(margin=dict(l=10, r=10, t=60, b=10))

# 4. Donut topik
fig4 = px.pie(ringkasan_topik, names='topik', values='jumlah_matkul', hole=0.5,
              color_discrete_sequence=PALETTE, title='Sebaran per Topik Kepmen')
fig4.update_traces(textinfo='label+value')
fig4.update_layout(showlegend=False, height=400, margin=dict(l=10, r=10, t=60, b=10))

# 5. Tren per tahun (stacked per fakultas)
df_tren = sub[sub['tahun'].notna()].copy()
fig5 = px.bar(df_tren.groupby(['tahun', 'fakultas']).size().reset_index(name='jumlah'),
              x='tahun', y='jumlah', color='fakultas', color_discrete_sequence=PALETTE,
              labels={'tahun': 'Tahun (dari judul)', 'jumlah': 'Matkul terkait'},
              title='Tren per Tahun (dari judul matkul — indikasi kasar)')
fig5.update_layout(height=420, legend=dict(orientation='h', y=-0.25),
                   margin=dict(l=10, r=10, t=60, b=10))
fig5.update_xaxes(dtick=1)

# tabel: daftar lengkap matkul terkait
daftar = sub[['fakultas', 'program', 'nama_normal', 'nama_topik', 'tahun']].sort_values(
    ['fakultas', 'program', 'nama_normal'])
daftar['program'] = daftar['program'].fillna('').replace('', '(tanpa program)')

ringkasan_prodi_t = ringkasan_prodi.copy()
ringkasan_prodi_t['program'] = ringkasan_prodi_t['program'].fillna('(tanpa program)')

def tabel_html(dframe, judul):
    styled = dframe.style.bar(subset=['persen'], color='#c8e6c9', vmin=0, vmax=100) \
        .format({'persen': '{:.1f}%'}).hide(axis='index')
    return f'<h3>{judul}</h3>{styled.to_html()}'

html = f"""<!DOCTYPE html>
<html lang="id"><head><meta charset="utf-8">
<title>Laporan Mata Kuliah Sustainability — Kepmen 361/M/KEP/2025</title>
<style>
 body {{ font-family: 'Segoe UI', sans-serif; margin: 2rem auto; max-width: 1100px; color: #222; }}
 h1 {{ color: #1b5e20; }} h2 {{ border-bottom: 2px solid #1b5e20; padding-bottom: .3rem; }}
 table {{ border-collapse: collapse; width: 100%; margin: .5rem 0 1.5rem; font-size: .85rem; }}
 th, td {{ border: 1px solid #ddd; padding: .35rem .5rem; text-align: left; }}
 th {{ background: #e8f5e9; }}
 .warning {{ background: #fff3cd; border: 1px solid #ffeeba; padding: .6rem 1rem; border-radius: 6px; }}
 .metrics {{ display: flex; gap: 1rem; margin: 1rem 0; }}
 .metric {{ flex: 1; background: #e8f5e9; border-radius: 8px; padding: .8rem 1rem; }}
 .metric .angka {{ font-size: 1.6rem; font-weight: 700; color: #1b5e20; }}
</style></head><body>
<h1>🌱 Laporan Mata Kuliah Terkait Sustainability</h1>
<p>Indikator Kepmen 361/M/KEP/2025 — Dampak Lingkungan, Tema 5 (Pendidikan dan Penelitian).
Keyword matching ke judul + deskripsi mata kuliah (sumber: eLOK UGM).</p>
<div class="warning">⚠️ Data masih SAMPLE dari eLOK — bukan cakupan penuh seluruh mata kuliah UGM.
41% deskripsi kosong dan sebagian terpotong, jadi angka ini lower-bound.
Beberapa judul (mis. 'Pekerti') membawa deskripsi keliru dari eLOK — cek manual.</div>
<div class="metrics">
 <div class="metric"><div class="angka">{len(df)}</div>Matkul (setelah dedup)</div>
 <div class="metric"><div class="angka">{n_match}</div>Terkait sustainability</div>
 <div class="metric"><div class="angka">{n_match/len(df)*100:.1f}%</div>Cakupan</div>
 <div class="metric"><div class="angka">{int((fak['sustain']>0).sum())}</div>Fakultas terwakili</div>
</div>
{fig1.to_html(full_html=False, include_plotlyjs=True)}
{fig2.to_html(full_html=False, include_plotlyjs=False)}
<h2>Heatmap Topik × Fakultas</h2>
{fig3.to_html(full_html=False, include_plotlyjs=False)}
{fig4.to_html(full_html=False, include_plotlyjs=False)}
{fig5.to_html(full_html=False, include_plotlyjs=False)}
<h2>Daftar Lengkap Mata Kuliah Terkait Sustainability ({len(daftar)})</h2>
{daftar.to_html(index=False, escape=False)}
<h2>Ringkasan per Prodi (Fakultas × Program)</h2>
{tabel_html(ringkasan_prodi_t, '')}
</body></html>"""

with open('laporan_matkul_kepmen.html', 'w', encoding='utf-8') as f:
    f.write(html)
print(f'Tersimpan laporan_matkul_kepmen.html ({len(html)/1024:.0f} KB, plotly.js inline)')
