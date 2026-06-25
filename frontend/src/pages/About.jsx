import { FaShieldAlt, FaBolt, FaHardHat, FaVest, FaBell, FaChartBar, FaServer, FaReact, FaPython } from "react-icons/fa";
import { SiYolo } from "react-icons/si";

const TECH_STACK = [
  { icon: <FaReact  className="text-2xl text-cyan-400"   />, name: "React 19",      desc: "Frontend UI framework"        },
  { icon: <FaPython className="text-2xl text-yellow-400" />, name: "FastAPI",        desc: "Python backend API"           },
  { icon: <SiYolo   className="text-2xl text-emerald-400"/>, name: "YOLOv8",         desc: "AI detection model"           },
  { icon: <FaServer className="text-2xl text-purple-400" />, name: "SQLite + ORM",   desc: "Violation data storage"       },
  { icon: <FaChartBar className="text-2xl text-blue-400" />, name: "Recharts",       desc: "Analytics visualizations"     },
];

const CAPABILITIES = [
  { icon: <FaHardHat />, label: "Helmet Detection",    desc: "Identifies workers not wearing safety helmets in real-time.",          color: "text-blue-400    bg-blue-500/10    border-blue-500/20"    },
  { icon: <FaVest />,    label: "Vest Detection",       desc: "Detects missing safety vests across all workers simultaneously.",      color: "text-emerald-400 bg-emerald-500/10 border-emerald-500/20" },
  { icon: <FaBell />,    label: "Instant Alerts",       desc: "Triggers real-time alerts the moment a PPE violation is detected.",    color: "text-red-400     bg-red-500/10     border-red-500/20"     },
  { icon: <FaChartBar />,label: "Analytics",            desc: "Tracks trends over time with daily and weekly violation breakdowns.",  color: "text-purple-400  bg-purple-500/10  border-purple-500/20"  },
  { icon: <FaBolt />,    label: "Live CCTV",            desc: "Processes live webcam and CCTV streams for continuous monitoring.",   color: "text-yellow-400  bg-yellow-500/10  border-yellow-500/20"  },
  { icon: <FaServer />,  label: "CSV Export",           desc: "Export full violation logs and compliance certificates as CSV.",       color: "text-cyan-400    bg-cyan-500/10    border-cyan-500/20"    },
];

function About() {
  return (
    <div className="space-y-8 max-w-5xl">

      {/* Hero block */}
      <div className="bg-white/[0.03] backdrop-blur-sm border border-white/[0.08] rounded-2xl p-8">
        <div className="flex items-center gap-4 mb-6">
          <div className="w-14 h-14 bg-gradient-to-br from-blue-500 to-cyan-400 rounded-2xl flex items-center justify-center shadow-lg shadow-blue-500/20">
            <FaShieldAlt className="text-2xl text-white" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-white">SafeVision AI</h1>
            <p className="text-slate-400 text-sm">AI-Powered PPE Safety Monitoring System</p>
          </div>
        </div>

        <p className="text-slate-300 leading-relaxed text-base">
          SafeVision AI is an intelligent workplace safety platform that uses deep learning and computer vision
          to automatically detect Personal Protective Equipment (PPE) violations on construction sites and
          industrial facilities. The system analyzes images and video streams in real-time to identify workers
          missing helmets or safety vests, instantly logging violations and alerting safety managers.
        </p>
      </div>

      {/* Capabilities */}
      <div>
        <p className="text-xs font-bold text-slate-500 uppercase tracking-widest mb-4">What It Does</p>
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
          {CAPABILITIES.map((c) => {
            const [text, bg, border] = c.color.trim().split(/\s+/);
            return (
              <div key={c.label} className={`${bg} border ${border} rounded-xl p-5`}>
                <div className={`text-xl mb-3 ${text}`}>{c.icon}</div>
                <h3 className="font-bold text-white text-sm mb-1">{c.label}</h3>
                <p className="text-slate-400 text-xs leading-relaxed">{c.desc}</p>
              </div>
            );
          })}
        </div>
      </div>

      {/* Tech stack */}
      <div>
        <p className="text-xs font-bold text-slate-500 uppercase tracking-widest mb-4">Technology Stack</p>
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4">
          {TECH_STACK.map((t) => (
            <div key={t.name} className="bg-white/[0.03] border border-white/[0.08] rounded-xl p-4 text-center">
              <div className="flex justify-center mb-2">{t.icon}</div>
              <p className="text-white text-sm font-bold">{t.name}</p>
              <p className="text-slate-500 text-[11px] mt-1">{t.desc}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Footer */}
      <div className="bg-white/[0.03] border border-white/[0.08] rounded-2xl px-8 py-6 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <p className="text-white font-semibold text-sm">SafeVision AI &copy; 2026</p>
          <p className="text-slate-500 text-xs mt-0.5">Built for workplace safety, powered by AI.</p>
        </div>
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs font-semibold w-max">
          <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
          System Active
        </div>
      </div>
    </div>
  );
}

export default About;
