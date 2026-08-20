import React from 'react';
import { ShieldCheck, Radio, Sparkles, FileText, CheckCircle2, AlertCircle } from 'lucide-react';

interface Props {
  jobId?: string;
  jobStatus?: string;
  backendOnline: boolean;
  onLoadPreset: (presetKey: string) => void;
}

export const Navbar: React.FC<Props> = ({
  jobId,
  jobStatus,
  backendOnline,
  onLoadPreset,
}) => {
  return (
    <header className="sticky top-0 z-50">
      {/* Tricolor National Ribbon */}
      <div className="tricolor-strip" />

      <div className="bg-[#090E1A]/90 backdrop-blur-xl border-b border-white/10 px-6 py-3.5">
        <div className="max-w-[1440px] mx-auto flex flex-wrap items-center justify-between gap-4">
          
          {/* Logo & Platform Name */}
          <div className="flex items-center gap-3.5">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-cyan-600 to-blue-600 flex items-center justify-center shadow-lg shadow-cyan-500/25 border border-cyan-400/30">
              <Radio className="w-5 h-5 text-white" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-extrabold text-xl tracking-tight text-white">
                  Vaani<span className="text-cyan-400">Reach</span>
                </span>
                <span className="text-xs px-2 py-0.5 rounded-full bg-cyan-500/15 border border-cyan-400/30 text-cyan-300 font-semibold tracking-wide">
                  IndicGov AI 2.0
                </span>
              </div>
              <p className="text-xs text-slate-400 font-medium">
                Official Circular-to-Multilingual Video Broadcast Pipeline
              </p>
            </div>
          </div>

          {/* Quick Preset Templates */}
          <div className="flex items-center gap-2">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-400 hidden sm:inline flex items-center gap-1">
              <Sparkles className="w-3.5 h-3.5 text-amber-400" /> Presets:
            </span>
            <button
              type="button"
              onClick={() => onLoadPreset('pmkisan')}
              className="px-2.5 py-1 text-xs font-medium rounded-lg bg-slate-800/80 hover:bg-slate-700 text-slate-200 border border-white/10 transition-all"
            >
              🌾 PM-KISAN
            </button>
            <button
              type="button"
              onClick={() => onLoadPreset('dbt_scholarship')}
              className="px-2.5 py-1 text-xs font-medium rounded-lg bg-slate-800/80 hover:bg-slate-700 text-slate-200 border border-white/10 transition-all"
            >
              🎓 DBT Scholarship
            </button>
            <button
              type="button"
              onClick={() => onLoadPreset('soil_health')}
              className="px-2.5 py-1 text-xs font-medium rounded-lg bg-slate-800/80 hover:bg-slate-700 text-slate-200 border border-white/10 transition-all"
            >
              🌱 Soil Health Card
            </button>
          </div>

          {/* Active Job ID & Backend Status */}
          <div className="flex items-center gap-4">
            {jobId && (
              <div className="hidden md:flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-900/90 border border-white/10 text-xs">
                <FileText className="w-3.5 h-3.5 text-cyan-400" />
                <span className="text-slate-400">Job:</span>
                <span className="font-mono font-semibold text-slate-200">{jobId.slice(0, 14)}...</span>
                {jobStatus && (
                  <span className="ml-1 px-2 py-0.5 rounded text-[10px] font-bold uppercase bg-cyan-500/20 text-cyan-300">
                    {jobStatus}
                  </span>
                )}
              </div>
            )}

            {/* Officer Security Badge */}
            <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 text-xs font-semibold">
              <ShieldCheck className="w-4 h-4 text-emerald-400" />
              <span>HITL Review Officer</span>
            </div>

            {/* Backend Health Dot */}
            <div
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-semibold border ${
                backendOnline
                  ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
                  : 'bg-rose-500/10 text-rose-400 border-rose-500/30'
              }`}
              title={backendOnline ? 'Backend service online' : 'Backend offline - start server.py'}
            >
              {backendOnline ? (
                <>
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  <span className="hidden sm:inline">Engine Online</span>
                </>
              ) : (
                <>
                  <AlertCircle className="w-3.5 h-3.5" />
                  <span className="hidden sm:inline">Engine Offline</span>
                </>
              )}
            </div>
          </div>

        </div>
      </div>
    </header>
  );
};
