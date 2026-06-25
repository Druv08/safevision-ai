import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import {
  FaShieldAlt, FaArrowRight, FaChartBar, FaBolt, FaCheckCircle,
  FaCloud, FaHardHat, FaUserShield, FaBell, FaVideo, FaChartPie,
  FaCloudUploadAlt, FaMicrochip, FaExclamationTriangle, FaFileExport,
} from "react-icons/fa";
import heroImage from "../assets/hero_construction.png";

/* ── Particle Canvas ─────────────────────────────────────────── */
function ParticleCanvas() {
  const canvasRef = useRef(null);
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    let animId;
    const mouse = { x: -999, y: -999 };

    const resize = () => {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
    };
    resize();

    const N = 60;
    const pts = Array.from({ length: N }, () => ({
      x: Math.random() * canvas.width,
      y: Math.random() * canvas.height,
      vx: (Math.random() - 0.5) * 0.35,
      vy: (Math.random() - 0.5) * 0.35,
      r: Math.random() * 1.5 + 0.5,
    }));

    const onMouse = (e) => { mouse.x = e.clientX; mouse.y = e.clientY; };
    window.addEventListener("mousemove", onMouse);
    window.addEventListener("resize", resize);

    const draw = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      pts.forEach((p) => {
        const dx = mouse.x - p.x;
        const dy = mouse.y - p.y;
        const d = Math.hypot(dx, dy);
        if (d < 160 && d > 0) {
          p.vx += (dx / d) * 0.015;
          p.vy += (dy / d) * 0.015;
        }
        const spd = Math.hypot(p.vx, p.vy);
        if (spd > 1.2) { p.vx *= 0.95; p.vy *= 0.95; }
        p.x += p.vx;
        p.y += p.vy;
        if (p.x < 0) p.x = canvas.width;
        if (p.x > canvas.width) p.x = 0;
        if (p.y < 0) p.y = canvas.height;
        if (p.y > canvas.height) p.y = 0;
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
        ctx.fillStyle = "rgba(96,165,250,0.5)";
        ctx.fill();
      });
      for (let i = 0; i < N; i++) {
        for (let j = i + 1; j < N; j++) {
          const dx = pts[i].x - pts[j].x;
          const dy = pts[i].y - pts[j].y;
          const d = Math.hypot(dx, dy);
          if (d < 120) {
            ctx.beginPath();
            ctx.moveTo(pts[i].x, pts[i].y);
            ctx.lineTo(pts[j].x, pts[j].y);
            ctx.strokeStyle = `rgba(96,165,250,${0.12 * (1 - d / 120)})`;
            ctx.lineWidth = 0.5;
            ctx.stroke();
          }
        }
      }
      animId = requestAnimationFrame(draw);
    };
    draw();

    return () => {
      cancelAnimationFrame(animId);
      window.removeEventListener("mousemove", onMouse);
      window.removeEventListener("resize", resize);
    };
  }, []);
  return <canvas ref={canvasRef} className="fixed inset-0 z-0 pointer-events-none opacity-60" />;
}

/* ── Scroll Progress Bar ─────────────────────────────────────── */
function ScrollProgress() {
  const [pct, setPct] = useState(0);
  useEffect(() => {
    const fn = () => {
      const h = document.documentElement.scrollHeight - window.innerHeight;
      setPct(h > 0 ? (window.scrollY / h) * 100 : 0);
    };
    window.addEventListener("scroll", fn, { passive: true });
    return () => window.removeEventListener("scroll", fn);
  }, []);
  return (
    <div
      className="fixed top-0 left-0 z-50 h-[3px] bg-gradient-to-r from-blue-500 via-cyan-400 to-emerald-400"
      style={{ width: `${pct}%`, transition: "width 80ms linear" }}
    />
  );
}

