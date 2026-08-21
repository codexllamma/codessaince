import { useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { toast } from 'react-toastify'
import { UploadCloud, FileText, CheckCircle2, ArrowRight } from 'lucide-react'
import PageShell from '../../Components/PageShell'
import Card from '../../Components/UI/Card'
import Button from '../../Components/UI/Button'
import StepProgress from '../../Components/UI/StepProgress'
import { useApp } from '../../Context/AppContext'

const STEPS = ['Upload', 'Categorize', 'Ingest', 'Fact grounding', 'Storyboard', 'Voice', 'Approval']

/** The dropzone promises "PDF up to 25MB", so enforce exactly that here rather
 *  than letting the backend reject a multi-minute upload after the fact. */
const MAX_BYTES = 25 * 1024 * 1024

export default function UploadPdf() {
  const navigate = useNavigate()
  const { uploadedFile, setUploadedFile, uploadedFileName, setUploadedFileName, resetJob } = useApp()
  const [dragging, setDragging] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

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
