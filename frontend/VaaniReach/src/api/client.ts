const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';

export type FactCategory =
  | 'SCHEME_NAME'
  | 'AMOUNT'
  | 'DEADLINE'
  | 'ELIGIBILITY'
  | 'BENEFICIARY'
  | 'AUTHORITY'
  | 'ACTION_REQUIRED';

export interface ExtractedFact {
  fact_id: string;
  category: FactCategory;
  raw_value: string;
  normalized_value: string;
  source_page?: number;
  source_char_start: number;
  source_char_end: number;
  confidence_score: number;
  is_verified: boolean;
  officer_override?: string | null;
}

export interface ScriptSegment {
  type: 'filler' | 'core_fact';
  text: string;
  emphasis_level?: 'none' | 'moderate' | 'strong';
  pause_after_ms?: number;
  linked_fact_id?: string | null;
}

export interface VisualTextHierarchy {
  badge_tag: string;
  headline: string;
  subtext: string;
  highlight_metric?: string | null;
  highlight_sublabel?: string | null;
}

export interface VisualAssetSelection {
  asset_id: string;
  asset_type: 'video_loop' | 'static_graphic' | 'mesh_gradient';
  file_path: string;
  accent_color?: string;
  dim_overlay_opacity?: number;
}

export interface GestureInfo {
  name: string;
  /** neutral = resting, present = used on core facts, stress = deadline scenes */
  role: string;
  duration_sec: number;
}

export interface AvatarInfo {
  avatar_id: string;
  display_name: string;
  /** language codes, or '*' as a catch-all */
  languages: string[];
  source: 'synthetic' | 'licensed_stock' | 'consented_performer';
  licence: string;
  /** rendered on screen the whole time the presenter is visible */
  disclosure_label: string;
  /** empty when the avatar has no gesture sidecar — it loops instead */
  gestures: GestureInfo[];
}

export interface WordTimestamp {
  word: string;
  start_sec: number;
  end_sec: number;
  is_core_fact?: boolean;
}

export interface SceneDefinition {
  scene_id: number;
  template_type: 'HERO_ANNOUNCEMENT' | 'METRIC_FOCUS' | 'DEADLINE_ALERT' | 'OUTRO_CALL_TO_ACTION';
  script_segments: ScriptSegment[];
  full_spoken_text: string;
  visual_hierarchy: VisualTextHierarchy;
  asset: VisualAssetSelection;
  audio_path?: string | null;
  scene_duration_sec?: number | null;
  subtitles?: WordTimestamp[] | null;
}

export interface PipelineTelemetry {
  ocr_latency_sec?: number;
  extraction_confidence_avg?: number;
  nli_entailment_score?: number;
  entity_preservation_rate?: number;
  speech_visual_drift_ms?: number;
}

export interface NoticeVideoJob {
  job_id: string;
  source_file_name: string;
  raw_extracted_text: string;
  target_languages: string[];
  selected_voice_id: string;
  voice_speed_modifier: string;
  extracted_facts: ExtractedFact[];
  master_scenes_en: SceneDefinition[];
  localized_scenes: Record<string, SceneDefinition[]>;
  telemetry?: PipelineTelemetry;
  officer_approved: boolean;
  final_video_paths: Record<string, string>;
  final_srt_paths?: Record<string, string>;
}

export interface WarmupComponentStatus {
  ok: boolean;
  detail: string;
  elapsed_sec: number;
}

export interface WarmupResponse {
  wav2lip: WarmupComponentStatus;
  ollama: WarmupComponentStatus;
  total_elapsed_sec: number;
}

export interface UploadDocResult {
  status: string;
  extracted_facts: ExtractedFact[];
  results: ExtractedFact[];
  raw_text: string;
  pages_processed: number;
}

