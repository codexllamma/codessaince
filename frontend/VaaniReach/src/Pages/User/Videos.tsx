import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Download, AlertCircle, Loader2, RefreshCw } from 'lucide-react'
import PageShell from '../../Components/PageShell'
import Card from '../../Components/UI/Card'
import Button from '../../Components/UI/Button'
import { useApp, toLangCode } from '../../Context/AppContext'
import { api, type ExtractedFact } from '../../api/client'

// What the backend is doing while the request is open. It is one long
// synchronous call with no progress channel, so these are elapsed-time
// milestones, not measured progress -- worth being honest about, because a
// bar that pretends to know how far along it is will sit at 90% for minutes.
const STAGES = [
  'Reading the notice',
  'Grounding the facts',
  'Writing the narration',
  'Recording the voice',
  'Syncing the presenter',
  'Composing the video',
]

export default function Videos() {
  const navigate = useNavigate()
  const { selectedCircular, selectedLanguage, selectedAvatar, selectedVoice } = useApp()

  const [videoUrl, setVideoUrl] = useState<string | null>(null)
  const [facts, setFacts] = useState<ExtractedFact[]>([])
  const [generating, setGenerating] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [stage, setStage] = useState(0)
  const [elapsed, setElapsed] = useState(0)
  const startedRef = useRef(false)

  const generate = async () => {
    setGenerating(true)
    setError(null)
    setVideoUrl(null)
    setStage(0)
    setElapsed(0)
    try {
      const res = await api.runE2E(
        toLangCode(selectedLanguage || 'Hindi'),
        selectedAvatar,
        selectedVoice
      )
      setVideoUrl(api.getVideoUrl(res.video_path))
      setFacts(res.facts ?? [])
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'The video could not be generated')
    } finally {
      setGenerating(false)
    }
  }

  // React 18+ StrictMode mounts effects twice in development; without this
  // guard the whole multi-minute pipeline would be kicked off twice.
  useEffect(() => {
    if (startedRef.current) return
    startedRef.current = true
    void generate()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    if (!generating) return
    const id = setInterval(() => {
      setElapsed((s) => {
        const next = s + 1
        setStage(Math.min(Math.floor(next / 20), STAGES.length - 1))
        return next
      })
    }, 1000)
    return () => clearInterval(id)
  }, [generating])

  const mmss = `${String(Math.floor(elapsed / 60)).padStart(2, '0')}:${String(elapsed % 60).padStart(2, '0')}`

  return (
    <PageShell showBack backTo="/user/avatar" wide density="medium">
      <div className="pt-4 sm:pt-8">
        <h1 className="font-display text-3xl font-semibold text-plum-900">
          {generating ? 'Building your video' : videoUrl ? 'Your video is ready' : 'Your video'}
        </h1>
        <p className="mt-2 text-plum-800/70">
          {selectedCircular?.title || 'Government notice'} &middot; narrated in{' '}
          <span className="font-medium text-plum-900">{selectedLanguage || 'Hindi'}</span>
        </p>

        <div className="mt-8 grid grid-cols-1 lg:grid-cols-3 gap-6">
          <Card strong className="lg:col-span-2 p-0 overflow-hidden">
            <div className="relative aspect-video bg-linear-to-br from-blossom-200 via-lavendercandy/60 to-skycandy-200 flex items-center justify-center">
              {generating && (
                <div className="flex flex-col items-center px-6 text-center text-plum-800">
                  <Loader2 className="animate-spin" size={30} />
                  <span className="mt-3 text-sm font-medium">{STAGES[stage]}…</span>
                  <span className="mt-1 text-xs text-plum-800/60">
                    {mmss} elapsed &middot; this usually takes several minutes
                  </span>
                </div>
              )}

              {!generating && error && (
                <div className="flex max-w-md flex-col items-center px-6 text-center text-plum-900">
                  <AlertCircle size={28} className="text-blossom-600" />
                  <span className="mt-3 text-sm font-medium">The video could not be generated</span>
                  <span className="mt-1 text-xs text-plum-800/65 wrap-break-word">{error}</span>
                </div>
              )}

              {!generating && videoUrl && (
                <video src={videoUrl} controls className="h-full w-full bg-black" />
              )}
            </div>

            <div className="p-5 flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="text-sm font-medium text-plum-900">
                  {selectedCircular?.title || 'Government notice'}
                </p>
                <p className="text-xs text-plum-800/55 mt-0.5">
                  {generating ? 'Rendering…' : videoUrl ? 'Ready to watch' : 'Not generated'}
                </p>
              </div>
              <div className="flex gap-2">
                {(error || videoUrl) && !generating && (
                  <Button size="sm" variant="outline" icon={<RefreshCw size={15} />} onClick={() => void generate()}>
                    {error ? 'Try again' : 'Regenerate'}
                  </Button>
                )}
                {/* Only offered once a real file exists to download. */}
                {videoUrl && !generating && (
                  <a href={videoUrl} download>
                    <Button size="sm" icon={<Download size={15} />}>Download</Button>
                  </a>
                )}
              </div>
            </div>
          </Card>

          <Card className="h-fit">
            <h3 className="font-display text-base font-semibold text-plum-900 mb-3">
              What this video says
            </h3>

            {/* The facts come back from the same call that produced the video,
                so this is what was actually narrated -- not a written summary
                that could drift from it. */}
            {facts.length > 0 ? (
              <ul className="space-y-2.5">
                {facts.map((f) => (
                  <li key={f.fact_id} className="text-sm">
                    <span className="text-xs font-medium uppercase tracking-wide text-plum-800/50">
                      {f.category.replace(/_/g, ' ')}
                    </span>
                    <p className="text-plum-900">{f.normalized_value}</p>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-plum-800/60">
                {generating ? 'Extracting the facts from the notice…' : 'No facts to show yet.'}
              </p>
            )}

            <Button
              variant="ghost"
              size="sm"
              className="w-full mt-5"
              onClick={() => navigate('/user/circulars')}
            >
              Browse another circular
            </Button>
          </Card>
        </div>
      </div>
    </PageShell>
  )
}
