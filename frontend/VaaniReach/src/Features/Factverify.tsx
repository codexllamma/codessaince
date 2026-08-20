import React, { useState } from 'react';
import {
  CheckCircle,
  Edit3,
  Plus,
  Trash2,
  Save,
  ArrowRight,
  Loader2,
  Sparkles,
  AlertTriangle,
} from 'lucide-react';
import type { ExtractedFact, FactCategory } from '../api/client';

interface Props {
  facts: ExtractedFact[];
  onSaveFacts: (updatedFacts: ExtractedFact[]) => Promise<void>;
  onGenerateScenes: () => Promise<void>;
  loading: boolean;
}

const CATEGORIES: { value: FactCategory; label: string; colorClass: string }[] = [
  { value: 'SCHEME_NAME', label: 'Scheme / Initiative', colorClass: 'badge-SCHEME_NAME' },
  { value: 'AMOUNT', label: 'Disbursement Amount', colorClass: 'badge-AMOUNT' },
  { value: 'DEADLINE', label: 'Compliance Deadline', colorClass: 'badge-DEADLINE' },
  { value: 'AUTHORITY', label: 'Issuing Authority', colorClass: 'badge-AUTHORITY' },
  { value: 'ACTION_REQUIRED', label: 'Mandatory Action', colorClass: 'badge-ACTION_REQUIRED' },
  { value: 'ELIGIBILITY', label: 'Eligibility Criterion', colorClass: 'badge-ELIGIBILITY' },
  { value: 'BENEFICIARY', label: 'Target Beneficiary', colorClass: 'badge-BENEFICIARY' },
];

