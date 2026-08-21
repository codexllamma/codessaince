import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { toast } from 'react-toastify'
import { Play, Pause, CheckCircle2, XCircle, ClipboardCheck } from 'lucide-react'
import PageShell from '../../Components/PageShell'
import Card from '../../Components/UI/Button'
import Button from '../../Components/UI/Button'
import StepProgress from '../../Components/UI/StepProgress'
import { useApp } from '../../Context/AppContext'

const STEPS = ['Upload', 'Categorize', 'Ingest', 'Fact grounding', 'Storyboard', 'Voice', 'Approval']

export default function OfficerApproval() {
  const navigate = useNavigate()
  const { uploadedFileName, setUploadedFileName } = useApp()
  const [playing, setPlaying] = useState(false)
  const [decision, setDecision] = useState<'approved' | 'rejected' | null>(null)

  const approve = () => {
    setDecision('approved')
    toast.success('Video approved and queued for publication', { icon: () => <CheckCircle2 size={18} className="text-green-500" /> })
  }

  const reject = () => {
    setDecision('rejected')
    toast.error('Video sent back for revision', { icon: () => <XCircle size={18} className="text-red-500" /> })
  }

  const startNew = () => {
    setUploadedFileName('')
    navigate('/admin/upload')
  }

  return (
    <PageShell showBack backTo="/admin/voice-karaoke">
      <div className="pt-4 sm:pt-8">
        <StepProgress steps={STEPS} current={6} />

        <div className="mt-8 flex items-center gap-2">
          <ClipboardCheck size={22} className="text-blossom-500" />
          <h1 className="font-display text-3xl font-semibold text-plum-900">Officer approval</h1>
        </div>
        <p className="mt-2 text-plum-800/70">
          One last look before this reaches the public. {uploadedFileName && <>Source: <span className="font-medium text-plum-900">{uploadedFileName}</span></>}
        </p>

        <Card className="mt-7 p-0 overflow-hidden max-w-2xl mx-auto">
          <div className="relative aspect-video bg-linear-to-br from-blossom-200 via-lavendercandy/60 to-skycandy-200 flex items-center justify-center">
            <button
              onClick={() => setPlaying((p) => !p)}
              className="flex h-16 w-16 items-center justify-center rounded-full bg-white/80 text-blossom-500 shadow-glow hover:scale-105 transition-transform"
              aria-label={playing ? 'Pause video' : 'Play video'}
            >
              {playing ? <Pause size={26} /> : <Play size={26} className="ml-1" />}
            </button>
            {decision && (
              <span
                className={`absolute top-4 right-4 rounded-full px-3 py-1.5 text-xs font-semibold ${
                  decision === 'approved' ? 'bg-green-500 text-white' : 'bg-red-400 text-white'
                }`}
              >
                {decision === 'approved' ? 'Approved' : 'Sent for revision'}
              </span>
            )}
          </div>
          <div className="p-5 flex flex-col sm:flex-row items-center justify-between gap-4">
            <p className="text-sm text-plum-800/60">Final render &middot; three languages &middot; captions included</p>
            <div className="flex gap-3">
              <Button variant="outline" icon={<XCircle size={17} />} onClick={reject} disabled={decision !== null}>
                Reject
              </Button>
              <Button icon={<CheckCircle2 size={17} />} onClick={approve} disabled={decision !== null}>
                Approve
              </Button>
            </div>
          </div>
        </Card>

        {decision && (
          <div className="mt-8 text-center">
            <Button variant="ghost" onClick={startNew}>
              Process another notice
            </Button>
          </div>
        )}
      </div>
    </PageShell>
  )
}
