import { useEffect } from "react";
import { Link } from "react-router-dom";
import { 
  FaShieldAlt, 
  FaArrowRight, 
  FaChartBar, 
  FaBolt, 
  FaCheckCircle, 
  FaCloud, 
  FaHardHat, 
  FaUserShield, 
  FaBell, 
  FaVideo, 
  FaChartPie, 
  FaCloudUploadAlt,
  FaMicrochip,
  FaExclamationTriangle,
  FaFileExport
} from "react-icons/fa";

import heroImage from "../assets/hero_construction.png";

function Landing() {
  useEffect(() => {
    const observerOptions = {
      root: null,
      rootMargin: "0px",
      threshold: 0.1,
    };

    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.remove("opacity-0", "translate-y-10", "-translate-x-10", "translate-x-10");
          entry.target.classList.add("opacity-100", "translate-y-0", "translate-x-0");
          observer.unobserve(entry.target);
        }
      });
    }, observerOptions);

    const animatedElements = document.querySelectorAll(".animate-on-scroll");
    animatedElements.forEach((el) => observer.observe(el));

    return () => observer.disconnect();
  }, []);

  return (
    <div className="min-h-screen bg-[#0b1120] text-slate-200 font-sans selection:bg-blue-500/30">
      {/* Background Grid Pattern */}
      <div className="fixed inset-0 z-0 opacity-20 pointer-events-none" style={{ backgroundImage: 'radial-gradient(circle at 1px 1px, rgba(255, 255, 255, 0.15) 1px, transparent 0)', backgroundSize: '40px 40px' }}></div>

      {/* Navbar */}
      <nav className="relative z-10 flex items-center justify-between px-6 py-6 max-w-7xl mx-auto">
        <div className="flex items-center gap-3">
          <div className="bg-gradient-to-br from-blue-500 to-cyan-400 p-2.5 rounded-xl">
            <FaShieldAlt className="text-white text-xl" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-white tracking-tight">SafeVision<span className="text-blue-400">AI</span></h1>
            <p className="text-[10px] text-slate-400 uppercase tracking-widest font-semibold">PPE Monitoring</p>
          </div>
        </div>

        <div className="hidden md:flex items-center gap-8 text-sm font-medium text-slate-300">
          <a href="#features" className="hover:text-white transition">Features</a>
          <a href="#how-it-works" className="hover:text-white transition">How It Works</a>
          <Link to="/dashboard" className="hover:text-white transition">Dashboard</Link>
          <Link to="/about" className="hover:text-white transition">About</Link>
        </div>

        <div className="flex items-center gap-6 text-sm font-medium">
          <Link to="/dashboard" className="text-slate-300 hover:text-white transition">Sign In</Link>
          <Link to="/dashboard" className="bg-blue-600 hover:bg-blue-500 text-white px-5 py-2.5 rounded-lg shadow-[0_0_15px_rgba(37,99,235,0.5)] transition-all">
            Get Started
          </Link>
        </div>
      </nav>

      {/* Hero Section */}
      <main className="relative z-10 max-w-7xl mx-auto px-6 pt-20 pb-32 grid lg:grid-cols-2 gap-12 items-center">
        
        {/* Left Content */}
        <div>
          <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs font-semibold uppercase tracking-wider mb-8">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
            AI-Powered Safety Monitoring
          </div>
          
          <h1 className="text-5xl lg:text-7xl font-extrabold text-white leading-[1.1] mb-6">
            AI Powered <br />
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-emerald-400">PPE Safety</span> <br />
            Monitoring System
          </h1>
          
          <p className="text-lg text-slate-400 mb-10 max-w-xl leading-relaxed">
            Real-time detection of safety violations using advanced computer vision and deep learning. Protect your workers before incidents happen.
          </p>

          <div className="flex flex-wrap items-center gap-4 mb-12">
            <Link to="/dashboard" className="flex items-center gap-2 bg-blue-600 hover:bg-blue-500 text-white px-6 py-3.5 rounded-xl font-semibold shadow-lg shadow-blue-500/25 transition-all">
              Get Started <FaArrowRight />
            </Link>
            <Link to="/dashboard" className="flex items-center gap-2 bg-slate-800/50 hover:bg-slate-800 border border-slate-700 text-white px-6 py-3.5 rounded-xl font-semibold backdrop-blur-sm transition-all">
              View Dashboard <FaChartBar />
            </Link>
          </div>

          <div className="flex items-center gap-8 border-t border-slate-800 pt-8">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-full bg-blue-500/10 border border-blue-500/20 flex items-center justify-center text-blue-400">
                <FaBolt />
              </div>
              <div>
                <p className="text-sm font-bold text-white">Real-time Detection</p>
                <p className="text-xs text-slate-400">Instant violation alerts</p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-full bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400">
                <FaCheckCircle />
              </div>
              <div>
                <p className="text-sm font-bold text-white">High Accuracy</p>
                <p className="text-xs text-slate-400">YOLOv8 AI Model</p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-full bg-purple-500/10 border border-purple-500/20 flex items-center justify-center text-purple-400">
                <FaCloud />
              </div>
              <div>
                <p className="text-sm font-bold text-white">Cloud Ready</p>
                <p className="text-xs text-slate-400">Export & Monitor Data</p>
              </div>
            </div>
          </div>
        </div>

        {/* Right Content - Visual Mockup */}
        <div className="relative">
          <div className="absolute inset-0 bg-gradient-to-tr from-blue-500/20 to-emerald-500/20 blur-3xl -z-10 rounded-full"></div>
          
          <div className="relative bg-slate-900 border border-slate-700/50 rounded-2xl shadow-2xl overflow-hidden group">
            {/* Mockup Image/Scene */}
            <div className="aspect-video bg-slate-800 relative">
              <img src={heroImage} alt="Construction Site" className="w-full h-full object-cover opacity-80" />
              
              {/* Bounding Boxes */}
              <div className="absolute top-[20%] left-[30%] w-32 h-48 border-2 border-emerald-500 bg-emerald-500/10 rounded">
                <div className="absolute -top-6 left-0 bg-emerald-500 text-white text-[10px] font-bold px-2 py-0.5 rounded-sm">Helmet: 99.99%</div>
                <div className="absolute -bottom-6 left-0 bg-emerald-500 text-white text-[10px] font-bold px-2 py-0.5 rounded-sm">Safety Vest: 99.99%</div>
              </div>

              <div className="absolute top-[15%] right-[20%] w-28 h-44 border-2 border-red-500 bg-red-500/10 rounded">
                <div className="absolute -top-6 left-0 bg-red-500 text-white text-[10px] font-bold px-2 py-0.5 rounded-sm">No Helmet</div>
              </div>

              {/* Status overlays */}
              <div className="absolute top-4 left-4 bg-black/60 backdrop-blur-md border border-white/10 px-3 py-1.5 rounded-lg flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse"></span>
                <span className="text-xs font-bold text-white">LIVE</span>
              </div>
            </div>

            {/* Floating UI Elements */}
            <div className="absolute -bottom-6 -left-6 bg-slate-800/90 backdrop-blur-xl border border-slate-700 p-4 rounded-xl shadow-xl flex items-center gap-4 group-hover:-translate-y-2 transition-transform duration-500">
              <div className="w-10 h-10 rounded-lg bg-red-500/10 flex items-center justify-center text-red-500">
                <FaExclamationTriangle />
              </div>
              <div>
                <p className="text-[10px] text-slate-400 font-bold uppercase">Active Violations</p>
                <p className="text-xl font-bold text-white">3</p>
              </div>
            </div>

            <div className="absolute -top-6 -right-6 bg-slate-800/90 backdrop-blur-xl border border-slate-700 p-4 rounded-xl shadow-xl flex items-center gap-4 group-hover:-translate-y-2 transition-transform duration-500 delay-100">
              <div className="w-10 h-10 rounded-lg bg-emerald-500/10 flex items-center justify-center text-emerald-500">
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

      {/* Features Section */}
      <section id="features" className="relative z-10 py-24 bg-slate-900/50 border-y border-slate-800">
        <div className="max-w-7xl mx-auto px-6">
          <div className="text-center mb-16">
            <p className="text-blue-500 font-bold tracking-wider uppercase text-sm mb-4">Features</p>
            <h2 className="text-4xl md:text-5xl font-bold text-white mb-6">
              Everything you need for <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-emerald-400">workplace safety</span>
            </h2>
            <p className="text-slate-400 text-lg max-w-2xl mx-auto">
              A complete AI safety stack — from real-time detection to compliance reporting — built for construction sites.
            </p>
          </div>

          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
            <FeatureCard 
              icon={<FaHardHat />}
              title="Helmet Detection"
              desc="Detects workers without helmets in real-time using YOLOv8 object detection with 99.99% accuracy."
              stat="99.99%"
              statLabel="Detection accuracy"
              color="blue"
              delayClass="delay-75"
            />
            <FeatureCard 
              icon={<FaUserShield />}
              title="Vest Detection"
              desc="Monitors safety vests and ensures compliance across all workers on site simultaneously."
              stat="<200ms"
              statLabel="Detection latency"
              color="emerald"
              delayClass="delay-200"
            />
            <FeatureCard 
              icon={<FaBell />}
              title="Real-time Alerts"
              desc="Instant push notifications and SMS alerts to safety managers when violations are detected."
              stat="0.2s"
              statLabel="Alert response time"
              color="red"
              delayClass="delay-300"
            />
            <FeatureCard 
              icon={<FaVideo />}
              title="Video Monitoring"
              desc="Analyze live CCTV footage from multiple cameras for continuous 24/7 safety surveillance."
              stat="32+"
              statLabel="Cameras per site"
              color="yellow"
              delayClass="delay-75"
            />
            <FeatureCard 
              icon={<FaChartPie />}
              title="Analytics Dashboard"
              desc="Get detailed insights, violation trends, compliance reports, and exportable CSV data."
              stat="50+"
              statLabel="Report metrics"
              color="blue"
              delayClass="delay-200"
            />
            <FeatureCard 
              icon={<FaCloud />}
              title="Cloud Export"
              desc="Export violation logs, compliance certificates, and audit trails directly to cloud storage."
              stat="99.99%"
              statLabel="Uptime SLA"
              color="emerald"
              delayClass="delay-300"
            />
          </div>
        </div>
      </section>

      {/* Dashboard Preview Section */}
      <section className="relative z-10 py-24 bg-[#0b1120] border-b border-slate-800">
        <div className="max-w-7xl mx-auto px-6">
          <div className="text-center mb-16 animate-on-scroll opacity-0 translate-y-10 transition-all duration-700">
            <p className="text-blue-500 font-bold tracking-wider uppercase text-sm mb-4">Interactive Platform</p>
            <h2 className="text-4xl md:text-5xl font-bold text-white mb-6">
              Intelligent <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-cyan-400">Control Center</span>
            </h2>
            <p className="text-slate-400 text-lg max-w-2xl mx-auto">
              Monitor compliance, analyze violation trends, and manage safety alerts through our comprehensive dashboard.
            </p>
          </div>

          {/* Browser Mockup */}
          <div className="bg-slate-900 border border-slate-700/50 rounded-2xl shadow-2xl shadow-blue-500/5 overflow-hidden max-w-5xl mx-auto group animate-on-scroll opacity-0 translate-y-10 transition-all duration-1000">
            {/* Browser Header Bar */}
            <div className="bg-slate-950 px-4 py-3 flex items-center gap-2 border-b border-slate-800">
              <div className="flex gap-1.5">
                <span className="w-3 h-3 rounded-full bg-red-500/80"></span>
                <span className="w-3 h-3 rounded-full bg-yellow-500/80"></span>
                <span className="w-3 h-3 rounded-full bg-green-500/80"></span>
              </div>
              <div className="bg-slate-900 text-slate-500 text-xs px-4 py-1.5 rounded-lg w-96 mx-auto text-center border border-slate-800/80 truncate">
                https://safevision.ai/dashboard
              </div>
            </div>

            {/* Dashboard UI mockup inside */}
            <div className="bg-slate-950 p-6 grid md:grid-cols-[180px_1fr] gap-6 text-left">
              {/* Mock Sidebar */}
              <div className="hidden md:flex flex-col gap-4 border-r border-slate-800 pr-4 text-xs">
                <div className="font-bold text-slate-400 tracking-wider mb-2">MONITOR</div>
                <div className="flex items-center gap-2 text-white font-semibold"><span className="w-2 h-2 rounded bg-blue-500"></span> Dashboard</div>
                <div className="flex items-center gap-2 text-slate-500 hover:text-white transition"><span className="w-2 h-2 rounded bg-slate-800"></span> Image Detection</div>
                <div className="flex items-center gap-2 text-slate-500 hover:text-white transition"><span className="w-2 h-2 rounded bg-slate-800"></span> Video Detection</div>
                <div className="flex items-center gap-2 text-slate-500 hover:text-white transition"><span className="w-2 h-2 rounded bg-slate-800"></span> Violations</div>
              </div>

              {/* Mock Main Panel */}
              <div className="space-y-6">
                {/* Upper row - Mini Cards */}
                <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                  <div className="bg-gradient-to-br from-red-500/10 to-red-600/5 border border-red-500/20 p-4 rounded-xl">
                    <span className="text-[10px] text-slate-400 font-bold uppercase">Total Violations</span>
                    <div className="text-2xl font-bold text-red-500 mt-1">284</div>
                  </div>
                  <div className="bg-gradient-to-br from-yellow-500/10 to-yellow-600/5 border border-yellow-500/20 p-4 rounded-xl">
                    <span className="text-[10px] text-slate-400 font-bold uppercase">No Vest Cases</span>
                    <div className="text-2xl font-bold text-yellow-500 mt-1">154</div>
                  </div>
                  <div className="bg-gradient-to-br from-orange-500/10 to-orange-600/5 border border-orange-500/20 p-4 rounded-xl">
                    <span className="text-[10px] text-slate-400 font-bold uppercase">No Helmet Cases</span>
                    <div className="text-2xl font-bold text-orange-500 mt-1">130</div>
                  </div>
                  <div className="bg-gradient-to-br from-green-500/10 to-green-600/5 border border-green-500/20 p-4 rounded-xl flex items-center justify-between">
                    <div>
                      <span className="text-[10px] text-slate-400 font-bold uppercase">System Status</span>
                      <div className="text-sm font-bold text-green-400 mt-1">Active</div>
                    </div>
                    <span className="w-2.5 h-2.5 bg-green-400 rounded-full animate-ping"></span>
                  </div>
                </div>

                {/* Middle Row - Graph Mockup */}
                <div className="bg-slate-900/50 border border-slate-800 p-4 rounded-xl">
                  <div className="flex justify-between items-center mb-4">
                    <span className="text-xs font-bold text-slate-300">Compliance Rate over Week</span>
                    <span className="text-[10px] text-emerald-400 font-semibold bg-emerald-500/10 px-2 py-0.5 rounded">99.99% Target</span>
                  </div>
                  {/* CSS Bar Graph Mockup */}
                  <div className="h-32 flex items-end justify-between pt-4 px-2 gap-2">
                    <div className="w-full bg-slate-800 rounded-t h-[60%] flex flex-col justify-end transition-all duration-700"><div className="bg-blue-500 rounded-t w-full h-[60%]"></div></div>
                    <div className="w-full bg-slate-800 rounded-t h-[75%] flex flex-col justify-end transition-all duration-700"><div className="bg-blue-500 rounded-t w-full h-[70%]"></div></div>
                    <div className="w-full bg-slate-800 rounded-t h-[55%] flex flex-col justify-end transition-all duration-700"><div className="bg-blue-500 rounded-t w-full h-[65%]"></div></div>
                    <div className="w-full bg-slate-800 rounded-t h-[80%] flex flex-col justify-end transition-all duration-700"><div className="bg-blue-500 rounded-t w-full h-[85%]"></div></div>
                    <div className="w-full bg-slate-800 rounded-t h-[90%] flex flex-col justify-end transition-all duration-700"><div className="bg-blue-500 rounded-t w-full h-[90%]"></div></div>
                  </div>
                  <div className="flex justify-between text-[9px] text-slate-500 mt-2 px-1">
                    <span>Mon</span><span>Tue</span><span>Wed</span><span>Thu</span><span>Fri</span>
                  </div>
                </div>

                {/* Lower Row - Live Alert simulation */}
                <div className="bg-red-500/10 border border-red-500/30 p-3 rounded-lg flex items-center justify-between text-xs">
                  <div className="flex items-center gap-2 text-red-400">
                    <span className="w-2 h-2 bg-red-500 rounded-full animate-ping"></span>
                    <strong>⚠️ Alert:</strong> Helmet Missing violation detected at Gate 3.
                  </div>
                  <span className="text-[10px] text-slate-500">Just now</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* How It Works Section */}
      <section id="how-it-works" className="relative z-10 py-24">
        <div className="max-w-7xl mx-auto px-6">
          <div className="text-center mb-16">
            <h2 className="text-4xl md:text-5xl font-bold text-white mb-6">
              From camera to <span className="text-emerald-400">compliance report</span> <br /> in under 1 second
            </h2>
            <p className="text-slate-400 text-lg">Four simple steps from raw footage to actionable safety insights.</p>
          </div>

          <div className="grid md:grid-cols-4 gap-6 relative">
            {/* Connecting Line */}
            <div className="hidden md:block absolute top-12 left-[10%] right-[10%] h-[2px] bg-slate-800 -z-10"></div>

            <StepCard num="01" icon={<FaCloudUploadAlt />} title="Upload / Capture" desc="Upload image or video from site or connect live CCTV camera feeds directly." color="blue" delayClass="delay-75" />
            <StepCard num="02" icon={<FaMicrochip />} title="AI Detection" desc="YOLOv8 model detects PPE compliance — helmets, vests, and other safety gear." color="emerald" delayClass="delay-150" />
            <StepCard num="03" icon={<FaExclamationTriangle />} title="Violation Analysis" desc="System identifies violations, calculates confidence scores, and triggers alerts." color="red" delayClass="delay-200" />
            <StepCard num="04" icon={<FaFileExport />} title="Dashboard & Export" desc="View reports, analytics, compliance certificates, and export CSV data." color="yellow" delayClass="delay-300" />
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="relative z-10 border-t border-slate-800 py-8 text-center text-slate-500 text-sm">
        <p>&copy; 2026 SafeVision AI. All rights reserved.</p>
      </footer>
    </div>
  );
}