/* ── Magnetic Button ─────────────────────────────────────────── */
function MagneticButton({ children, className, to }) {
  const ref = useRef(null);
  const onMove = (e) => {
    const el = ref.current;
    const r = el.getBoundingClientRect();
    const x = (e.clientX - r.left - r.width / 2) * 0.22;
    const y = (e.clientY - r.top - r.height / 2) * 0.22;
    el.style.transform = `translate(${x}px, ${y}px)`;
    el.style.transition = "transform 0.08s ease";
  };
  const onLeave = () => {
    ref.current.style.transform = "translate(0,0)";
    ref.current.style.transition = "transform 0.45s cubic-bezier(0.23,1,0.32,1)";
  };
  return (
    <Link ref={ref} to={to} className={className} onMouseMove={onMove} onMouseLeave={onLeave}>
      {children}
    </Link>
  );
}

/* ── 3-D Tilt Card ───────────────────────────────────────────── */
function TiltCard({ children, className, style }) {
  const ref = useRef(null);
  const onMove = (e) => {
    const el = ref.current;
    const r = el.getBoundingClientRect();
    const x = (e.clientX - r.left) / r.width - 0.5;
    const y = (e.clientY - r.top) / r.height - 0.5;
    el.style.transform = `perspective(700px) rotateY(${x * 14}deg) rotateX(${-y * 14}deg) scale(1.03)`;
    el.style.transition = "transform 0.08s ease";
  };
  const onLeave = () => {
    ref.current.style.transform = "perspective(700px) rotateY(0deg) rotateX(0deg) scale(1)";
    ref.current.style.transition = "transform 0.5s cubic-bezier(0.23,1,0.32,1)";
  };
  return (
    <div ref={ref} className={className} style={style} onMouseMove={onMove} onMouseLeave={onLeave}>
      {children}
    </div>
  );
}

/* ── Typewriter Text ─────────────────────────────────────────── */
function TypewriterText({ text, speed = 75, onDone }) {
  const [shown, setShown] = useState("");
  useEffect(() => {
    let i = 0;
    const id = setInterval(() => {
      i += 1;
      setShown(text.slice(0, i));
      if (i >= text.length) { clearInterval(id); onDone?.(); }
    }, speed);
    return () => clearInterval(id);
  }, [text, speed, onDone]);
  return (
    <>
      {shown}
      {shown.length < text.length && (
        <span
          className="inline-block w-[3px] h-[0.85em] bg-blue-400 ml-1 align-middle"
          style={{ animation: "cursor-blink 0.7s steps(1) infinite" }}
        />
      )}
    </>
  );
}

/* ── Count-Up Number ─────────────────────────────────────────── */
function CountUp({ target, suffix = "", duration = 2000 }) {
  const [val, setVal] = useState(0);
  const ref = useRef(null);
  const fired = useRef(false);
  useEffect(() => {
    const obs = new IntersectionObserver(([e]) => {
      if (e.isIntersecting && !fired.current) {
        fired.current = true;
        const t0 = performance.now();
        const tick = (now) => {
          const p = Math.min((now - t0) / duration, 1);
          const ease = 1 - Math.pow(1 - p, 3);
          setVal(Math.round(ease * target));
          if (p < 1) requestAnimationFrame(tick);
        };
        requestAnimationFrame(tick);
        obs.disconnect();
      }
    }, { threshold: 0.4 });
    if (ref.current) obs.observe(ref.current);
    return () => obs.disconnect();
  }, [target, duration]);
  return <span ref={ref}>{val}{suffix}</span>;
}

