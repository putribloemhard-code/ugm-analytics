"""Kamus keyword per SDG untuk tagging LANGSUNG url sitemap -> SDG (tanpa tema Kepmen).

Dipakai mode dashboard "SDGs saja": seluruh 32.130 URL berita ugm.ac.id
ditandai ke 17 SDG berdasarkan teks = kata-kata slug URL + judul + deskripsi
(kalau sudah di-fetch). Tidak memperhitungkan tema dampak Kepmen, jadi
jangkauannya lebih luas dari pemetaan tema -> SDG.

Sumber keyword: nama resmi SDG + target/indikator SDG (UN Sustainable
Development Goals), padanan ID dari SDG_NAMA di kepmen_sdg.py. Kata terlalu
generik (mis. "pembangunan", "program", "ugm") TIDAK dipakai. Satu berita
bisa masuk beberapa SDG (multi-SDG by design).

Konvensi: keyword <= 5 huruf dipakai dengan word-boundary (\\b..\\b) saat
matching (lihat tag_kepmen_all.py); yang lebih panjang substring match.
"""

# 17 SDG -> keyword ID+EN (lowercase). Sumber: target/indikator SDG resmi.
SDG_KEYWORDS = {
    1: [  # Tanpa Kemiskinan
        "kemiskinan", "poverty", "miskin ekstrem", "extreme poverty",
        "prasejahtera", "pra-sejahtera", "keluarga prasejahtera", "bantuan sosial",
        "bansos", "bantuan tunai", "cash transfer", "pkh", "program keluarga harapan",
        "desil", "kemiskinan multidimensi", "multidimensional poverty",
        "penerima manfaat", "beneficiary", "kesejahteraan sosial", "social welfare",
    ],
    2: [  # Tanpa Kelaparan
        "kelaparan", "hunger", "ketahanan pangan", "food security", "swasembada pangan",
        "krisis pangan", "food crisis", "stunting", "gizi", "nutrition", "malnutrisi",
        "malnutrition", "gizi buruk", "pangan lokal", "pangan bergizi", "pangan lestari",
        "ketahanan gizi", "food sovereignty", "kedaulatan pangan", "pangan sehat",
    ],
    3: [  # Kehidupan Sehat dan Sejahtera
        "kesehatan", "health", "rumah sakit", "hospital", "puskesmas", "klinik",
        "vaksin", "vaccine", "imunisasi", "immunization", "obat", "medicine",
        "farmasi", "pharmacy", "covid", "pandemi", "pandemic", "penyakit", "disease",
        "epidemi", "epidemic", "kesehatan mental", "mental health", "dokter", "doctor",
        "perawat", "nurse", "universal health", "jaminan kesehatan", "jkn", "bpjs kesehatan",
        "posyandu", "kesehatan reproduksi", "reproductive health", "sanitasi kesehatan",
    ],
    4: [  # Pendidikan Berkualitas
        "pendidikan", "education", "sekolah", "school", "kurikulum", "curriculum",
        "pembelajaran", "learning", "pengajaran", "teaching", "guru", "teacher",
        "siswa", "murid", "literasi", "literacy", "numerasi", "numeracy", "beasiswa",
        "scholarship", "kampus mengajar", "sekolah dasar", "sekolah menengah",
        "pendidikan tinggi", "higher education", "pendidikan vokasi", "vocational",
        "magang", "internship", "pendidikan inklusif", "inclusive education", "paud",
        "anak usia dini", "early childhood", "perguruan tinggi", "quality education",
        "kualitas pendidikan", "pendidikan karakter", "belajar mengajar", "pelatihan",
        "training",
    ],
    5: [  # Kesetaraan Gender
        "gender", "kesetaraan gender", "gender equality", "perempuan", "woman",
        "women", "pemberdayaan perempuan", "women empowerment", "kekerasan gender",
        "gender based violence", "diskriminasi gender", "gender discrimination",
        "kesenjangan gender", "gender gap", "anak perempuan", "girls", "emansipasi",
        "partisipasi perempuan", "kepemimpinan perempuan", "women leadership",
        "perlindungan perempuan", "setara", "keadilan gender", "gender justice",
    ],
    6: [  # Air Bersih dan Sanitasi Layak
        "air bersih", "clean water", "sanitasi", "sanitation", "air minum",
        "drinking water", "sumber air", "water source", "sungai", "river",
        "limbah cair", "wastewater", "irigasi", "irrigation", "air tanah", "groundwater",
        "pdam", "jamban", "toilet", "air limbah", "pengolahan air", "water treatment",
        "kualitas air", "water quality", "citarum", "resapan air", "daerah aliran sungai",
        "das", "watershed", "air bersih dan sanitasi",
    ],
    7: [  # Energi Bersih dan Terjangkau
        "energi", "energy", "listrik", "electricity", "tenaga surya", "solar",
        "panel surya", "solar panel", "pembangkit listrik", "power plant", "biomassa",
        "biomass", "biogas", "energi terbarukan", "renewable energy", "efisiensi energi",
        "energy efficiency", "panas bumi", "geothermal", "pembangkit listrik tenaga",
        "plt", "energi bersih", "clean energy", "akses energi", "energy access",
        "energi terjangkau", "konservasi energi", "energy conservation", "baterai",
        "battery", "kendaraan listrik", "electric vehicle", "transisi energi",
        "energy transition",
    ],
    8: [  # Pekerjaan Layak dan Pertumbuhan Ekonomi
        "ekonomi", "economic", "pekerjaan", "employment", "lapangan kerja", "jobs",
        "wirausaha", "entrepreneurship", "umkm", "sme", "smes", "usaha mikro",
        "usaha kecil", "industri kreatif", "creative economy", "pariwisata", "tourism",
        "tenaga kerja", "labor", "workforce", "pengangguran", "unemployment", "upah",
        "wage", "pendapatan", "income", "ekonomi digital", "digital economy",
        "ekonomi kreatif", "koperasi", "cooperative", "pertumbuhan ekonomi",
        "economic growth", "pekerjaan layak", "decent work", "pekerja informal",
        "informal workers", "perbankan", "bank", "keuangan inklusif", "financial inclusion",
        "ekonomi lokal", "local economy", "berwirausaha", "startup ekonomi",
    ],
    9: [  # Industri, Inovasi dan Infrastruktur
        "industri", "industry", "inovasi", "innovation", "teknologi", "technology",
        "riset", "research", "penelitian", "manufaktur", "manufacturing",
        "infrastruktur", "infrastructure", "jalan", "road", "jembatan", "bridge",
        "digitalisasi", "digitalization", "internet", "jaringan telekomunikasi",
        "telecommunication", "hilirisasi", "downstream", "paten", "patent", "robotik",
        "robotic", "robot", "kecerdasan buatan", "artificial intelligence",
        "big data", "iot", "pabrik", "factory", "industri kreatif digital", "startup",
        "teknologi tepat guna", "appropriate technology", "telekomunikasi",
        "industri pengolahan", "processing industry", "transportasi publik infrastruktur",
    ],
    10: [  # Berkurangnya Kesenjangan
        "kesenjangan", "inequality", "disparitas", "disparity", "inklusif", "inclusion",
        "inklusi", "disabilitas", "disability", "difabel", "kelompok rentan",
        "vulnerable groups", "masyarakat adat", "indigenous", "daerah tertinggal",
        "daerah terdepan", "daerah terluar", "daerah 3t", "migrasi", "migration",
        "pengungsi", "refugee", "pekerja migran", "migrant workers", "kesetaraan",
        "equality", "kesenjangan sosial", "social inequality", "aksesibilitas",
        "accessibility", "pendidikan inklusi", "redistribusi", "bantuan afirmasi",
    ],
    11: [  # Kota dan Permukiman yang Berkelanjutan
        "kota", "city", "urban", "perkotaan", "urbanisasi", "urbanization",
        "permukiman", "settlement", "perumahan", "housing", "transportasi publik",
        "public transport", "transportasi umum", "lalu lintas", "traffic", "kemacetan",
        "congestion", "tata kota", "urban planning", "ruang terbuka hijau",
        "green space", "taman kota", "city park", "mitigasi bencana", "disaster",
        "banjir", "flood", "longsor", "landslide", "gempa", "earthquake", "cagar budaya",
        "cultural heritage", "heritage", "museum", "bangunan bersejarah",
        "historic building", "kota berkelanjutan", "sustainable city", "desa kota",
        "permukiman kumuh", "slum", "tanggul", "normalisasi sungai", "tata ruang",
        "spatial planning", "transportasi berkelanjutan", "mobilitas",
    ],
    12: [  # Konsumsi dan Produksi yang Bertanggung Jawab
        "sampah", "waste", "limbah", "daur ulang", "recycle", "recycling", "reuse",
        "pengelolaan sampah", "waste management", "plastik", "plastic", "bank sampah",
        "waste bank", "kompos", "composting", "zero waste", "ekonomi sirkular",
        "circular economy", "konsumsi berkelanjutan", "sustainable consumption",
        "produksi berkelanjutan", "sustainable production", "food loss", "susut pangan",
        "sampah plastik", "plastic waste", "sampah organik", "organic waste",
        "eco friendly", "ramah lingkungan", "green product", "produk ramah lingkungan",
        "sustainable lifestyle", "gaya hidup berkelanjutan", "pengurangan sampah",
    ],
    13: [  # Penanganan Perubahan Iklim
        "iklim", "climate", "perubahan iklim", "climate change", "emisi", "emission",
        "karbon", "carbon", "gas rumah kaca", "greenhouse gas", "grk", "net zero",
        "dekarbonisasi", "decarbonization", "cuaca ekstrem", "extreme weather",
        "adaptasi iklim", "climate adaptation", "mitigasi iklim", "climate mitigation",
        "pemanasan global", "global warming", "ketahanan iklim", "climate resilience",
        "karbon netral", "carbon neutral", "jejak karbon", "carbon footprint",
        "pengurangan emisi", "emission reduction", "transisi energi", "resiliensi iklim",
    ],
    14: [  # Ekosistem Lautan
        "laut", "sea", "ocean", "lautan", "pesisir", "coastal", "pantai", "beach",
        "terumbu karang", "coral reef", "mangrove", "ikan", "fish", "perikanan",
        "fishery", "kelautan", "marine", "pencemaran laut", "marine pollution",
        "sampah laut", "marine debris", "wisata bahari", "tambak", "aquaculture",
        "budidaya laut", "ekonomi biru", "blue economy", "ekosistem laut",
        "marine ecosystem", "penyu", "turtle", "hiu", "shark", "nelayan", "fishermen",
        "pelabuhan", "port", "konservasi laut", "marine conservation",
    ],
    15: [  # Ekosistem Daratan
        "hutan", "forest", "kehutanan", "forestry", "keanekaragaman hayati",
        "biodiversity", "biodiversitas", "satwa", "wildlife", "fauna", "flora",
        "hewan liar", "spesies langka", "endangered species", "konservasi",
        "conservation", "taman nasional", "national park", "reboisasi", "reforestation",
        "restorasi lahan", "land restoration", "lahan kritis", "degraded land",
        "deforestasi", "deforestation", "ekosistem darat", "terrestrial", "gambut",
        "peatland", "lahan gambut", "orangutan", "gajah", "elephant", "badak",
        "rhino", "harimau", "tiger", "burung", "bird", "ekosistem hutan", "forest ecosystem",
        "suaka margasatwa", "wildlife reserve", "konservasi alam", "nature conservation",
    ],
    16: [  # Perdamaian, Keadilan dan Kelembagaan yang Tangguh
        "hukum", "law", "keadilan", "justice", "hak asasi manusia", "human rights",
        "ham", "korupsi", "corruption", "anti korupsi", "anti corruption",
        "tata kelola", "good governance", "transparansi", "transparency",
        "akuntabilitas", "accountability", "demokrasi", "democracy", "pemilu",
        "election", "partisipasi publik", "public participation", "perdamaian",
        "peace", "konflik", "conflict", "kekerasan", "violence", "kelembagaan",
        "institution", "pelayanan publik", "public service", "desentralisasi",
        "decentralisation", "otonomi daerah", "regional autonomy", "pemerintahan",
        "governance", "regulasi", "regulation", "kebijakan publik", "public policy",
        "penegakan hukum", "law enforcement", "pengadilan", "court", "keamanan publik",
    ],
    17: [  # Kemitraan untuk Mencapai Tujuan
        "kemitraan", "partnership", "kolaborasi", "collaboration", "kerja sama",
        "cooperation", "internasional", "international", "sdgs", "pembangunan berkelanjutan",
        "sustainable development", "filantropi", "philanthropy", "donor", "hibah",
        "grant", "multilateral", "organisasi internasional", "international organization",
        "capacity building", "pengembangan kapasitas", "transfer teknologi",
        "technology transfer", "tujuan pembangunan berkelanjutan", "global compact",
        "forum internasional", "international forum", "jejaring internasional",
        "mitra pembangunan", "development partners", "agenda 2030",
    ],
}
