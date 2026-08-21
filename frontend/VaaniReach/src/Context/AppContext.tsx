
import { createContext, useContext, useState, type ReactNode } from 'react'
import type { NoticeVideoJob } from '../api/client'

export type Role = 'user' | 'admin' | null

export interface Circular {
  id: string
  title: string
  category: 'Agriculture' | 'Finance' | 'News' | 'Politics'
  date: string
  summary: string
}

/** Language codes the backend speaks, keyed by the label the UI shows.
 *  The screens were written with human-readable names ("Hindi"), while every
 *  backend route wants an ISO code ("hi"), so the translation has to happen
 *  somewhere -- doing it here keeps it in one place instead of in each page. */
export const LANGUAGE_CODES: Record<string, string> = {
  English: 'en',
  Hindi: 'hi',
  Bengali: 'bn',
  Tamil: 'ta',
  Telugu: 'te',
  Marathi: 'mr',
  Gujarati: 'gu',
  Kannada: 'kn',
  Malayalam: 'ml',
  Punjabi: 'pa',
  Odia: 'or',
  Assamese: 'as',
}

export const toLangCode = (label: string): string =>
  LANGUAGE_CODES[label] ?? label.toLowerCase().slice(0, 2)

export interface AppState {
  role: Role
  setRole: (r: Role) => void
  userName: string
  setUserName: (n: string) => void
  selectedCircular: Circular | null
  setSelectedCircular: (c: Circular | null) => void
  selectedLanguage: string
  setSelectedLanguage: (l: string) => void
  selectedAvatar: string
  setSelectedAvatar: (a: string) => void
  uploadedFileName: string
  setUploadedFileName: (n: string) => void
  targetLanguages: string[]
  setTargetLanguages: (l: string[]) => void

  /** The actual PDF, not just its name. The upload screen previously kept
   *  only the filename, so the file the officer chose was discarded before
   *  anything could be sent anywhere. */
  uploadedFile: File | null
  setUploadedFile: (f: File | null) => void

  /** Backend job id, set once the notice has been ingested. Every later step
   *  addresses the pipeline through this. */
  jobId: string | null
  setJobId: (id: string | null) => void

  /** Last job payload returned by the backend. Facts, scenes, audio paths and
   *  the rendered video all live on it, so the screens read from this rather
   *  than each holding a private copy that can drift. */
  job: NoticeVideoJob | null
  setJob: (j: NoticeVideoJob | null) => void

  /** Raw OCR text, kept so the fact screen can show the passage a fact was
   *  grounded in rather than a hardcoded quotation. */
  rawText: string
  setRawText: (t: string) => void

  /** Voice id chosen on the voice screen and used for synthesis. */
  selectedVoice: string
  setSelectedVoice: (v: string) => void

  /** Drop everything job-related. Used when starting a fresh notice, so a
   *  half-finished previous run cannot leak into the next one. */
  resetJob: () => void
}

const AppContext = createContext<AppState | undefined>(undefined)

export const AppProvider = ({ children }: { children: ReactNode }) => {
  const [role, setRole] = useState<Role>(null)
  const [userName, setUserName] = useState('')
  const [selectedCircular, setSelectedCircular] = useState<Circular | null>(null)
  const [selectedLanguage, setSelectedLanguage] = useState('')
  const [selectedAvatar, setSelectedAvatar] = useState('')
  const [uploadedFileName, setUploadedFileName] = useState('')
  const [targetLanguages, setTargetLanguages] = useState<string[]>(['Hindi', 'Tamil', 'Bengali'])

  const [uploadedFile, setUploadedFile] = useState<File | null>(null)
  const [jobId, setJobId] = useState<string | null>(null)
  const [job, setJob] = useState<NoticeVideoJob | null>(null)
  const [rawText, setRawText] = useState('')
  const [selectedVoice, setSelectedVoice] = useState('')

  const resetJob = () => {
    setJobId(null)
    setJob(null)
    setRawText('')
    setUploadedFile(null)
    setUploadedFileName('')
  }

  return (
    <AppContext.Provider
      value={{
        role,
        setRole,
        userName,
        setUserName,
        selectedCircular,
        setSelectedCircular,
        selectedLanguage,
        setSelectedLanguage,
        selectedAvatar,
        setSelectedAvatar,
        uploadedFileName,
        setUploadedFileName,
        targetLanguages,
        setTargetLanguages,
        uploadedFile,
        setUploadedFile,
        jobId,
        setJobId,
        job,
        setJob,
        rawText,
        setRawText,
        selectedVoice,
        setSelectedVoice,
        resetJob,
      }}
    >
      {children}
    </AppContext.Provider>
  )
}

// This hook intentionally shares the provider's context from this module.
// Keep the fast-refresh rule from treating this utility export as a component.
// eslint-disable-next-line react-refresh/only-export-components
export const useApp = () => {
  const ctx = useContext(AppContext)
  if (!ctx) throw new Error('useApp must be used within AppProvider')
  return ctx
}