/* ── Feature Data ────────────────────────────────────────────── */
const FEATURES = [
  {
    icon: <FaHardHat />,
    title: "Helmet Detection",
    desc: "Detects workers without helmets in real-time using YOLOv8 object detection with state-of-the-art accuracy.",
    stat: "99.99%", statLabel: "Detection accuracy",
    ic: "text-blue-400 border-blue-500/30 bg-blue-500/10",
    sc: "text-blue-400",
    glow: "0 0 40px rgba(59,130,246,0.15)",
  },
  {
    icon: <FaUserShield />,
    title: "Vest Detection",
    desc: "Monitors safety vests and ensures compliance across all workers on site simultaneously.",
    stat: "<200ms", statLabel: "Detection latency",
    ic: "text-emerald-400 border-emerald-500/30 bg-emerald-500/10",
    sc: "text-emerald-400",
    glow: "0 0 40px rgba(16,185,129,0.15)",
  },
  {
    icon: <FaBell />,
    title: "Real-time Alerts",
    desc: "Instant notifications to safety managers the moment a violation is detected anywhere on site.",
    stat: "0.2s", statLabel: "Alert response time",
    ic: "text-red-400 border-red-500/30 bg-red-500/10",
    sc: "text-red-400",
    glow: "0 0 40px rgba(239,68,68,0.15)",
  },
  {
    icon: <FaVideo />,
    title: "Video Monitoring",
    desc: "Analyze live CCTV footage from multiple cameras for continuous 24/7 safety surveillance.",
    stat: "32+", statLabel: "Cameras per site",
    ic: "text-yellow-400 border-yellow-500/30 bg-yellow-500/10",
    sc: "text-yellow-400",
    glow: "0 0 40px rgba(234,179,8,0.15)",
  },
  {
    icon: <FaChartPie />,
    title: "Analytics Dashboard",
    desc: "Get detailed insights, violation trends, compliance reports, and exportable CSV data.",
    stat: "50+", statLabel: "Report metrics",
    ic: "text-purple-400 border-purple-500/30 bg-purple-500/10",
    sc: "text-purple-400",
    glow: "0 0 40px rgba(168,85,247,0.15)",
  },
  {
    icon: <FaCloud />,
    title: "Cloud Export",
    desc: "Export violation logs, compliance certificates, and audit trails directly to cloud storage.",
    stat: "99.9%", statLabel: "Uptime SLA",
    ic: "text-cyan-400 border-cyan-500/30 bg-cyan-500/10",
    sc: "text-cyan-400",
    glow: "0 0 40px rgba(6,182,212,0.15)",
  },
];

