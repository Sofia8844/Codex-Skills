import { UiIcon } from '../components/UiIcon'
import type { DashboardNavItem, ThemeMode } from '../services/dashboardData'

interface DashboardHeaderProps {
  activeItem: DashboardNavItem
  isLoading: boolean
  onMenuToggle: () => void
  onSearchChange: (value: string) => void
  onThemeToggle: () => void
  searchQuery: string
  theme: ThemeMode
}

export function DashboardHeader({
  activeItem,
  isLoading,
  onMenuToggle,
  onSearchChange,
  onThemeToggle,
  searchQuery,
  theme,
}: DashboardHeaderProps) {
  return (
    <header className="dashboard-header">
      <div className="dashboard-header__identity">
        <button
          aria-label="Open navigation"
          className="icon-button mobile-toggle"
          onClick={onMenuToggle}
          type="button"
        >
          <UiIcon name="menu" />
        </button>

        <div>
          <p className="eyebrow">Northstar signal room</p>
          <div className="dashboard-header__title-row">
            <strong className="dashboard-header__title">{activeItem.label}</strong>
            <span
              className={`status-pill ${isLoading ? 'status-pill--loading' : ''}`}
            >
              <span className="status-pill__dot" />
              {isLoading ? 'Refreshing mock data' : 'Live mock data'}
            </span>
          </div>
          <p className="dashboard-header__subtitle">{activeItem.description}</p>
        </div>
      </div>

      <label className="search-field">
        <UiIcon name="search" />
        <input
          aria-label="Search dashboard content"
          onChange={(event) => onSearchChange(event.target.value)}
          placeholder="Search activity, owners, or priorities"
          type="search"
          value={searchQuery}
        />
      </label>

      <div className="dashboard-header__actions">
        <button
          aria-label={`Switch to ${theme === 'light' ? 'dark' : 'light'} mode`}
          className="icon-button"
          onClick={onThemeToggle}
          type="button"
        >
          <UiIcon name={theme === 'light' ? 'moon' : 'sun'} />
        </button>

        <button
          aria-label="View notifications"
          className="icon-button icon-button--alert"
          type="button"
        >
          <UiIcon name="bell" />
          <span className="notification-dot" />
        </button>

        <div className="profile-chip">
          <div className="avatar">NS</div>
          <div>
            <strong>Sofia Team</strong>
            <span>Morning sync at 09:30</span>
          </div>
        </div>
      </div>
    </header>
  )
}
