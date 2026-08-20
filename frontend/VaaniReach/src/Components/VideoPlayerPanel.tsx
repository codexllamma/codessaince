import React, { useState } from 'react';
import { api } from '../api/client';

interface Props {
  videoPaths: Record<string, string>;
}

const LANGUAGE_LABELS: Record<string, string> = {
  en: 'English (Master)',
  hi: 'हिंदी (Hindi)',
  ta: 'தமிழ் (Tamil)',
  te: 'తెలుగు (Telugu)',
};

export const VideoPlayerPanel: React.FC<Props> = ({ videoPaths }) => {
  const availableLangs = Object.keys(videoPaths);
  const [selectedLang, setSelectedLang] = useState<string>(availableLangs[0] || 'en');

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-xl text-white">
      <h2 className="text-xl font-bold mb-4">Broadcast Video Deliverables</h2>

      {/* Language Selector Tabs */}
      <div className="flex flex-wrap gap-2 mb-4">
        {availableLangs.map((lang) => (
          <button
            key={lang}
            onClick={() => setSelectedLang(lang)}
            className={`px-4 py-2 rounded-lg font-medium text-sm transition-all ${
              selectedLang === lang
                ? 'bg-blue-600 text-white shadow-lg shadow-blue-600/30'
                : 'bg-slate-800 text-slate-300 hover:bg-slate-700'
            }`}
          >
            {LANGUAGE_LABELS[lang] || lang.toUpperCase()}
          </button>
        ))}
      </div>

      {/* Video Stream */}
      <div className="relative aspect-video w-full rounded-lg overflow-hidden bg-black border border-slate-800">
        <video
          key={videoPaths[selectedLang]}
          controls
          autoPlay
          className="w-full h-full object-contain"
          src={api.getVideoUrl(videoPaths[selectedLang])}
        >
          Your browser does not support the video tag.
        </video>
      </div>

      <div className="mt-4 flex justify-between items-center text-sm text-slate-400">
        <span>File: {videoPaths[selectedLang]}</span>
        <a
          href={api.getVideoUrl(videoPaths[selectedLang])}
          download
          className="text-blue-400 hover:text-blue-300 underline font-medium"
        >
          Download MP4
        </a>
      </div>
    </div>
  );
};