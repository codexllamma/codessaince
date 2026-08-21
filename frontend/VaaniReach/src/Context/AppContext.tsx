
import { createContext, useContext, useState, type ReactNode } from 'react'

export type Role = 'user' | 'admin' | null

export interface Circular {
  id: string
  title: string
  category: 'Agriculture' | 'Finance' | 'News' | 'Politics'
  date: string
  summary: string
}

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
