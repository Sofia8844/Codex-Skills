import { useId } from 'react'
import type { TrendDirection } from '../../services/dashboardData'

interface SparklineProps {
  trend: TrendDirection
  values: number[]
}

export function Sparkline({ trend, values }: SparklineProps) {
  const gradientId = `spark-${useId().replace(/:/g, '')}`
  const width = 132
  const height = 64
  const padding = 4
  const maxValue = Math.max(...values)
  const minValue = Math.min(...values)
  const range = Math.max(maxValue - minValue, 1)

  const points = values.map((value, index) => {
    const x =
      padding + (index * (width - padding * 2)) / Math.max(values.length - 1, 1)
    const y =
      height -
      padding -
      ((value - minValue) / range) * (height - padding * 2)

    return { x, y }
  })

  const linePath = points
    .map((point, index) => `${index === 0 ? 'M' : 'L'} ${point.x} ${point.y}`)
    .join(' ')

  const firstPoint = points[0]
  const lastPoint = points[points.length - 1]
  const areaPath = `${linePath} L ${lastPoint?.x ?? width} ${
    height - padding
  } L ${firstPoint?.x ?? padding} ${height - padding} Z`

  return (
    <svg
      aria-hidden="true"
      className={`sparkline sparkline--${trend}`}
      viewBox={`0 0 ${width} ${height}`}
    >
      <defs>
        <linearGradient id={gradientId} x1="0%" x2="0%" y1="0%" y2="100%">
          <stop offset="0%" stopColor="var(--accent)" stopOpacity="0.28" />
          <stop offset="100%" stopColor="var(--accent)" stopOpacity="0" />
        </linearGradient>
      </defs>
      <path className="sparkline__area" d={areaPath} fill={`url(#${gradientId})`} />
      <path className="sparkline__line" d={linePath} fill="none" />
    </svg>
  )
}