/* ── Vertical Features Section ───────────────────────────────── */
function FeaturesSection() {
  return (
    <section id="features" className="relative z-10 py-24">
      <div className="max-w-7xl mx-auto px-6">
        <div className="text-center mb-16 animate-on-scroll opacity-0 translate-y-10 transition-all duration-700">
          <p className="text-blue-400 font-bold tracking-wider uppercase text-sm mb-3">Platform Features</p>
          <h2 className="text-4xl md:text-5xl font-bold text-white">
            Everything you need for{" "}
            <span className="shimmer-text">workplace safety</span>
          </h2>
          <p className="text-slate-400 mt-4 text-lg max-w-2xl mx-auto">
            A complete AI safety stack — from real-time detection to compliance reporting.
          </p>
        </div>

        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
          {FEATURES.map((f, i) => (
            <TiltCard
              key={i}
              className="animate-on-scroll opacity-0 translate-y-10 transition-all duration-700 bg-white/[0.04] backdrop-blur-lg border border-white/10 p-8 rounded-2xl hover:border-blue-500/30 transition-colors cursor-default"
              style={{ boxShadow: f.glow, transitionDelay: `${(i % 3) * 100}ms` }}
            >
              <div className={`w-12 h-12 rounded-xl flex items-center justify-center border mb-6 text-lg ${f.ic}`}>
                {f.icon}
              </div>
              <h3 className="text-lg font-bold text-white mb-3">{f.title}</h3>
              <p className="text-slate-400 mb-8 leading-relaxed text-sm">{f.desc}</p>
              <div className="flex items-end gap-3 pt-6 border-t border-white/10">
                <span className={`text-2xl font-bold ${f.sc}`}>{f.stat}</span>
                <span className="text-xs text-slate-500 font-medium mb-1">{f.statLabel}</span>
              </div>
            </TiltCard>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ── Step Card ───────────────────────────────────────────────── */
function StepCard({ num, icon, title, desc, color, delay = 0 }) {
  const C = {
    blue:    { border: "border-blue-500/25 hover:border-blue-500/60",     icon: "bg-blue-500/10    border-blue-500/30    text-blue-400",    num: "text-blue-500"    },
    emerald: { border: "border-emerald-500/25 hover:border-emerald-500/60", icon: "bg-emerald-500/10 border-emerald-500/30 text-emerald-400", num: "text-emerald-500" },
    red:     { border: "border-red-500/25 hover:border-red-500/60",       icon: "bg-red-500/10     border-red-500/30     text-red-400",     num: "text-red-500"     },
    yellow:  { border: "border-amber-500/25 hover:border-amber-500/60",   icon: "bg-amber-500/10   border-amber-500/30   text-amber-400",   num: "text-amber-500"   },
  }[color] || {};
  return (
    <div
      className={`animate-on-scroll opacity-0 translate-y-10 transition-all duration-700 bg-slate-900/60 backdrop-blur-md border ${C.border} p-6 rounded-2xl relative hover:scale-105 shadow-xl`}
      style={{ transitionDelay: `${delay}ms` }}
    >
      <span className={`absolute top-5 right-5 text-2xl font-black ${C.num} opacity-80`}>{num}</span>
      <div className={`w-12 h-12 rounded-xl flex items-center justify-center text-xl mb-6 border ${C.icon}`}>
        {icon}
      </div>
      <h3 className="text-lg font-bold text-white mb-2">{title}</h3>
      <p className="text-sm text-slate-400 leading-relaxed">{desc}</p>
    </div>
  );
}

/* ── Dashboard Mock Cards ────────────────────────────────────── */
const MOCK_CARDS = [
  { label: "Violations", val: "284", bg: "bg-red-500/10",    border: "border-red-500/20",    tc: "text-red-400",    ping: false },
  { label: "No Vest",    val: "154", bg: "bg-yellow-500/10", border: "border-yellow-500/20", tc: "text-yellow-400", ping: false },
  { label: "No Helmet",  val: "130", bg: "bg-orange-500/10", border: "border-orange-500/20", tc: "text-orange-400", ping: false },
  { label: "Status",     val: "Active", bg: "bg-green-500/10", border: "border-green-500/20", tc: "text-green-400",  ping: true  },
];

/* ── Landing Page ────────────────────────────────────────────── */
function Landing() {
  const [typingDone, setTypingDone] = useState(false);
  const [pathVisible, setPathVisible] = useState(false);
  const pathRef = useRef(null);

  useEffect(() => {
    const obs = new IntersectionObserver(([e]) => {
      if (e.isIntersecting) { setPathVisible(true); obs.disconnect(); }
    }, { threshold: 0.2 });
    if (pathRef.current) obs.observe(pathRef.current);
    return () => obs.disconnect();
  }, []);

  useEffect(() => {
    const obs = new IntersectionObserver((entries) => {
      entries.forEach((en) => {
        if (en.isIntersecting) {
          en.target.classList.remove("opacity-0", "translate-y-10");
          en.target.classList.add("opacity-100", "translate-y-0");
          obs.unobserve(en.target);
        }
      });
    }, { threshold: 0.1 });
    document.querySelectorAll(".animate-on-scroll").forEach((el) => obs.observe(el));
    return () => obs.disconnect();
  }, []);

  const reveal = (delay = 0) => ({
    opacity: typingDone ? 1 : 0,
    transform: typingDone ? "translateY(0)" : "translateY(12px)",
    transition: `opacity 0.6s ease ${delay}s, transform 0.6s ease ${delay}s`,
  });

  return (
    <div className="min-h-screen bg-[#070d1a] text-slate-200 font-sans selection:bg-blue-500/30 overflow-x-hidden">
      <ScrollProgress />
      <ParticleCanvas />

      {/* Aurora blobs */}
      <div className="fixed inset-0 z-0 pointer-events-none overflow-hidden">
        <div className="aurora-blob w-[700px] h-[700px] bg-blue-700"
          style={{ top: "-180px", left: "-180px", animation: "aurora-1 22s ease-in-out infinite" }} />
        <div className="aurora-blob w-[550px] h-[550px] bg-purple-700"
          style={{ bottom: "-120px", right: "-160px", animation: "aurora-2 28s ease-in-out infinite" }} />
        <div className="aurora-blob w-[450px] h-[450px] bg-cyan-800"
          style={{ top: "38%", right: "12%", animation: "aurora-3 20s ease-in-out infinite" }} />
      </div>

      {/* ── Navbar ── */}
      <nav className="relative z-10 flex items-center justify-between px-6 py-6 max-w-7xl mx-auto">
        <div className="flex items-center gap-3">
          <div className="bg-gradient-to-br from-blue-500 to-cyan-400 p-2.5 rounded-xl shadow-lg shadow-blue-500/25">
            <FaShieldAlt className="text-white text-xl" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-white tracking-tight">
              SafeVision<span className="text-blue-400">AI</span>
            </h1>
            <p className="text-[10px] text-slate-400 uppercase tracking-widest font-semibold">PPE Monitoring</p>
          </div>
        </div>

        <div className="hidden md:flex items-center gap-8 text-sm font-medium text-slate-300">
          <a href="#features" className="hover:text-white transition-colors">Features</a>
          <a href="#how-it-works" className="hover:text-white transition-colors">How It Works</a>
          <Link to="/dashboard" className="hover:text-white transition-colors">Dashboard</Link>
          <Link to="/about" className="hover:text-white transition-colors">About</Link>
        </div>

        <div className="flex items-center gap-4 text-sm font-medium">
          <Link to="/dashboard" className="text-slate-300 hover:text-white transition-colors">Sign In</Link>
          <Link
            to="/dashboard"
            className="bg-blue-600 hover:bg-blue-500 text-white px-5 py-2.5 rounded-lg font-medium transition-colors"
            style={{ boxShadow: "0 0 20px rgba(37,99,235,0.5)" }}
          >
            Get Started
          </Link>
        </div>
      </nav>

      {/* ── Hero ── */}
      <main className="relative z-10 max-w-7xl mx-auto px-6 pt-16 pb-32 grid lg:grid-cols-2 gap-16 items-center">
        <div>
          <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs font-semibold uppercase tracking-wider mb-8">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
            AI-Powered Safety Monitoring
          </div>

          <h1 className="text-5xl lg:text-7xl font-extrabold text-white leading-[1.1] mb-6">
            <TypewriterText text="AI Powered" speed={75} onDone={() => setTypingDone(true)} />
            <br />
            <span className="shimmer-text" style={{ display: "inline-block", ...reveal(0.1) }}>
              PPE Safety
            </span>
            <br />
            <span style={{ display: "inline-block", ...reveal(0.35) }}>
              Monitoring System
            </span>
          </h1>

          <p className="text-lg text-slate-400 mb-10 max-w-xl leading-relaxed" style={reveal(0.6)}>
            Real-time detection of safety violations using advanced computer vision and deep learning.
            Protect your workers before incidents happen.
          </p>

          <div className="flex flex-wrap items-center gap-4 mb-12" style={reveal(0.8)}>
            <MagneticButton
              to="/dashboard"
              className="flex items-center gap-2 bg-blue-600 hover:bg-blue-500 text-white px-6 py-3.5 rounded-xl font-semibold transition-colors shadow-[0_0_25px_rgba(37,99,235,0.5)]"
            >
              Get Started <FaArrowRight />
            </MagneticButton>
            <MagneticButton
              to="/dashboard"
              className="flex items-center gap-2 bg-white/[0.06] hover:bg-white/10 border border-white/10 text-white px-6 py-3.5 rounded-xl font-semibold backdrop-blur-sm transition-colors"
            >
              View Dashboard <FaChartBar />
            </MagneticButton>
          </div>

          <div className="flex items-center gap-8 border-t border-white/10 pt-8" style={reveal(1.0)}>
            {[
              { icon: <FaBolt />,        label: "Real-time Detection", sub: "Instant violation alerts", cls: "bg-blue-500/10   border-blue-500/20   text-blue-400"   },
              { icon: <FaCheckCircle />, label: "High Accuracy",       sub: "YOLOv8 AI Model",         cls: "bg-emerald-500/10 border-emerald-500/20 text-emerald-400" },
              { icon: <FaCloud />,       label: "Cloud Ready",         sub: "Export & Monitor",        cls: "bg-purple-500/10  border-purple-500/20  text-purple-400"  },
            ].map((item, i) => (
              <div key={i} className="flex items-center gap-3">
                <div className={`w-10 h-10 rounded-full border flex items-center justify-center flex-shrink-0 ${item.cls}`}>
                  {item.icon}
                </div>
                <div>
                  <p className="text-sm font-bold text-white">{item.label}</p>
                  <p className="text-xs text-slate-400">{item.sub}</p>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Hero visual */}
        <div className="relative" style={{ animation: "float-card 5s ease-in-out infinite" }}>
          <div className="absolute inset-0 bg-gradient-to-tr from-blue-500/20 to-emerald-500/20 blur-3xl -z-10 rounded-full" />
          <div className="relative bg-slate-900/80 backdrop-blur-xl border border-white/10 rounded-2xl shadow-2xl overflow-visible group">
            <div className="aspect-video bg-slate-800 relative rounded-2xl overflow-hidden">
              <img src={heroImage} alt="Construction Site" className="w-full h-full object-cover opacity-80" />
              <div className="absolute top-[20%] left-[30%] w-32 h-48 border-2 border-emerald-500 bg-emerald-500/10 rounded">
                <div className="absolute -top-6 left-0 bg-emerald-500 text-white text-[10px] font-bold px-2 py-0.5 rounded-sm">Helmet: 99.99%</div>
                <div className="absolute -bottom-6 left-0 bg-emerald-500 text-white text-[10px] font-bold px-2 py-0.5 rounded-sm">Safety Vest: 99.99%</div>
              </div>
              <div className="absolute top-[15%] right-[20%] w-28 h-44 border-2 border-red-500 bg-red-500/10 rounded">
                <div className="absolute -top-6 left-0 bg-red-500 text-white text-[10px] font-bold px-2 py-0.5 rounded-sm">No Helmet</div>
              </div>
              <div className="absolute top-4 left-4 bg-black/60 backdrop-blur-md border border-white/10 px-3 py-1.5 rounded-lg flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
                <span className="text-xs font-bold text-white">LIVE</span>
              </div>
            </div>
            <div className="absolute -bottom-5 -left-5 bg-slate-800/90 backdrop-blur-xl border border-white/10 p-4 rounded-xl shadow-xl flex items-center gap-4 group-hover:-translate-y-2 transition-transform duration-500">
              <div className="w-10 h-10 rounded-lg bg-red-500/10 flex items-center justify-center text-red-400">
                <FaExclamationTriangle />
              </div>
              <div>
                <p className="text-[10px] text-slate-400 font-bold uppercase">Active Violations</p>
                <p className="text-xl font-bold text-white">3</p>
              </div>
            </div>
            <div className="absolute -top-5 -right-5 bg-slate-800/90 backdrop-blur-xl border border-white/10 p-4 rounded-xl shadow-xl flex items-center gap-4 group-hover:-translate-y-2 transition-transform duration-500 delay-100">
              <div className="w-10 h-10 rounded-lg bg-emerald-500/10 flex items-center justify-center text-emerald-400">
                <FaCheckCircle />
              </div>
              <div>
                <p className="text-[10px] text-slate-400 font-bold uppercase">Compliance Rate</p>
                <p className="text-xl font-bold text-white">87%</p>
              </div>
            </div>
          </div>
        </div>
      </main>

      {/* ── Features Grid ── */}
      <FeaturesSection />

      {/* ── Stats Strip ── */}
      <section className="relative z-10 py-20 border-y border-white/[0.06]">
        <div className="max-w-5xl mx-auto px-6 grid grid-cols-2 lg:grid-cols-4 gap-10 text-center">
          {[
            { target: 99,  suffix: "%",  label: "Detection Accuracy", color: "text-blue-400"    },
            { target: 200, suffix: "ms", label: "Response Latency",   color: "text-emerald-400" },
            { target: 32,  suffix: "+",  label: "Cameras Per Site",   color: "text-purple-400"  },
            { target: 50,  suffix: "+",  label: "Report Metrics",     color: "text-yellow-400"  },
          ].map((s, i) => (
            <div
              key={i}
              className="animate-on-scroll opacity-0 translate-y-10 transition-all duration-700"
              style={{ transitionDelay: `${i * 100}ms` }}
            >
              <div className={`text-5xl font-black mb-2 ${s.color}`}>
                <CountUp target={s.target} suffix={s.suffix} />
              </div>
              <p className="text-slate-400 text-sm font-medium">{s.label}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ── Dashboard Preview ── */}
      <section className="relative z-10 py-24 border-b border-white/[0.06]">
        <div className="max-w-7xl mx-auto px-6">
          <div className="text-center mb-16 animate-on-scroll opacity-0 translate-y-10 transition-all duration-700">
            <p className="text-blue-400 font-bold tracking-wider uppercase text-sm mb-4">Interactive Platform</p>
            <h2 className="text-4xl md:text-5xl font-bold text-white mb-6">
              Intelligent{" "}
              <span className="shimmer-text">Control Center</span>
            </h2>
            <p className="text-slate-400 text-lg max-w-2xl mx-auto">
              Monitor compliance, analyze violation trends, and manage safety alerts through our comprehensive dashboard.
            </p>
          </div>

          <div className="bg-slate-900/60 backdrop-blur-xl border border-white/10 rounded-2xl shadow-2xl overflow-hidden max-w-5xl mx-auto animate-on-scroll opacity-0 translate-y-10 transition-all duration-1000">
            {/* Browser bar */}
            <div className="bg-slate-950/80 px-4 py-3 flex items-center gap-2 border-b border-white/[0.06]">
              <div className="flex gap-1.5">
                <span className="w-3 h-3 rounded-full bg-red-500/80" />
                <span className="w-3 h-3 rounded-full bg-yellow-500/80" />
                <span className="w-3 h-3 rounded-full bg-green-500/80" />
              </div>
              <div className="bg-slate-900/60 text-slate-500 text-xs px-4 py-1.5 rounded-lg w-72 mx-auto text-center border border-white/[0.05] truncate">
                https://safevision.ai/dashboard
              </div>
            </div>

            {/* Dashboard UI */}
            <div className="bg-slate-950/40 p-6 grid md:grid-cols-[160px_1fr] gap-6 text-left">
              <div className="hidden md:flex flex-col gap-4 border-r border-white/[0.06] pr-4 text-xs">
                <div className="font-bold text-slate-400 tracking-wider mb-2">MONITOR</div>
                <div className="flex items-center gap-2 text-white font-semibold">
                  <span className="w-2 h-2 rounded bg-blue-500" /> Dashboard
                </div>
                {["Image Detection", "Video Detection", "Violations"].map((l) => (
                  <div key={l} className="flex items-center gap-2 text-slate-500">
                    <span className="w-2 h-2 rounded bg-slate-700" /> {l}
                  </div>
                ))}
              </div>

              <div className="space-y-5">
                <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
                  {MOCK_CARDS.map((card) => (
                    <div key={card.label} className={`${card.bg} border ${card.border} p-3 rounded-xl`}>
                      <span className="text-[10px] text-slate-400 font-bold uppercase">{card.label}</span>
                      <div className={`text-xl font-bold ${card.tc} mt-1 flex items-center justify-between`}>
                        {card.val}
                        {card.ping && <span className="w-2 h-2 bg-green-400 rounded-full animate-ping" />}
                      </div>
                    </div>
                  ))}
                </div>

                <div className="bg-slate-900/50 border border-white/[0.06] p-4 rounded-xl">
                  <div className="flex justify-between items-center mb-3">
                    <span className="text-xs font-bold text-slate-300">Compliance Rate over Week</span>
                    <span className="text-[10px] text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded font-semibold">99.99% Target</span>
                  </div>
                  <div className="h-28 flex items-end gap-2 px-1">
                    {[60, 75, 55, 80, 90].map((h, i) => (
                      <div key={i} className="w-full rounded-t bg-slate-800 flex flex-col justify-end" style={{ height: `${h}%` }}>
                        <div className="bg-gradient-to-t from-blue-600 to-blue-400 rounded-t w-full" style={{ height: `${h * 0.85}%` }} />
                      </div>
                    ))}
                  </div>
                  <div className="flex justify-between text-[9px] text-slate-500 mt-2 px-1">
                    {["Mon", "Tue", "Wed", "Thu", "Fri"].map((d) => <span key={d}>{d}</span>)}
                  </div>
                </div>

                <div className="bg-red-500/10 border border-red-500/30 p-3 rounded-lg flex items-center justify-between text-xs">
                  <div className="flex items-center gap-2 text-red-400">
                    <span className="w-2 h-2 bg-red-500 rounded-full animate-ping" />
                    <strong>Alert:</strong> Helmet Missing violation detected at Gate 3.
                  </div>
                  <span className="text-[10px] text-slate-500">Just now</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── How It Works ── */}
      <section id="how-it-works" ref={pathRef} className="relative z-10 py-24">
        <div className="max-w-7xl mx-auto px-6">
          <div className="text-center mb-16 animate-on-scroll opacity-0 translate-y-10 transition-all duration-700">
            <h2 className="text-4xl md:text-5xl font-bold text-white mb-4">
              From camera to{" "}
              <span className="text-emerald-400">compliance report</span>
              <br />in under 1 second
            </h2>
            <p className="text-slate-400 text-lg">Four simple steps from raw footage to actionable safety insights.</p>
          </div>

          {/* Animated connecting line */}
          <div className="hidden md:block px-[10%] mb-[-44px] relative z-10">
            <div
              className="h-[1px] bg-gradient-to-r from-transparent via-blue-400/50 to-transparent"
              style={{ width: pathVisible ? "100%" : "0%", transition: "width 1.4s ease-in-out 0.2s" }}
            />
          </div>

          <div className="grid md:grid-cols-4 gap-6">
            <StepCard num="01" icon={<FaCloudUploadAlt />} title="Upload / Capture"   desc="Upload image or video from site, or connect live CCTV camera feeds directly."         color="blue"    delay={0}   />
            <StepCard num="02" icon={<FaMicrochip />}      title="AI Detection"        desc="YOLOv8 model detects PPE compliance — helmets, vests, and all safety gear."            color="emerald" delay={100} />
            <StepCard num="03" icon={<FaExclamationTriangle />} title="Violation Analysis" desc="System identifies violations, calculates confidence scores, and triggers alerts." color="red"     delay={200} />
            <StepCard num="04" icon={<FaFileExport />}     title="Export & Report"     desc="View analytics, compliance certificates, and export full CSV audit data."              color="yellow"  delay={300} />
          </div>
        </div>
      </section>

      {/* ── CTA Section ── */}
      <section className="relative z-10 py-28 text-center">
        <div className="animate-on-scroll opacity-0 translate-y-10 transition-all duration-700 max-w-2xl mx-auto px-6">
          <p className="text-blue-400 font-bold tracking-wider uppercase text-sm mb-4">Get Started Today</p>
          <h2 className="text-4xl md:text-5xl font-bold text-white mb-6">
            Ready to make your site{" "}
            <span className="shimmer-text">safer?</span>
          </h2>
          <p className="text-slate-400 text-lg mb-10">
            Join thousands of safety managers using SafeVision AI to protect their workers in real-time.
          </p>
          <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
            <MagneticButton
              to="/dashboard"
              className="flex items-center gap-2 bg-blue-600 hover:bg-blue-500 text-white px-8 py-4 rounded-xl font-bold text-lg transition-colors shadow-[0_0_35px_rgba(37,99,235,0.6),0_0_70px_rgba(37,99,235,0.2)]"
            >
              Launch Dashboard <FaArrowRight />
            </MagneticButton>
            <MagneticButton
              to="/about"
              className="flex items-center gap-2 text-slate-300 hover:text-white border border-white/10 hover:border-white/25 px-8 py-4 rounded-xl font-medium transition-all backdrop-blur-sm"
            >
              Learn More
            </MagneticButton>
          </div>
        </div>
      </section>

      {/* ── Footer ── */}
      <footer className="relative z-10 border-t border-white/[0.06] py-8 text-center text-slate-500 text-sm">
        <p>&copy; 2026 SafeVision AI. All rights reserved.</p>
      </footer>
    </div>
  );
}

export default Landing;
