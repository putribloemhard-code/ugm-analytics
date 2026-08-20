import requests

url = 'https://elok.ugm.ac.id/course/index.php?categoryid=726'  # ganti sesuai salah satu URL fakultas kamu
headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
resp = requests.get(url, headers=headers)

with open('debug_page.html', 'w', encoding='utf-8') as f:
    f.write(resp.text)

print(f"Status: {resp.status_code}")
print(f"Panjang HTML: {len(resp.text)} karakter")
print("Tersimpan di debug_page.html")