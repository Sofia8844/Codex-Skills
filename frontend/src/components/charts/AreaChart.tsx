import { useId } from 'react'
import type { TimelinePoint } from '../../services/dashboardData'

interface AreaChartProps {
  data: TimelinePoint[]
}

function buildPath(points: Array<{ x: number; y: number }>) {
  return points
    .map((point, index) => `${index === 0 ? 'M' : 'L'} ${point.x} ${point.y}`)
    .join(' ')
}

export function AreaChart({ data }: AreaChartProps) {
  const gradientId = `trend-${useId().replace(/:/g, '')}`
  const width = 680
  const height = 320
  const paddingX = 26
  const paddingTop = 18
  const paddingBottom = 34
  const baseline = height - paddingBottom
  const maxValue = Math.max(...data.map(({ value, target }) => Math.max(value, target)))
  const minValue = Math.min(...data.map(({ value, target }) => Math.min(value, target)))
  const range = Math.max(maxValue - minValue, 1)
  const normalizedMin = Math.max(0, minValue - range * 0.22)
  const normalizedMax = maxValue + range * 0.14
  const normalizedRange = Math.max(normalizedMax - normalizedMin, 1)

  const toX = (index: number) =>
    paddingX + (index * (width - paddingX * 2)) / Math.max(data.length - 1, 1)

  const toY = (value: number) =>
    baseline - ((value - normalizedMin) / normalizedRange) * (baseline - paddingTop)

  const valuePoints = data.map((point, index) => ({
    x: toX(index),
    y: toY(point.value),
  }))

  const targetPoints = data.map((point, index) => ({
    x: toX(index),
    y: toY(point.target),
  }))

  const valueLinePath = buildPath(valuePoints)
  const targetLinePath = buildPath(targetPoints)
  const firstPoint = valuePoints[0]
  const lastPoint = valuePoints[valuePoints.length - 1]
  const areaPath = `${valueLinePath} L ${lastPoint?.x ?? width} ${baseline} L ${
    firstPoint?.x ?? paddingX
  } ${baseline} Z`
  const guides = Array.from({ length: 4 }, (_, index) => {
    const position = paddingTop + ((baseline - paddingTop) * index) / 3
    return { id: `guide-${index}`, y: position }
  })

  return (
    <div className="area-chart">
      <svg
        aria-label="Mock performance chart"
        className="area-chart__canvas"
        role="img"
        viewBox={`0 0 ${width} ${height}`}
      >
        <defs>
          <linearGradient id={gradientId} x1="0%" x2="0%" y1="0%" y2="100%">
            <stop offset="0%" stopColor="var(--accent)" stopOpacity="0.24" />
            <stop offset="100%" stopColor="var(--accent)" stopOpacity="0.02" />
          </linearGradient>
        </defs>

        {guides.map((guide) => (
          <line
            className="area-chart__guide"
            key={guide.id}
            x1={paddingX}
            x2={width - paddingX}
            y1={guide.y}
            y2={guide.y}
          />
        ))}

        <path className="area-chart__area" d={areaPath} fill={`url(#${gradientId})`} />
        <path className="area-chart__target-line" d={targetLinePath} fill="none" />
        <path className="area-chart__value-line" d={valueLinePath} fill="none" />

        {valuePoints.map((point, index) => (
          <g className="area-chart__point" key={data[index]?.label}>
            <circle cx={point.x} cy={point.y} r="3.5" />
            <text
              className="area-chart__label"
              textAnchor={
                index === 0
                  ? 'start'
                  : index === valuePoints.length - 1
                    ? 'end'
                    : 'middle'
              }
              x={point.x}
              y={height - 8}
            >
              {data[index]?.label}
            </text>
          </g>
        ))}
      </svg>
    </div>
  )
}
