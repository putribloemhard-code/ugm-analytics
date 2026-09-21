import { useEffect, useRef, useState, type ReactNode, type RefObject } from 'react';
import { Link, NavLink, useLocation } from 'react-router-dom';

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

function useActiveSection(pathname: string) {
  const [active, setActive] = useState('');
  useEffect(() => {
    const elements = reportSections.map(section => document.getElementById(section.id)).filter((el): el is HTMLElement => !!el);
    if (!elements.length || typeof IntersectionObserver === 'undefined') { setActive(''); return; }
    const observer = new IntersectionObserver(entries => { const hit = entries.filter(entry => entry.isIntersecting).sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)[0]; if (hit) setActive(hit.target.id); }, { rootMargin: '-25% 0px -65% 0px' });
    elements.forEach(el => observer.observe(el));
    return () => observer.disconnect();
  }, [pathname]);
  return active;
}

function SiteHeader() {
  const location = useLocation();
  const { theme, toggle } = useTheme();
  const progress = useReadingProgress();
  const active = useActiveSection(location.pathname);
  const onReport = location.pathname !== '/akreditasi';
  return <header className="site-header">
    <div className="reading-progress" role="progressbar" aria-label="Kemajuan membaca" aria-valuemin={0} aria-valuemax={100} aria-valuenow={0}><div ref={progress} /></div>
    <div className="site-header__inner">
      <Link className="site-header__brand" to="/" aria-label="UGM Analytics — beranda"><img src={assetUrl('logo/LogoUGM.png')} alt="" /><span>UGM Analytics</span></Link>
      <nav className="site-header__nav" aria-label="Navigasi utama">
        {reportSections.map(section => <Link key={section.id} to={{ pathname: '/', hash: `#${section.id}` }} className={onReport && active === section.id ? 'active' : ''} aria-current={onReport && active === section.id ? 'location' : undefined}>{section.label}</Link>)}
      </nav>
      <NavLink to="/akreditasi" className={({ isActive }) => `site-header__tab ${isActive ? 'active' : ''}`}>Akreditasi</NavLink>
      <button className="theme-toggle" type="button" aria-pressed={theme === 'dark'} onClick={toggle}>{theme === 'dark' ? 'Mode terang' : 'Mode gelap'}</button>
    </div>
  </header>;
}

export function SiteFooter() {
  return <footer className="site-footer"><div className="site-footer__inner"><strong>UGM Analytics</strong><span>Analisis dampak UGM berdasarkan Kepmen 361/M/KEP/2025 dan SDGs. Angka adalah lower-bound berbasis keyword dan sumber yang tersedia.</span></div></footer>;
}

export function SiteShell({ children }: { children: ReactNode }) {
  return <div className="site"><a className="skip-link" href="#main-content">Lewati ke konten utama</a><SiteHeader /><main id="main-content">{children}</main><SiteFooter /></div>;
}
