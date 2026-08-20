import re
import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import os

BASE_URL = 'https://elok.ugm.ac.id'
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

def ambil_daftar_kategori_fakultas():
    """Ambil semua link kategori tingkat atas (Fakultas + Sekolah Pascasarjana + Sekolah Vokasi),
    dari SEMUA halaman (halaman utama course index ada paginasi -- 1, 2, dst)."""
    kategori = []
    halaman = 0
    while True:
        url = f'{BASE_URL}/course/index.php' if halaman == 0 else f'{BASE_URL}/course/index.php?page={halaman}'
        resp = requests.get(url, headers=HEADERS)
        soup = BeautifulSoup(resp.content, 'html.parser')

        ditemukan_di_halaman_ini = 0
        for a in soup.find_all('a', href=True):
            if 'categoryid=' in a['href']:
                nama = a.get_text(strip=True)
                if nama and (nama.startswith('Fakultas') or nama.startswith('Sekolah')):
                    kategori.append({'nama_fakultas': nama, 'url': a['href']})
                    ditemukan_di_halaman_ini += 1

        if ditemukan_di_halaman_ini == 0:
            break  # halaman kosong / sudah habis, berhenti

        halaman += 1
        if halaman > 10:  # jaga-jaga biar tidak infinite loop kalau pola paginasi beda dari dugaan
            break
        time.sleep(1)

    df = pd.DataFrame(kategori).drop_duplicates(subset='url')
    return df

def ambil_subkategori(url_fakultas):
    """Ambil semua link subkategori di dalam 1 halaman Fakultas/Sekolah.

    eLOK tidak selalu menamai level 2 sebagai "Program". Beberapa fakultas memakai
    Departemen/Jurusan/unit lain, jadi selector utama harus memakai class kategori
    Moodle, bukan filter teks saja.
    """
    if not url_fakultas.startswith('http'):
        url_fakultas = BASE_URL + url_fakultas

    resp = requests.get(url_fakultas, headers=HEADERS, timeout=15)
    soup = BeautifulSoup(resp.content, 'html.parser')

    subkategori = []
    for a in soup.select('h5.categoryname a.rui-category-link[href*="categoryid="]'):
        nama = a.get_text(strip=True)
        href = a['href']
        if nama and href != url_fakultas:
            subkategori.append({'nama_program': nama, 'url': href})

    if not subkategori:
        # fallback jika theme berubah: ambil link categoryid, tapi abaikan breadcrumb dan tombol View more
        for a in soup.find_all('a', href=True):
            href = a['href']
            nama = a.get_text(strip=True)
            if 'categoryid=' not in href or not nama or nama == 'View more' or href == url_fakultas:
                continue
            if a.find_parent('li', class_='breadcrumb-item'):
                continue
            subkategori.append({'nama_program': nama, 'url': href})

    df = pd.DataFrame(subkategori).drop_duplicates(subset='url')
    return df

def ambil_course_dari_kategori(url_kategori):
    if not url_kategori.startswith('http'):
        url_kategori = BASE_URL + url_kategori

    semua_data = {}  # dict, key = course_id, value = data course (otomatis dedup)
    halaman = 0
    while True:
        pemisah = '&' if '?' in url_kategori else '?'
        url_halaman = url_kategori if halaman == 0 else f'{url_kategori}{pemisah}page={halaman}'

        try:
            resp = requests.get(url_halaman, headers=HEADERS, timeout=15)
        except requests.exceptions.RequestException as e:
            print(f"    [gagal ambil halaman {halaman}: {e}]")
            break

        soup = BeautifulSoup(resp.content, 'html.parser')
        course_cards = soup.select('div.rui-course-card-wrapper')
        if not course_cards:
            break

        id_baru_di_halaman_ini = 0
        for card in course_cards:
            link_tag = card.select_one('h3.rui-course-card-title a.coursename')
            if not link_tag or not link_tag.get('href'):
                continue

            match_id = re.search(r'id=(\d+)', link_tag['href'])
            course_id = match_id.group(1) if match_id else None
            if not course_id:
                continue

            for sr in link_tag.select('.sr-only'):
                sr.decompose()
            judul = link_tag.get_text(strip=True)
            if not judul:
                continue

            if course_id not in semua_data:
                id_baru_di_halaman_ini += 1

                deskripsi_tag = card.select_one('div.rui-course-card-text div.no-overflow')
                deskripsi = deskripsi_tag.get_text(separator=' ', strip=True) if deskripsi_tag else ''

                fakultas_tag = card.select_one('div.rui-course-cat-badge div.text-truncate')
                fakultas_dari_card = fakultas_tag.get_text(strip=True) if fakultas_tag else ''

                semua_data[course_id] = {
                    'judul_course': judul,
                    'deskripsi': deskripsi,
                    'fakultas_dari_card': fakultas_dari_card,
                }

        if id_baru_di_halaman_ini == 0:
            print(f"    [halaman {halaman}: tidak ada course ID baru, berhenti]")
            break

        halaman += 1
        if halaman > 15:
            break
        time.sleep(0.5)

    return list(semua_data.values())

def scrape_semua():
    os.makedirs('data', exist_ok=True)

    df_kategori = ambil_daftar_kategori_fakultas()
    print(f"Ditemukan {len(df_kategori)} kategori fakultas/sekolah")

    semua_course = []
    for _, row_fakultas in df_kategori.iterrows():
        print(f"\n=== {row_fakultas['nama_fakultas']} ===")

        df_program = ambil_subkategori(row_fakultas['url'])

        if df_program.empty:
            # tidak ada sub-kategori Program -- kemungkinan fakultas ini langsung berisi course
            print(f"  Tidak ada sub-kategori Program, scrape langsung dari level fakultas")
            try:
                courses = ambil_course_dari_kategori(row_fakultas['url'])
            except Exception as e:
                print(f"  [ERROR: {e}]")
                courses = []
            for c in courses:
                c['fakultas'] = row_fakultas['nama_fakultas']
                c['program'] = ''
                semua_course.append(c)
            print(f"  -> {len(courses)} course ditemukan")
        else:
            print(f"  Ditemukan {len(df_program)} program: {list(df_program['nama_program'])}")
            for _, row_program in df_program.iterrows():
                print(f"  Scraping: {row_program['nama_program']}...")
                try:
                    courses = ambil_course_dari_kategori(row_program['url'])
                except Exception as e:
                    print(f"    [ERROR: {e}]")
                    courses = []
                for c in courses:
                    c['fakultas'] = row_fakultas['nama_fakultas']
                    c['program'] = row_program['nama_program']
                    semua_course.append(c)
                print(f"    -> {len(courses)} course ditemukan")
                time.sleep(1)

        time.sleep(1)

    df_final = pd.DataFrame(semua_course)
    df_final = df_final.drop_duplicates(subset=['judul_course', 'fakultas', 'program'])
    df_final.to_csv('data/elok_matkul_mentah.csv', index=False)
    print(f"\nSelesai. Total {len(df_final)} course disimpan di data/elok_matkul_mentah.csv")
    return df_final

if __name__ == '__main__':
    scrape_semua()