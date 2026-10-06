import { useEffect, useRef, useState, type ReactNode, type RefObject } from 'react';
import { Link, useLocation } from 'react-router-dom';

import { AUTH_EVENT, DAMPAK_AUTH_EVENT, accreditationLogout, accreditationMe, dampakLogout, dampakMe, type AuthUser } from './lib/api';

export const assetUrl = (path: string) => `${import.meta.env.BASE_URL}${path.replace(/^\//, '')}`;

/** Keluar lalu muat ulang ke gerbang login portal itu: state halaman (laporan & PIN yang sedang
 *  terbuka, filter) ikut hilang, bukan hanya chip nama di header. */
export async function keluarKe(portal: 'akreditasi' | 'dampak') {
  try { await (portal === 'akreditasi' ? accreditationLogout() : dampakLogout()); }
  finally { window.location.replace(assetUrl(portal)); }
}

/** Bagian-bagian laporan Analisis Dampak (satu halaman panjang); id dipakai sebagai anchor dan scrollspy. */
export const reportSections = [
  { id: 'sumber', label: 'Sumber' },
  { id: 'ringkasan', label: 'Ringkasan' },
  { id: 'dampak', label: 'Dampak' },
  { id: 'dampak-sdgs', label: 'Dampak × SDGs' },
  { id: 'sdgs', label: 'SDGs' },
];

const reportSectionIds = reportSections.map(section => section.id);
/** Sub-bullet pilar di rail: hash bertingkat seperti '#dampak-ekonomi' dipakai rail untuk
 *  memilih pilar di dalam satu scene analisis (lihat railSubItems + AnalysisScene). */
const PILLAR_HASH: Record<string, string> = { lingkungan: 'Lingkungan', ekonomi: 'Ekonomi', sosial: 'Sosial' };
const isPillarHash = (hash: string) => {
  const tail = hash.slice(1).split('-').pop() ?? '';
  return tail in PILLAR_HASH;
};
/** Laporan hanya hidup di pathname '/dampak' (di balik login); '/' kini beranda/landing page. */
// '#metodologi' = anchor lama bagian "Data & metodologi", kini digantikan bagian Sumber.
const isReportLocation = (pathname: string, hash: string) => pathname === '/dampak'
  && (!hash || hash === '#metodologi' || isPillarHash(hash) || reportSectionIds.some(id => `#${id}` === hash));
/** Halaman-halaman milik portal Akreditasi -- dipakai untuk menentukan kapan chip akun & nav akreditasi tampil. */
const accreditationPaths = ['/akreditasi', '/profil', '/admin'];

/** True begitu elemen pernah mendekati viewport (sekali saja) -- dipakai untuk lazy-load data tiap bagian. */
export function useInView<T extends Element>(ref: RefObject<T | null>, rootMargin = '400px 0px') {
  const [seen, setSeen] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el || seen) return;
    if (typeof IntersectionObserver === 'undefined') { setSeen(true); return; }
    const observer = new IntersectionObserver(entries => { if (entries.some(entry => entry.isIntersecting)) { setSeen(true); observer.disconnect(); } }, { rootMargin });
    observer.observe(el);
    return () => observer.disconnect();
  }, [ref, rootMargin, seen]);
  return seen;
}

function useReadingProgress() {
  const bar = useRef<HTMLDivElement>(null);
  useEffect(() => {
    function update() {
      const max = document.documentElement.scrollHeight - window.innerHeight;
      const pct = max > 0 ? Math.min(100, Math.max(0, (window.scrollY / max) * 100)) : 0;
      if (bar.current) { bar.current.style.width = `${pct}%`; bar.current.setAttribute('aria-valuenow', String(Math.round(pct))); }
    }
    update();
    window.addEventListener('scroll', update, { passive: true }); window.addEventListener('resize', update);
    return () => { window.removeEventListener('scroll', update); window.removeEventListener('resize', update); };
  }, []);
  return bar;
}

const headerSectionIds = reportSections.map(section => section.id);

