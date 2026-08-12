import { FaShieldAlt, FaBolt, FaHardHat, FaVest, FaBell, FaChartBar, FaServer, FaReact, FaPython } from "react-icons/fa";
import { SiYolo } from "react-icons/si";

const TECH_STACK = [
  { icon: <FaReact />,    name: "React 19",     desc: "Frontend UI framework"    },
  { icon: <FaPython />,   name: "FastAPI",      desc: "Python backend API"       },
  { icon: <SiYolo />,     name: "YOLOv8",       desc: "AI detection model"       },
  { icon: <FaServer />,   name: "SQLite + ORM", desc: "Violation data storage"   },
  { icon: <FaChartBar />, name: "Recharts",     desc: "Analytics visualizations" },
];

const CAPABILITIES = [
  { icon: <FaHardHat />,  label: "Helmet Detection", desc: "Identifies workers not wearing safety helmets in real-time."         },
  { icon: <FaVest />,     label: "Vest Detection",   desc: "Detects missing safety vests across all workers simultaneously."      },
  { icon: <FaBell />,     label: "Instant Alerts",   desc: "Triggers real-time alerts the moment a PPE violation is detected."    },
  { icon: <FaChartBar />, label: "Analytics",        desc: "Tracks trends over time with daily and weekly violation breakdowns."  },
  { icon: <FaBolt />,     label: "Live CCTV",        desc: "Processes live webcam and CCTV streams for continuous monitoring."    },
  { icon: <FaServer />,   label: "CSV Export",       desc: "Export full violation logs and compliance certificates as CSV."       },
];

function SectionLabel({ children }) {
  return (
    <p className="sv-mono sv-ink-gold text-[9.5px] font-bold uppercase tracking-[0.2em] mb-4">
      {children}
    </p>
  );
}

function About() {
  return (
    <div className="space-y-8 max-w-5xl">

      {/* Hero block */}
      <div className="sv-panel rounded-2xl p-8">
        <div className="flex items-center gap-4 mb-6">
          <div className="sv-logo-tile w-14 h-14 rounded-2xl flex items-center justify-center flex-shrink-0">
            <FaShieldAlt className="sv-ink-gold text-2xl" />
          </div>
          <div>
            <h1 className="sv-fg text-2xl font-extrabold tracking-[-0.01em]">
              SafeVision<span className="sv-ink-gold">AI</span>
            </h1>
            <p className="sv-fg-muted text-sm mt-0.5">AI-Powered PPE Safety Monitoring System</p>
          </div>
        </div>

        <p className="sv-fg-muted leading-relaxed text-[15px]">
          SafeVisionAI is an intelligent workplace safety platform that uses deep learning and computer vision
          to automatically detect Personal Protective Equipment (PPE) violations on construction sites and
          industrial facilities. The system analyzes images and video streams in real-time to identify workers
          missing helmets or safety vests, instantly logging violations and alerting safety managers.
        </p>
      </div>

      {/* Capabilities */}
      <div>
        <SectionLabel>What It Does</SectionLabel>
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
          {CAPABILITIES.map((c) => (
            <div key={c.label} className="sv-panel sv-panel-hover rounded-xl p-5">
              <div className="tone-gold sv-tone sv-tone-ink w-10 h-10 rounded-xl flex items-center justify-center mb-4">
                {c.icon}
              </div>
              <h3 className="sv-fg font-bold text-sm mb-1.5">{c.label}</h3>
              <p className="sv-fg-muted text-xs leading-relaxed">{c.desc}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Tech stack */}
      <div>
        <SectionLabel>Technology Stack</SectionLabel>
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4">
          {TECH_STACK.map((t) => (
            <div key={t.name} className="sv-panel rounded-xl p-4 text-center">
              <div className="sv-ink-gold flex justify-center mb-2.5 text-2xl">{t.icon}</div>
              <p className="sv-fg text-sm font-bold">{t.name}</p>
              <p className="sv-fg-dim text-[11px] mt-1">{t.desc}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Footer */}
      <div className="sv-panel rounded-2xl px-8 py-6 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <p className="sv-fg font-bold text-sm">SafeVisionAI &copy; 2026</p>
          <p className="sv-fg-dim text-xs mt-1">Built for workplace safety, powered by AI.</p>
        </div>
        <div className="tone-ok sv-tone sv-tone-ink sv-mono flex items-center gap-2 px-3 py-1.5 rounded-full text-[10px] font-bold uppercase tracking-[0.14em] w-max">
          <span
            className="sv-tone-dot w-1.5 h-1.5 rounded-full"
            style={{ animation: "sv-blink 1.6s ease-in-out infinite" }}
          />
          System Active
        </div>
      </div>
    </div>
  );
}

export default About;
