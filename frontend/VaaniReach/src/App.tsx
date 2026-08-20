import React, { useState, useEffect } from 'react';
import { Navbar } from './Components/Navbar';
import { Stepper } from './Components/Stepper';
import { NoticeIngestion } from './Features/NoticeIngestion';
import type { IngestConfig } from './Features/NoticeIngestion';
import { Factverify } from './Features/Factverify';
import { StoryboardEditor } from './Features/StoryboardEditor';
import { AudioGeneration } from './Features/AudioGeneration';
import { OfficerApprovalPanel } from './Features/OfficerApprovalPanel';
import { api } from './api/client';
import type { NoticeVideoJob, ExtractedFact } from './api/client';
import { AlertTriangle, CheckCircle2, X } from 'lucide-react';
import './App.css';

const PRESETS: Record<string, IngestConfig> = {
  pmkisan: {
    rawText: 'Ministry of Agriculture: PM-KISAN 17th installment of Rs 2000. Complete verification before 31-10-2026.',
    sourceFileName: 'pmkisan_17th_notice.pdf',
    targetLangs: ['en', 'hi', 'ta', 'te'],
    voiceId: 'en-IN-PrabhatNeural',
    speedMod: '+0%',
  },
  dbt_scholarship: {
    rawText: 'Ministry of Education: National Means-cum-Merit Scholarship disbursement of Rs 12000 per annum for eligible secondary students. Complete online verification on NSP portal before 30-11-2026.',
    sourceFileName: 'dbt_scholarship_gazette.pdf',
    targetLangs: ['en', 'hi', 'bn', 'mr'],
    voiceId: 'en-IN-PrabhatNeural',
    speedMod: '+0%',
  },
  soil_health: {
    rawText: 'Ministry of Agriculture: Distribution of Soil Health Cards across 100 rural districts with direct laboratory testing subsidy of Rs 500 per sample. Complete registration before 15-12-2026.',
    sourceFileName: 'soil_health_circular.pdf',
    targetLangs: ['en', 'hi', 'te', 'ta'],
    voiceId: 'en-IN-PrabhatNeural',
    speedMod: '+0%',
  },
};