function useActiveSection(pathname: string, ids: string[]) {
  const [active, setActive] = useState('');
  useEffect(() => {
    const elements = ids.map(id => document.getElementById(id)).filter((el): el is HTMLElement => !!el);
    if (!elements.length || typeof IntersectionObserver === 'undefined') { setActive(''); return; }
    // Bagian terakhir pendek dan tidak bisa naik ke pita deteksi; di dasar halaman anggap ia yang aktif.
    const last = elements[elements.length - 1].id;
    const atBottom = () => window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 4;
    const observer = new IntersectionObserver(entries => {
      if (atBottom()) { setActive(last); return; }
      const hit = entries.filter(entry => entry.isIntersecting).sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)[0];
      if (hit) setActive(hit.target.id);
    }, { rootMargin: '-25% 0px -65% 0px' });
    elements.forEach(el => observer.observe(el));
    function onScroll() { if (atBottom()) setActive(last); }
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => { observer.disconnect(); window.removeEventListener('scroll', onScroll); };
  }, [pathname, ids]);
  return active;
}

function useAuthUser() {
  const [user, setUser] = useState<AuthUser | null>(null);
  useEffect(() => {
    let alive = true;
    const refresh = () => { accreditationMe().then(value => { if (alive) setUser(value); }).catch(() => { if (alive) setUser(null); }); };
    refresh();
    window.addEventListener(AUTH_EVENT, refresh);
    return () => { alive = false; window.removeEventListener(AUTH_EVENT, refresh); };
  }, []);
  return user;
}

function useDampakAuthUser() {
  const [user, setUser] = useState<AuthUser | null>(null);
  useEffect(() => {
    let alive = true;
    const refresh = () => { dampakMe().then(value => { if (alive) setUser(value); }).catch(() => { if (alive) setUser(null); }); };
    refresh();
    window.addEventListener(DAMPAK_AUTH_EVENT, refresh);
    return () => { alive = false; window.removeEventListener(DAMPAK_AUTH_EVENT, refresh); };
  }, []);
  return user;
}

function SiteHeader() {
  const location = useLocation();
  const progress = useReadingProgress();
  const active = useActiveSection(location.pathname, headerSectionIds);
  const accUser = useAuthUser();
  const dampakUser = useDampakAuthUser();
  const onLanding = location.pathname === '/';
  const onDampak = location.pathname === '/dampak' || location.pathname === '/dampak/admin';
  const onReport = isReportLocation(location.pathname, location.hash);
  const onAccreditation = accreditationPaths.includes(location.pathname);
  const showReportNav = onReport && dampakUser;
  // "Beranda" dan "Akreditasi" selalu tampil di header supaya orang bisa pindah portal kapan
  // saja -- termasuk dari gerbang login. "Analisis Dampak" jadi nav bagian laporan begitu
  // sudah login dan berada di /dampak; kalau belum, tetap satu tautan biasa ke sana.
  return <header className="site-header">
    <div className="reading-progress" role="progressbar" aria-label="Kemajuan membaca" aria-valuemin={0} aria-valuemax={100} aria-valuenow={0}><div ref={progress} /></div>
    <div className="site-header__inner">
      <Link className="site-header__brand" to="/" aria-label="UGM Analytics, beranda"><img src={assetUrl('logo/LogoUGM.png')} alt="" /><span>UGM Analytics</span></Link>
      <nav className="site-header__nav" aria-label="Navigasi utama">
        <Link to="/" className={onLanding ? 'active' : ''} aria-current={onLanding ? 'location' : undefined}>Beranda</Link>
        {showReportNav ? reportSections.map(section => <Link key={section.id} to={{ pathname: '/dampak', hash: `#${section.id}` }} className={active === section.id ? 'active' : ''} aria-current={active === section.id ? 'location' : undefined}>{section.label}</Link>)
          : <Link to="/dampak" className={onDampak ? 'active' : ''} aria-current={onDampak ? 'location' : undefined}>Analisis Dampak</Link>}
        <Link to="/akreditasi" className={onAccreditation ? 'active' : ''} aria-current={onAccreditation ? 'location' : undefined}>Akreditasi</Link>
      </nav>
      {onDampak && dampakUser && <span className="auth-chip">
        <span className="auth-chip__name">{dampakUser.nama}</span>
        {dampakUser.is_admin && <Link className="auth-chip__admin" to="/dampak/admin" title="Kelola akun Analisis Dampak">Admin</Link>}
        <button type="button" onClick={() => { void keluarKe('dampak'); }}>Keluar</button>
      </span>}
      {onAccreditation && accUser && <span className="auth-chip">
        <Link to="/profil" title={accUser.email}>{accUser.nama}</Link>
        {accUser.is_admin && <Link className="auth-chip__admin" to="/admin" title="Kelola akun pengguna">Admin</Link>}
        <button type="button" onClick={() => { void keluarKe('akreditasi'); }}>Keluar</button>
      </span>}    </div>
  </header>;
}

