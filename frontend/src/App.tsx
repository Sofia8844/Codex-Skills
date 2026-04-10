import {
  startTransition,
  useDeferredValue,
  useEffect,
  useRef,
  useState,
} from 'react'
import { AppShell } from './layout/AppShell'
import { DashboardPage } from './pages/DashboardPage'
import {
  navigationItems,
  type DashboardViewId,
  type ThemeMode,
} from './services/dashboardData'

const themeStorageKey = 'frontend-theme'
const initialView: DashboardViewId = 'overview'

function getInitialTheme(): ThemeMode {
  if (typeof window === 'undefined') {
    return 'light'
  }

  const storedTheme = window.localStorage.getItem(themeStorageKey)

  if (storedTheme === 'light' || storedTheme === 'dark') {
    return storedTheme
  }

  return window.matchMedia('(prefers-color-scheme: dark)').matches
    ? 'dark'
    : 'light'
}

function App() {
  const [theme, setTheme] = useState<ThemeMode>(getInitialTheme)
  const [activeView, setActiveView] = useState<DashboardViewId>(initialView)
  const [searchQuery, setSearchQuery] = useState('')
  const [isLoading, setIsLoading] = useState(true)
  const loadingTimerRef = useRef<number | null>(null)

  useEffect(() => {
    document.documentElement.dataset.theme = theme
    document.documentElement.style.colorScheme = theme
    window.localStorage.setItem(themeStorageKey, theme)
  }, [theme])

  useEffect(() => {
    loadingTimerRef.current = window.setTimeout(() => {
      setIsLoading(false)
    }, 820)

    return () => {
      if (loadingTimerRef.current !== null) {
        window.clearTimeout(loadingTimerRef.current)
      }
    }
  }, [])

  const deferredSearchQuery = useDeferredValue(searchQuery)

  const scheduleReadyState = () => {
    if (loadingTimerRef.current !== null) {
      window.clearTimeout(loadingTimerRef.current)
    }

    loadingTimerRef.current = window.setTimeout(() => {
      setIsLoading(false)
    }, 440)
  }

  const handleViewChange = (nextView: DashboardViewId) => {
    if (nextView === activeView) {
      return
    }

    setIsLoading(true)

    startTransition(() => {
      setActiveView(nextView)
      setSearchQuery('')
    })

    scheduleReadyState()
  }

  return (
    <AppShell
      activeView={activeView}
      isLoading={isLoading}
      navigationItems={navigationItems}
      onSearchChange={setSearchQuery}
      theme={theme}
      searchQuery={searchQuery}
      onThemeToggle={() =>
        setTheme((currentTheme) =>
          currentTheme === 'light' ? 'dark' : 'light',
        )
      }
      onViewChange={handleViewChange}
    >
      <DashboardPage
        isLoading={isLoading}
        searchQuery={deferredSearchQuery}
        viewId={activeView}
      />
    </AppShell>
  )
}

export default App