export const Factverify: React.FC<Props> = ({
  facts: initialFacts,
  onSaveFacts,
  onGenerateScenes,
  loading,
}) => {
  const [facts, setFacts] = useState<ExtractedFact[]>(initialFacts);
  const [editingFactId, setEditingFactId] = useState<string | null>(null);
  const [editValue, setEditValue] = useState<string>('');
  const [isAddingNew, setIsAddingNew] = useState<boolean>(false);
  const [newCategory, setNewCategory] = useState<FactCategory>('SCHEME_NAME');
  const [newRawVal, setNewRawVal] = useState<string>('');
  const [newNormVal, setNewNormVal] = useState<string>('');
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState<boolean>(false);

  const startEdit = (fact: ExtractedFact) => {
    setEditingFactId(fact.fact_id);
    setEditValue(fact.officer_override || fact.normalized_value);
  };

  const saveEdit = (factId: string) => {
    setFacts((prev) =>
      prev.map((f) => {
        if (f.fact_id === factId) {
          return {
            ...f,
            normalized_value: editValue,
            officer_override: editValue,
            is_verified: true,
          };
        }
        return f;
      })
    );
    setEditingFactId(null);
    setHasUnsavedChanges(true);
  };

  const removeFact = (factId: string) => {
    setFacts((prev) => prev.filter((f) => f.fact_id !== factId));
    setHasUnsavedChanges(true);
  };

  const handleAddNewFact = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newNormVal.trim()) return;

    const newFact: ExtractedFact = {
      fact_id: `custom_${Date.now()}`,
      category: newCategory,
      raw_value: newRawVal.trim() || newNormVal.trim(),
      normalized_value: newNormVal.trim(),
      source_char_start: 0,
      source_char_end: 0,
      confidence_score: 1.0,
      is_verified: true,
      officer_override: newNormVal.trim(),
    };

    setFacts((prev) => [...prev, newFact]);
    setIsAddingNew(false);
    setNewRawVal('');
    setNewNormVal('');
    setHasUnsavedChanges(true);
  };

  const handleSaveAll = async () => {
    await onSaveFacts(facts);
    setHasUnsavedChanges(false);
  };

  return (
    <div className="glass-panel p-8 max-w-5xl mx-auto space-y-8">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-white/10 pb-6">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-2xl font-black text-white">2. Grounded Fact Matrix</h2>
            <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
              Stage 2 / 5
            </span>
          </div>
          <p className="text-sm text-slate-400 mt-1">
            Validate extracted entity pairs and apply officer overrides before scene script generation.
          </p>
        </div>

        <div className="flex items-center gap-3">
          {hasUnsavedChanges && (
            <button
              type="button"
              onClick={handleSaveAll}
              disabled={loading}
              className="btn-secondary text-amber-300 border-amber-500/30 hover:bg-amber-950/40 text-xs"
            >
              <Save className="w-3.5 h-3.5" />
              Save Overrides
            </button>
          )}

          <button
            type="button"
            onClick={() => setIsAddingNew(!isAddingNew)}
            className="btn-secondary text-xs"
          >
            <Plus className="w-3.5 h-3.5" />
            {isAddingNew ? 'Cancel' : 'Add Fact'}
          </button>
        </div>
      </div>

      {/* Add New Fact Form */}
      {isAddingNew && (
        <form
          onSubmit={handleAddNewFact}
          className="p-5 rounded-xl bg-[#090E1A]/90 border border-cyan-500/30 space-y-4 animate-fade-in"
        >
          <div className="flex items-center gap-2 text-cyan-300 text-xs font-bold uppercase">
            <Sparkles className="w-4 h-4" /> Add Officer Grounded Fact Entity
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div>
              <label className="text-[11px] uppercase font-bold text-slate-400 block mb-1">
                Category
              </label>
              <select
                value={newCategory}
                onChange={(e) => setNewCategory(e.target.value as FactCategory)}
                className="w-full bg-slate-900 border border-white/15 rounded-lg px-3 py-2 text-xs text-white"
              >
                {CATEGORIES.map((c) => (
                  <option key={c.value} value={c.value}>
                    {c.label}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="text-[11px] uppercase font-bold text-slate-400 block mb-1">
                Raw Phrase
              </label>
              <input
                type="text"
                value={newRawVal}
                onChange={(e) => setNewRawVal(e.target.value)}
                placeholder="e.g. 17th kist"
                className="w-full bg-slate-900 border border-white/15 rounded-lg px-3 py-2 text-xs text-white"
              />
            </div>

            <div>
              <label className="text-[11px] uppercase font-bold text-slate-400 block mb-1">
                Normalized Fact Value *
              </label>
              <input
                type="text"
                required
                value={newNormVal}
                onChange={(e) => setNewNormVal(e.target.value)}
                placeholder="e.g. 17th Installment"
                className="w-full bg-slate-900 border border-cyan-500/40 rounded-lg px-3 py-2 text-xs text-white"
              />
            </div>
          </div>

          <div className="flex justify-end gap-2">
            <button
              type="submit"
              className="btn-primary py-1.5 px-4 text-xs font-bold"
            >
              Add to Matrix
            </button>
          </div>
        </form>
      )}

      {/* Facts Matrix Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {facts.map((fact) => {
          const isEditing = editingFactId === fact.fact_id;
          const catInfo = CATEGORIES.find((c) => c.value === fact.category) || {
            label: fact.category,
            colorClass: 'badge-SCHEME_NAME',
          };

          return (
            <div
              key={fact.fact_id}
              className="glass-card p-5 flex flex-col justify-between gap-3 relative overflow-hidden group"
            >
              {/* Category & Status Badges */}
              <div className="flex items-center justify-between gap-2">
                <span className={`badge-category ${catInfo.colorClass}`}>
                  {catInfo.label}
                </span>

                <div className="flex items-center gap-2">
                  <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-300">
                    {Math.round(fact.confidence_score * 100)}% conf
                  </span>
                  {fact.officer_override && (
                    <span className="text-[10px] font-bold uppercase px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-300 border border-amber-500/30">
                      Overridden
                    </span>
                  )}
                </div>
              </div>

              {/* Normalized Value (or Inline Editor) */}
              {isEditing ? (
                <div className="space-y-2 py-1">
                  <label className="text-[11px] text-slate-400 font-bold uppercase">
                    Edit Normalized Value:
                  </label>
                  <input
                    type="text"
                    value={editValue}
                    onChange={(e) => setEditValue(e.target.value)}
                    className="w-full bg-slate-950 border border-cyan-400 rounded-lg p-2 text-sm text-white font-semibold focus:outline-none"
                    autoFocus
                  />
                  <div className="flex justify-end gap-2">
                    <button
                      type="button"
                      onClick={() => setEditingFactId(null)}
                      className="px-2.5 py-1 rounded text-xs text-slate-400 hover:bg-slate-800"
                    >
                      Cancel
                    </button>
                    <button
                      type="button"
                      onClick={() => saveEdit(fact.fact_id)}
                      className="btn-primary py-1 px-3 text-xs"
                    >
                      Apply
                    </button>
                  </div>
                </div>
              ) : (
                <div>
                  <div className="text-lg font-bold text-white tracking-tight">
                    {fact.normalized_value}
                  </div>
                  <div className="text-xs text-slate-400 mt-1 flex items-center gap-1.5 font-mono">
                    <span>Raw:</span>
                    <span className="text-slate-300 italic">"{fact.raw_value}"</span>
                  </div>
                </div>
              )}

              {/* Actions Footer */}
              <div className="flex items-center justify-between pt-2 border-t border-white/5 text-xs text-slate-400">
                <span className="text-[11px] font-mono text-slate-500">
                  Span: [{fact.source_char_start}..{fact.source_char_end}]
                </span>

                <div className="flex items-center gap-1">
                  {!isEditing && (
                    <button
                      type="button"
                      onClick={() => startEdit(fact)}
                      className="p-1.5 rounded hover:bg-slate-800 text-slate-400 hover:text-cyan-300 transition-colors"
                      title="Edit fact value"
                    >
                      <Edit3 className="w-3.5 h-3.5" />
                    </button>
                  )}
                  <button
                    type="button"
                    onClick={() => removeFact(fact.fact_id)}
                    className="p-1.5 rounded hover:bg-rose-950/40 text-slate-500 hover:text-rose-400 transition-colors"
                    title="Remove fact"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {facts.length === 0 && (
        <div className="text-center py-12 border-2 border-dashed border-white/10 rounded-xl space-y-3">
          <AlertTriangle className="w-8 h-8 text-amber-400 mx-auto" />
          <div className="text-slate-300 font-semibold">No grounded facts extracted.</div>
          <p className="text-xs text-slate-500 max-w-sm mx-auto">
            Click "Add Fact" above to manually specify claims or check the circular text in Step 1.
          </p>
        </div>
      )}

      {/* Advance to Storyboard Step */}
      <div className="pt-4 border-t border-white/10 flex flex-wrap items-center justify-between gap-4">
        <div className="text-xs text-slate-400 flex items-center gap-2">
          <CheckCircle className="w-4 h-4 text-emerald-400" />
          <span>{facts.length} Verified entity facts ready for multilingual storyboard mapping.</span>
        </div>

        <button
          type="button"
          onClick={onGenerateScenes}
          disabled={loading || facts.length === 0}
          className="btn-primary py-3 px-6 text-sm"
        >
          {loading ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              Generating Multilingual Scenes...
            </>
          ) : (
            <>
              Generate Multilingual Storyboard
              <ArrowRight className="w-4 h-4" />
            </>
          )}
        </button>
      </div>
    </div>
  );
};
