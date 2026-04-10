import type { SVGProps } from 'react'
import type { DashboardIconName } from '../services/dashboardData'

interface UiIconProps extends SVGProps<SVGSVGElement> {
  name: DashboardIconName
}

export function UiIcon({ name, ...props }: UiIconProps) {
  switch (name) {
    case 'compass':
      return (
        <svg fill="none" viewBox="0 0 24 24" {...props}>
          <circle cx="12" cy="12" r="8" stroke="currentColor" strokeWidth="1.8" />
          <path
            d="M14.9 9.1 13 13l-3.9 1.9L11 11l3.9-1.9Z"
            stroke="currentColor"
            strokeLinejoin="round"
            strokeWidth="1.8"
          />
        </svg>
      )
    case 'chart':
      return (
        <svg fill="none" viewBox="0 0 24 24" {...props}>
          <path
            d="M5 19V9m7 10V5m7 14v-7"
            stroke="currentColor"
            strokeLinecap="round"
            strokeWidth="1.8"
          />
        </svg>
      )
    case 'people':
      return (
        <svg fill="none" viewBox="0 0 24 24" {...props}>
          <path
            d="M15.5 19c0-2-1.8-3.6-4-3.6s-4 1.6-4 3.6m10-8.5a2.5 2.5 0 1 1-5 0 2.5 2.5 0 0 1 5 0ZM6.4 13.5A2.2 2.2 0 0 0 4 15.7M19.5 15.7a2.2 2.2 0 0 0-2.4-2.2"
            stroke="currentColor"
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth="1.8"
          />
        </svg>
      )
    case 'bolt':
      return (
        <svg fill="none" viewBox="0 0 24 24" {...props}>
          <path
            d="M13.3 3 6.7 13h4.5L10.7 21l6.6-10h-4.5L13.3 3Z"
            stroke="currentColor"
            strokeLinejoin="round"
            strokeWidth="1.8"
          />
        </svg>
      )
    case 'moon':
      return (
        <svg fill="none" viewBox="0 0 24 24" {...props}>
          <path
            d="M18 14.7A7.2 7.2 0 0 1 9.3 6a7.8 7.8 0 1 0 8.7 8.7Z"
            stroke="currentColor"
            strokeLinejoin="round"
            strokeWidth="1.8"
          />
        </svg>
      )
    case 'sun':
      return (
        <svg fill="none" viewBox="0 0 24 24" {...props}>
          <circle cx="12" cy="12" r="3.4" stroke="currentColor" strokeWidth="1.8" />
          <path
            d="M12 3.5v2.1m0 12.8v2.1M5.9 5.9 7.4 7.4m9.2 9.2 1.5 1.5M3.5 12h2.1m12.8 0h2.1M5.9 18.1l1.5-1.5m9.2-9.2 1.5-1.5"
            stroke="currentColor"
            strokeLinecap="round"
            strokeWidth="1.8"
          />
        </svg>
      )
    case 'menu':
      return (
        <svg fill="none" viewBox="0 0 24 24" {...props}>
          <path
            d="M4.5 7h15m-15 5h15m-15 5h15"
            stroke="currentColor"
            strokeLinecap="round"
            strokeWidth="1.8"
          />
        </svg>
      )
    case 'search':
      return (
        <svg fill="none" viewBox="0 0 24 24" {...props}>
          <circle cx="11" cy="11" r="5.7" stroke="currentColor" strokeWidth="1.8" />
          <path
            d="m19 19-3.2-3.2"
            stroke="currentColor"
            strokeLinecap="round"
            strokeWidth="1.8"
          />
        </svg>
      )
    case 'bell':
      return (
        <svg fill="none" viewBox="0 0 24 24" {...props}>
          <path
            d="M8 17.5h8m-7-9.4a3 3 0 1 1 6 0c0 4 1.7 4.7 1.7 6.4H7.3c0-1.7 1.7-2.4 1.7-6.4Zm1.8 9.4a2.2 2.2 0 0 0 4.4 0"
            stroke="currentColor"
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth="1.8"
          />
        </svg>
      )
    case 'shield':
      return (
        <svg fill="none" viewBox="0 0 24 24" {...props}>
          <path
            d="M12 3.5 6.5 5.8v4.5c0 4.1 2.3 7.5 5.5 9.2 3.2-1.7 5.5-5.1 5.5-9.2V5.8L12 3.5Z"
            stroke="currentColor"
            strokeLinejoin="round"
            strokeWidth="1.8"
          />
          <path
            d="m9.6 11.8 1.5 1.6 3.5-3.9"
            stroke="currentColor"
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth="1.8"
          />
        </svg>
      )
    case 'spark':
      return (
        <svg fill="none" viewBox="0 0 24 24" {...props}>
          <path
            d="m12 3 1.8 4.8L18.5 9l-4.7 1.3L12 15l-1.8-4.7L5.5 9l4.7-1.2L12 3Z"
            stroke="currentColor"
            strokeLinejoin="round"
            strokeWidth="1.8"
          />
        </svg>
      )
    case 'check':
      return (
        <svg fill="none" viewBox="0 0 24 24" {...props}>
          <path
            d="m6.5 12.5 3.4 3.4 7.6-7.8"
            stroke="currentColor"
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth="1.8"
          />
        </svg>
      )
    case 'clock':
      return (
        <svg fill="none" viewBox="0 0 24 24" {...props}>
          <circle cx="12" cy="12" r="7.5" stroke="currentColor" strokeWidth="1.8" />
          <path
            d="M12 8v4.2l2.8 1.7"
            stroke="currentColor"
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth="1.8"
          />
        </svg>
      )
    case 'close':
      return (
        <svg fill="none" viewBox="0 0 24 24" {...props}>
          <path
            d="m7 7 10 10M17 7 7 17"
            stroke="currentColor"
            strokeLinecap="round"
            strokeWidth="1.8"
          />
        </svg>
      )
    case 'arrowUp':
      return (
        <svg fill="none" viewBox="0 0 24 24" {...props}>
          <path
            d="m7 14 5-5 5 5"
            stroke="currentColor"
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth="1.8"
          />
        </svg>
      )
    case 'arrowDown':
      return (
        <svg fill="none" viewBox="0 0 24 24" {...props}>
          <path
            d="m7 10 5 5 5-5"
            stroke="currentColor"
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth="1.8"
          />
        </svg>
      )
    case 'minus':
      return (
        <svg fill="none" viewBox="0 0 24 24" {...props}>
          <path
            d="M7 12h10"
            stroke="currentColor"
            strokeLinecap="round"
            strokeWidth="1.8"
          />
        </svg>
      )
    default:
      return null
  }
}