function FeatureCard({ icon, title, desc, stat, statLabel, color, delayClass = "" }) {
  const colorMap = {
    blue: "text-blue-400 border-blue-400/20 bg-blue-400/10",
    emerald: "text-emerald-400 border-emerald-400/20 bg-emerald-400/10",
    red: "text-red-400 border-red-400/20 bg-red-400/10",
    yellow: "text-yellow-400 border-yellow-400/20 bg-yellow-400/10",
  };

  return (
    <div className={`animate-on-scroll opacity-0 translate-y-10 transition-all duration-1000 ${delayClass} bg-slate-800/30 border border-slate-700/50 p-8 rounded-2xl hover:bg-slate-800/50 transition duration-300`}>
      <div className={`w-12 h-12 rounded-xl flex items-center justify-center border mb-6 ${colorMap[color]}`}>
        {icon}
      </div>
      <h3 className="text-xl font-bold text-white mb-3">{title}</h3>
      <p className="text-slate-400 mb-8 leading-relaxed">{desc}</p>
      
      <div className="flex items-end gap-3 pt-6 border-t border-slate-700/50">
        <span className={`text-2xl font-bold ${colorMap[color].split(' ')[0]}`}>{stat}</span>
        <span className="text-xs text-slate-500 font-medium mb-1">{statLabel}</span>
      </div>
    </div>
  );
}

