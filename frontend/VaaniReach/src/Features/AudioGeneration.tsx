import React, { useState, useRef } from 'react';
import {
  Volume2,
  Play,
  Pause,
  Sparkles,
  ArrowRight,
  Loader2,
  CheckCircle2,
  Radio,
  FileCheck,
} from 'lucide-react';
import type { SceneDefinition, WordTimestamp } from '../api/client';
import { api } from '../api/client';

interface Props {
  masterScenes: SceneDefinition[];
  localizedScenes: Record<string, SceneDefinition[]>;
  targetLangs: string[];
  onSynthesize: () => Promise<void>;
  onProceedToApproval: () => void;
  loading: boolean;
}

const LANG_DISPLAY: Record<string, { label: string; flag: string }> = {
  en: { label: 'English', flag: '🇬🇧' },
  hi: { label: 'हिंदी (Hindi)', flag: '🇮🇳' },
  ta: { label: 'தமிழ் (Tamil)', flag: '🇮🇳' },
  te: { label: 'తెలుగు (Telugu)', flag: '🇮🇳' },
  bn: { label: 'বাংলা (Bengali)', flag: '🇮🇳' },
  mr: { label: 'मराठी (Marathi)', flag: '🇮🇳' },
};

export const AudioGeneration: React.FC<Props> = ({
  masterScenes,
  localizedScenes,
  targetLangs,
  onSynthesize,
  onProceedToApproval,
  loading,
}) => {
  const [selectedLang, setSelectedLang] = useState<string>('en');
  const [playingSceneIdx, setPlayingSceneIdx] = useState<number | null>(null);
  const [currentPlayTime, setCurrentPlayTime] = useState<number>(0);
  const audioRefs = useRef<(HTMLAudioElement | null)[]>([]);

  const activeScenes =
    selectedLang === 'en'
      ? masterScenes
      : localizedScenes[selectedLang] || [];

  const isSynthesized = activeScenes.some((s) => s.audio_path && s.scene_duration_sec);

  // Synchronize audio playback time for karaoke highlight
  const handleTimeUpdate = (sceneIdx: number) => {
    const audioEl = audioRefs.current[sceneIdx];
    if (audioEl) {
      setCurrentPlayTime(audioEl.currentTime);
    }
  };

  const handlePlayPause = (sceneIdx: number) => {
    const audioEl = audioRefs.current[sceneIdx];
    if (!audioEl) return;

    if (playingSceneIdx === sceneIdx) {
      audioEl.pause();
      setPlayingSceneIdx(null);
    } else {
      if (playingSceneIdx !== null && audioRefs.current[playingSceneIdx]) {
        audioRefs.current[playingSceneIdx]?.pause();
      }
      audioEl.play();
      setPlayingSceneIdx(sceneIdx);
    }
  };

  const handleEnded = () => {
    setPlayingSceneIdx(null);
    setCurrentPlayTime(0);
  };

  return (
    <div className="glass-panel p-8 max-w-5xl mx-auto space-y-8">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-white/10 pb-6">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-2xl font-black text-white">4. Voice & Subtitle Synchronization Studio</h2>
            <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-500/20 text-amber-300 border border-amber-500/30">
              Stage 4 / 5
            </span>
          </div>
          <p className="text-sm text-slate-400 mt-1">
            Generate neural TTS speech, inspect word-level subtitle boundaries, and test real-time karaoke sync.
          </p>
        </div>

        {/* Synthesis Action Button */}
        <button
          type="button"
          onClick={onSynthesize}
          disabled={loading}
          className="btn-primary text-xs"
        >
          {loading ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              Synthesizing All Languages via Edge-TTS...
            </>
          ) : (
            <>
              <Sparkles className="w-4 h-4 text-amber-300" />
              {isSynthesized ? 'Re-Synthesize Audio & Subtitles' : 'Synthesize Audio & Subtitles'}
            </>
          )}
        </button>
      </div>

      {/* Language Selector Bar */}
      <div className="flex items-center gap-2 border-b border-white/10 pb-4 overflow-x-auto">
        <span className="text-xs font-bold uppercase tracking-wider text-slate-400 flex items-center gap-1.5 mr-2">
          <Volume2 className="w-4 h-4 text-amber-400" /> Language:
        </span>

        {targetLangs.map((lang) => {
          const info = LANG_DISPLAY[lang] || { label: lang.toUpperCase(), flag: '🌐' };
          const isActive = selectedLang === lang;

          return (
            <button
              key={lang}
              type="button"
              onClick={() => {
                setSelectedLang(lang);
                setPlayingSceneIdx(null);
              }}
              className={`lang-tab flex items-center gap-2 ${isActive ? 'active' : ''}`}
            >
              <span>{info.flag}</span>
              <span>{info.label}</span>
              {isActive && <CheckCircle2 className="w-3.5 h-3.5" />}
            </button>
          );
        })}
      </div>

      {/* Scenes Audio & Karaoke List */}
      <div className="space-y-6">
        {activeScenes.map((scene, idx) => {
          const hasAudio = !!scene.audio_path;
          const duration = scene.scene_duration_sec || 0;
          const subtitles: WordTimestamp[] = scene.subtitles || [];
          const isCurrentScenePlaying = playingSceneIdx === idx;

          return (
            <div
              key={scene.scene_id || idx}
              className="glass-card p-6 space-y-4 border border-white/10"
            >
              {/* Scene Audio Player Row */}
              <div className="flex flex-wrap items-center justify-between gap-4">
                <div className="flex items-center gap-3">
                  <button
                    type="button"
                    disabled={!hasAudio}
                    onClick={() => handlePlayPause(idx)}
                    className={`w-11 h-11 rounded-xl flex items-center justify-center transition-all ${
                      hasAudio
                        ? isCurrentScenePlaying
                          ? 'bg-amber-500 text-slate-950 shadow-lg shadow-amber-500/30'
                          : 'bg-cyan-600 hover:bg-cyan-500 text-white shadow-lg shadow-cyan-600/30'
                        : 'bg-slate-800 text-slate-600 cursor-not-allowed'
                    }`}
                  >
                    {isCurrentScenePlaying ? (
                      <Pause className="w-5 h-5" />
                    ) : (
                      <Play className="w-5 h-5 ml-0.5" />
                    )}
                  </button>

                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-bold text-white font-mono">
                        Scene {idx + 1}: {scene.template_type.replace('_', ' ')}
                      </span>
                      {hasAudio && (
                        <span className="text-xs px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 font-mono">
                          {duration.toFixed(1)}s duration
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-slate-400 mt-0.5">
                      {scene.visual_hierarchy.headline}
                    </p>
                  </div>
                </div>

                {/* Audio Element */}
                {hasAudio && (
                  <audio
                    ref={(el) => {
                      audioRefs.current[idx] = el;
                    }}
                    src={api.getAudioUrl(scene.audio_path || '')}
                    onTimeUpdate={() => handleTimeUpdate(idx)}
                    onEnded={handleEnded}
                    preload="auto"
                  />
                )}
              </div>

              {/* Real-time Interactive Karaoke Subtitle Box */}
              <div className="space-y-2">
                <div className="flex items-center justify-between text-xs font-bold uppercase tracking-wider text-slate-400">
                  <span className="flex items-center gap-1.5">
                    <Radio className="w-3.5 h-3.5 text-amber-400 animate-pulse" />
                    Audio-Synchronized Subtitles (Live Active Word Highlight):
                  </span>
                  {isCurrentScenePlaying && (
                    <span className="font-mono text-amber-400">
                      t = {currentPlayTime.toFixed(2)}s
                    </span>
                  )}
                </div>

                <div className="karaoke-box">
                  {subtitles.length > 0 ? (
                    subtitles.map((sub, sIdx) => {
                      const isActive =
                        isCurrentScenePlaying &&
                        currentPlayTime >= sub.start_sec &&
                        currentPlayTime <= sub.end_sec;
                      const isPast =
                        isCurrentScenePlaying && currentPlayTime > sub.end_sec;

                      let className = 'karaoke-word';
                      if (isActive) className += ' active';
                      else if (isPast) className += ' past';
                      if (sub.is_core_fact) className += ' core-fact';

                      return (
                        <span
                          key={sIdx}
                          className={className}
                          title={`[${sub.start_sec.toFixed(2)}s - ${sub.end_sec.toFixed(2)}s] ${sub.is_core_fact ? '(Core Fact - Triggers Card Pop)' : ''}`}
                        >
                          {sub.word}
                        </span>
                      );
                    })
                  ) : (
                    <span className="text-sm text-slate-400 italic">
                      {hasAudio
                        ? scene.full_spoken_text
                        : 'Audio not yet synthesized. Click "Synthesize Audio" above.'}
                    </span>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Advance to Approval Gate */}
      <div className="pt-6 border-t border-white/10 flex flex-wrap items-center justify-between gap-4">
        <div className="text-xs text-slate-400 flex items-center gap-2">
          <FileCheck className="w-4 h-4 text-emerald-400" />
          <span>Speech tracks and kinetic word timings prepared for officer verification.</span>
        </div>

        <button
          type="button"
          onClick={onProceedToApproval}
          disabled={!isSynthesized}
          className="btn-success py-3 px-6 text-sm"
        >
          Proceed to Officer Sign-Off Gate
          <ArrowRight className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
};
