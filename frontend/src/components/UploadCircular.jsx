import React, { useState } from 'react';

const VOICES = {
  en: [{ id: 'en-IN-PrabhatNeural', name: 'Prabhat (Male)' }, { id: 'en-IN-NeerjaNeural', name: 'Neerja (Female)' }],
  hi: [{ id: 'hi-IN-MadhurNeural', name: 'Madhur (Male)' }, { id: 'hi-IN-SwaraNeural', name: 'Swara (Female)' }],
  ta: [{ id: 'ta-IN-ValluvarNeural', name: 'Valluvar (Male)' }, { id: 'ta-IN-PallaviNeural', name: 'Pallavi (Female)' }],
  te: [{ id: 'te-IN-MohanNeural', name: 'Mohan (Male)' }, { id: 'te-IN-ShrutiNeural', name: 'Shruti (Female)' }],
  mr: [{ id: 'mr-IN-ManoharNeural', name: 'Manohar (Male)' }, { id: 'mr-IN-AarohiNeural', name: 'Aarohi (Female)' }],
  bn: [{ id: 'bn-IN-BashkarNeural', name: 'Bashkar (Male)' }, { id: 'bn-IN-TanishaaNeural', name: 'Tanishaa (Female)' }],
  gu: [{ id: 'gu-IN-NiranjanNeural', name: 'Niranjan (Male)' }, { id: 'gu-IN-DhwaniNeural', name: 'Dhwani (Female)' }],
  kn: [{ id: 'kn-IN-GaganNeural', name: 'Gagan (Male)' }, { id: 'kn-IN-SapnaNeural', name: 'Sapna (Female)' }],
  ml: [{ id: 'ml-IN-MidhunNeural', name: 'Midhun (Male)' }, { id: 'ml-IN-SobhanaNeural', name: 'Sobhana (Female)' }],
};

const CHARACTERS = [
  { id: 'male_raw', name: 'Male Raw' },
  { id: 'female_raw', name: 'Female Raw' },
  { id: 'male_punjabi_raw', name: 'Punjabi Male Raw' },
  { id: 'female_saree_raw', name: 'Saree Female Raw' },
];

export default function UploadCircular() {
  const [lang, setLang] = useState('en');
  const [character, setCharacter] = useState('male_raw');
  const [voice, setVoice] = useState(VOICES['en'][0].id);
  const [isProcessing, setIsProcessing] = useState(false);
  const [videoPath, setVideoPath] = useState(null);
  const [error, setError] = useState(null);

  const handleLangChange = (l) => {
    setLang(l);
    setVoice(VOICES[l][0].id); // Auto-select first voice for the new language
  };

  const handleSubmit = async (e) => {
    if (e) e.preventDefault();
    setIsProcessing(true);
    setError(null);
    setVideoPath(null);

    try {
      const response = await fetch('http://localhost:8000/api/jobs/run-e2e', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          lang: lang,
          character: character,
          voice: voice,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `Generation failed with HTTP ${response.status}`);
      }

      const data = await response.json();
      setVideoPath(data.video_path);
    } catch (err) {
      console.error('Pipeline Error:', err);
      setError(err.message || 'Failed to run pipeline. Please try again.');
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <div className="w-full max-w-5xl mx-auto p-6 space-y-6">
      <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-6 shadow-xl backdrop-blur-md">
        <div className="flex items-center space-x-3 mb-2">
          <div className="h-9 w-9 rounded-xl bg-gradient-to-tr from-amber-500 to-orange-600 flex items-center justify-center shadow-lg shadow-orange-500/20 text-white font-bold">
            E2E
          </div>
          <div>
            <h2 className="text-xl font-bold text-slate-100">End-to-End Pipeline Configuration</h2>
            <p className="text-sm text-slate-400">
              Select local PDF, Character, and Voice to synthesize a complete video.
            </p>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="mt-6 space-y-6">
          {/* Language Selector */}
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">
              Primary Language
            </label>
            <div className="grid grid-cols-3 sm:grid-cols-5 gap-2">
              {Object.keys(VOICES).map((l) => (
                <button
                  key={l}
                  type="button"
                  disabled={isProcessing}
                  onClick={() => handleLangChange(l)}
                  className={`px-3 py-2 rounded-xl text-sm font-medium transition-all ${
                    lang === l
                      ? 'bg-amber-500/20 text-amber-400 border border-amber-500/50 shadow-md shadow-amber-500/10'
                      : 'bg-slate-950/60 text-slate-400 border border-slate-800 hover:border-slate-600 hover:bg-slate-900'
                  } disabled:opacity-50`}
                >
                  {l.toUpperCase()}
                </button>
              ))}
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Character Selector */}
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">
                Presenter Character
              </label>
              <select
                value={character}
                onChange={(e) => setCharacter(e.target.value)}
                disabled={isProcessing}
                className="w-full bg-slate-950/80 border border-slate-700 rounded-xl p-3 text-slate-200 outline-none focus:border-amber-500/50 focus:ring-1 focus:ring-amber-500/50 transition-all"
              >
                {CHARACTERS.map((char) => (
                  <option key={char.id} value={char.id}>
                    {char.name}
                  </option>
                ))}
              </select>
            </div>

            {/* Voice Selector */}
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">
                Speech Voice
              </label>
              <select
                value={voice}
                onChange={(e) => setVoice(e.target.value)}
                disabled={isProcessing}
                className="w-full bg-slate-950/80 border border-slate-700 rounded-xl p-3 text-slate-200 outline-none focus:border-amber-500/50 focus:ring-1 focus:ring-amber-500/50 transition-all"
              >
                {VOICES[lang].map((v) => (
                  <option key={v.id} value={v.id}>
                    {v.name}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {error && (
            <div className="bg-rose-950/50 border border-rose-900/50 rounded-xl p-4 text-sm text-rose-300">
              {error}
            </div>
          )}

          <div className="pt-2 flex justify-end">
            <button
              type="submit"
              disabled={isProcessing}
              className="bg-amber-600 hover:bg-amber-500 text-white font-medium py-3 px-8 rounded-xl transition-all shadow-lg shadow-amber-900/20 active:scale-95 disabled:opacity-50 disabled:pointer-events-none flex items-center space-x-2"
            >
              {isProcessing ? (
                <>
                  <svg className="animate-spin h-5 w-5 text-white/80" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  <span>Synthesizing Video...</span>
                </>
              ) : (
                <span>Generate Video</span>
              )}
            </button>
          </div>
        </form>
      </div>

      {videoPath && (
        <div className="bg-emerald-950/30 border border-emerald-900/50 rounded-2xl p-6 backdrop-blur-md">
          <h3 className="text-emerald-400 font-medium mb-4 flex items-center">
            <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7"></path>
            </svg>
            Pipeline Complete
          </h3>
          <p className="text-sm text-slate-300">
            Video rendered at: <code className="bg-slate-900 px-2 py-1 rounded text-slate-400">{videoPath}</code>
          </p>
        </div>
      )}
    </div>
  );
}
