import { Check } from 'lucide-react'

interface StepProgressProps {
  steps: string[]
  current: number
}

export default function StepProgress({ steps, current }: StepProgressProps) {
  return (
    <div className="w-full overflow-x-auto pb-2">
      <div className="flex min-w-max items-center gap-1 sm:gap-2 px-1">
        {steps.map((label, i) => {
          const done = i < current
          const active = i === current
          return (
            <div key={label} className="flex items-center">
              <div className="flex flex-col items-center gap-1.5">
                <div
                  className={`flex h-8 w-8 sm:h-9 sm:w-9 items-center justify-center rounded-full text-xs sm:text-sm font-semibold transition-all duration-300 ${
                    done
                      ? 'bg-blossom-400 text-white'
                      : active
                      ? 'bg-white text-blossom-500 ring-2 ring-blossom-400 shadow-glow'
                      : 'bg-white/70 text-plum-800/40'
                  }`}
                >
                  {done ? <Check size={16} /> : i + 1}
                </div>
                <span
                  className={`text-[10px] sm:text-xs whitespace-nowrap font-medium ${
                    active ? 'text-blossom-600' : 'text-plum-800/50'
                  }`}
                >
                  {label}
                </span>
              </div>
              {i < steps.length - 1 && (
                <div className={`h-0.5 w-6 sm:w-10 mx-1 rounded ${done ? 'bg-blossom-400' : 'bg-white/70'}`} />
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
