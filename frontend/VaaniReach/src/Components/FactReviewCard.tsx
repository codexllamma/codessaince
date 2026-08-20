import React, { useState } from 'react';
import type { ExtractedFact, SceneDefinition } from '../api/client';
import { api } from '../api/client';

interface Props {
  facts: ExtractedFact[];
  masterScenes: SceneDefinition[];
  localizedScenes?: Record<string, SceneDefinition[]>;
  onApprove: () => void;
  loading: boolean;
}

export const FactReviewCard: React.FC<Props> = ({
  facts,
  masterScenes,
  localizedScenes = {},
  onApprove,
  loading,
}) => {
  const [activeLang, setActiveLang] = useState<string>('en');

  // Select scenes based on active language tab
  const activeScenes =
    activeLang === 'en'
      ? masterScenes
      : localizedScenes[activeLang] || [];

  const availableLangs = ['en', ...Object.keys(localizedScenes)];

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-xl text-white space-y-6">
      <div className="flex items-center justify-between border-b border-slate-800 pb-4">
        <div>
          <h2 className="text-xl font-bold">Officer Fact & Audio Verification</h2>
          <p className="text-sm text-slate-400">
            Review facts and listen to generated Edge-TTS speech before rendering.
          </p>
        </div>
        <span className="bg-amber-500/20 text-amber-300 px-3 py-1 rounded-full text-xs font-semibold uppercase">
          Approval Required
        </span>
      </div>

      {/* Extracted Facts Grid */}
      <div>
        <h3 className="text-xs uppercase tracking-wider text-slate-400 font-semibold mb-3">
          Verified Fact Entities
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {facts.map((fact) => (
            <div
              key={fact.fact_id}
              className="bg-slate-950/60 border border-slate-800 p-3.5 rounded-lg flex flex-col"
            >
              <span className="text-xs text-slate-400 uppercase tracking-wider font-mono">
                {fact.category}
              </span>
              <span className="text-base font-semibold text-amber-400 mt-1">
                {fact.normalized_value}
              </span>
              <span className="text-xs text-slate-500 mt-0.5">
                Raw: "{fact.raw_value}"
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Audio Playback Review per Language & Scene */}
      <div className="border-t border-slate-800 pt-5">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-xs uppercase tracking-wider text-slate-400 font-semibold">
            Audio Synthesis Preview
          </h3>
          <div className="flex gap-1.5">
            {availableLangs.map((lang) => (
              <button
                key={lang}
                type="button"
                onClick={() => setActiveLang(lang)}
                className={`px-2.5 py-1 rounded text-xs font-bold uppercase transition-all ${
                  activeLang === lang
                    ? 'bg-amber-500 text-slate-950'
                    : 'bg-slate-800 text-slate-400 hover:bg-slate-700'
                }`}
              >
                {lang}
              </button>
            ))}
          </div>
        </div>

        <div className="space-y-3">
          {activeScenes.map((scene, idx) => (
            <div
              key={scene.scene_id || idx}
              className="bg-slate-950/80 border border-slate-800 rounded-lg p-3 flex flex-col md:flex-row md:items-center justify-between gap-3"
            >
              <div className="flex-1">
                <span className="text-xs text-slate-500 font-mono">
                  Scene {idx + 1} ({scene.scene_duration_sec ? `${scene.scene_duration_sec}s` : 'Auto'}):
                </span>
                <p className="text-sm text-slate-200 mt-0.5">{scene.full_spoken_text}</p>
              </div>

              {scene.audio_path && (
                <audio
                  controls
                  className="h-9 w-full md:w-64 accent-amber-500"
                  src={api.getVideoUrl(scene.audio_path)}
                >
                  Your browser does not support audio playback.
                </audio>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Approve Button */}
      <button
        onClick={onApprove}
        disabled={loading}
        className="w-full bg-emerald-600 hover:bg-emerald-500 disabled:bg-slate-700 text-white font-bold py-3 rounded-lg transition-all flex items-center justify-center gap-2"
      >
        {loading ? 'Authorizing & Rendering...' : '✓ Approve Speech & Render Video Broadcast'}
      </button>
    </div>
  );
};