import { UiIcon } from '../components/UiIcon'
import type {
  DashboardNavItem,
  DashboardViewId,
} from '../services/dashboardData'

interface SidebarNavProps {
  activeView: DashboardViewId
  isOpen: boolean
  navigationItems: DashboardNavItem[]
  onClose: () => void
  onNavigate: (view: DashboardViewId) => void
}

export function SidebarNav({
  activeView,
  isOpen,
  navigationItems,
  onClose,
  onNavigate,
}: SidebarNavProps) {
  return (
    <aside
      aria-label="Sidebar navigation"
      className={`sidebar ${isOpen ? 'is-open' : ''}`}
    >
      <div className="sidebar__inner">
        <div className="sidebar__brand">
          <div className="sidebar__mark">
            <UiIcon name="compass" />
          </div>
          <div className="sidebar__titles">
            <strong>Northstar</strong>
            <span>Editorial operations dashboard</span>
          </div>
          <button
            aria-label="Close navigation"
            className="icon-button sidebar__close"
            onClick={onClose}
            type="button"
          >
            <UiIcon name="close" />
          </button>
        </div>

        <section className="workspace-card">
          <p className="sidebar__section-label">Workspace</p>
          <div className="workspace-card__header">
            <strong>Executive operator lane</strong>
            <span>Quarter close in motion</span>
          </div>
          <div className="workspace-card__grid">
            <div className="workspace-card__metric">
              <span>Risk</span>
              <strong>Low</strong>
            </div>
            <div className="workspace-card__metric">
              <span>Focus</span>
              <strong>07 queues</strong>
            </div>
            <div className="workspace-card__metric">
              <span>Review</span>
              <strong>14:00 UTC</strong>
            </div>
          </div>
        </section>

        <nav className="sidebar__nav">
          <p className="sidebar__section-label">Navigation</p>
          {navigationItems.map((item) => {
            const isActive = item.id === activeView

            return (
              <button
                className={`sidebar__link ${isActive ? 'is-active' : ''}`}
                key={item.id}
                onClick={() => onNavigate(item.id)}
                type="button"
              >
                <span className="sidebar__link-icon">
                  <UiIcon name={item.icon} />
                </span>
                <span className="sidebar__link-copy">
                  <strong>{item.label}</strong>
                  <span>{item.description}</span>
                </span>
                <span className="sidebar__badge">{item.badge}</span>
              </button>
            )
          })}
        </nav>

        <section className="sidebar__footer">
          <p className="sidebar__section-label">Operator notes</p>
          <h2>Automation drift stays inside the calm band.</h2>
          <p>
            Contract approvals are pacing ahead of plan, and only three routines
            need human review before noon.
          </p>
          <div className="sidebar__footer-row">
            <div className="sidebar__footer-stat">
              <span>Coverage</span>
              <strong>28 plays</strong>
            </div>
            <div className="sidebar__footer-stat">
              <span>Escalations</span>
              <strong>03 open</strong>
            </div>
          </div>
        </section>
      </div>
    </aside>
  )
}
