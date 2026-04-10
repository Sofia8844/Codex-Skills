import { Sparkline } from './charts/Sparkline'
import { UiIcon } from './UiIcon'
import type { DashboardMetric } from '../services/dashboardData'

interface MetricCardProps {
  metric: DashboardMetric
}

export function MetricCard({ metric }: MetricCardProps) {
  const trendIcon =
    metric.trend === 'up'
      ? 'arrowUp'
      : metric.trend === 'down'
        ? 'arrowDown'
        : 'minus'

  return (
    <article className="metric-card">
      <div className="metric-card__header">
        <p className="metric-card__label">{metric.label}</p>
        <span className={`metric-pill metric-pill--${metric.trend}`}>
          <UiIcon name={trendIcon} />
          {metric.change}
        </span>
      </div>

      <div className="metric-card__body">
        <div>
          <strong className="metric-card__value">{metric.value}</strong>
          <p className="metric-card__detail">{metric.detail}</p>
        </div>
        <Sparkline trend={metric.trend} values={metric.sparkline} />
      </div>
    </article>
  )
}