export const App: React.FC = () => {
  const [currentStep, setCurrentStep] = useState<number>(1);
  const [maxStepReached, setMaxStepReached] = useState<number>(1);
  const [job, setJob] = useState<NoticeVideoJob | null>(null);
  const [ingestConfig, setIngestConfig] = useState<IngestConfig>(PRESETS.pmkisan);
  const [backendOnline, setBackendOnline] = useState<boolean>(true);
  const [loading, setLoading] = useState<boolean>(false);
  const [rendering, setRendering] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Poll Backend Health on mount
  useEffect(() => {
    const check = async () => {
      const isUp = await api.checkHealth();
      setBackendOnline(isUp);
    };
    check();
    const interval = setInterval(check, 10000);
    return () => clearInterval(interval);
  }, []);

  const handleLoadPreset = (key: string) => {
    if (PRESETS[key]) {
      setIngestConfig(PRESETS[key]);
      setSuccessMsg(`Loaded preset: ${key.toUpperCase()}`);
      setTimeout(() => setSuccessMsg(null), 3000);
    }
  };

  // Step 1: Create Job & Extract Facts
  const handleIngestSubmit = async (config: IngestConfig) => {
    setLoading(true);
    setErrorMsg(null);
    try {
      // 1. Create Job
      const newJob = await api.createJob(
        config.rawText,
        config.sourceFileName,
        config.targetLangs,
        config.voiceId,
        config.speedMod
      );

      // 2. Extract Facts
      const extractedJob = await api.extractFacts(newJob.job_id);
      setJob(extractedJob);
      setCurrentStep(2);
      setMaxStepReached(Math.max(maxStepReached, 2));
      setSuccessMsg(`Extracted ${extractedJob.extracted_facts.length} grounded facts.`);
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to initialize job or extract facts.');
    } finally {
      setLoading(false);
    }
  };

  // Step 2: Save Facts & Generate Scenes
  const handleSaveFacts = async (updatedFacts: ExtractedFact[]) => {
    if (!job) return;
    setLoading(true);
    setErrorMsg(null);
    try {
      const updatedJob = await api.updateFacts(job.job_id, updatedFacts);
      setJob(updatedJob);
      setSuccessMsg('Fact overrides saved successfully.');
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to save facts.');
    } finally {
      setLoading(false);
    }
  };

  const handleGenerateScenes = async () => {
    if (!job) return;
    setLoading(true);
    setErrorMsg(null);
    try {
      const updatedJob = await api.generateScenes(job.job_id);
      setJob(updatedJob);
      setCurrentStep(3);
      setMaxStepReached(Math.max(maxStepReached, 3));
      setSuccessMsg(`Generated ${updatedJob.master_scenes_en.length} scenes localized across languages.`);
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to generate scenes.');
    } finally {
      setLoading(false);
    }
  };

  // Step 3 -> 4: Proceed to Audio Studio
  const handleProceedToAudio = () => {
    setCurrentStep(4);
    setMaxStepReached(Math.max(maxStepReached, 4));
  };

  // Step 4: Synthesize Audio & Subtitles
  const handleSynthesizeAudio = async () => {
    if (!job) return;
    setLoading(true);
    setErrorMsg(null);
    try {
      const updatedJob = await api.synthesizeAudio(job.job_id);
      setJob(updatedJob);
      setSuccessMsg('Neural TTS speech and word-level timestamps synthesized successfully.');
    } catch (err: any) {
      setErrorMsg(err.message || 'Audio synthesis failed. Check edge-tts connection.');
    } finally {
      setLoading(false);
    }
  };

  // Step 4 -> 5: Proceed to Approval Gate
  const handleProceedToApproval = () => {
    setCurrentStep(5);
    setMaxStepReached(Math.max(maxStepReached, 5));
  };

  // Step 5: Officer Approve Job
  const handleApproveJob = async (notes?: string) => {
    if (!job) return;
    setLoading(true);
    setErrorMsg(null);
    try {
      const updatedJob = await api.approveJob(job.job_id, notes);
      setJob(updatedJob);
      setSuccessMsg('Digital Officer Seal applied. Broadcast rendering unlocked.');
    } catch (err: any) {
      setErrorMsg(err.message || 'Approval sign-off failed.');
    } finally {
      setLoading(false);
    }
  };

  // Step 5: Render Video Broadcast
  const handleRenderVideo = async () => {
    if (!job) return;
    setRendering(true);
    setErrorMsg(null);
    try {
      const updatedJob = await api.renderVideo(job.job_id);
      setJob(updatedJob);
      setSuccessMsg('All multilingual video broadcasts rendered successfully!');
    } catch (err: any) {
      setErrorMsg(err.message || 'Video composition & rendering failed.');
    } finally {
      setRendering(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#070B14] text-slate-100 flex flex-col font-sans">
      {/* Top Navigation */}
      <Navbar
        jobId={job?.job_id}
        jobStatus={job?.officer_approved ? 'APPROVED' : job?.extracted_facts.length ? 'ACTIVE' : undefined}
        backendOnline={backendOnline}
        onLoadPreset={handleLoadPreset}
      />

      <main className="flex-1 max-w-[1440px] w-full mx-auto px-4 sm:px-6 py-6 space-y-6">
        {/* Toast Alerts */}
        {errorMsg && (
          <div className="p-4 rounded-xl bg-rose-950/80 border border-rose-500/40 text-rose-200 text-xs flex items-center justify-between shadow-lg animate-fade-in">
            <div className="flex items-center gap-2.5">
              <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0" />
              <span>{errorMsg}</span>
            </div>
            <button
              type="button"
              onClick={() => setErrorMsg(null)}
              className="p-1 text-rose-400 hover:text-white"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        )}

        {successMsg && (
          <div className="p-4 rounded-xl bg-emerald-950/80 border border-emerald-500/40 text-emerald-200 text-xs flex items-center justify-between shadow-lg animate-fade-in">
            <div className="flex items-center gap-2.5">
              <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
              <span>{successMsg}</span>
            </div>
            <button
              type="button"
              onClick={() => setSuccessMsg(null)}
              className="p-1 text-emerald-400 hover:text-white"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        )}

        {/* Stepper Header */}
        <Stepper
          currentStep={currentStep}
          maxStepReached={maxStepReached}
          onSelectStep={(stepId) => setCurrentStep(stepId)}
        />

        {/* Pipeline Stage Content */}
        <div className="pt-2">
          {currentStep === 1 && (
            <NoticeIngestion
              initialConfig={ingestConfig}
              onSubmit={handleIngestSubmit}
              loading={loading}
            />
          )}

          {currentStep === 2 && job && (
            <Factverify
              facts={job.extracted_facts}
              onSaveFacts={handleSaveFacts}
              onGenerateScenes={handleGenerateScenes}
              loading={loading}
            />
          )}

          {currentStep === 3 && job && (
            <StoryboardEditor
              masterScenes={job.master_scenes_en}
              localizedScenes={job.localized_scenes}
              targetLangs={job.target_languages}
              onProceedToAudio={handleProceedToAudio}
            />
          )}

          {currentStep === 4 && job && (
            <AudioGeneration
              masterScenes={job.master_scenes_en}
              localizedScenes={job.localized_scenes}
              targetLangs={job.target_languages}
              onSynthesize={handleSynthesizeAudio}
              onProceedToApproval={handleProceedToApproval}
              loading={loading}
            />
          )}

          {currentStep === 5 && job && (
            <OfficerApprovalPanel
              job={job}
              onApproveJob={handleApproveJob}
              onRenderVideo={handleRenderVideo}
              loading={loading}
              rendering={rendering}
            />
          )}
        </div>
      </main>

      {/* Global Footer */}
      <footer className="border-t border-white/10 py-6 text-center text-xs text-slate-500 bg-[#090E1A]/60">
        <div className="max-w-[1440px] mx-auto px-4 flex flex-wrap items-center justify-between gap-4">
          <p>© 2026 VaaniReach • National Multilingual Circular Dissemination Engine</p>
          <div className="flex items-center gap-4 text-slate-400">
            <span>Edge-TTS 2.0</span>
            <span>•</span>
            <span>HarfBuzz Complex Script Shaping</span>
            <span>•</span>
            <span>FFmpeg NVENC / libx264</span>
          </div>
        </div>
      </footer>
    </div>
  );
};

export default App;