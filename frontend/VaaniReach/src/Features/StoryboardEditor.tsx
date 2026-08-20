import React, { useState } from 'react';
import {
  Layers,
  Globe,
  Image as ImageIcon,
  Sparkles,
  ArrowRight,
  Eye,
  CheckCircle2,
  Calendar,
  DollarSign,
  AlertCircle,
  ExternalLink,
  X,
} from 'lucide-react';
import type { SceneDefinition } from '../api/client';
import { api } from '../api/client';

interface Props {
  masterScenes: SceneDefinition[];
  localizedScenes: Record<string, SceneDefinition[]>;
  targetLangs: string[];
  onProceedToAudio: () => void;
}

const TEMPLATE_ICONS: Record<string, React.FC<{ className?: string }>> = {
  HERO_ANNOUNCEMENT: Sparkles,
  METRIC_FOCUS: DollarSign,
  DEADLINE_ALERT: Calendar,
  OUTRO_CALL_TO_ACTION: ExternalLink,
};

const LANG_DISPLAY: Record<string, { label: string; flag: string }> = {
  en: { label: 'English (Master)', flag: '🇬🇧' },
  hi: { label: 'हिंदी (Hindi)', flag: '🇮🇳' },
  ta: { label: 'தமிழ் (Tamil)', flag: '🇮🇳' },
  te: { label: 'తెలుగు (Telugu)', flag: '🇮🇳' },
  bn: { label: 'বাংলা (Bengali)', flag: '🇮🇳' },
  mr: { label: 'मराठी (Marathi)', flag: '🇮🇳' },
};

