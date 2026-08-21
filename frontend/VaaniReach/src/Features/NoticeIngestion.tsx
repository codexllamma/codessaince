import React, { useState } from 'react';
import { FileText, Globe, Mic2, Sparkles, ArrowRight, Loader2, Info } from 'lucide-react';

export interface IngestConfig {
  rawText: string;
  sourceFileName: string;
  targetLangs: string[];
  voiceId: string;
  speedMod: string;
  primaryLang?: string;
}

interface Props {
  initialConfig: IngestConfig;
  onSubmit: (config: IngestConfig) => Promise<void>;
  loading: boolean;
}

const ALL_LANGUAGES = [
  { code: 'en', label: 'English', script: 'Latin', flag: '🇬🇧' },
  { code: 'hi', label: 'हिंदी (Hindi)', script: 'Devanagari', flag: '🇮🇳' },
  { code: 'ta', label: 'தமிழ் (Tamil)', script: 'Tamil', flag: '🇮🇳' },
  { code: 'te', label: 'తెలుగు (Telugu)', script: 'Telugu', flag: '🇮🇳' },
  { code: 'bn', label: 'বাংলা (Bengali)', script: 'Bengali', flag: '🇮🇳' },
  { code: 'mr', label: 'मराठी (Marathi)', script: 'Devanagari', flag: '🇮🇳' },
];

const VOICES = [
  { id: 'en-IN-PrabhatNeural', label: 'Prabhat (Indian English - Male)' },
  { id: 'en-IN-NeerjaNeural', label: 'Neerja (Indian English - Female)' },
  { id: 'hi-IN-MadhurNeural', label: 'Madhur (Hindi - Male)' },
  { id: 'hi-IN-SwaraNeural', label: 'Swara (Hindi - Female)' },
  { id: 'ta-IN-ValluvarNeural', label: 'Valluvar (Tamil - Male)' },
  { id: 'ta-IN-PallaviNeural', label: 'Pallavi (Tamil - Female)' },
  { id: 'te-IN-MohanNeural', label: 'Mohan (Telugu - Male)' },
  { id: 'te-IN-ShrutiNeural', label: 'Shruti (Telugu - Female)' },
  { id: 'mr-IN-ManoharNeural', label: 'Manohar (Marathi - Male)' },
  { id: 'mr-IN-AarohiNeural', label: 'Aarohi (Marathi - Female)' },
  { id: 'bn-IN-BashkarNeural', label: 'Bashkar (Bengali - Male)' },
  { id: 'bn-IN-TanishaaNeural', label: 'Tanishaa (Bengali - Female)' },
];

