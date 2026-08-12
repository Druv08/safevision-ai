import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import {
  FaShieldAlt, FaArrowRight, FaBolt, FaCloud, FaBullseye,
  FaHardHat, FaVideo, FaChartPie, FaBell, FaCloudUploadAlt, FaMicrochip,
  FaExclamationTriangle, FaFileExport, FaCheck,
} from "react-icons/fa";

import { GOLD, OK, ALERT } from "../theme";

/* ── Reveal-on-scroll ────────────────────────────────────────── */
function useReveal() {
  useEffect(() => {
    const els = document.querySelectorAll(".sv-reveal");
    const obs = new IntersectionObserver(
      (entries) => {
        entries.forEach((en) => {
          if (en.isIntersecting) {
            en.target.classList.add("sv-in");
            obs.unobserve(en.target);
          }
        });
      },
      { threshold: 0.12, rootMargin: "0px 0px -60px 0px" }
    );
    els.forEach((el) => obs.observe(el));
    return () => obs.disconnect();
  }, []);
}

/* Fires once when the element scrolls into view. */
function useInView(threshold = 0.35) {
  const ref = useRef(null);
  const [seen, setSeen] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const obs = new IntersectionObserver(
      ([e]) => {
        if (e.isIntersecting) {
          setSeen(true);
          obs.disconnect();
        }
      },
      { threshold }
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, [threshold]);
  return [ref, seen];
}

/* ── Scroll progress rail ────────────────────────────────────── */
function ScrollProgress() {
  const [pct, setPct] = useState(0);
  useEffect(() => {
    const fn = () => {
      const h = document.documentElement.scrollHeight - window.innerHeight;
      setPct(h > 0 ? (window.scrollY / h) * 100 : 0);
    };
    fn();
    window.addEventListener("scroll", fn, { passive: true });
    return () => window.removeEventListener("scroll", fn);
  }, []);
  return (
    <div
      className="fixed top-0 left-0 z-[60] h-[2px]"
      style={{
        width: `${pct}%`,
        background: `linear-gradient(90deg, ${OK}, ${GOLD})`,
        transition: "width 90ms linear",
      }}
    />
  );
}

