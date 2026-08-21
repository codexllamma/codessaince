import { useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { toast } from 'react-toastify'
import { UploadCloud, FileText, CheckCircle2, ArrowRight, Flame, Loader2, CircleCheck, CircleAlert } from 'lucide-react'
import PageShell from '../../Components/PageShell'
import Card from '../../Components/UI/Card'
import Button from '../../Components/UI/Button'
import StepProgress from '../../Components/UI/StepProgress'
import { useApp } from '../../Context/AppContext'
import { api, type WarmupResponse } from '../../api/client'

const STEPS = ['Upload', 'Categorize', 'Ingest', 'Fact grounding', 'Storyboard', 'Voice', 'Approval']

/** The dropzone promises "PDF up to 25MB", so enforce exactly that here rather
 *  than letting the backend reject a multi-minute upload after the fact. */
const MAX_BYTES = 25 * 1024 * 1024

export default function UploadPdf() {
  const navigate = useNavigate()
  const { uploadedFile, setUploadedFile, uploadedFileName, setUploadedFileName, resetJob } = useApp()
  const [dragging, setDragging] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  const [warmingUp, setWarmingUp] = useState(false)
  const [warmupResult, setWarmupResult] = useState<WarmupResponse | null>(null)

  const handleWarmup = async () => {
    setWarmingUp(true)
    try {
      const result = await api.warmup()
      setWarmupResult(result)
      if (result.wav2lip.ok) {
        toast.success(`Presenter model ready (${result.total_elapsed_sec.toFixed(1)}s).`)
      } else {
        toast.error('Presenter model failed to warm up — check the backend log.')
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Warmup request failed.')
    } finally {
      setWarmingUp(false)
    }
  }

  const handleFile = (file?: File) => {
    // No fallback filename: a missing file has to stay missing, otherwise the
    // flow walks forward with a document that does not exist.
    if (!file) {
      toast.error('No file was received. Pick the PDF again.')
      return
    }

    const isPdf = file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf')
    if (!isPdf) {
      toast.error(`"${file.name}" is not a PDF. Only PDF notices can be processed.`)
      return
    }

    if (file.size > MAX_BYTES) {
      toast.error(`"${file.name}" is ${(file.size / 1024 / 1024).toFixed(1)}MB — the limit is 25MB.`)
      return
    }

    // A new document invalidates whatever a previous run produced, so drop the
    // old job before the new file is held.
    resetJob()
    setUploadedFile(file)
    setUploadedFileName(file.name)
    toast.success(`"${file.name}" selected. It is sent for reading at the ingest step.`)
  }

  return (
    <PageShell showBack backTo="/role">
      <div className="pt-4 sm:pt-8">
        <StepProgress steps={STEPS} current={0} />

        <h1 className="mt-8 font-display text-3xl font-semibold text-plum-900">Upload a notice</h1>
        <p className="mt-2 text-plum-800/70">Start with the official press release or notice as a PDF.</p>

        {/* Optional, independent of the upload flow: loads the presenter
            model and the local LLM extractor ahead of time, so their one-time
            cold-start cost doesn't land on the officer during a real render. */}
        <Card className="mt-6 flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-skycandy-100 text-skycandy-600">
              <Flame size={18} />
            </span>
            <div>
              <p className="text-sm font-medium text-plum-900">Warm up models</p>
              <p className="text-xs text-plum-800/55">
                Loads the presenter and extraction models now, so the render step doesn't wait on it later.
              </p>
            </div>
          </div>
          <Button
            size="sm"
            variant="outline"
            onClick={() => void handleWarmup()}
            disabled={warmingUp}
            icon={warmingUp ? <Loader2 size={15} className="animate-spin" /> : <Flame size={15} />}
          >
            {warmingUp ? 'Warming up…' : 'Warm up now'}
          </Button>
        </Card>

        {warmupResult && (
          <div className="mt-3 flex flex-wrap gap-3 text-xs">
            <span
              className={`flex items-center gap-1.5 rounded-full px-3 py-1 font-medium ${
                warmupResult.wav2lip.ok ? 'bg-green-100 text-green-700' : 'bg-orange-100 text-orange-700'
              }`}
              title={warmupResult.wav2lip.detail}
            >
              {warmupResult.wav2lip.ok ? <CircleCheck size={13} /> : <CircleAlert size={13} />}
              Presenter (Wav2Lip): {warmupResult.wav2lip.ok ? `ready in ${warmupResult.wav2lip.elapsed_sec}s` : 'failed'}
            </span>
            <span
              className={`flex items-center gap-1.5 rounded-full px-3 py-1 font-medium ${
                warmupResult.ollama.ok ? 'bg-green-100 text-green-700' : 'bg-plum-800/10 text-plum-800/60'
              }`}
              title={warmupResult.ollama.detail}
            >
              {warmupResult.ollama.ok ? <CircleCheck size={13} /> : <CircleAlert size={13} />}
              Extraction (Ollama): {warmupResult.ollama.ok ? `ready in ${warmupResult.ollama.elapsed_sec}s` : 'not available'}
            </span>
          </div>
        )}

        <div
          onDragOver={(e) => {
            e.preventDefault()
            setDragging(true)
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => {
            e.preventDefault()
            setDragging(false)
            handleFile(e.dataTransfer.files?.[0])
          }}
          onClick={() => inputRef.current?.click()}
          className={`mt-8 flex flex-col items-center justify-center rounded-3xl border-2 border-dashed px-6 py-16 text-center cursor-pointer transition-colors ${
            dragging ? 'border-blossom-400 bg-blossom-50' : 'border-blossom-200 bg-white/50 hover:bg-blossom-50/60'
          }`}
        >
          <input
            ref={inputRef}
            type="file"
            accept="application/pdf"
            className="hidden"
            onChange={(e) => {
              handleFile(e.target.files?.[0])
              // Let the same file be re-picked after a rejection.
              e.target.value = ''
            }}
          />
          <span className="flex h-16 w-16 items-center justify-center rounded-full bg-linear-to-br from-blossom-200 to-skycandy-200 text-blossom-600 mb-4">
            <UploadCloud size={28} />
          </span>
          <p className="font-medium text-plum-900">Drag and drop your PDF here</p>
          <p className="text-sm text-plum-800/60 mt-1">or click to browse from your device &middot; PDF up to 25MB</p>
        </div>

        {uploadedFile && (
          <Card className="mt-6 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-blossom-100 text-blossom-500">
                <FileText size={18} />
              </span>
              <div>
                <p className="text-sm font-medium text-plum-900">{uploadedFileName}</p>
                <p className="text-xs text-plum-800/55">
                  {(uploadedFile.size / 1024 / 1024).toFixed(1)}MB &middot; selected on this device, not sent yet
                </p>
              </div>
            </div>
            <CheckCircle2 size={20} className="text-green-500" />
          </Card>
        )}

        <div className="mt-10 flex justify-end">
          <Button
            disabled={!uploadedFile}
            icon={<ArrowRight size={17} />}
            onClick={() => navigate('/admin/categorize')}
            title={!uploadedFile ? 'Choose a PDF to continue' : ''}
          >
            Process document
          </Button>
        </div>
      </div>
    </PageShell>
  )
}