/** Peta scroll melayang di sisi kanan: posisi baca, lompat antar bagian, ke atas/bawah. */
const railItems = [
  { id: 'pembuka', node: '↑', caption: 'Orientasi', title: 'Pembuka & pencarian' },
  { id: 'sumber', node: '01', caption: 'Bagian I', title: 'Sumber data' },
  { id: 'ringkasan', node: '02', caption: 'Bagian II', title: 'Tiga jalur membaca dampak' },
  { id: 'dampak', node: '03', caption: 'Analisis 1 / 3', title: 'Dampak' },
  { id: 'dampak-sdgs', node: '04', caption: 'Analisis 2 / 3', title: 'Dampak × SDGs' },
  { id: 'sdgs', node: '05', caption: 'Analisis 3 / 3', title: 'SDGs' },
];
const railIds = railItems.map(item => item.id);

type RailSub = { key: string; label: string } & ({ kind: 'pillar'; pillar: string } | { kind: 'scroll'; anchor: string });

/** Sub-bullet per scene analisis: item rail yang mengembang saat bagian itu dibuka/aktif.
 *  kind 'pillar' = menulis hash bertingkat (#dampak-ekonomi) yang diparsing AnalysisScene untuk
 *  memilih pilar lalu menggulir ke detailnya; kind 'scroll' = gulir murni ke anchor blok. */
const railSubItems: Record<string, RailSub[]> = {
  // Urutan pilar = urutan di halaman (laporan resmi: Sosial, Ekonomi, Lingkungan).
  dampak: [
    { key: 'sosial', label: 'Sosial', kind: 'pillar', pillar: 'Sosial' },
    { key: 'ekonomi', label: 'Ekonomi', kind: 'pillar', pillar: 'Ekonomi' },
    { key: 'lingkungan', label: 'Lingkungan', kind: 'pillar', pillar: 'Lingkungan' },
    { key: 'laporan', label: 'Laporan', kind: 'scroll', anchor: 'laporan-unduh-impact' },
  ],
  'dampak-sdgs': [
    { key: 'sosial', label: 'Sosial', kind: 'pillar', pillar: 'Sosial' },
    { key: 'ekonomi', label: 'Ekonomi', kind: 'pillar', pillar: 'Ekonomi' },
    { key: 'lingkungan', label: 'Lingkungan', kind: 'pillar', pillar: 'Lingkungan' },
    { key: 'laporan', label: 'Laporan', kind: 'scroll', anchor: 'laporan-unduh-impact-sdgs' },
  ],
  sdgs: [
    { key: 'peta', label: 'Peta 17 SDG', kind: 'scroll', anchor: 'sdg-map-title' },
    { key: 'matkul', label: 'Mata kuliah', kind: 'scroll', anchor: 'laporan-matkul-sdgs' },
    { key: 'cek', label: 'Cek manual', kind: 'scroll', anchor: 'sdg-tag-title' },
    { key: 'laporan', label: 'Laporan', kind: 'scroll', anchor: 'laporan-unduh-sdgs' },
  ],
};