export const api = {
  // Check Backend Health
  checkHealth: async (): Promise<boolean> => {
    try {
      const res = await fetch(`${BASE_URL}/health`, { method: 'GET' });
      return res.ok;
    } catch {
      return false;
    }
  },

  // Upload a circular PDF: streams it to the backend, which runs OCR (in an
  // isolated subprocess) and grounded fact extraction in one call. This is
  // the entry point for the "user picks a file" flow, upstream of createJob
  // — the raw text it returns is what createJob takes as input.
  uploadDocument: async (file: File, lang: string = 'en'): Promise<UploadDocResult> => {
    const form = new FormData();
    form.append('file', file);
    form.append('lang', lang);
    const res = await fetch(`${BASE_URL}/api/jobs/upload-doc`, {
      method: 'POST',
      body: form,
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  // 1. Initialize Job
  createJob: async (
    rawText: string,
    sourceFileName: string = 'notice.pdf',
    targetLangs: string[] = ['en', 'hi'],
    voiceId: string = 'en-IN-PrabhatNeural',
    speedMod: string = '+0%',
    primaryLang?: string
  ): Promise<NoticeVideoJob> => {
    const res = await fetch(`${BASE_URL}/api/jobs`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        raw_extracted_text: rawText,
        source_file_name: sourceFileName,
        target_languages: targetLangs,
        selected_voice_id: voiceId,
        voice_speed_modifier: speedMod,
        primary_lang: primaryLang,
      }),
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  // Get Existing Job
  getJob: async (jobId: string): Promise<NoticeVideoJob> => {
    const res = await fetch(`${BASE_URL}/api/jobs/${jobId}`);
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  // 2. Extract Facts
  extractFacts: async (jobId: string): Promise<NoticeVideoJob> => {
    const res = await fetch(`${BASE_URL}/api/jobs/${jobId}/extract-facts`, { method: 'POST' });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  // Update Facts / Officer Overrides
  updateFacts: async (jobId: string, facts: ExtractedFact[]): Promise<NoticeVideoJob> => {
    const res = await fetch(`${BASE_URL}/api/jobs/${jobId}/facts`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ extracted_facts: facts }),
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  // 3. Generate Scenes & Translations
  generateScenes: async (jobId: string): Promise<NoticeVideoJob> => {
    const res = await fetch(`${BASE_URL}/api/jobs/${jobId}/generate-scenes`, { method: 'POST' });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  // Update Scenes
  updateScenes: async (jobId: string, lang: string, scenes: SceneDefinition[]): Promise<NoticeVideoJob> => {
    const res = await fetch(`${BASE_URL}/api/jobs/${jobId}/scenes`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ language: lang, scenes }),
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  // 4. Synthesize Edge-TTS Audio & Timestamps
  synthesizeAudio: async (jobId: string): Promise<NoticeVideoJob> => {
    const res = await fetch(`${BASE_URL}/api/jobs/${jobId}/synthesize`, { method: 'POST' });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  // 5. Officer Verification Gate
  approveJob: async (jobId: string, notes?: string): Promise<NoticeVideoJob> => {
    const res = await fetch(`${BASE_URL}/api/jobs/${jobId}/approve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ approved: true, notes }),
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  // 6. Render Video Broadcast
  renderVideo: async (jobId: string, lang?: string, avatarId?: string): Promise<NoticeVideoJob> => {
    const params = new URLSearchParams();
    if (lang) params.append('lang', lang);
    if (avatarId) params.append('avatar_id', avatarId);
    
    const url = `${BASE_URL}/api/jobs/${jobId}/render${params.toString() ? '?' + params.toString() : ''}`;
    const res = await fetch(url, { method: 'POST' });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  // One-shot pipeline for the citizen-facing flow: pick a language, a
  // presenter and a voice, get a finished video back.
  //
  // Note what this does NOT do: it reads a pre-generated notice PDF on the
  // server (ocr_engine/extensive_test_<lang>.pdf) rather than anything the
  // caller uploads. The officer flow is the one that ingests a real document
  // -- upload-doc, then createJob and the per-stage routes below. Do not use
  // this for a notice a user supplied; it will silently narrate a different
  // document.
  //
  // Runs OCR, extraction, narration, lip-sync and the render in one request,
  // so it takes MINUTES. Give it a long-running UI, not a spinner that looks
  // like it hung.
  runE2E: async (
    lang: string,
    character: string,
    voice: string
  ): Promise<{ status: string; video_path: string; facts: ExtractedFact[] }> => {
    const res = await fetch(`${BASE_URL}/api/jobs/run-e2e`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ lang, character, voice }),
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  // Pre-load Wav2Lip and Ollama before the officer starts a real job, so the
  // first render/extraction doesn't pay their one-time cold-start cost while
  // someone is watching a progress bar. Never throws for a component that
  // failed to warm -- per-component `ok` says whether it actually loaded; a
  // missing Ollama install is a normal, reportable state, not an error.
  warmup: async (): Promise<WarmupResponse> => {
    const res = await fetch(`${BASE_URL}/api/warmup`, { method: 'POST' });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  // 7. Registered presenters and the gestures each can perform.
  // An empty array is normal — it means no presenter is installed and the
  // compositor renders its full-width layout instead.
  listAvatars: async (): Promise<AvatarInfo[]> => {
    const res = await fetch(`${BASE_URL}/api/avatars`);
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  // Get dynamic card preview URL
  getCardPreviewUrl: (lang: string) => `${BASE_URL}/api/test/preview-card/${lang}?t=${Date.now()}`,

  // Resolve static video URL
  getVideoUrl: (relativePath: string) => {
    if (!relativePath) return '';
    return relativePath.startsWith('http') ? relativePath : `${BASE_URL}${relativePath}`;
  },

  // Resolve static audio URL
  getAudioUrl: (relativePath: string) => {
    if (!relativePath) return '';
    return relativePath.startsWith('http') ? relativePath : `${BASE_URL}${relativePath}`;
  },

  // Resolve static SRT URL
  getSrtUrl: (relativePath: string) => {
    if (!relativePath) return '';
    return relativePath.startsWith('http') ? relativePath : `${BASE_URL}${relativePath}`;
  },
};
