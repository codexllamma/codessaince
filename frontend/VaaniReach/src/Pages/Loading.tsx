import { useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import gsap from 'gsap'
import { Flower2 } from 'lucide-react'
import PetalBackground from '../Components/PetalBackground'

export default function Loading() {
  const navigate = useNavigate()
  const iconRef = useRef<HTMLSpanElement>(null)
  const titleRef = useRef<HTMLHeadingElement>(null)
  const subRef = useRef<HTMLParagraphElement>(null)
  const barRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const tl = gsap.timeline({
      onComplete: () => {
        gsap.to('.loading-wrap', {
          opacity: 0,
          duration: 0.5,
          onComplete: () => navigate('/landing'),
        })
      },
    })

    tl.fromTo(
      iconRef.current,
      { scale: 0, rotate: -60, opacity: 0 },
      { scale: 1, rotate: 0, opacity: 1, duration: 0.7, ease: 'back.out(2)' }
    )
      .fromTo(titleRef.current, { y: 16, opacity: 0 }, { y: 0, opacity: 1, duration: 0.5 }, '-=0.2')
      .fromTo(subRef.current, { y: 10, opacity: 0 }, { y: 0, opacity: 1, duration: 0.5 }, '-=0.3')
      .fromTo(barRef.current, { scaleX: 0 }, { scaleX: 1, duration: 1.4, ease: 'power2.inOut', transformOrigin: 'left' })
      .to(iconRef.current, { rotate: 360, duration: 1.2, ease: 'power1.inOut' }, '-=1.4')

    return () => {
      tl.kill()
    }
  }, [navigate])

  return (
    <div className="loading-wrap relative flex min-h-screen items-center justify-center overflow-hidden bg-candy-sky">
      <PetalBackground density="medium" />
      <div className="relative z-10 flex flex-col items-center text-center px-6">
        <span
          ref={iconRef}
          className="mb-6 flex h-20 w-20 items-center justify-center rounded-full bg-white/70 glass-strong shadow-glow"
        >
          <Flower2 size={38} className="text-blossom-500" strokeWidth={2} />
        </span>
        <h1 ref={titleRef} className="font-display text-3xl sm:text-4xl font-semibold text-plum-900">
          Vaani<span className="text-gradient">Reach</span>
        </h1>
        <p ref={subRef} className="mt-2 text-sm sm:text-base text-plum-800/70">
          Preparing your multilingual outreach studio
        </p>
        <div className="mt-8 h-1.5 w-56 sm:w-72 overflow-hidden rounded-full bg-white/60">
          <div ref={barRef} className="h-full w-full rounded-full bg-linear-to-r from-blossom-400 to-skycandy-400" />
        </div>
      </div>
    </div>
  )
}
