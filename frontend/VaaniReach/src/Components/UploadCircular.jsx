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
  { id: 'male_raw', name: 'Male Official', image: 'male_raw.png' },
  { id: 'female_raw', name: 'Female Official', image: 'female_raw.png' },
  { id: 'male_punjabi_raw', name: 'Punjabi Official', image: 'male_punjabi_raw.png' },
  { id: 'female_saree_raw', name: 'Saree Official', image: 'female_saree_raw.png' },
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
              Select local PDF, Presenter Avatar, and Voice to synthesize a complete video.
            </p>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="mt-6 space-y-8">
          {/* Settings Grid (Language & Voice) */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Language Selector */}
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">
                Primary Language
              </label>
              <div className="grid grid-cols-3 gap-2">
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

            {/* Voice Selector */}
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">
                Speech Voice
              </label>
              <div className="flex flex-col space-y-2">
                {VOICES[lang].map((v) => (
                  <label
                    key={v.id}
                    className={`flex items-center p-3 rounded-xl border cursor-pointer transition-all ${
                      voice === v.id
                        ? 'bg-amber-500/10 border-amber-500/50 text-amber-400'
                        : 'bg-slate-950/60 border-slate-800 text-slate-300 hover:bg-slate-900'
                    } ${isProcessing ? 'opacity-50 pointer-events-none' : ''}`}
                  >
                    <input
                      type="radio"
                      name="voice"
                      value={v.id}
                      checked={voice === v.id}
                      onChange={(e) => setVoice(e.target.value)}
                      className="hidden"
                    />
                    <span className="flex-1 text-sm font-medium">{v.name}</span>
                    {voice === v.id && (
                      <svg className="w-5 h-5 text-amber-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7"></path>
                      </svg>
                    )}
                  </label>
                ))}
              </div>
            </div>
          </div>

          {/* Avatar Selector Grid */}
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-3">
              Presenter Avatar Selection
            </label>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {CHARACTERS.map((char) => (
                <div
                  key={char.id}
                  onClick={() => !isProcessing && setCharacter(char.id)}
                  className={`group relative overflow-hidden rounded-xl border-2 cursor-pointer transition-all duration-300 ${
                    character === char.id
                      ? 'border-amber-500 shadow-lg shadow-amber-500/20 scale-[1.02]'
                      : 'border-slate-800 hover:border-slate-600 hover:scale-[1.01]'
                  } ${isProcessing ? 'opacity-50 pointer-events-none' : ''}`}
                >
                  {/* Image Container */}
                  <div className="aspect-[4/5] bg-slate-950 flex items-center justify-center overflow-hidden">
                    <img
                      src={`http://localhost:8000/avatars/${char.image}`}
                      alt={char.name}
                      className="w-full h-full object-cover group-hover:opacity-90 transition-opacity"
                    />
                  </div>
                  
                  {/* Overlay Info */}
                  <div className="absolute bottom-0 inset-x-0 bg-gradient-to-t from-slate-950 via-slate-950/80 to-transparent p-3 pt-8">
                    <p className={`text-sm font-bold truncate text-center ${
                      character === char.id ? 'text-amber-400' : 'text-slate-200'
                    }`}>
                      {char.name}
                    </p>
                  </div>
                  
                  {/* Selection Checkmark */}
                  {character === char.id && (
                    <div className="absolute top-2 right-2 bg-amber-500 text-slate-900 rounded-full p-1 shadow-md">
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="3" d="M5 13l4 4L19 7"></path>
                      </svg>
                    </div>
                  )}
                </div>
              ))}
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
                  <span>Generating Pipeline (RAG + Wav2Lip + Render)...</span>
                </>
              ) : (
                <span>Generate Video</span>
              )}
            </button>
          </div>
        </form>
      </div>

      {videoPath && (
        <div className="bg-emerald-950/30 border border-emerald-900/50 rounded-2xl p-6 backdrop-blur-md shadow-xl animate-in fade-in slide-in-from-bottom-4">
          <h3 className="text-emerald-400 font-bold mb-3 flex items-center text-lg">
            <svg className="w-6 h-6 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path>
            </svg>
            Pipeline Complete!
          </h3>
          <p className="text-slate-300">
            Final Rendered Video path:<br/>
            <code className="bg-slate-900 px-3 py-1.5 rounded-lg text-emerald-300 mt-2 block break-all">{videoPath}</code>
          </p>
        </div>
      )}
    </div>
  );
}