/** Gulir ke `anchor`. Blok di dalam scene analisis baru dirender setelah scene-nya terlihat dan
 *  datanya termuat (useInView + fetch), jadi anchor bisa belum ada saat diklik: gulir dulu ke
 *  `bagian` (memicu pemuatan), lalu tunggu anchor muncul dan gulir lagi. Satu gulir ulang setelah
 *  jeda kecil menyesuaikan posisi bila tinggi blok di atasnya masih berubah. */
let batalTunggu: (() => void) | null = null;
function scrollKe(anchor: string, bagian: string) {
  batalTunggu?.();
  const gulir = (el: HTMLElement) => {
    el.scrollIntoView({ block: 'start' });
    window.setTimeout(() => el.isConnected && el.scrollIntoView({ block: 'start' }), 350);
  };
  const ada = document.getElementById(anchor);
  if (ada) { gulir(ada); return; }
  document.getElementById(bagian)?.scrollIntoView({ block: 'start' });
  const amati = new MutationObserver(() => {
    const el = document.getElementById(anchor);
    if (el) { selesai(); gulir(el); }
  });
  const batas = window.setTimeout(() => selesai(), 10000);
  const selesai = () => { amati.disconnect(); window.clearTimeout(batas); batalTunggu = null; };
  batalTunggu = selesai;
  amati.observe(document.getElementById('main-content') ?? document.body, { childList: true, subtree: true });
}

