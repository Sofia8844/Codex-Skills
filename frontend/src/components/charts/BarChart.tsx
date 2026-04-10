import type { CSSProperties } from 'react'
import type { BreakdownItem } from '../../services/dashboardData'

interface BarChartProps {
  items: BreakdownItem[]
}

export function BarChart({ items }: BarChartProps) {
  const maxValue = Math.max(...items.map((item) => item.value), 1)

  return (
    <div className="bar-chart">
      {items.map((item, index) => (
        <div className="bar-chart__item" key={item.label}>
          <div className="bar-chart__header">
            <div>
              <strong className="bar-chart__label">{item.label}</strong>
              <p className="bar-chart__note">{item.note}</p>
            </div>
            <span className={`bar-chart__value ${index === 0 ? 'is-emphasis' : ''}`}>
              {item.share}
            </span>
          </div>
          <div className="bar-chart__track">
            <div
              className={`bar-chart__fill ${index === 0 ? 'is-emphasis' : ''}`}
              style={
                {
                  '--bar-width': `${(item.value / maxValue) * 100}%`,
                } as CSSProperties
              }
            />
          </div>
        </div>
      ))}
    </div>
  )
}
