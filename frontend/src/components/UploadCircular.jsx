import React, { useState } from 'react';

export default function UploadCircular() {
  const [file, setFile] = useState(null);
  const [lang, setLang] = useState('en');
  const [isProcessing, setIsProcessing] = useState(false);
  const [results, setResults] = useState([]);
  const [error, setError] = useState(null);

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files.length > 0) {
      setFile(e.target.files[0]);
      setError(null);
    }
  };

  const handleSubmit = async (e) => {
    if (e) e.preventDefault();
    if (!file) {
      setError('Please select a PDF document to upload.');
      return;
    }

    setIsProcessing(true);
    setError(null);

    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('lang', lang);

      // Native fetch POST with FormData (Browser automatically sets boundary)
      const response = await fetch('http://localhost:8000/api/jobs/upload-doc', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `Upload failed with HTTP ${response.status}`);
      }

      const data = await response.json();
      const extractedFacts = data.results || data.extracted_facts || [];
      setResults(extractedFacts);
    } catch (err) {
      console.error('Upload Error:', err);
      setError(err.message || 'Failed to process document. Please try again.');
    } finally {
      setIsProcessing(false);
    }
  };

  const getCategoryBadgeClass = (category) => {
    switch (category) {
      case 'AUTHORITY':
        return 'bg-blue-900/60 text-blue-300 border-blue-700/60';
      case 'SCHEME_NAME':
        return 'bg-purple-900/60 text-purple-300 border-purple-700/60';
      case 'AMOUNT':
        return 'bg-emerald-900/60 text-emerald-300 border-emerald-700/60';
      case 'DEADLINE':
        return 'bg-amber-900/60 text-amber-300 border-amber-700/60';
      case 'ACTION_REQUIRED':
        return 'bg-rose-900/60 text-rose-300 border-rose-700/60';
      default:
        return 'bg-slate-800 text-slate-300 border-slate-700';
    }
  };

  return (
    <div className="w-full max-w-5xl mx-auto p-6 space-y-6">
      {/* Header Banner */}
      <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-6 shadow-xl backdrop-blur-md">
        <div className="flex items-center space-x-3 mb-2">
          <div className="h-9 w-9 rounded-xl bg-gradient-to-tr from-amber-500 to-orange-600 flex items-center justify-center shadow-lg shadow-orange-500/20 text-white font-bold">
            OCR
          </div>
          <div>
            <h2 className="text-xl font-bold text-slate-100">Upload Government Circular</h2>
            <p className="text-sm text-slate-400">
              GPU-accelerated ephemeral OCR extraction and grounded fact entity extraction
            </p>
          </div>
        </div>

        {/* Upload Form */}
        <form onSubmit={handleSubmit} className="mt-6 space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* File Input Box */}
            <div className="md:col-span-2">
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1.5">
                Target PDF Circular
              </label>
              <div className="relative flex items-center justify-between border-2 border-dashed border-slate-700 hover:border-amber-500/60 rounded-xl p-3 bg-slate-950/60 transition-colors">
                <input
                  type="file"
                  accept="application/pdf"
                  onChange={handleFileChange}
                  disabled={isProcessing}
                  className="absolute inset-0 w-full h-full opacity-0 cursor-pointer disabled:cursor-not-allowed"
                />
                <div className="flex items-center space-x-3 overflow-hidden">
                  <svg className="w-6 h-6 text-amber-400 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                  </svg>
                  <span className="text-sm text-slate-300 truncate">
                    {file ? file.name : 'Choose a circular PDF or drag & drop here'}
                  </span>
                </div>
                {file && (
                  <span className="text-xs text-slate-400 font-mono bg-slate-800 px-2 py-1 rounded">
                    {(file.size / 1024).toFixed(1)} KB
                  </span>
                )}
              </div>
            </div>

            {/* Language Selector */}
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1.5">
                Primary Language
              </label>
              <select
                value={lang}
                onChange={(e) => setLang(e.target.value)}
                disabled={isProcessing}
                className="w-full bg-slate-950/80 border border-slate-700 rounded-xl p-3 text-sm text-slate-200 focus:outline-none focus:border-amber-500 disabled:opacity-60"
              >
                <option value="en">English (en)</option>
                <option value="hi">Hindi (hi - हिन्दी)</option>
                <option value="ta">Tamil (ta - தமிழ்)</option>
                <option value="te">Telugu (te - తెలుగు)</option>
              </select>
            </div>
          </div>

          {/* Error Message */}
          {error && (
            <div className="p-3 bg-rose-950/60 border border-rose-800/80 rounded-xl text-rose-300 text-sm flex items-center space-x-2">
              <svg className="w-5 h-5 shrink-0 text-rose-400" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
              </svg>
              <span>{error}</span>
            </div>
          )}

          {/* Action Button */}
          <div className="flex justify-end">
            <button
              type="submit"
              disabled={!file || isProcessing}
              className={`px-6 py-2.5 rounded-xl font-medium text-sm flex items-center space-x-2 shadow-lg transition-all ${
                !file || isProcessing
                  ? 'bg-slate-800 text-slate-500 cursor-not-allowed'
                  : 'bg-gradient-to-r from-amber-500 to-orange-600 hover:from-amber-400 hover:to-orange-500 text-white shadow-orange-500/20'
              }`}
            >
              {isProcessing ? (
                <>
                  <svg className="animate-spin h-4 w-4 text-white" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                  </svg>
                  <span>Running GPU OCR & Extraction...</span>
                </>
              ) : (
                <>
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                  </svg>
                  <span>Extract Facts from Circular</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>

      {/* Extracted Facts Results */}
      {results.length > 0 && (
        <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-6 shadow-xl backdrop-blur-md space-y-4">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <div>
              <h3 className="text-lg font-bold text-slate-100">Grounded Extracted Facts</h3>
              <p className="text-xs text-slate-400">Extracted {results.length} fact entities from circular text</p>
            </div>
            <span className="text-xs font-semibold px-2.5 py-1 bg-emerald-950/80 border border-emerald-700/60 text-emerald-300 rounded-full">
              Verified Entities
            </span>
          </div>

          {/* Results Table */}
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-slate-800 text-xs font-semibold text-slate-400 uppercase tracking-wider bg-slate-950/40">
                  <th className="py-3 px-4">Fact ID</th>
                  <th className="py-3 px-4">Category</th>
                  <th className="py-3 px-4">Raw Extracted Value</th>
                  <th className="py-3 px-4">Normalized Value</th>
                  <th className="py-3 px-4 text-right">Confidence Score</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 text-sm">
                {results.map((fact, idx) => (
                  <tr key={fact.fact_id || idx} className="hover:bg-slate-800/30 transition-colors">
                    <td className="py-3.5 px-4 font-mono text-xs text-slate-400">
                      {fact.fact_id || `f${idx + 1}`}
                    </td>
                    <td className="py-3.5 px-4">
                      <span className={`inline-block text-xs font-semibold px-2.5 py-0.5 rounded-full border ${getCategoryBadgeClass(fact.category)}`}>
                        {fact.category}
                      </span>
                    </td>
                    <td className="py-3.5 px-4 text-slate-200 font-medium">
                      {fact.raw_value}
                    </td>
                    <td className="py-3.5 px-4 text-amber-300/90 font-medium">
                      {fact.normalized_value || fact.raw_value}
                    </td>
                    <td className="py-3.5 px-4 text-right font-mono text-xs">
                      <span className={`px-2 py-0.5 rounded ${
                        fact.confidence_score >= 0.9
                          ? 'text-emerald-400 bg-emerald-950/60 border border-emerald-800/40'
                          : 'text-amber-400 bg-amber-950/60 border border-amber-800/40'
                      }`}>
                        {(fact.confidence_score * 100).toFixed(1)}%
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