function SectionRail() {
  const location = useLocation();
  const segmen = location.hash.slice(1).split('-');
  const pilarHash = PILLAR_HASH[segmen[segmen.length - 1]] ?? '';
  // Hash '#dampak-ekonomi' tetap berarti bagian 'dampak' untuk penanda posisi baca.
  const bagianHash = pilarHash ? segmen.slice(0, -1).join('-') : location.hash.slice(1);
  const scrollAktif = useActiveSection(location.pathname, railIds);
  const active = (bagianHash && railIds.includes(bagianHash) ? bagianHash : scrollAktif) || 'pembuka';
  const activeIndex = Math.max(0, railIds.indexOf(active));
  const [buka, setBuka] = useState('');
  // Sub-bullet yang tampil: milik bagian yang diklik, atau (bila belum ada yang diklik) milik bagian aktif.
  const tampil = railSubItems[buka] ? buka : (railSubItems[active] ? active : '');
  useEffect(() => { if (railSubItems[active] && !railSubItems[buka]) setBuka(active); }, [active, buka]);
  // Sub-bullet yang terakhir dipilih ("dampak:laporan"). Tombol gulir (Laporan, Peta SDG, ...) tidak
  // mengubah hash, jadi penandanya disimpan di state; hash pilar (#dampak-sosial) ikut mengisinya.
  const [subAktif, setSubAktif] = useState('');
  useEffect(() => { if (pilarHash) setSubAktif(`${bagianHash}:${pilarHash.toLowerCase()}`); }, [location.key, pilarHash, bagianHash]);
  // Ikuti posisi gulir: sub-bullet aktif = target terakhir yang sudah melewati 30% atas layar.
  // Target pilar = blok "Detail dampak", dan hanya untuk pilar yang sedang dipilih di scene itu
  // (atribut data-pilar); bila pilar berganti tanpa scroll, MutationObserver menghitung ulang.
  useEffect(() => {
    const subs = railSubItems[tampil];
    if (!subs) return;
    let raf = 0;
    const hitung = () => {
      raf = 0;
      const scene = document.getElementById(tampil);
      const batas = window.innerHeight * 0.3;
      const diDasar = window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 4;
      let pilih = '';
      let terdekat = -Infinity;
      for (const sub of subs) {
        if (sub.kind === 'pillar' && scene?.dataset.pilar !== sub.pillar) continue;
        const el = document.getElementById(sub.kind === 'pillar' ? `${tampil}-detail` : sub.anchor);
        if (!el) continue;
        const atas = el.getBoundingClientRect().top;
        // Blok terakhir di dasar halaman tidak bisa naik ke 30% atas; anggap terlewati bila terlihat.
        const lewat = atas <= batas || (diDasar && atas < window.innerHeight);
        if (lewat && atas > terdekat) { terdekat = atas; pilih = `${tampil}:${sub.key}`; }
      }
      setSubAktif(pilih);
    };
    const jadwal = () => { if (!raf) raf = requestAnimationFrame(hitung); };
    window.addEventListener('scroll', jadwal, { passive: true });
    const scene = document.getElementById(tampil);
    const amati = new MutationObserver(jadwal);
    if (scene) amati.observe(scene, { attributes: true, attributeFilter: ['data-pilar'] });
    return () => { window.removeEventListener('scroll', jadwal); amati.disconnect(); cancelAnimationFrame(raf); };
  }, [tampil]);
  return <nav className="rail" aria-label="Peta laporan">
    <p className="rail__heading">Jelajahi laporan</p>
    <ol className="rail__list">
      {railItems.map((item, index) => {
        const state = item.id === active ? 'is-active' : index < activeIndex ? 'is-past' : '';
        const subs = railSubItems[item.id];
        return <li key={item.id} className={`rail__item ${state}`}>
          <Link to={{ pathname: '/dampak', hash: `#${item.id}` }} aria-current={item.id === active ? 'location' : undefined} aria-label={`${item.caption}: ${item.title}`}
            onClick={() => { if (subs) setBuka(item.id); }}>
            <span className="rail__label"><small>{item.caption}</small><strong>{item.title}</strong></span>
            <span className="rail__node" aria-hidden="true">{item.node}</span>
          </Link>
          {subs && <ol className={`rail__subs ${tampil === item.id ? 'is-open' : ''}`} aria-label={`Lompat di dalam ${item.title}`}>
            {subs.map(sub => <li key={sub.key}>
              {sub.kind === 'pillar'
                // Gulir langsung ke detail pilar yang sudah tampil; AnalysisScene menggulir lagi
                // setelah data pilar baru selesai dimuat.
                ? <Link to={{ pathname: '/dampak', hash: `#${item.id}-${sub.key}` }} className={subAktif === `${item.id}:${sub.key}` ? 'is-on' : ''} aria-current={subAktif === `${item.id}:${sub.key}` ? 'location' : undefined}
                    onClick={() => { setSubAktif(`${item.id}:${sub.key}`); scrollKe(`${item.id}-detail`, item.id); }}>{sub.label}</Link>
                : <button type="button" className={subAktif === `${item.id}:${sub.key}` ? 'is-on' : ''} aria-current={subAktif === `${item.id}:${sub.key}` ? 'location' : undefined}
                    onClick={() => { setSubAktif(`${item.id}:${sub.key}`); scrollKe(sub.anchor, item.id); }}>{sub.label}</button>}
            </li>)}
          </ol>}
        </li>;
      })}
    </ol>
    <button className="rail__end" type="button" aria-label="Ke bagian akhir laporan" onClick={() => window.scrollTo({ top: document.documentElement.scrollHeight })}>↓</button>
  </nav>;
}

export function SiteFooter() {
  return <footer className="site-footer"><div className="site-footer__inner"><strong>UGM Analytics</strong><span>Analisis dampak UGM berdasarkan Kepmen 361/M/KEP/2025 dan SDGs. Angka adalah lower-bound berbasis keyword dan sumber yang tersedia.</span></div></footer>;
}

export function SiteShell({ children, plain }: { children: ReactNode; plain?: boolean }) {
  // Peta laporan hanya untuk halaman laporan yang sudah login; beranda, gerbang login, portal
  // Akreditasi, Profil, dan Admin punya navigasi sendiri sehingga rail di kanan justru mengganggu.
  const { pathname, hash } = useLocation();
  const onReport = !plain && isReportLocation(pathname, hash);
  return <div className={`site ${pathname === '/' ? 'site--landing' : ''}`}><a className="skip-link" href="#main-content">Lewati ke konten utama</a><SiteHeader />{onReport && <SectionRail />}<main id="main-content">{children}</main><SiteFooter /></div>;
}