export const NoticeIngestion: React.FC<Props> = ({
  initialConfig,
  onSubmit,
  loading,
}) => {
  const [config, setConfig] = useState<IngestConfig>(initialConfig);

  const toggleLang = (code: string) => {
    if (code === 'en') return; // English is master baseline
    setConfig((prev) => {
      const exists = prev.targetLangs.includes(code);
      const updated = exists
        ? prev.targetLangs.filter((l) => l !== code)
        : [...prev.targetLangs, code];
      return { ...prev, targetLangs: updated };
    });
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!config.rawText.trim() && !config.primaryLang) return;
    onSubmit(config);
  };

  return (
    <div className="glass-panel p-8 max-w-4xl mx-auto space-y-8">
      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-4 border-b border-white/10 pb-6">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-2xl font-black text-white">1. Circular & Notice Ingestion</h2>
            <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-cyan-500/20 text-cyan-300 border border-cyan-500/30">
              Stage 1 / 5
            </span>
          </div>
          <p className="text-sm text-slate-400 mt-1">
            Input official government circular text or select a preset to extract grounded fact entities.
          </p>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Source PDF Selection (Local) */}
        <div className="space-y-3">
          <label className="text-xs font-bold uppercase tracking-wider text-slate-300 flex items-center gap-2">
            <FileText className="w-4 h-4 text-cyan-400" /> Source Circular PDF (Local)
          </label>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
            {ALL_LANGUAGES.map((lang) => {
              const isSelected = config.primaryLang === lang.code;
              return (
                <button
                  key={`source-${lang.code}`}
                  type="button"
                  onClick={() => setConfig({ ...config, primaryLang: lang.code, rawText: 'AUTO_GENERATED' })}
                  className={`p-3.5 rounded-xl border text-left flex items-center justify-between transition-all ${
                    isSelected
                      ? 'bg-amber-950/40 border-amber-500/50 shadow-md shadow-amber-950/40 text-white'
                      : 'bg-slate-900/40 border-white/10 text-slate-400 hover:border-white/20'
                  }`}
                >
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-base">{lang.flag}</span>
                      <span className="text-sm font-semibold">{lang.label}</span>
                    </div>
                    <span className="text-[11px] text-slate-500 font-mono block mt-0.5">
                      extensive_test_{lang.code}.pdf
                    </span>
                  </div>
                  <div
                    className={`w-5 h-5 rounded-full flex items-center justify-center text-xs font-bold ${
                      isSelected ? 'bg-amber-500 text-slate-950' : 'bg-slate-800 border border-slate-600'
                    }`}
                  />
                </button>
              );
            })}
          </div>
        </div>

        {/* Target Languages Multi-select */}
        <div className="space-y-3">
          <label className="text-xs font-bold uppercase tracking-wider text-slate-300 flex items-center gap-2">
            <Globe className="w-4 h-4 text-emerald-400" /> Target Broadcast Languages (Multilingual Delivery)
          </label>
          
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
            {ALL_LANGUAGES.map((lang) => {
              const isSelected = config.targetLangs.includes(lang.code);
              const isMaster = lang.code === 'en';

              return (
                <button
                  key={lang.code}
                  type="button"
                  onClick={() => toggleLang(lang.code)}
                  className={`p-3.5 rounded-xl border text-left flex items-center justify-between transition-all ${
                    isSelected
                      ? 'bg-cyan-950/40 border-cyan-500/50 shadow-md shadow-cyan-950/40 text-white'
                      : 'bg-slate-900/40 border-white/10 text-slate-400 hover:border-white/20'
                  }`}
                >
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-base">{lang.flag}</span>
                      <span className="text-sm font-semibold">{lang.label}</span>
                    </div>
                    <span className="text-[11px] text-slate-500 font-mono block mt-0.5">
                      Script: {lang.script} {isMaster ? '(Master)' : ''}
                    </span>
                  </div>
                  <div
                    className={`w-5 h-5 rounded-md flex items-center justify-center text-xs font-bold ${
                      isSelected ? 'bg-cyan-500 text-slate-950' : 'bg-slate-800 text-slate-600'
                    }`}
                  >
                    ✓
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        {/* Voice Model & Speed Selection */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2">
          <div className="space-y-2">
            <label className="text-xs font-bold uppercase tracking-wider text-slate-300 flex items-center gap-2">
              <Mic2 className="w-4 h-4 text-amber-400" /> Default Neural Voice
            </label>
            <select
              value={config.voiceId}
              onChange={(e) => setConfig({ ...config, voiceId: e.target.value })}
              className="w-full bg-[#090E1A]/80 border border-white/15 focus:border-cyan-400 rounded-xl px-4 py-2.5 text-slate-200 text-sm focus:outline-none transition-all"
            >
              {VOICES.map((v) => (
                <option key={v.id} value={v.id} className="bg-slate-900 text-slate-100">
                  {v.label}
                </option>
              ))}
            </select>
          </div>

          <div className="space-y-2">
            <label className="text-xs font-bold uppercase tracking-wider text-slate-300 flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-cyan-400" /> Voice Speed Pace
            </label>
            <select
              value={config.speedMod}
              onChange={(e) => setConfig({ ...config, speedMod: e.target.value })}
              className="w-full bg-[#090E1A]/80 border border-white/15 focus:border-cyan-400 rounded-xl px-4 py-2.5 text-slate-200 text-sm focus:outline-none transition-all"
            >
              <option value="-10%" className="bg-slate-900 text-slate-100">Paced & Deliberate (-10%)</option>
              <option value="+0%" className="bg-slate-900 text-slate-100">Standard Broadcast (+0%)</option>
              <option value="+10%" className="bg-slate-900 text-slate-100">Energetic Pace (+10%)</option>
            </select>
          </div>
        </div>

        {/* Information Callout */}
        <div className="flex items-start gap-3 p-3.5 rounded-xl bg-cyan-950/30 border border-cyan-500/20 text-xs text-cyan-200/80">
          <Info className="w-4 h-4 text-cyan-400 shrink-0 mt-0.5" />
          <span>
            The pipeline will extract normalized amounts, deadlines, and action items using regex and LLM entity isolation, ensuring strict factual grounding before video compositing.
          </span>
        </div>

        {/* Submit Action Button */}
        <button
          type="submit"
          disabled={loading || (!config.rawText.trim() && !config.primaryLang)}
          className="btn-primary w-full py-3.5 text-base"
        >
          {loading ? (
            <>
              <Loader2 className="w-5 h-5 animate-spin" />
              Initializing Job & Extracting Grounded Facts...
            </>
          ) : (
            <>
              Initialize Pipeline & Extract Facts
              <ArrowRight className="w-5 h-5" />
            </>
          )}
        </button>
      </form>
    </div>
  );
};
