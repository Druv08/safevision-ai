import { Link } from "react-router-dom";
import {
  LuArrowRight, LuImage, LuFilm, LuCctv, LuShieldCheck, LuClipboardList, LuChartColumn,
  LuScanLine, LuUserCheck, LuDatabase, LuHardHat, LuShirt, LuCircleCheck, LuCircleMinus, LuSun, LuMoon,
} from "react-icons/lu";
import { useTheme } from "../context/ThemeContext";
import { Logo, StatusBadge } from "../components/ui";

const FACTS = [
  ["3 models", "per frame"],
  ["Image · video · camera", "inputs"],
  ["Evidence", "for every violation"],
  ["Audit log", "for every action"],
];

const CAPABILITIES = [
  { icon: LuImage, title: "Image detection", text: "Upload a site photo and get per-worker results with bounding boxes and confidence scores in seconds." },
  { icon: LuFilm, title: "Video analysis", text: "Every frame of recorded footage is checked. Violations are logged with their timestamp so you can jump straight to the moment." },
  { icon: LuCctv, title: "Live camera monitoring", text: "Point a camera connected to the browser at the work area and check it continuously, frame by frame or in short clips." },
  { icon: LuShieldCheck, title: "PPE compliance checks", text: "Missing PPE only counts when it belongs to a detected person. A hard hat carried in the hand is still a violation." },
  { icon: LuClipboardList, title: "Violation tracking", text: "A review queue with evidence screenshots, filters, notes and a new → acknowledged → closed workflow. Export to CSV." },
  { icon: LuChartColumn, title: "Analytics", text: "See violation trends by day, type, source and review status, alongside live model and system health." },
];

const STEPS = [
  { icon: LuScanLine, title: "Capture", text: "Upload an image or video, or start a live camera session." },
  { icon: LuShieldCheck, title: "Detect", text: "YOLOv8 models find people, hard hats and high-visibility vests in every frame." },
  { icon: LuUserCheck, title: "Verify", text: "Rules attribute PPE to each worker, so a vest on the floor doesn't count as worn." },
  { icon: LuDatabase, title: "Record & review", text: "Violations are stored with a screenshot for your safety team to review and close." },
];

const FAQ = [
  ["Which PPE does SafeVisionAI detect?", "Hard hats (including whether they are actually worn on the head) and high-visibility vests. Gloves, goggles, boots and harnesses are not detected by the current models."],
  ["Does it work with CCTV or RTSP cameras?", "Yes. Add RTSP cameras on the Cameras page; the server reads them continuously, reconnects when a stream drops, and applies per-zone rules (hard hat, vest, both, none, or no entry). The webcam page is a browser demo."],
  ["Where are images and violations stored?", "In your own Supabase project: violation records in Postgres with row-level security, and evidence screenshots in a private storage bucket, shown only through links that expire after a few minutes."],
  ["Who can change or delete records?", "There are two roles. Viewers can review and export. Admins can also acknowledge, close and delete violations. Every evidence view, export, status change and deletion is written to an append-only audit log."],
  ["How accurate is it?", "It depends on camera angle, distance, lighting and occlusion. Treat each violation as a lead to review, not a verdict. Every record keeps the frame it came from so a person can confirm it."],
];