/* ── Count-up metric ─────────────────────────────────────────── */
function CountUp({ target, suffix = "", decimals = 0, duration = 1800 }) {
  const [ref, seen] = useInView(0.4);
  const [val, setVal] = useState(0);
  useEffect(() => {
    if (!seen) return;
    let raf;
    const t0 = performance.now();
    const tick = (now) => {
      const p = Math.min((now - t0) / duration, 1);
      setVal(target * (1 - Math.pow(1 - p, 3)));
      if (p < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [seen, target, duration]);
  return (
    <span ref={ref}>
      {val.toFixed(decimals)}
      {suffix}
    </span>
  );
}

/* ── Detection bounding box ──────────────────────────────────── */
function DetectionBox({ tone = "ok", id, top: topLabel, bottom: bottomLabel, style, delay = 0 }) {
  const ok = tone === "ok";
  const c = ok ? OK : ALERT;
  const corner = "absolute w-3.5 h-3.5 border-[2.5px]";
  return (
    <div
      className="absolute"
      style={{ ...style, animation: `sv-box-in .55s cubic-bezier(.16,1,.3,1) ${delay}s both` }}
    >
      {/* box body */}
      <div
        className="absolute inset-0 rounded-[2px]"
        style={{ border: `1.5px solid ${c}99`, background: `${c}1A` }}
      />
      {/* corner brackets */}
      <span className={`${corner} -top-px -left-px border-r-0 border-b-0`} style={{ borderColor: c }} />
      <span className={`${corner} -top-px -right-px border-l-0 border-b-0`} style={{ borderColor: c }} />
      <span className={`${corner} -bottom-px -left-px border-r-0 border-t-0`} style={{ borderColor: c }} />
      <span className={`${corner} -bottom-px -right-px border-l-0 border-t-0`} style={{ borderColor: c }} />

      {/* top label */}
      <div
        className="sv-mono absolute -top-[21px] left-0 flex items-center gap-1.5 px-1.5 py-[3px] text-[9px] font-bold tracking-wide whitespace-nowrap rounded-[2px]"
        style={{
          background: c,
          color: ok ? "#06170F" : "#2A0A05",
          animation: ok ? undefined : "sv-alert-pulse 1.6s ease-out infinite",
        }}
      >
        {!ok && <FaExclamationTriangle className="text-[8px]" />}
        {topLabel}
      </div>

      {/* id tag */}
      {id && (
        <div
          className="sv-mono absolute -top-[21px] right-0 px-1.5 py-[3px] text-[9px] font-bold tracking-wide rounded-[2px] backdrop-blur-sm"
          style={{ background: "rgba(8,21,15,0.78)", color: c, border: `1px solid ${c}55` }}
        >
          {id}
        </div>
      )}

      {/* bottom label */}
      {bottomLabel && (
        <div
          className="sv-mono absolute -bottom-[20px] left-0 px-1.5 py-[3px] text-[9px] font-bold tracking-wide whitespace-nowrap rounded-[2px] backdrop-blur-sm"
          style={{ background: "rgba(8,21,15,0.82)", color: c, border: `1px solid ${c}55` }}
        >
          {bottomLabel}
        </div>
      )}
    </div>
  );
}

/* ── Compliance rate widget ──────────────────────────────────── */
function ComplianceRing({ value = 94.2 }) {
  const [ref, seen] = useInView(0.5);
  const R = 32;
  const C = 2 * Math.PI * R;
  return (
    <div
      ref={ref}
      className="sv-glass rounded-2xl p-4 shadow-2xl flex items-center gap-4"
      style={{ boxShadow: "0 24px 60px -20px rgba(0,0,0,0.85)" }}
    >
      <div className="relative flex-shrink-0">
        <svg width="80" height="80" viewBox="0 0 80 80" className="-rotate-90">
          <circle cx="40" cy="40" r={R} fill="none" stroke="rgba(247,240,235,0.12)" strokeWidth="6" />
          <circle
            cx="40" cy="40" r={R}
            fill="none" stroke={GOLD} strokeWidth="6" strokeLinecap="round"
            strokeDasharray={C}
            strokeDashoffset={seen ? C - (C * value) / 100 : C}
            style={{ transition: "stroke-dashoffset 1.7s cubic-bezier(.16,1,.3,1) .15s" }}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-[15px] font-extrabold text-[#F7F0EB] leading-none">
            <CountUp target={value} decimals={1} suffix="%" />
          </span>
        </div>
      </div>

      <div className="pr-1">
        <p className="sv-mono text-[9px] font-bold uppercase tracking-[0.14em] text-[#F7F0EB]/45">
          Compliance Rate
        </p>
        <p className="text-[13px] font-semibold text-[#F7F0EB] mt-0.5 whitespace-nowrap">
          Shift average
        </p>
        <div className="flex items-end gap-[3px] h-7 mt-2">
          {[52, 64, 58, 71, 66, 80, 88].map((h, i) => (
            <span
              key={i}
              className="w-[5px] rounded-[1px]"
              style={{
                height: seen ? `${h}%` : "6%",
                background: i === 6 ? GOLD : "rgba(226,164,66,0.32)",
                transition: `height .8s cubic-bezier(.16,1,.3,1) ${0.3 + i * 0.06}s`,
              }}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

/* ── Live monitoring feed mockup ─────────────────────────────── */
function LiveFeed() {
  const [clock, setClock] = useState("23:48:17");
  useEffect(() => {
    const id = setInterval(() => {
      const d = new Date();
      setClock(
        [d.getHours(), d.getMinutes(), d.getSeconds()]
          .map((n) => String(n).padStart(2, "0"))
          .join(":")
      );
    }, 1000);
    return () => clearInterval(id);
  }, []);

  return (
    <div className="relative" style={{ animation: "sv-drift 7s ease-in-out infinite" }}>
      {/* ambient glow */}
      <div
        className="absolute -inset-8 -z-10 rounded-[40px] blur-3xl"
        style={{ background: "radial-gradient(ellipse at 60% 40%, rgba(226,164,66,0.18), rgba(39,96,75,0.22) 45%, transparent 72%)" }}
      />

      <div
        className="sv-glass rounded-2xl overflow-hidden"
        style={{ boxShadow: "0 40px 90px -30px rgba(0,0,0,0.9), 0 0 0 1px rgba(247,240,235,0.06)" }}
      >
        {/* ── chrome bar ── */}
        <div className="flex items-center justify-between px-4 py-2.5 border-b sv-hairline bg-[#08150F]/70">
          <div className="flex items-center gap-3 min-w-0">
            <span
              className="sv-mono flex items-center gap-1.5 px-2 py-[3px] rounded-[3px] text-[9px] font-bold tracking-widest text-[#F7F0EB]"
              style={{ background: ALERT }}
            >
              <span className="w-1.5 h-1.5 rounded-full bg-[#F7F0EB]" style={{ animation: "sv-blink 1.4s ease-in-out infinite" }} />
              LIVE
            </span>
            <span className="sv-mono text-[10px] font-semibold tracking-wider text-[#F7F0EB]/70 truncate">
              CAM-04 · ZONE B — NORTH YARD
            </span>
          </div>
          <span className="sv-mono text-[10px] font-semibold tracking-wider text-[#F7F0EB]/50 tabular-nums flex-shrink-0">
            {clock}
          </span>
        </div>

        {/* ── feed ── */}
        <div className="relative aspect-video overflow-hidden sv-feed-fallback sv-scanline">
          {/* scene photo, degrades to sv-feed-fallback if /bg1.png is absent */}
          <div className="absolute inset-0 sv-feed-scene" />
          {/* vignette + CRT texture */}
          <div
            className="absolute inset-0"
            style={{ background: "radial-gradient(ellipse 78% 70% at 50% 45%, transparent 40%, rgba(6,17,12,0.82) 100%)" }}
          />
          <div className="absolute inset-0 sv-crt pointer-events-none" />

          {/* HUD frame */}
          <div className="absolute inset-3 border sv-hairline rounded-[3px] pointer-events-none opacity-40" />

          {/* Detections. Coordinates are tuned to the workers in
              public/bg1.png (836x388) as cropped by `cover` at 16/9 —
              swapping the photo means retuning these three boxes. */}
          <DetectionBox
            id="#019"
            tone="ok"
            top="HELMET 98%"
            bottom="VEST 96%"
            delay={0.35}
            style={{ left: "24.3%", top: "20%", width: "13.2%", height: "66%" }}
          />
          <DetectionBox
            id="#022"
            tone="ok"
            top="HELMET 97%"
            bottom="VEST 99%"
            delay={0.55}
            style={{ left: "40.3%", top: "26%", width: "11.8%", height: "62%" }}
          />
          <DetectionBox
            id="#027"
            tone="ok"
            top="HELMET 96%"
            bottom="VEST 98%"
            delay={0.75}
            style={{ left: "62%", top: "29%", width: "14.7%", height: "57%" }}
          />

          {/* inference chip */}
          <div className="sv-mono absolute bottom-5 left-5 flex items-center gap-2 px-2.5 py-1.5 rounded-md bg-[#08150F]/75 backdrop-blur-sm border sv-hairline">
            <span className="w-1.5 h-1.5 rounded-full" style={{ background: OK, boxShadow: `0 0 8px ${OK}` }} />
            <span className="text-[9px] font-bold tracking-wider text-[#F7F0EB]/80">YOLOv8 · 47 FPS</span>
          </div>
        </div>

        {/* ── detection tally ── */}
        <div className="grid grid-cols-4 divide-x divide-[#F7F0EB]/10 border-t sv-hairline bg-[#08150F]/70">
          {[
            { n: "5", l: "Persons", c: "#F7F0EB" },
            { n: "5", l: "Helmets", c: OK },
            { n: "5", l: "Vests", c: OK },
            { n: "0", l: "Violations", c: OK },
          ].map((s) => (
            <div key={s.l} className="px-3 py-3 text-center">
              <p className="sv-mono text-lg font-extrabold leading-none" style={{ color: s.c }}>{s.n}</p>
              <p className="sv-mono text-[8.5px] font-bold uppercase tracking-[0.16em] text-[#F7F0EB]/40 mt-1.5">
                {s.l}
              </p>
            </div>
          ))}
        </div>
      </div>

      {/* floating compliance widget */}
      <div className="absolute -top-7 -right-4 sm:-right-8 hidden sm:block">
        <ComplianceRing value={94.2} />
      </div>

    </div>
  );
}

/* ── Hero feature strip ──────────────────────────────────────── */
const HERO_FEATURES = [
  { icon: <FaBolt />, title: "Real-time Detection", sub: "Sub-200ms violation alerts" },
  { icon: <FaBullseye />, title: "High Accuracy", sub: "YOLOv8 · 99.2% mAP" },
  { icon: <FaCloud />, title: "Cloud Ready", sub: "Export, audit & scale" },
];

/* ── Platform capabilities ───────────────────────────────────── */
const CAPABILITIES = [
  { icon: <FaHardHat />, title: "Helmet Detection", desc: "Flags any worker entering a hard-hat zone without head protection, frame by frame.", stat: "99.2%", statLabel: "Detection mAP" },
  { icon: <FaShieldAlt />, title: "Vest Detection", desc: "Tracks hi-vis compliance across every worker in frame, simultaneously and continuously.", stat: "<200ms", statLabel: "Inference latency" },
  { icon: <FaBell />, title: "Real-time Alerts", desc: "Pushes violations to safety managers the instant they occur — no manual review loop.", stat: "0.2s", statLabel: "Alert dispatch" },
  { icon: <FaVideo />, title: "Multi-camera Feeds", desc: "Ingests live CCTV or RTSP streams from across the site for 24/7 surveillance coverage.", stat: "32+", statLabel: "Streams per site" },
  { icon: <FaChartPie />, title: "Analytics Dashboard", desc: "Compliance trends, violation breakdowns and shift-level reporting in one control center.", stat: "50+", statLabel: "Tracked metrics" },
  { icon: <FaCloud />, title: "Cloud Export", desc: "Ships violation logs, compliance certificates and audit trails straight to your storage.", stat: "99.9%", statLabel: "Uptime SLA" },
];

const STEPS = [
  { n: "01", icon: <FaCloudUploadAlt />, title: "Capture", desc: "Connect a live CCTV feed or upload site footage directly to the platform." },
  { n: "02", icon: <FaMicrochip />, title: "Detect", desc: "The YOLOv8 model localises every worker and classifies their PPE in real time." },
  { n: "03", icon: <FaExclamationTriangle />, title: "Analyse", desc: "Violations are scored, deduplicated and escalated to the right supervisor." },
  { n: "04", icon: <FaFileExport />, title: "Report", desc: "Compliance dashboards and exportable CSV audit trails, ready for inspection." },
];

/* ── Section heading ─────────────────────────────────────────── */
function SectionHead({ eyebrow, children, sub }) {
  return (
    <div className="text-center max-w-2xl mx-auto mb-16 sv-reveal">
      <p className="sv-mono text-[11px] font-bold uppercase tracking-[0.22em] mb-4" style={{ color: GOLD }}>
        {eyebrow}
      </p>
      <h2 className="text-[2rem] md:text-[2.75rem] font-extrabold text-[#F7F0EB] leading-[1.12] tracking-[-0.02em]">
        {children}
      </h2>
      {sub && <p className="text-[#F7F0EB]/55 mt-5 text-lg leading-relaxed">{sub}</p>}
    </div>
  );
}

/* ══════════════════════════════════════════════════════════════
   Landing page
   ══════════════════════════════════════════════════════════════ */
function Landing() {
  useReveal();
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const fn = () => setScrolled(window.scrollY > 24);
    fn();
    window.addEventListener("scroll", fn, { passive: true });
    return () => window.removeEventListener("scroll", fn);
  }, []);

  return (
    <div className="sv-root min-h-screen bg-[#08150F] text-[#F7F0EB] overflow-x-hidden selection:bg-[#E2A442]/30">
      <ScrollProgress />

      {/* ── Navbar ───────────────────────────────────────────── */}
      <header
        className={`fixed top-0 inset-x-0 z-50 transition-all duration-500 ${
          scrolled ? "bg-[#08150F]/85 backdrop-blur-xl border-b border-[#F7F0EB]/10" : "border-b border-transparent"
        }`}
      >
        <nav className="w-full flex items-center justify-between px-5 lg:px-8 py-4">
          <Link to="/" className="flex items-center gap-3">
            <div
              className="w-10 h-10 rounded-xl flex items-center justify-center"
              style={{ background: "linear-gradient(150deg,#27604B,#1B4436)", border: "1px solid rgba(226,164,66,0.35)" }}
            >
              <FaShieldAlt style={{ color: GOLD }} />
            </div>
            <div className="leading-none">
              <p className="text-[17px] font-extrabold tracking-[-0.01em]">
                SafeVision<span style={{ color: GOLD }}>AI</span>
              </p>
              <p className="sv-mono text-[8.5px] font-bold uppercase tracking-[0.22em] text-[#F7F0EB]/40 mt-1">
                PPE Monitoring
              </p>
            </div>
          </Link>

          {/* nav links, sign-in and CTA ride together on the far right */}
          <div className="flex items-center gap-7">
            <div className="hidden lg:flex items-center gap-8 text-[14px] font-medium text-[#F7F0EB]/65">
              <a href="#capabilities" className="hover:text-[#F7F0EB] transition-colors">Capabilities</a>
              <a href="#how-it-works" className="hover:text-[#F7F0EB] transition-colors">How it works</a>
              <a href="#control-center" className="hover:text-[#F7F0EB] transition-colors">Control Center</a>
              <Link to="/about" className="hover:text-[#F7F0EB] transition-colors">About</Link>
            </div>

            <div className="flex items-center gap-4">
              <Link
                to="/dashboard"
                className="hidden sm:block text-[14px] font-medium text-[#F7F0EB]/65 hover:text-[#F7F0EB] transition-colors"
              >
                Sign in
              </Link>
              <Link
                to="/dashboard"
                className="sv-gold-btn text-[#1B2410] text-[14px] font-bold px-5 py-2.5 rounded-lg transition-shadow duration-300"
              >
                Get Started
              </Link>
            </div>
          </div>
        </nav>
      </header>

      {/* ── Hero ─────────────────────────────────────────────── */}
      <section className="relative">
        {/* background stack: photo → dark green wash → grid → grain */}
        <div className="absolute inset-0 overflow-hidden">
          <div className="absolute inset-0 sv-hero-ground" />
          <div className="absolute inset-0 sv-hero-photo" />
          <div className="absolute inset-0 sv-hero-tint" />
          <div className="absolute inset-0 sv-grid" />
          <div className="absolute inset-0 sv-grain pointer-events-none" />
          <div className="absolute inset-x-0 bottom-0 h-40 bg-gradient-to-b from-transparent to-[#08150F]" />
        </div>

        <div className="relative max-w-7xl mx-auto px-6 pt-36 lg:pt-44 pb-24 grid lg:grid-cols-[1.05fr_1fr] gap-14 xl:gap-20 items-center">
          {/* copy */}
          <div>
            <div
              className="inline-flex items-center gap-2.5 px-3.5 py-1.5 rounded-full mb-8 sv-reveal"
              style={{ background: "rgba(95,208,138,0.1)", border: "1px solid rgba(95,208,138,0.28)" }}
            >
              <span className="w-1.5 h-1.5 rounded-full" style={{ background: OK, boxShadow: `0 0 8px ${OK}` }} />
              <span className="sv-mono text-[10px] font-bold uppercase tracking-[0.16em]" style={{ color: OK }}>
                Live on 32 sites
              </span>
            </div>

            <h1
              className="text-[2.75rem] sm:text-[3.5rem] xl:text-[4.25rem] font-extrabold leading-[1.04] tracking-[-0.03em] mb-7 sv-reveal"
              style={{ transitionDelay: "80ms" }}
            >
              AI Powered <span className="sv-gold-text">PPE Safety</span>
              <br />
              Monitoring System
            </h1>

            <p
              className="text-[1.0625rem] sm:text-lg text-[#F7F0EB]/60 leading-relaxed max-w-xl mb-10 sv-reveal"
              style={{ transitionDelay: "160ms" }}
            >
              Computer vision that watches every hard-hat zone in real time — detecting missing
              helmets and vests the moment they appear, so you act before the incident does.
            </p>

            <div className="flex flex-wrap items-center gap-4 mb-14 sv-reveal" style={{ transitionDelay: "240ms" }}>
              <Link
                to="/dashboard"
                className="sv-gold-btn group flex items-center gap-2.5 text-[#1B2410] px-7 py-4 rounded-xl font-bold text-[15px] transition-shadow duration-300"
              >
                Get Started
                <FaArrowRight className="text-xs transition-transform duration-300 group-hover:translate-x-1" />
              </Link>
            </div>

            {/* feature strip */}
            <div
              className="grid sm:grid-cols-3 gap-6 pt-9 border-t border-[#F7F0EB]/10 sv-reveal"
              style={{ transitionDelay: "320ms" }}
            >
              {HERO_FEATURES.map((f) => (
                <div key={f.title} className="flex items-center gap-3">
                  <div
                    className="w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0 text-sm"
                    style={{ background: "rgba(226,164,66,0.11)", border: "1px solid rgba(226,164,66,0.3)", color: GOLD }}
                  >
                    {f.icon}
                  </div>
                  <div className="min-w-0">
                    <p className="text-[13.5px] font-bold text-[#F7F0EB] leading-tight">{f.title}</p>
                    <p className="text-[11.5px] text-[#F7F0EB]/45 mt-0.5 truncate">{f.sub}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* live feed mockup */}
          <div className="sv-reveal lg:mt-0 mt-6" style={{ transitionDelay: "180ms" }}>
            <LiveFeed />
          </div>
        </div>
      </section>

      {/* ── Stats strip ──────────────────────────────────────── */}
      <section className="relative border-y border-[#F7F0EB]/[0.08] bg-[#0E2419]/40">
        <div className="max-w-6xl mx-auto px-6 py-16 grid grid-cols-2 lg:grid-cols-4 gap-10 text-center">
          {[
            { t: 99.2, s: "%", d: 1, l: "Detection accuracy" },
            { t: 180, s: "ms", d: 0, l: "Inference latency" },
            { t: 32, s: "+", d: 0, l: "Cameras per site" },
            { t: 24, s: "/7", d: 0, l: "Continuous coverage" },
          ].map((s, i) => (
            <div key={s.l} className="sv-reveal" style={{ transitionDelay: `${i * 90}ms` }}>
              <p className="text-[2.5rem] font-extrabold tracking-[-0.03em] mb-1.5" style={{ color: GOLD }}>
                <CountUp target={s.t} suffix={s.s} decimals={s.d} />
              </p>
              <p className="sv-mono text-[10px] font-bold uppercase tracking-[0.16em] text-[#F7F0EB]/45">
                {s.l}
              </p>
            </div>
          ))}
        </div>
      </section>

      {/* ── Capabilities ─────────────────────────────────────── */}
      <section id="capabilities" className="relative py-28">
        <div className="max-w-7xl mx-auto px-6">
          <SectionHead
            eyebrow="Platform Capabilities"
            sub="A complete safety stack — from the camera on the gantry to the compliance report on your desk."
          >
            Everything you need to keep a site{" "}
            <span className="sv-gold-text">compliant</span>
          </SectionHead>

          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-5">
            {CAPABILITIES.map((c, i) => (
              <div
                key={c.title}
                className="sv-reveal group relative rounded-2xl p-7 bg-[#0E2419]/60 border border-[#F7F0EB]/[0.09] hover:border-[#E2A442]/35 transition-colors duration-400 overflow-hidden"
                style={{ transitionDelay: `${(i % 3) * 90}ms` }}
              >
                <div
                  className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-500 pointer-events-none"
                  style={{ background: "radial-gradient(ellipse 80% 60% at 50% 0%, rgba(226,164,66,0.09), transparent 70%)" }}
                />
                <div
                  className="relative w-11 h-11 rounded-xl flex items-center justify-center mb-6"
                  style={{ background: "rgba(226,164,66,0.1)", border: "1px solid rgba(226,164,66,0.28)", color: GOLD }}
                >
                  {c.icon}
                </div>
                <h3 className="relative text-[17px] font-bold text-[#F7F0EB] mb-2.5">{c.title}</h3>
                <p className="relative text-[13.5px] text-[#F7F0EB]/50 leading-relaxed mb-7">{c.desc}</p>
                <div className="relative flex items-baseline gap-2.5 pt-5 border-t border-[#F7F0EB]/[0.09]">
                  <span className="text-[22px] font-extrabold tracking-tight" style={{ color: GOLD }}>{c.stat}</span>
                  <span className="sv-mono text-[9.5px] font-bold uppercase tracking-[0.14em] text-[#F7F0EB]/38">
                    {c.statLabel}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Control center preview ───────────────────────────── */}
      <section id="control-center" className="relative py-28 border-y border-[#F7F0EB]/[0.08] bg-[#0E2419]/30">
        <div className="max-w-7xl mx-auto px-6">
          <SectionHead
            eyebrow="Interactive Platform"
            sub="Monitor compliance, analyse violation trends and manage alerts across every site from one screen."
          >
            The <span className="sv-gold-text">Control Center</span>
          </SectionHead>

          <div className="sv-reveal max-w-5xl mx-auto rounded-2xl overflow-hidden sv-glass" style={{ boxShadow: "0 40px 90px -30px rgba(0,0,0,0.85)" }}>
            {/* browser chrome */}
            <div className="flex items-center gap-2 px-4 py-3 border-b sv-hairline bg-[#08150F]/70">
              <div className="flex gap-1.5">
                {[ALERT, GOLD, OK].map((c) => (
                  <span key={c} className="w-2.5 h-2.5 rounded-full" style={{ background: c, opacity: 0.7 }} />
                ))}
              </div>
              <div className="sv-mono mx-auto text-[10px] text-[#F7F0EB]/40 px-4 py-1.5 rounded-md bg-[#F7F0EB]/[0.05] border sv-hairline w-72 text-center truncate">
                safevision.ai/dashboard
              </div>
            </div>

            <div className="p-5 sm:p-6 grid md:grid-cols-[150px_1fr] gap-6 bg-[#08150F]/40">
              {/* sidebar */}
              <div className="hidden md:flex flex-col gap-3.5 pr-5 border-r sv-hairline">
                <p className="sv-mono text-[9px] font-bold uppercase tracking-[0.18em] text-[#F7F0EB]/35 mb-1">
                  Monitor
                </p>
                {[
                  { l: "Dashboard", active: true },
                  { l: "Image Detection" },
                  { l: "Video Detection" },
                  { l: "Violations" },
                  { l: "Reports" },
                ].map((it) => (
                  <div
                    key={it.l}
                    className={`flex items-center gap-2.5 text-[12px] ${
                      it.active ? "text-[#F7F0EB] font-semibold" : "text-[#F7F0EB]/40"
                    }`}
                  >
                    <span
                      className="w-1.5 h-1.5 rounded-[2px] flex-shrink-0"
                      style={{ background: it.active ? GOLD : "rgba(247,240,235,0.2)" }}
                    />
                    {it.l}
                  </div>
                ))}
              </div>

              {/* body */}
              <div className="space-y-4 min-w-0">
                <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
                  {[
                    { l: "Violations", v: "284", c: ALERT },
                    { l: "No Vest", v: "154", c: GOLD },
                    { l: "No Helmet", v: "130", c: GOLD },
                    { l: "Status", v: "Active", c: OK, ping: true },
                  ].map((k) => (
                    <div
                      key={k.l}
                      className="rounded-xl p-3 border"
                      style={{ background: `${k.c}12`, borderColor: `${k.c}2E` }}
                    >
                      <p className="sv-mono text-[8.5px] font-bold uppercase tracking-[0.14em] text-[#F7F0EB]/45">
                        {k.l}
                      </p>
                      <div className="flex items-center justify-between mt-1.5">
                        <span className="text-[19px] font-extrabold leading-none" style={{ color: k.c }}>{k.v}</span>
                        {k.ping && <span className="w-1.5 h-1.5 rounded-full" style={{ background: k.c, animation: "sv-blink 1.4s ease-in-out infinite" }} />}
                      </div>
                    </div>
                  ))}
                </div>

                {/* chart */}
                <div className="rounded-xl p-4 bg-[#F7F0EB]/[0.03] border sv-hairline">
                  <div className="flex items-center justify-between mb-4">
                    <p className="text-[12px] font-semibold text-[#F7F0EB]/80">Compliance rate — this week</p>
                    <span
                      className="sv-mono text-[9px] font-bold px-2 py-0.5 rounded"
                      style={{ background: `${OK}1A`, color: OK }}
                    >
                      95% TARGET
                    </span>
                  </div>
                  <div className="h-24 flex items-end gap-2">
                    {[72, 86, 64, 91, 88, 79, 94].map((h, i) => (
                      <div key={i} className="flex-1 rounded-t-[3px] bg-[#F7F0EB]/[0.05] flex items-end" style={{ height: "100%" }}>
                        <div
                          className="w-full rounded-t-[3px]"
                          style={{
                            height: `${h}%`,
                            background: h >= 90
                              ? `linear-gradient(180deg, ${GOLD}, ${GOLD}66)`
                              : `linear-gradient(180deg, rgba(39,96,75,1), rgba(39,96,75,0.45))`,
                          }}
                        />
                      </div>
                    ))}
                  </div>
                  <div className="sv-mono flex justify-between text-[8.5px] font-bold tracking-wider text-[#F7F0EB]/30 mt-2.5">
                    {["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"].map((d) => <span key={d}>{d}</span>)}
                  </div>
                </div>

                {/* alert row */}
                <div
                  className="rounded-lg px-3.5 py-2.5 flex items-center justify-between gap-3 border"
                  style={{ background: `${ALERT}12`, borderColor: `${ALERT}33` }}
                >
                  <p className="text-[11.5px] flex items-center gap-2 min-w-0" style={{ color: ALERT }}>
                    <span className="w-1.5 h-1.5 rounded-full flex-shrink-0" style={{ background: ALERT, animation: "sv-blink 1.2s ease-in-out infinite" }} />
                    <strong className="font-bold">Alert</strong>
                    <span className="truncate text-[#F7F0EB]/70">Helmet missing detected at Gate 3</span>
                  </p>
                  <span className="sv-mono text-[9px] text-[#F7F0EB]/35 flex-shrink-0">JUST NOW</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── How it works ─────────────────────────────────────── */}
      <section id="how-it-works" className="relative py-28">
        <div className="max-w-7xl mx-auto px-6">
          <SectionHead
            eyebrow="How It Works"
            sub="Four steps from raw footage to an actionable safety record."
          >
            From camera to <span className="sv-gold-text">compliance report</span>
            <br className="hidden sm:block" /> in under a second
          </SectionHead>

          <div className="relative grid md:grid-cols-4 gap-5">
            {/* connector rail */}
            <div className="hidden md:block absolute top-[52px] left-[12%] right-[12%] h-px bg-gradient-to-r from-transparent via-[#E2A442]/30 to-transparent" />

            {STEPS.map((s, i) => (
              <div
                key={s.n}
                className="sv-reveal relative rounded-2xl p-6 bg-[#0E2419]/60 border border-[#F7F0EB]/[0.09] hover:border-[#E2A442]/30 transition-colors duration-400"
                style={{ transitionDelay: `${i * 110}ms` }}
              >
                <span className="sv-mono absolute top-5 right-5 text-[11px] font-bold tracking-wider text-[#F7F0EB]/20">
                  {s.n}
                </span>
                <div
                  className="w-11 h-11 rounded-xl flex items-center justify-center mb-5"
                  style={{ background: "rgba(27,68,54,0.9)", border: "1px solid rgba(226,164,66,0.3)", color: GOLD }}
                >
                  {s.icon}
                </div>
                <h3 className="text-[16px] font-bold text-[#F7F0EB] mb-2">{s.title}</h3>
                <p className="text-[13px] text-[#F7F0EB]/50 leading-relaxed">{s.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Final CTA ────────────────────────────────────────── */}
      <section className="relative py-28 overflow-hidden">
        <div
          className="absolute inset-0 pointer-events-none"
          style={{ background: "radial-gradient(ellipse 55% 60% at 50% 50%, rgba(27,68,54,0.75), transparent 72%)" }}
        />
        <div className="relative max-w-2xl mx-auto px-6 text-center sv-reveal">
          <p className="sv-mono text-[11px] font-bold uppercase tracking-[0.22em] mb-5" style={{ color: GOLD }}>
            Get Started Today
          </p>
          <h2 className="text-[2.25rem] md:text-[3rem] font-extrabold leading-[1.1] tracking-[-0.025em] mb-6">
            Ready to make your site <span className="sv-gold-text">safer?</span>
          </h2>
          <p className="text-[#F7F0EB]/55 text-lg leading-relaxed mb-10">
            Point SafeVisionAI at your existing cameras and start catching PPE violations
            in real time — no new hardware required.
          </p>
          <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
            <Link
              to="/dashboard"
              className="sv-gold-btn group flex items-center gap-2.5 text-[#1B2410] px-8 py-4 rounded-xl font-bold text-base transition-shadow duration-300"
            >
              Get Started
              <FaArrowRight className="text-xs transition-transform duration-300 group-hover:translate-x-1" />
            </Link>
            <Link
              to="/about"
              className="px-8 py-4 rounded-xl font-semibold text-base text-[#F7F0EB] border border-[#F7F0EB]/18 hover:bg-[#F7F0EB]/[0.06] hover:border-[#F7F0EB]/30 transition-all duration-300"
            >
              Learn more
            </Link>
          </div>

          <div className="flex flex-wrap items-center justify-center gap-x-7 gap-y-3 mt-11">
            {["No new hardware", "Works with existing CCTV", "Deploy in a day"].map((t) => (
              <span key={t} className="flex items-center gap-2 text-[12.5px] text-[#F7F0EB]/45">
                <FaCheck className="text-[9px]" style={{ color: OK }} />
                {t}
              </span>
            ))}
          </div>
        </div>
      </section>

      {/* ── Footer ───────────────────────────────────────────── */}
      <footer className="relative border-t border-[#F7F0EB]/[0.08] bg-[#08150F]">
        <div className="max-w-7xl mx-auto px-6 py-10 flex flex-col sm:flex-row items-center justify-between gap-5">
          <div className="flex items-center gap-3">
            <div
              className="w-8 h-8 rounded-lg flex items-center justify-center"
              style={{ background: "linear-gradient(150deg,#27604B,#1B4436)", border: "1px solid rgba(226,164,66,0.3)" }}
            >
              <FaShieldAlt className="text-xs" style={{ color: GOLD }} />
            </div>
            <p className="text-[14px] font-bold">
              SafeVision<span style={{ color: GOLD }}>AI</span>
            </p>
          </div>
          <p className="sv-mono text-[10.5px] tracking-wider text-[#F7F0EB]/35">
            © 2026 SafeVisionAI — All rights reserved
          </p>
        </div>
      </footer>
    </div>
  );
}

export default Landing;
