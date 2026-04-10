import { useId } from 'react'

interface ProgressRingProps {
  score: number
}

export function ProgressRing({ score }: ProgressRingProps) {
  const gradientId = `health-${useId().replace(/:/g, '')}`
  const normalizedScore = Math.min(100, Math.max(0, score))
  const radius = 54
  const circumference = 2 * Math.PI * radius
  const dashOffset = circumference * (1 - normalizedScore / 100)

  return (
    <div className="progress-ring">
      <svg className="progress-ring__svg" viewBox="0 0 160 160">
        <defs>
          <linearGradient id={gradientId} x1="0%" x2="100%" y1="0%" y2="100%">
            <stop offset="0%" stopColor="var(--accent)" />
            <stop offset="100%" stopColor="var(--accent-strong)" />
          </linearGradient>
        </defs>

        <circle
          className="progress-ring__track"
          cx="80"
          cy="80"
          r={radius}
          strokeWidth="12"
        />
        <circle
          className="progress-ring__meter"
          cx="80"
          cy="80"
          r={radius}
          stroke={`url(#${gradientId})`}
          strokeDasharray={`${circumference} ${circumference}`}
          strokeDashoffset={dashOffset}
          strokeLinecap="round"
          strokeWidth="12"
          transform="rotate(-90 80 80)"
        />
      </svg>

      <div className="progress-ring__center">
        <span className="progress-ring__label">Health</span>
        <strong className="progress-ring__value">{normalizedScore}%</strong>
      </div>
    </div>
  )
}
