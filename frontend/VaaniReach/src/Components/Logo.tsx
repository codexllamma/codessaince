import { Flower2 } from 'lucide-react'
import { Link } from 'react-router-dom'

export default function Logo({ to = '/landing' }: { to?: string }) {
  return (
    <Link to={to} className="flex items-center gap-2 group">
      <span className="flex h-9 w-9 items-center justify-center rounded-full bg-linear-to-br from-blossom-300 to-skycandy-300 text-white shadow-glow group-hover:scale-105 transition-transform">
        <Flower2 size={18} strokeWidth={2.5} />
      </span>
      <span className="font-display text-xl font-semibold tracking-tight text-plum-900">
        Vaani<span className="text-gradient">Reach</span>
      </span>
    </Link>
  )
}
