import { useEffect, useRef } from 'react'
import gsap from 'gsap'

interface PetalBackgroundProps {
  density?: 'low' | 'medium' | 'high'
  clouds?: boolean
}

const PETAL_COLORS = ['#FFA9C6', '#FFCBDE', '#FF87AF', '#FFE7EF']

export default function PetalBackground({ density = 'low', clouds = true }: PetalBackgroundProps) {
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const container = containerRef.current
    if (!container) return
    const prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    const count = prefersReduced ? 0 : density === 'high' ? 18 : density === 'medium' ? 11 : 6
    const petals: HTMLDivElement[] = []
    const tweens: gsap.core.Tween[] = []

    for (let i = 0; i < count; i++) {
      const petal = document.createElement('div')
      const size = gsap.utils.random(8, 18)
      const color = PETAL_COLORS[i % PETAL_COLORS.length]
      petal.className = 'petal'
      petal.style.width = `${size}px`
      petal.style.height = `${size * 0.8}px`
      petal.style.left = `${gsap.utils.random(0, 100)}%`
      petal.style.background = color
      petal.style.borderRadius = '0% 70% 0% 70%'
      petal.style.opacity = `${gsap.utils.random(0.4, 0.85)}`
      container.appendChild(petal)
      petals.push(petal)

      const duration = gsap.utils.random(9, 18)
      const sway = gsap.utils.random(40, 120)

      const tl = gsap.timeline({ repeat: -1, delay: gsap.utils.random(0, 8) })
      tl.set(petal, { y: -40, x: 0, rotation: gsap.utils.random(0, 360) })
      tl.to(petal, {
        y: '110vh',
        duration,
        ease: 'none',
      }, 0)
      tl.to(petal, {
        x: `+=${sway}`,
        duration: duration / 2,
        ease: 'sine.inOut',
        yoyo: true,
        repeat: 1,
      }, 0)
      tl.to(petal, {
        rotation: `+=${gsap.utils.random(180, 540)}`,
        duration,
        ease: 'none',
      }, 0)
      tweens.push(tl as unknown as gsap.core.Tween)
    }

    return () => {
      tweens.forEach((t) => t.kill())
      petals.forEach((p) => p.remove())
    }
  }, [density])

  return (
    <div ref={containerRef} className="pointer-events-none fixed inset-0 overflow-hidden" aria-hidden="true">
      {clouds && (
        <>
          <div className="absolute -top-24 -left-20 h-72 w-72 rounded-blob bg-skycandy-200/50 blur-3xl animate-drift" />
          <div
            className="absolute top-1/3 -right-24 h-80 w-80 rounded-blob bg-blossom-200/40 blur-3xl animate-drift"
            style={{ animationDelay: '2s' }}
          />
          <div
            className="absolute bottom-0 left-1/4 h-64 w-64 rounded-blob bg-lavendercandy/40 blur-3xl animate-drift"
            style={{ animationDelay: '4s' }}
          />
        </>
      )}
    </div>
  )
}