function StepCard({ num, icon, title, desc, color, delayClass = "" }) {
  const colorMap = {
    blue: {
      border: "border-blue-500/20 hover:border-blue-500/40",
      glow: "bg-blue-500/10 border-blue-500/30 text-blue-400 shadow-[0_0_20px_rgba(59,130,246,0.35)]",
      num: "text-blue-500 font-extrabold opacity-90"
    },
    emerald: {
      border: "border-emerald-500/20 hover:border-emerald-500/40",
      glow: "bg-emerald-500/10 border-emerald-500/30 text-emerald-400 shadow-[0_0_20px_rgba(16,185,129,0.35)]",
      num: "text-emerald-500 font-extrabold opacity-90"
    },
    red: {
      border: "border-red-500/20 hover:border-red-500/40",
      glow: "bg-red-500/10 border-red-500/30 text-red-400 shadow-[0_0_20px_rgba(239,68,68,0.35)]",
      num: "text-red-500 font-extrabold opacity-90"
    },
    yellow: {
      border: "border-amber-500/20 hover:border-amber-500/40",
      glow: "bg-amber-500/10 border-amber-500/30 text-amber-400 shadow-[0_0_20px_rgba(245,158,11,0.35)]",
      num: "text-amber-500 font-extrabold opacity-90"
    }
  };

  const activeColors = colorMap[color] || colorMap.blue;

  return (
    <div className={`animate-on-scroll opacity-0 translate-y-10 transition-all duration-1000 ${delayClass} bg-slate-900 border ${activeColors.border} p-6 rounded-2xl relative transition-all duration-300 hover:scale-105 shadow-xl`}>
      <span className={`absolute top-6 right-6 text-2xl ${activeColors.num}`}>{num}</span>
      <div className={`w-12 h-12 rounded-xl flex items-center justify-center text-xl mb-6 border ${activeColors.glow}`}>
        {icon}
      </div>
      <h3 className="text-lg font-bold text-white mb-2">{title}</h3>
      <p className="text-sm text-slate-400 leading-relaxed">{desc}</p>
    </div>
  );
}

export default Landing;