export const StoryboardEditor: React.FC<Props> = ({
  masterScenes,
  localizedScenes,
  targetLangs,
  onProceedToAudio,
}) => {
  const [selectedLang, setSelectedLang] = useState<string>('en');
  const [previewCardLang, setPreviewCardLang] = useState<string | null>(null);

  // Active scenes for currently selected language
  const activeScenes =
    selectedLang === 'en'
      ? masterScenes
      : localizedScenes[selectedLang] || [];

  return (
    <div className="glass-panel p-8 max-w-6xl mx-auto space-y-8">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-white/10 pb-6">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-2xl font-black text-white">3. Multilingual Storyboard & Visual Cards</h2>
            <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-500/20 text-blue-300 border border-blue-500/30">
              Stage 3 / 5
            </span>
          </div>
          <p className="text-sm text-slate-400 mt-1">
            Review localized visual hierarchies, kinetic card layouts, and spoken scripts across target Indic languages.
          </p>
        </div>

        <button
          type="button"
          onClick={() => setPreviewCardLang(selectedLang)}
          className="btn-secondary text-xs"
        >
          <Eye className="w-4 h-4 text-cyan-400" />
          Test Card Frame Preview ({selectedLang.toUpperCase()})
        </button>
      </div>

      {/* Language Selector Bar */}
      <div className="flex items-center gap-2 border-b border-white/10 pb-4 overflow-x-auto">
        <span className="text-xs font-bold uppercase tracking-wider text-slate-400 flex items-center gap-1.5 mr-2">
          <Globe className="w-4 h-4 text-cyan-400" /> Language:
        </span>

        {targetLangs.map((lang) => {
          const info = LANG_DISPLAY[lang] || { label: lang.toUpperCase(), flag: '🌐' };
          const isActive = selectedLang === lang;

          return (
            <button
              key={lang}
              type="button"
              onClick={() => setSelectedLang(lang)}
              className={`lang-tab flex items-center gap-2 ${isActive ? 'active' : ''}`}
            >
              <span>{info.flag}</span>
              <span>{info.label}</span>
              {isActive && <CheckCircle2 className="w-3.5 h-3.5" />}
            </button>
          );
        })}
      </div>

      {/* Storyboard Scenes Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {activeScenes.map((scene, idx) => {
          const TemplateIcon = TEMPLATE_ICONS[scene.template_type] || Layers;
          const vh = scene.visual_hierarchy;
          const accentColor = scene.asset?.accent_color || '#06B6D4';

          return (
            <div
              key={scene.scene_id || idx}
              className="glass-card p-6 flex flex-col justify-between gap-5 relative overflow-hidden border border-white/10 hover:border-cyan-500/40 transition-all group"
            >
              {/* Top Accent Strip */}
              <div
                className="absolute top-0 left-0 right-0 h-1"
                style={{ backgroundColor: accentColor }}
              />

              {/* Scene Header */}
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div
                    className="w-8 h-8 rounded-lg flex items-center justify-center text-white"
                    style={{ backgroundColor: `${accentColor}33`, border: `1px solid ${accentColor}66` }}
                  >
                    <TemplateIcon className="w-4 h-4" />
                  </div>
                  <div>
                    <span className="text-xs font-bold uppercase text-slate-300 font-mono">
                      Scene {idx + 1}: {scene.template_type.replace('_', ' ')}
                    </span>
                  </div>
                </div>

                <span
                  className="text-[10px] font-bold uppercase px-2.5 py-1 rounded-full text-slate-950 font-sans shadow-sm"
                  style={{ backgroundColor: accentColor }}
                >
                  {vh.badge_tag || 'OFFICIAL'}
                </span>
              </div>

              {/* Visual Card Representation */}
              <div className="bg-[#090E1A]/90 border border-white/10 rounded-xl p-4 space-y-3 relative">
                {/* Headline & Subtext */}
                <div>
                  <div className="text-base font-bold text-white tracking-tight leading-snug">
                    {vh.headline}
                  </div>
                  <div className="text-xs text-slate-400 mt-0.5">
                    {vh.subtext}
                  </div>
                </div>

                {/* Highlight Metric Card if METRIC_FOCUS */}
                {vh.highlight_metric && (
                  <div className="mt-2 p-3 rounded-lg bg-slate-900/90 border border-white/10 text-center space-y-1">
                    <div className="text-2xl font-black text-amber-300 tracking-tight">
                      {vh.highlight_metric}
                    </div>
                    {vh.highlight_sublabel && (
                      <div className="text-[11px] font-medium text-slate-400">
                        {vh.highlight_sublabel}
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* Spoken Script with Core Fact Highlights */}
              <div className="space-y-1.5 pt-2 border-t border-white/5">
                <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400 block">
                  Narration Script:
                </span>
                <div className="text-xs text-slate-300 leading-relaxed bg-[#070B14]/60 p-3 rounded-lg border border-white/5">
                  {scene.script_segments && scene.script_segments.length > 0 ? (
                    scene.script_segments.map((seg, sIdx) => (
                      <span
                        key={sIdx}
                        className={
                          seg.type === 'core_fact'
                            ? 'bg-amber-500/20 text-amber-300 font-semibold px-1.5 py-0.5 rounded mx-0.5 border border-amber-500/30'
                            : 'text-slate-300'
                        }
                      >
                        {seg.text}{' '}
                      </span>
                    ))
                  ) : (
                    <span>{scene.full_spoken_text}</span>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {activeScenes.length === 0 && (
        <div className="text-center py-12 border-2 border-dashed border-white/10 rounded-xl space-y-3">
          <AlertCircle className="w-8 h-8 text-cyan-400 mx-auto" />
          <div className="text-slate-300 font-semibold">No scenes generated for {selectedLang.toUpperCase()}.</div>
        </div>
      )}

      {/* Advance Action */}
      <div className="pt-6 border-t border-white/10 flex flex-wrap items-center justify-between gap-4">
        <div className="text-xs text-slate-400">
          Ready to synthesize neural TTS speech and word-level karaoke timestamps for {targetLangs.length} languages.
        </div>

        <button
          type="button"
          onClick={onProceedToAudio}
          className="btn-primary py-3 px-6 text-sm"
        >
          Proceed to Audio & Subtitle Studio
          <ArrowRight className="w-4 h-4" />
        </button>
      </div>

      {/* Instant Frame Preview Modal */}
      {previewCardLang && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-md flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-white/20 rounded-2xl max-w-4xl w-full p-6 space-y-4 shadow-2xl">
            <div className="flex items-center justify-between border-b border-white/10 pb-4">
              <div className="flex items-center gap-2">
                <ImageIcon className="w-5 h-5 text-cyan-400" />
                <h3 className="text-lg font-bold text-white">
                  Live Compositor Card Preview ({previewCardLang.toUpperCase()})
                </h3>
              </div>
              <button
                type="button"
                onClick={() => setPreviewCardLang(null)}
                className="p-1.5 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="aspect-video w-full rounded-xl overflow-hidden bg-black border border-white/10 flex items-center justify-center">
              <img
                src={api.getCardPreviewUrl(previewCardLang)}
                alt="Card Preview"
                className="w-full h-full object-contain"
              />
            </div>

            <div className="flex items-center justify-between text-xs text-slate-400 pt-2">
              <span>Rendered with HarfBuzz complex Indic text shaping & bundled Noto fonts.</span>
              <button
                type="button"
                onClick={() => setPreviewCardLang(null)}
                className="btn-secondary py-1.5 px-4 text-xs"
              >
                Close Preview
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
