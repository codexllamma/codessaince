import React from 'react';
import { FileInput, Network, Layers, Mic, ShieldAlert, Check } from 'lucide-react';

export interface StepItem {
  id: number;
  label: string;
  sublabel: string;
}

interface Props {
  currentStep: number;
  maxStepReached: number;
  onSelectStep: (stepId: number) => void;
}

const STEPS: { id: number; label: string; sublabel: string; icon: React.FC<{ className?: string }> }[] = [
  { id: 1, label: 'Notice Ingest', sublabel: 'Upload & Target Languages', icon: FileInput },
  { id: 2, label: 'Fact Grounding', sublabel: 'Entity Extraction & Edit', icon: Network },
  { id: 3, label: 'Storyboard', sublabel: 'Multilingual Card Layouts', icon: Layers },
  { id: 4, label: 'Voice & Karaoke', sublabel: 'Neural TTS & Word Timings', icon: Mic },
  { id: 5, label: 'Officer Approval', sublabel: 'Sign-Off & Broadcast Video', icon: ShieldAlert },
];

export const Stepper: React.FC<Props> = ({
  currentStep,
  maxStepReached,
  onSelectStep,
}) => {
  return (
    <nav aria-label="Pipeline Progress" className="w-full max-w-5xl mx-auto my-8 px-4">
      <div className="relative flex items-center justify-between">
        {/* Background Connecting Line */}
        <div className="absolute top-1/2 left-0 w-full h-1 bg-white/10 -translate-y-1/2 z-0" />
        
        {/* Active Progress Line */}
        <div
          className="absolute top-1/2 left-0 h-1 bg-gradient-to-r from-cyan-500 via-blue-500 to-emerald-500 -translate-y-1/2 transition-all duration-500 z-0"
          style={{ width: `${((Math.min(maxStepReached, 5) - 1) / (STEPS.length - 1)) * 100}%` }}
        />

        {STEPS.map((step) => {
          const Icon = step.icon;
          const isCompleted = step.id < currentStep || (step.id <= maxStepReached && step.id !== currentStep);
          const isActive = step.id === currentStep;
          const isAccessible = step.id <= maxStepReached;

          return (
            <button
              key={step.id}
              type="button"
              disabled={!isAccessible}
              onClick={() => onSelectStep(step.id)}
              className={`relative z-10 flex flex-col items-center gap-2 group transition-all ${
                !isAccessible ? 'cursor-not-allowed opacity-50' : 'cursor-pointer'
              }`}
            >
              {/* Step Circle */}
              <div
                className={`w-12 h-12 rounded-full flex items-center justify-center font-bold text-sm transition-all duration-300 border-2 ${
                  isActive
                    ? 'bg-gradient-to-tr from-cyan-500 to-blue-600 border-cyan-300 text-white shadow-lg shadow-cyan-500/40 scale-110'
                    : isCompleted
                    ? 'bg-emerald-600 border-emerald-400 text-white'
                    : 'bg-[#0D1424] border-white/20 text-slate-400 group-hover:border-white/40'
                }`}
              >
                {isCompleted && !isActive ? (
                  <Check className="w-5 h-5 text-white" />
                ) : (
                  <Icon className="w-5 h-5" />
                )}
              </div>

              {/* Step Text */}
              <div className="text-center">
                <span
                  className={`block text-xs font-bold uppercase tracking-wider transition-colors ${
                    isActive
                      ? 'text-cyan-400'
                      : isCompleted
                      ? 'text-emerald-400'
                      : 'text-slate-400'
                  }`}
                >
                  {step.label}
                </span>
                <span className="block text-[11px] text-slate-500 hidden sm:block">
                  {step.sublabel}
                </span>
              </div>
            </button>
          );
        })}
      </div>
    </nav>
  );
};
