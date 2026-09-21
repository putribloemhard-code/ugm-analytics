import { useEffect, useRef, useState, type ReactNode, type RefObject } from 'react';
import { Link, NavLink, useLocation } from 'react-router-dom';

import { AUTH_EVENT, accreditationLogout, accreditationMe, type AuthUser } from './lib/api';

export const assetUrl = (path: string) => `${import.meta.env.BASE_URL}${path.replace(/^\//, '')}`;

/** Bagian-bagian laporan satu halaman; id dipakai sebagai anchor dan scrollspy. */
export const reportSections = [
  { id: 'ringkasan', label: 'Ringkasan' },
  { id: 'dampak', label: 'Dampak' },
  { id: 'dampak-sdgs', label: 'Dampak × SDGs' },
  { id: 'sdgs', label: 'SDGs' },
  { id: 'metodologi', label: 'Data & metodologi' },
];

const prefersReducedMotion = () => typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

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

/** Angka yang naik dari 0 saat pertama terlihat; langsung tampil final bila pengguna meminta motion dikurangi. */
export function CountUp({ value }: { value: unknown }) {
  const ref = useRef<HTMLSpanElement>(null);
  const seen = useInView(ref, '0px');
  const target = typeof value === 'number' ? value : NaN;
  const [shown, setShown] = useState(0);
  useEffect(() => {
    if (!seen || Number.isNaN(target)) return;
    if (prefersReducedMotion()) { setShown(target); return; }
    let frame = 0; const start = performance.now(); const duration = 1400;
    const tick = (now: number) => { const t = Math.min(1, (now - start) / duration); setShown(Math.round(target * (1 - Math.pow(1 - t, 3)))); if (t < 1) frame = requestAnimationFrame(tick); };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [seen, target]);
  if (Number.isNaN(target)) return <span ref={ref}>{String(value ?? '-')}</span>;
  return <span ref={ref}>{(seen ? shown : 0).toLocaleString('id-ID')}</span>;
}

function useTheme() {
  const [theme, setTheme] = useState<'light' | 'dark'>(() => (document.documentElement.dataset.theme === 'dark' ? 'dark' : 'light'));
  function toggle() {
    const next = theme === 'dark' ? 'light' : 'dark';
    document.documentElement.dataset.theme = next;
    try { localStorage.setItem('ugm-analytics-theme', next); } catch { /* penyimpanan diblokir -- tema tetap berlaku untuk sesi ini */ }
    setTheme(next);
  }
  return { theme, toggle };
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

function SiteHeader() {
  const location = useLocation();
  const { theme, toggle } = useTheme();
  const progress = useReadingProgress();
  const active = useActiveSection(location.pathname, headerSectionIds);
  const user = useAuthUser();
  const onReport = location.pathname !== '/akreditasi';
  return <header className="site-header">
    <div className="reading-progress" role="progressbar" aria-label="Kemajuan membaca" aria-valuemin={0} aria-valuemax={100} aria-valuenow={0}><div ref={progress} /></div>
    <div className="site-header__inner">
      <Link className="site-header__brand" to="/" aria-label="UGM Analytics — beranda"><img src={assetUrl('logo/LogoUGM.png')} alt="" /><span>UGM Analytics</span></Link>
      <nav className="site-header__nav" aria-label="Navigasi utama">
        {reportSections.map(section => <Link key={section.id} to={{ pathname: '/', hash: `#${section.id}` }} className={onReport && active === section.id ? 'active' : ''} aria-current={onReport && active === section.id ? 'location' : undefined}>{section.label}</Link>)}
      </nav>
      <NavLink to="/akreditasi" className={({ isActive }) => `site-header__tab ${isActive ? 'active' : ''}`}>Akreditasi</NavLink>
      {user
        ? <span className="auth-chip"><Link to="/akreditasi" title={user.email}>{user.nama}</Link><button type="button" onClick={() => { void accreditationLogout(); }}>Keluar</button></span>
        : <Link className="auth-link" to="/akreditasi">Masuk</Link>}
      <button className="theme-toggle" type="button" aria-pressed={theme === 'dark'} onClick={toggle}>{theme === 'dark' ? 'Mode terang' : 'Mode gelap'}</button>
    </div>
  </header>;
}

/** Peta scroll melayang di sisi kanan: posisi baca, lompat antar bagian, ke atas/bawah. */
const railItems = [
  { id: 'pembuka', node: '↑', caption: 'Orientasi', title: 'Pembuka & ringkasan data' },
  { id: 'ringkasan', node: '01', caption: 'Bagian I', title: 'Tiga jalur membaca dampak' },
  { id: 'dampak', node: '02', caption: 'Analisis 1 / 3', title: 'Dampak' },
  { id: 'dampak-sdgs', node: '03', caption: 'Analisis 2 / 3', title: 'Dampak × SDGs' },
  { id: 'sdgs', node: '04', caption: 'Analisis 3 / 3', title: 'SDGs' },
  { id: 'metodologi', node: '05', caption: 'Bagian III', title: 'Data & metodologi' },
];
const railIds = railItems.map(item => item.id);

function SectionRail() {
  const location = useLocation();
  const active = useActiveSection(location.pathname, railIds) || 'pembuka';
  const activeIndex = railIds.indexOf(active);
  return <nav className="rail" aria-label="Peta laporan">
    <p className="rail__heading">Jelajahi laporan</p>
    <ol className="rail__list">
      {railItems.map((item, index) => {
        const state = index === activeIndex ? 'is-active' : index < activeIndex ? 'is-past' : '';
        return <li key={item.id} className={`rail__item ${state}`}>
          <Link to={{ pathname: '/', hash: `#${item.id}` }} aria-current={index === activeIndex ? 'location' : undefined} aria-label={`${item.caption}: ${item.title}`}>
            <span className="rail__label"><small>{item.caption}</small><strong>{item.title}</strong></span>
            <span className="rail__node" aria-hidden="true">{item.node}</span>
          </Link>
        </li>;
      })}
    </ol>
    <button className="rail__end" type="button" aria-label="Ke bagian akhir laporan" onClick={() => window.scrollTo({ top: document.documentElement.scrollHeight })}>↓</button>
  </nav>;
}

export function SiteFooter() {
  return <footer className="site-footer"><div className="site-footer__inner"><strong>UGM Analytics</strong><span>Analisis dampak UGM berdasarkan Kepmen 361/M/KEP/2025 dan SDGs. Angka adalah lower-bound berbasis keyword dan sumber yang tersedia.</span></div></footer>;
}

export function SiteShell({ children }: { children: ReactNode }) {
  const onReport = useLocation().pathname !== '/akreditasi';
  return <div className="site"><a className="skip-link" href="#main-content">Lewati ke konten utama</a><SiteHeader />{onReport && <SectionRail />}<main id="main-content">{children}</main><SiteFooter /></div>;
}