function Landing() {
  const { theme, toggleTheme } = useTheme();
  const isDark = theme === "dark";

  return (
    <div className="min-h-screen bg-canvas text-fg overflow-x-hidden">
      {/* Nav */}
      <header className="sticky top-0 z-30 border-b border-line bg-canvas/80 backdrop-blur">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 h-16 flex items-center gap-6">
          <Link to="/" aria-label="SafeVisionAI home" className="rounded-md"><Logo /></Link>
          <nav aria-label="Sections" className="hidden md:flex items-center gap-6 text-sm text-muted">
            <a href="#capabilities" className="hover:text-fg">Capabilities</a>
            <a href="#how-it-works" className="hover:text-fg">How it works</a>
            <a href="#faq" className="hover:text-fg">FAQ</a>
          </nav>
          <div className="ml-auto flex items-center gap-2">
            <button onClick={toggleTheme} className="btn btn-ghost btn-icon" aria-label={isDark ? "Switch to light theme" : "Switch to dark theme"}>
              {isDark ? <LuSun /> : <LuMoon />}
            </button>
            <Link to="/dashboard" className="btn btn-primary">Open dashboard</Link>
          </div>
        </div>
      </header>

      <main>
        {/* Hero */}
        <section className="relative">
          <div
            className="absolute inset-0 -z-0 pointer-events-none"
            aria-hidden="true"
            style={{
              background: "radial-gradient(60% 50% at 50% 0%, color-mix(in srgb, var(--primary) 14%, transparent), transparent 70%)",
            }}
          />
          <div
            className="absolute inset-0 pointer-events-none opacity-60"
            aria-hidden="true"
            style={{
              backgroundImage: "linear-gradient(var(--line) 1px, transparent 1px), linear-gradient(90deg, var(--line) 1px, transparent 1px)",
              backgroundSize: "56px 56px",
              maskImage: "radial-gradient(70% 60% at 50% 20%, #000 10%, transparent 70%)",
              WebkitMaskImage: "radial-gradient(70% 60% at 50% 20%, #000 10%, transparent 70%)",
            }}
          />
          <div className="relative max-w-6xl mx-auto px-4 sm:px-6 pt-16 sm:pt-24 pb-12 text-center">
            <p className="animate-fade-up inline-flex items-center gap-2 rounded-full border border-line bg-surface/70 px-3 py-1 text-xs font-medium text-muted">
              <span className="w-1.5 h-1.5 rounded-full bg-primary" aria-hidden="true" />
              PPE compliance monitoring for industrial sites
            </p>
            <h1 className="animate-fade-up mt-6 text-4xl sm:text-6xl font-semibold tracking-tight leading-[1.05] max-w-4xl mx-auto" style={{ animationDelay: "60ms" }}>
              AI-Powered PPE Compliance.
              <span className="block text-primary">In Real Time.</span>
            </h1>
            <p className="animate-fade-up mt-6 text-base sm:text-lg text-muted max-w-2xl mx-auto leading-relaxed" style={{ animationDelay: "120ms" }}>
              Detect missing personal protective equipment, identify workplace safety violations, and monitor compliance across images, videos and live camera feeds.
            </p>
            <div className="animate-fade-up mt-8 flex flex-col sm:flex-row items-center justify-center gap-3" style={{ animationDelay: "180ms" }}>
              <Link to="/dashboard" className="btn btn-primary btn-lg w-full sm:w-auto">Open dashboard <LuArrowRight /></Link>
              <a href="#capabilities" className="btn btn-secondary btn-lg w-full sm:w-auto">Explore capabilities</a>
            </div>
            <dl className="animate-fade-up mt-12 grid grid-cols-2 md:grid-cols-4 gap-px rounded-xl overflow-hidden border border-line bg-line max-w-3xl mx-auto" style={{ animationDelay: "240ms" }}>
              {FACTS.map(([v, l]) => (
                <div key={l} className="bg-surface px-4 py-4">
                  <dt className="sr-only">{l}</dt>
                  <dd className="text-sm font-semibold">{v}</dd>
                  <dd className="text-xs text-muted mt-0.5">{l}</dd>
                </div>
              ))}
            </dl>
          </div>

          {/* Product preview: a real screenshot of the dashboard */}
          <div className="relative max-w-6xl mx-auto px-4 sm:px-6 pb-20">
            <figure className="rounded-2xl border border-line bg-surface p-2 shadow-2xl shadow-black/30">
              <div className="flex items-center gap-1.5 px-2 pb-2" aria-hidden="true">
                <span className="w-2.5 h-2.5 rounded-full bg-line-strong" />
                <span className="w-2.5 h-2.5 rounded-full bg-line-strong" />
                <span className="w-2.5 h-2.5 rounded-full bg-line-strong" />
              </div>
              <img
                src="/product-dashboard.jpg"
                width="1440"
                height="900"
                alt="The SafeVisionAI dashboard: violation counts, a violations-over-time chart, breakdowns by type, source and review status, system health and recent violations."
                className="w-full h-auto rounded-xl border border-line"
              />
              <figcaption className="sr-only">Screenshot of the SafeVisionAI dashboard</figcaption>
            </figure>
          </div>
        </section>

        {/* Capabilities */}
        <section id="capabilities" className="border-t border-line py-20 sm:py-24 scroll-mt-16">
          <div className="max-w-6xl mx-auto px-4 sm:px-6">
            <SectionIntro eyebrow="Capabilities" title="Everything a safety team needs to act on PPE gaps">
              From a single photo to a live camera, every finding ends up in one reviewable log.
            </SectionIntro>
            <div className="mt-12 grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {CAPABILITIES.map(({ icon: Icon, title, text }) => (
                <article key={title} className="card p-6 transition-colors hover:border-line-strong">
                  <div className="w-10 h-10 rounded-lg bg-primary/10 text-primary flex items-center justify-center text-lg">
                    <Icon aria-hidden="true" />
                  </div>
                  <h3 className="mt-4 font-semibold">{title}</h3>
                  <p className="mt-2 text-sm text-muted leading-relaxed">{text}</p>
                </article>
              ))}
            </div>
          </div>
        </section>

        {/* How it works */}
        <section id="how-it-works" className="border-t border-line py-20 sm:py-24 bg-sidebar scroll-mt-16">
          <div className="max-w-6xl mx-auto px-4 sm:px-6">
            <SectionIntro eyebrow="How it works" title="From frame to reviewed incident in four steps" />
            <ol className="mt-12 grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
              {STEPS.map(({ icon: Icon, title, text }, i) => (
                <li key={title} className="relative card p-6">
                  <div className="flex items-center justify-between">
                    <Icon className="text-primary text-xl" aria-hidden="true" />
                    <span className="text-xs font-mono text-subtle">0{i + 1}</span>
                  </div>
                  <h3 className="mt-4 font-semibold">{title}</h3>
                  <p className="mt-2 text-sm text-muted leading-relaxed">{text}</p>
                </li>
              ))}
            </ol>
          </div>
        </section>

        {/* Coverage + workflow */}
        <section className="border-t border-line py-20 sm:py-24">
          <div className="max-w-6xl mx-auto px-4 sm:px-6 grid lg:grid-cols-2 gap-6">
            <div className="card p-6 sm:p-8">
              <p className="eyebrow">PPE coverage</p>
              <h2 className="mt-3 text-2xl font-semibold tracking-tight">What the models check today</h2>
              <ul className="mt-6 space-y-4">
                {[
                  [LuHardHat, "Hard hats", "Detected and checked for being worn on the head", true],
                  [LuShirt, "High-visibility vests", "Detected and matched to each worker", true],
                  [null, "Gloves, goggles, boots, harnesses", "Not covered by the current models", false],
                ].map(([Icon, label, text, ok]) => (
                  <li key={label} className="flex gap-3">
                    {ok ? <LuCircleCheck className="text-primary mt-0.5 flex-shrink-0" aria-label="Supported" /> : <LuCircleMinus className="text-subtle mt-0.5 flex-shrink-0" aria-label="Not supported" />}
                    <div>
                      <p className="font-medium flex items-center gap-2">{Icon && <Icon className="text-muted" aria-hidden="true" />}{label}</p>
                      <p className="text-sm text-muted">{text}</p>
                    </div>
                  </li>
                ))}
              </ul>
            </div>
            <div className="card p-6 sm:p-8">
              <p className="eyebrow">Review workflow</p>
              <h2 className="mt-3 text-2xl font-semibold tracking-tight">Every violation has an owner and an outcome</h2>
              <p className="mt-3 text-sm text-muted leading-relaxed">
                New violations wait in a review queue with their evidence frame. Admins acknowledge them, add a note and close them. Viewers can follow along and export the log.
              </p>
              <div className="mt-6 flex flex-wrap items-center gap-2">
                <StatusBadge status="new" /><LuArrowRight className="text-subtle" aria-hidden="true" />
                <StatusBadge status="acknowledged" /><LuArrowRight className="text-subtle" aria-hidden="true" />
                <StatusBadge status="closed" />
              </div>
              <ul className="mt-6 grid grid-cols-2 gap-3 text-sm">
                {["Evidence screenshots", "Notes on status changes", "CSV export", "Append-only audit log"].map((t) => (
                  <li key={t} className="flex items-center gap-2 text-muted"><LuCircleCheck className="text-primary flex-shrink-0" aria-hidden="true" />{t}</li>
                ))}
              </ul>
            </div>
          </div>
        </section>

        {/* FAQ */}
        <section id="faq" className="border-t border-line py-20 sm:py-24 bg-sidebar scroll-mt-16">
          <div className="max-w-3xl mx-auto px-4 sm:px-6">
            <SectionIntro eyebrow="FAQ" title="Questions safety teams ask" />
            <div className="mt-10 divide-y divide-line border-y border-line">
              {FAQ.map(([q, a]) => (
                <details key={q} className="group py-4">
                  <summary className="flex items-center justify-between gap-4 cursor-pointer list-none font-medium rounded-md [&::-webkit-details-marker]:hidden">
                    {q}
                    <span className="text-muted text-xl leading-none transition-transform group-open:rotate-45" aria-hidden="true">+</span>
                  </summary>
                  <p className="mt-3 text-sm text-muted leading-relaxed">{a}</p>
                </details>
              ))}
            </div>
          </div>
        </section>

        {/* Final CTA */}
        <section className="border-t border-line py-20 sm:py-24">
          <div className="max-w-3xl mx-auto px-4 sm:px-6 text-center">
            <h2 className="text-3xl sm:text-4xl font-semibold tracking-tight">See your site's PPE compliance today</h2>
            <p className="mt-4 text-muted">Upload a photo or a video, or start a live camera, and review the results in minutes.</p>
            <div className="mt-8 flex flex-col sm:flex-row justify-center gap-3">
              <Link to="/dashboard" className="btn btn-primary btn-lg">Open dashboard <LuArrowRight /></Link>
              <Link to="/image-detection" className="btn btn-secondary btn-lg">Try image detection</Link>
            </div>
          </div>
        </section>
      </main>

      <footer className="border-t border-line">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 py-10 flex flex-col md:flex-row gap-6 md:items-center md:justify-between">
          <div>
            <Logo />
            <p className="mt-2 text-sm text-muted">PPE compliance and workplace safety monitoring.</p>
          </div>
          <nav aria-label="Footer" className="flex flex-wrap gap-x-6 gap-y-2 text-sm text-muted">
            <Link to="/dashboard" className="hover:text-fg">Dashboard</Link>
            <Link to="/live" className="hover:text-fg">Live monitoring</Link>
            <Link to="/violations" className="hover:text-fg">Violations</Link>
            <Link to="/about" className="hover:text-fg">System status</Link>
          </nav>
          <p className="text-xs text-subtle">© {new Date().getFullYear()} SafeVisionAI</p>
        </div>
      </footer>
    </div>
  );
}

function SectionIntro({ eyebrow, title, children }) {
  return (
    <div className="max-w-2xl">
      <p className="eyebrow">{eyebrow}</p>
      <h2 className="mt-3 text-3xl sm:text-4xl font-semibold tracking-tight">{title}</h2>
      {children && <p className="mt-4 text-muted leading-relaxed">{children}</p>}
    </div>
  );
}

export default Landing;
