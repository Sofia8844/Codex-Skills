import type { CSSProperties } from 'react'
import { MetricCard } from '../components/MetricCard'
import { UiIcon } from '../components/UiIcon'
import { AreaChart } from '../components/charts/AreaChart'
import { BarChart } from '../components/charts/BarChart'
import { ProgressRing } from '../components/charts/ProgressRing'
import { dashboardViews, type DashboardViewId } from '../services/dashboardData'

interface DashboardPageProps {
  isLoading: boolean
  searchQuery: string
  viewId: DashboardViewId
}

function matchesSearch(searchQuery: string, fields: string[]) {
  if (!searchQuery.trim()) {
    return true
  }

  const normalizedQuery = searchQuery.trim().toLowerCase()

  return fields.some((field) => field.toLowerCase().includes(normalizedQuery))
}

export function DashboardPage({
  isLoading,
  searchQuery,
  viewId,
}: DashboardPageProps) {
  const view = dashboardViews[viewId]

  if (isLoading) {
    return <DashboardSkeleton />
  }

  const filteredActivity = view.activity.filter((item) =>
    matchesSearch(searchQuery, [item.title, item.detail, item.status]),
  )

  const filteredFocus = view.focus.filter((item) =>
    matchesSearch(searchQuery, [item.title, item.owner, item.due]),
  )

  return (
    <div className="dashboard-page" key={viewId}>
      <section className="hero-panel panel">
        <div className="hero-panel__copy">
          <p className="eyebrow">{view.eyebrow}</p>
          <h1>{view.title}</h1>
          <p className="hero-panel__lead">{view.subtitle}</p>
          <div className="hero-panel__tags">
            {view.tags.map((tag) => (
              <span className="hero-tag" key={tag}>
                {tag}
              </span>
            ))}
          </div>
        </div>

        <div className="hero-panel__signals">
          {view.heroSignals.map((signal) => (
            <article className="signal-card" key={signal.label}>
              <span className="signal-card__label">{signal.label}</span>
              <strong className="signal-card__value">{signal.value}</strong>
              <p className="signal-card__note">{signal.note}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="metric-grid">
        {view.metrics.map((metric) => (
          <MetricCard key={metric.label} metric={metric} />
        ))}
      </section>

      <section className="analytics-grid">
        <article className="panel panel--chart">
          <div className="panel__header">
            <div className="panel__title-group">
              <p className="panel__kicker">Primary trend</p>
              <h2 className="panel__heading">{view.timelineTitle}</h2>
            </div>
            <p className="panel__description">{view.timelineSubtitle}</p>
          </div>

          <AreaChart data={view.timeline} />

          <div className="area-chart__footer">
            {view.chartHighlights.map((highlight) => (
              <div className="area-chart__footer-item" key={highlight.label}>
                <span>{highlight.label}</span>
                <strong>{highlight.value}</strong>
                <p>{highlight.note}</p>
              </div>
            ))}
          </div>
        </article>

        <div className="analytics-grid__aside">
          <article className="panel">
            <div className="panel__header">
              <div className="panel__title-group">
                <p className="panel__kicker">Mix</p>
                <h2 className="panel__heading">{view.breakdownTitle}</h2>
              </div>
              <p className="panel__description">{view.breakdownSubtitle}</p>
            </div>

            <BarChart items={view.breakdown} />
          </article>

          <article className="panel panel--health">
            <div className="panel__header">
              <div className="panel__title-group">
                <p className="panel__kicker">System health</p>
                <h2 className="panel__heading">{view.health.title}</h2>
              </div>
              <p className="panel__description">{view.health.summary}</p>
            </div>

            <div className="health-layout">
              <ProgressRing score={view.health.score} />

              <div className="health-layout__copy">
                <p className="health-layout__detail">{view.health.detail}</p>
                <div className="health-list">
                  {view.health.segments.map((segment) => (
                    <div className="health-list__item" key={segment.label}>
                      <span className={`tone-dot tone-dot--${segment.tone}`} />
                      <span>{segment.label}</span>
                      <strong>{segment.value}</strong>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </article>
        </div>
      </section>

      <section className="detail-grid">
        <article className="panel">
          <div className="panel__header">
            <div className="panel__title-group">
              <p className="panel__kicker">Activity</p>
              <h2 className="panel__heading">{view.activityTitle}</h2>
            </div>
            <p className="panel__description">{view.activitySubtitle}</p>
          </div>

          {filteredActivity.length > 0 ? (
            <div className="activity-list">
              {filteredActivity.map((item) => (
                <article className="activity-row" key={`${item.title}-${item.timestamp}`}>
                  <div className={`activity-row__icon tone-chip--${item.tone}`}>
                    <UiIcon name={item.icon} />
                  </div>
                  <div className="activity-row__body">
                    <div className="activity-row__copy">
                      <strong>{item.title}</strong>
                      <p>{item.detail}</p>
                    </div>
                    <div className="activity-row__meta">
                      <span
                        className={`activity-row__status activity-row__status--${item.tone}`}
                      >
                        {item.status}
                      </span>
                      <span>{item.timestamp}</span>
                    </div>
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <EmptyState searchQuery={searchQuery} />
          )}
        </article>

        <article className="panel">
          <div className="panel__header">
            <div className="panel__title-group">
              <p className="panel__kicker">Focus queue</p>
              <h2 className="panel__heading">{view.focusTitle}</h2>
            </div>
            <p className="panel__description">{view.focusSubtitle}</p>
          </div>

          {filteredFocus.length > 0 ? (
            <div className="focus-list">
              {filteredFocus.map((item) => (
                <article className="focus-row" key={`${item.title}-${item.owner}`}>
                  <div className="focus-row__header">
                    <div>
                      <strong>{item.title}</strong>
                      <p className="focus-row__meta">
                        {item.owner} · {item.due}
                      </p>
                    </div>
                    <span className={`activity-row__status activity-row__status--${item.tone}`}>
                      {item.progress}%
                    </span>
                  </div>
                  <div className="progress-bar">
                    <span
                      className={`progress-bar__fill progress-bar__fill--${item.tone}`}
                      style={
                        {
                          '--progress-width': `${item.progress}%`,
                        } as CSSProperties
                      }
                    />
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <EmptyState searchQuery={searchQuery} />
          )}
        </article>
      </section>
    </div>
  )
}

function EmptyState({ searchQuery }: { searchQuery: string }) {
  return (
    <div className="panel-empty">
      <p>No dashboard items match "{searchQuery}".</p>
      <span>Clear the search field to bring the full queue back.</span>
    </div>
  )
}

function DashboardSkeleton() {
  return (
    <div className="dashboard-page dashboard-page--loading">
      <section className="hero-panel panel">
        <div className="skeleton skeleton--eyebrow" />
        <div className="skeleton skeleton--title" />
        <div className="skeleton skeleton--text" />
        <div className="skeleton-row">
          <div className="skeleton skeleton--chip" />
          <div className="skeleton skeleton--chip" />
          <div className="skeleton skeleton--chip" />
        </div>
        <div className="skeleton-grid">
          {Array.from({ length: 3 }, (_, index) => (
            <div className="signal-card signal-card--loading" key={index}>
              <div className="skeleton skeleton--metric-label" />
              <div className="skeleton skeleton--metric" />
              <div className="skeleton skeleton--short" />
            </div>
          ))}
        </div>
      </section>

      <section className="metric-grid">
        {Array.from({ length: 4 }, (_, index) => (
          <article className="metric-card" key={index}>
            <div className="metric-card__header">
              <div className="skeleton skeleton--metric-label" />
              <div className="skeleton skeleton--pill" />
            </div>
            <div className="skeleton skeleton--metric" />
            <div className="skeleton skeleton--short" />
            <div className="skeleton skeleton--mini-chart" />
          </article>
        ))}
      </section>

      <section className="analytics-grid">
        <article className="panel">
          <div className="skeleton skeleton--panel-title" />
          <div className="skeleton skeleton--chart" />
          <div className="skeleton-grid skeleton-grid--footer">
            {Array.from({ length: 3 }, (_, index) => (
              <div className="skeleton skeleton--short" key={index} />
            ))}
          </div>
        </article>

        <div className="analytics-grid__aside">
          <article className="panel">
            <div className="skeleton skeleton--panel-title" />
            {Array.from({ length: 4 }, (_, index) => (
              <div className="skeleton skeleton--bar" key={index} />
            ))}
          </article>

          <article className="panel">
            <div className="skeleton skeleton--panel-title" />
            <div className="skeleton skeleton--ring" />
            <div className="skeleton skeleton--text" />
          </article>
        </div>
      </section>

      <section className="detail-grid">
        {Array.from({ length: 2 }, (_, index) => (
          <article className="panel" key={index}>
            <div className="skeleton skeleton--panel-title" />
            {Array.from({ length: 4 }, (_, rowIndex) => (
              <div className="skeleton skeleton--list" key={rowIndex} />
            ))}
          </article>
        ))}
      </section>
    </div>
  )
}
