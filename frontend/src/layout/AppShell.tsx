import { useEffect, useEffectEvent, useState, type ReactNode } from 'react'
import { DashboardHeader } from './DashboardHeader'
import { SidebarNav } from './SidebarNav'
import type {
  DashboardNavItem,
  DashboardViewId,
  ThemeMode,
} from '../services/dashboardData'

interface AppShellProps {
  activeView: DashboardViewId
  children: ReactNode
  isLoading: boolean
  navigationItems: DashboardNavItem[]
  onSearchChange: (value: string) => void
  onThemeToggle: () => void
  onViewChange: (view: DashboardViewId) => void
  searchQuery: string
  theme: ThemeMode
}

export function AppShell({
  activeView,
  children,
  isLoading,
  navigationItems,
  onSearchChange,
  onThemeToggle,
  onViewChange,
  searchQuery,
  theme,
}: AppShellProps) {
  const [isSidebarOpen, setIsSidebarOpen] = useState(false)

  const handleKeyDown = useEffectEvent((event: KeyboardEvent) => {
    if (event.key === 'Escape') {
      setIsSidebarOpen(false)
    }
  })

  useEffect(() => {
    if (!isSidebarOpen) {
      document.body.classList.remove('nav-open')
      return undefined
    }

    document.body.classList.add('nav-open')

    const onWindowKeyDown = (event: KeyboardEvent) => {
      handleKeyDown(event)
    }

    window.addEventListener('keydown', onWindowKeyDown)

    return () => {
      document.body.classList.remove('nav-open')
      window.removeEventListener('keydown', onWindowKeyDown)
    }
  }, [isSidebarOpen])

  const activeItem =
    navigationItems.find((item) => item.id === activeView) ?? navigationItems[0]

  const handleNavigate = (nextView: DashboardViewId) => {
    onViewChange(nextView)
    setIsSidebarOpen(false)
  }

  return (
    <div className="app-shell">
      <button
        aria-hidden={!isSidebarOpen}
        className={`app-shell__backdrop ${isSidebarOpen ? 'is-visible' : ''}`}
        onClick={() => setIsSidebarOpen(false)}
        tabIndex={isSidebarOpen ? 0 : -1}
        type="button"
      />

      <SidebarNav
        activeView={activeView}
        isOpen={isSidebarOpen}
        navigationItems={navigationItems}
        onClose={() => setIsSidebarOpen(false)}
        onNavigate={handleNavigate}
      />

      <div className="app-shell__main">
        <DashboardHeader
          activeItem={activeItem}
          isLoading={isLoading}
          onMenuToggle={() => setIsSidebarOpen(true)}
          onSearchChange={onSearchChange}
          onThemeToggle={onThemeToggle}
          searchQuery={searchQuery}
          theme={theme}
        />
        <main className="app-shell__content">{children}</main>
      </div>
    </div>
  )
}
