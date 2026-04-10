export type ThemeMode = 'light' | 'dark'
export type DashboardViewId = 'overview' | 'revenue' | 'accounts' | 'automation'
export type TrendDirection = 'up' | 'down' | 'steady'
export type DashboardIconName =
  | 'compass'
  | 'chart'
  | 'people'
  | 'bolt'
  | 'moon'
  | 'sun'
  | 'menu'
  | 'search'
  | 'bell'
  | 'shield'
  | 'spark'
  | 'check'
  | 'clock'
  | 'close'
  | 'arrowUp'
  | 'arrowDown'
  | 'minus'

export interface DashboardNavItem {
  badge: string
  description: string
  icon: DashboardIconName
  id: DashboardViewId
  label: string
}

export interface HeroSignal {
  label: string
  note: string
  value: string
}

export interface DashboardMetric {
  change: string
  detail: string
  label: string
  sparkline: number[]
  trend: TrendDirection
  value: string
}

export interface TimelinePoint {
  label: string
  target: number
  value: number
}

export interface ChartHighlight {
  label: string
  note: string
  value: string
}

export interface BreakdownItem {
  label: string
  note: string
  share: string
  value: number
}

export interface HealthSegment {
  label: string
  tone: 'accent' | 'positive' | 'warning' | 'muted'
  value: string
}

export interface ActivityItem {
  detail: string
  icon: DashboardIconName
  status: string
  timestamp: string
  title: string
  tone: 'accent' | 'positive' | 'warning' | 'muted'
}

export interface FocusItem {
  due: string
  owner: string
  progress: number
  title: string
  tone: 'accent' | 'positive' | 'warning' | 'muted'
}

export interface DashboardViewData {
  activity: ActivityItem[]
  activitySubtitle: string
  activityTitle: string
  breakdown: BreakdownItem[]
  breakdownSubtitle: string
  breakdownTitle: string
  chartHighlights: ChartHighlight[]
  eyebrow: string
  focus: FocusItem[]
  focusSubtitle: string
  focusTitle: string
  health: {
    detail: string
    score: number
    segments: HealthSegment[]
    summary: string
    title: string
  }
  heroSignals: HeroSignal[]
  metrics: DashboardMetric[]
  subtitle: string
  tags: string[]
  timeline: TimelinePoint[]
  timelineSubtitle: string
  timelineTitle: string
  title: string
}

export const navigationItems: DashboardNavItem[] = [
  {
    badge: '08',
    description: 'Executive snapshot and pacing',
    icon: 'compass',
    id: 'overview',
    label: 'Overview',
  },
  {
    badge: '14',
    description: 'Booked revenue and forecast quality',
    icon: 'chart',
    id: 'revenue',
    label: 'Revenue',
  },
  {
    badge: '06',
    description: 'Relationship heat and renewals',
    icon: 'people',
    id: 'accounts',
    label: 'Accounts',
  },
  {
    badge: '03',
    description: 'Workflow stability and automations',
    icon: 'bolt',
    id: 'automation',
    label: 'Automation',
  },
]

export const dashboardViews: Record<DashboardViewId, DashboardViewData> = {
  overview: {
    activity: [
      {
        detail: 'Contract packets moved from draft to approval two days early.',
        icon: 'spark',
        status: 'Ahead of plan',
        timestamp: '12 min ago',
        title: 'Renewal cohort crossed the weekly target band',
        tone: 'positive',
      },
      {
        detail: 'Alert fan-out rerouted to the backup queue with no customer impact.',
        icon: 'shield',
        status: 'Protected',
        timestamp: '26 min ago',
        title: 'Failover routine contained a transient sync issue',
        tone: 'accent',
      },
      {
        detail: 'Three legal approvals remain before the noon ops review.',
        icon: 'clock',
        status: 'Needs review',
        timestamp: '38 min ago',
        title: 'Expansion approvals stacked in the shared inbox',
        tone: 'warning',
      },
      {
        detail: 'Customer success staffed a deeper coverage block for EMEA.',
        icon: 'people',
        status: 'Rebalanced',
        timestamp: '53 min ago',
        title: 'Renewal staffing shifted to support a larger wave',
        tone: 'muted',
      },
    ],
    activitySubtitle: 'Operator feed for the last ninety minutes',
    activityTitle: 'Recent activity',
    breakdown: [
      {
        label: 'Expansion',
        note: 'Cross-sell plays accelerate in enterprise accounts.',
        share: '44%',
        value: 44,
      },
      {
        label: 'Renewals',
        note: 'Healthy pacing and low discount pressure.',
        share: '27%',
        value: 27,
      },
      {
        label: 'New logo',
        note: 'Mid-market volume is steady but watch the close rate.',
        share: '19%',
        value: 19,
      },
      {
        label: 'Services',
        note: 'Enablement packaging keeps services inside range.',
        share: '10%',
        value: 10,
      },
    ],
    breakdownSubtitle: 'Where booked momentum is coming from this week',
    breakdownTitle: 'Channel mix',
    chartHighlights: [
      {
        label: 'Booked this week',
        note: 'Fastest close cadence in the quarter',
        value: '$1.84M',
      },
      {
        label: 'Pace to plan',
        note: 'Comfortably ahead of the operating line',
        value: '108%',
      },
      {
        label: 'Forecast quality',
        note: 'Confidence remains inside the green band',
        value: '96%',
      },
    ],
    eyebrow: 'Morning brief',
    focus: [
      {
        due: 'Due 10:30',
        owner: 'Revenue operations',
        progress: 84,
        title: 'Approve the final enterprise uplift package',
        tone: 'accent',
      },
      {
        due: 'Due 11:15',
        owner: 'Legal',
        progress: 62,
        title: 'Clear the high-value renewal language review',
        tone: 'warning',
      },
      {
        due: 'Due 12:00',
        owner: 'Customer success',
        progress: 71,
        title: 'Prepare the churn-risk recovery playbook',
        tone: 'positive',
      },
      {
        due: 'Due 13:30',
        owner: 'Automation team',
        progress: 53,
        title: 'Audit the fallback rules on alert fan-out',
        tone: 'muted',
      },
    ],
    focusSubtitle: 'Shared owner handoffs before the noon review',
    focusTitle: 'Priority queue',
    health: {
      detail:
        'Operating rhythm, escalation load, and automation behavior all sit inside the calm zone.',
      score: 94,
      segments: [
        { label: 'Coverage', tone: 'accent', value: '28 plays' },
        { label: 'SLA risk', tone: 'warning', value: '03 queues' },
        { label: 'Recovered', tone: 'positive', value: '12 issues' },
      ],
      summary: 'Systems are balanced and recovery time is low.',
      title: 'Execution health',
    },
    heroSignals: [
      {
        label: 'Forecast confidence',
        note: 'Three points above last week',
        value: '96%',
      },
      {
        label: 'Open approvals',
        note: 'Two are tagged high-value',
        value: '07',
      },
      {
        label: 'Time to recovery',
        note: 'Automation incidents resolve quickly',
        value: '19m',
      },
    ],
    metrics: [
      {
        change: '+12.4%',
        detail: 'Annual recurring revenue versus last quarter',
        label: 'ARR',
        sparkline: [52, 57, 54, 60, 64, 66, 72],
        trend: 'up',
        value: '$18.4M',
      },
      {
        change: '+2.1 pts',
        detail: 'Retention health across the active base',
        label: 'Net retention',
        sparkline: [102, 106, 108, 111, 113, 116, 118],
        trend: 'up',
        value: '117.8%',
      },
      {
        change: '+0.08%',
        detail: 'Sustained workflow reliability this month',
        label: 'Workflow uptime',
        sparkline: [93, 95, 94, 97, 96, 98, 99],
        trend: 'up',
        value: '99.94%',
      },
      {
        change: '-3 cleared',
        detail: 'Enterprise expansions in active negotiation',
        label: 'Expansion velocity',
        sparkline: [17, 19, 21, 24, 22, 20, 19],
        trend: 'steady',
        value: '42 deals',
      },
    ],
    subtitle:
      'Growth is pacing ahead of plan, renewals are settling back into range, and the automation queue only needs a light touch today.',
    tags: ['Quarter close', 'North America lead', 'Live sandbox feed'],
    timeline: [
      { label: 'Mon', target: 980, value: 1010 },
      { label: 'Tue', target: 1015, value: 1120 },
      { label: 'Wed', target: 1070, value: 1210 },
      { label: 'Thu', target: 1140, value: 1320 },
      { label: 'Fri', target: 1180, value: 1365 },
      { label: 'Sat', target: 1225, value: 1430 },
      { label: 'Sun', target: 1280, value: 1495 },
    ],
    timelineSubtitle: 'Booked revenue versus operating target',
    timelineTitle: 'Weekly performance cadence',
    title: 'Command pulse at 08:30',
  },
  revenue: {
    activity: [
      {
        detail: 'The deal desk approved a wider multi-year discount guardrail.',
        icon: 'check',
        status: 'Approved',
        timestamp: '9 min ago',
        title: 'Pricing committee signed off on the enterprise corridor',
        tone: 'positive',
      },
      {
        detail: 'East region is soft on mid-market velocity this morning.',
        icon: 'chart',
        status: 'Watch closely',
        timestamp: '21 min ago',
        title: 'New logo funnel dipped below the comfort band',
        tone: 'warning',
      },
      {
        detail: 'Renewal pacing for strategic accounts remains strong.',
        icon: 'spark',
        status: 'On track',
        timestamp: '33 min ago',
        title: 'Strategic renewal motion outperformed the weekly model',
        tone: 'accent',
      },
      {
        detail: 'Shared commentary posted for the afternoon forecast meeting.',
        icon: 'clock',
        status: 'Prepared',
        timestamp: '47 min ago',
        title: 'Finance annotated the latest forecast swing',
        tone: 'muted',
      },
    ],
    activitySubtitle: 'Revenue desk updates with operator context',
    activityTitle: 'Revenue desk',
    breakdown: [
      {
        label: 'Enterprise',
        note: 'High-value contracts continue to anchor the week.',
        share: '51%',
        value: 51,
      },
      {
        label: 'Mid-market',
        note: 'Volume is healthy, but some deals are slipping right.',
        share: '24%',
        value: 24,
      },
      {
        label: 'Renewal',
        note: 'Low churn pressure keeps the base resilient.',
        share: '17%',
        value: 17,
      },
      {
        label: 'Partner',
        note: 'Partner-sourced pipeline is rebuilding after a quiet start.',
        share: '8%',
        value: 8,
      },
    ],
    breakdownSubtitle: 'Contribution split for committed bookings',
    breakdownTitle: 'Revenue mix',
    chartHighlights: [
      {
        label: 'Commit this week',
        note: 'Finance holds the upper range of the forecast',
        value: '$4.9M',
      },
      {
        label: 'Deal slippage',
        note: 'Only two enterprise contracts moved past Friday',
        value: '6.2%',
      },
      {
        label: 'Discount integrity',
        note: 'Pricing discipline is steady across regions',
        value: '91%',
      },
    ],
    eyebrow: 'Revenue signal',
    focus: [
      {
        due: 'Due 10:00',
        owner: 'Deal desk',
        progress: 88,
        title: 'Final check on the enterprise corridor package',
        tone: 'positive',
      },
      {
        due: 'Due 11:00',
        owner: 'Regional sales lead',
        progress: 57,
        title: 'Tighten the East region recovery plan for mid-market',
        tone: 'warning',
      },
      {
        due: 'Due 12:20',
        owner: 'Finance',
        progress: 74,
        title: 'Reconcile the weekly commit notes before the forecast call',
        tone: 'accent',
      },
      {
        due: 'Due 15:00',
        owner: 'Pricing operations',
        progress: 49,
        title: 'Audit discount spread in the late-stage enterprise queue',
        tone: 'muted',
      },
    ],
    focusSubtitle: 'Revenue actions that shape the afternoon forecast',
    focusTitle: 'Forecast queue',
    health: {
      detail:
        'Pricing, slippage, and enterprise concentration are healthy, with one region below the preferred volume band.',
      score: 89,
      segments: [
        { label: 'Commit quality', tone: 'accent', value: 'A-' },
        { label: 'Discount guardrail', tone: 'positive', value: '91%' },
        { label: 'Regional drift', tone: 'warning', value: 'East' },
      ],
      summary: 'Revenue motion is strong with one region to correct.',
      title: 'Forecast resilience',
    },
    heroSignals: [
      {
        label: 'Committed bookings',
        note: 'Upper forecast range remains intact',
        value: '$4.9M',
      },
      {
        label: 'Avg. close cycle',
        note: 'Shorter than the trailing monthly average',
        value: '7.2d',
      },
      {
        label: 'Enterprise share',
        note: 'Large-contract momentum leads the week',
        value: '51%',
      },
    ],
    metrics: [
      {
        change: '+8.6%',
        detail: 'Committed bookings versus same week last quarter',
        label: 'Weekly commit',
        sparkline: [44, 48, 50, 54, 58, 61, 65],
        trend: 'up',
        value: '$4.9M',
      },
      {
        change: '-1.4 pts',
        detail: 'Slip rate in the final negotiation lane',
        label: 'Deal slippage',
        sparkline: [16, 14, 13, 12, 10, 8, 6],
        trend: 'up',
        value: '6.2%',
      },
      {
        change: '+3.2%',
        detail: 'Weighted pipeline inside the current quarter',
        label: 'Pipeline cover',
        sparkline: [88, 91, 90, 93, 96, 100, 102],
        trend: 'up',
        value: '3.4x',
      },
      {
        change: '-0.3 pts',
        detail: 'Average discount spread across open enterprise deals',
        label: 'Discount spread',
        sparkline: [19, 18, 18, 17, 16, 16, 15],
        trend: 'steady',
        value: '15.8%',
      },
    ],
    subtitle:
      'The revenue engine is leaning on enterprise strength today, with disciplined pricing and only one regional softness pattern to course-correct.',
    tags: ['Forecast day', 'Enterprise heavy', 'Pricing corridor'],
    timeline: [
      { label: 'Mon', target: 2200, value: 2180 },
      { label: 'Tue', target: 2320, value: 2415 },
      { label: 'Wed', target: 2440, value: 2510 },
      { label: 'Thu', target: 2530, value: 2760 },
      { label: 'Fri', target: 2610, value: 2890 },
      { label: 'Sat', target: 2680, value: 3025 },
      { label: 'Sun', target: 2750, value: 3140 },
    ],
    timelineSubtitle: 'Committed bookings versus forecast model',
    timelineTitle: 'Commit trajectory',
    title: 'Revenue cadence is steady and controlled',
  },
  accounts: {
    activity: [
      {
        detail: 'Customer success completed three recovery workshops this morning.',
        icon: 'people',
        status: 'Recovered',
        timestamp: '11 min ago',
        title: 'Strategic accounts climbed back into the healthy band',
        tone: 'positive',
      },
      {
        detail: 'One account reopened discount discussions after a delayed launch.',
        icon: 'clock',
        status: 'Needs touchpoint',
        timestamp: '24 min ago',
        title: 'The top renewal queue surfaced one at-risk expansion',
        tone: 'warning',
      },
      {
        detail: 'Usage adoption metrics lifted after the weekend release.',
        icon: 'spark',
        status: 'Improving',
        timestamp: '35 min ago',
        title: 'Product adoption signals rose across the EMEA cohort',
        tone: 'accent',
      },
      {
        detail: 'Success leads aligned on rescue coverage for three mid-market logos.',
        icon: 'check',
        status: 'Aligned',
        timestamp: '50 min ago',
        title: 'Retention squad redistributed the renewal workload',
        tone: 'muted',
      },
    ],
    activitySubtitle: 'Signals from success, support, and account owners',
    activityTitle: 'Relationship feed',
    breakdown: [
      {
        label: 'Healthy',
        note: 'Accounts renewing on plan and expanding naturally.',
        share: '58%',
        value: 58,
      },
      {
        label: 'Growing',
        note: 'Adoption and seat growth are trending in the right direction.',
        share: '22%',
        value: 22,
      },
      {
        label: 'Watchlist',
        note: 'Requires proactive touchpoints this week.',
        share: '13%',
        value: 13,
      },
      {
        label: 'Critical',
        note: 'Small but important group needing executive support.',
        share: '7%',
        value: 7,
      },
    ],
    breakdownSubtitle: 'Relationship temperature across the active base',
    breakdownTitle: 'Account health',
    chartHighlights: [
      {
        label: 'Renewal wave',
        note: 'Larger strategic accounts are on a strong path',
        value: '$7.6M',
      },
      {
        label: 'Risk concentration',
        note: 'Only five accounts represent most of the downside',
        value: '5 logos',
      },
      {
        label: 'Product adoption',
        note: 'Usage depth improved after the last release',
        value: '+14%',
      },
    ],
    eyebrow: 'Account health',
    focus: [
      {
        due: 'Due 10:45',
        owner: 'Customer success',
        progress: 79,
        title: 'Run an executive rescue touchpoint for the delayed launch account',
        tone: 'warning',
      },
      {
        due: 'Due 11:40',
        owner: 'Product specialist',
        progress: 67,
        title: 'Package the new adoption story for the EMEA cohort review',
        tone: 'accent',
      },
      {
        due: 'Due 13:10',
        owner: 'Account director',
        progress: 92,
        title: 'Confirm next-year seat growth assumptions with the top renewal',
        tone: 'positive',
      },
      {
        due: 'Due 16:00',
        owner: 'Support lead',
        progress: 44,
        title: 'Close the remaining support debt on the watchlist segment',
        tone: 'muted',
      },
    ],
    focusSubtitle: 'Shared relationship actions for today',
    focusTitle: 'Retention queue',
    health: {
      detail:
        'The base is healthy overall, but one strategic account still needs executive air cover before the weekly renewal review.',
      score: 87,
      segments: [
        { label: 'Healthy base', tone: 'positive', value: '58%' },
        { label: 'Watchlist', tone: 'warning', value: '13%' },
        { label: 'Expansion ready', tone: 'accent', value: '31 logos' },
      ],
      summary: 'Relationship quality is strong with a narrow rescue lane.',
      title: 'Customer temperature',
    },
    heroSignals: [
      {
        label: 'Renewal coverage',
        note: 'Strategic renewals remain safely above plan',
        value: '1.8x',
      },
      {
        label: 'Healthy base',
        note: 'Most accounts are staying in the calm zone',
        value: '58%',
      },
      {
        label: 'Expansion-ready logos',
        note: 'Usage depth supports a wider seat motion',
        value: '31',
      },
    ],
    metrics: [
      {
        change: '+1.9 pts',
        detail: 'Customer health score across strategic accounts',
        label: 'Strategic health',
        sparkline: [61, 62, 64, 65, 67, 69, 70],
        trend: 'up',
        value: '70 / 100',
      },
      {
        change: '+4.3%',
        detail: 'Product adoption depth month over month',
        label: 'Usage depth',
        sparkline: [38, 41, 44, 48, 50, 53, 57],
        trend: 'up',
        value: '57%',
      },
      {
        change: '-2 logos',
        detail: 'Accounts requiring executive rescue',
        label: 'Critical risk',
        sparkline: [12, 11, 10, 9, 8, 7, 5],
        trend: 'up',
        value: '5 logos',
      },
      {
        change: '+6.7%',
        detail: 'Expansion-ready seat opportunity in active accounts',
        label: 'Seat growth',
        sparkline: [20, 21, 22, 25, 27, 30, 31],
        trend: 'up',
        value: '$2.3M',
      },
    ],
    subtitle:
      'Relationships look healthy overall, and adoption is improving, but one executive account still needs deliberate rescue attention before the renewal review.',
    tags: ['Success orchestration', 'Renewal wave', 'Adoption uplift'],
    timeline: [
      { label: 'Mon', target: 62, value: 61 },
      { label: 'Tue', target: 63, value: 64 },
      { label: 'Wed', target: 64, value: 65 },
      { label: 'Thu', target: 65, value: 67 },
      { label: 'Fri', target: 66, value: 68 },
      { label: 'Sat', target: 67, value: 69 },
      { label: 'Sun', target: 68, value: 70 },
    ],
    timelineSubtitle: 'Strategic account health score versus target curve',
    timelineTitle: 'Relationship temperature',
    title: 'Customer confidence is trending upward',
  },
  automation: {
    activity: [
      {
        detail: 'Fallback routing handled the alert flood without breaching SLA.',
        icon: 'shield',
        status: 'Contained',
        timestamp: '8 min ago',
        title: 'Notification failover absorbed a transient queue spike',
        tone: 'positive',
      },
      {
        detail: 'One enrichment step timed out and retried twice before success.',
        icon: 'clock',
        status: 'Investigate',
        timestamp: '19 min ago',
        title: 'Customer enrichment flow showed a short latency wobble',
        tone: 'warning',
      },
      {
        detail: 'The deployment lane stayed under the expected duration ceiling.',
        icon: 'bolt',
        status: 'Stable',
        timestamp: '31 min ago',
        title: 'Workflow release train finished inside the target window',
        tone: 'accent',
      },
      {
        detail: 'Engineering closed the noisy monitor that fired overnight.',
        icon: 'check',
        status: 'Closed',
        timestamp: '44 min ago',
        title: 'The alert hygiene pass removed one stale trigger',
        tone: 'muted',
      },
    ],
    activitySubtitle: 'Operational feed across workflows and release rails',
    activityTitle: 'Automation events',
    breakdown: [
      {
        label: 'Background jobs',
        note: 'The majority of runtime stays in predictable async work.',
        share: '39%',
        value: 39,
      },
      {
        label: 'Integrations',
        note: 'External systems remain the noisiest dependency layer.',
        share: '28%',
        value: 28,
      },
      {
        label: 'Alerts',
        note: 'Monitoring volume stayed light after the cleanup pass.',
        share: '18%',
        value: 18,
      },
      {
        label: 'Deployments',
        note: 'Release automation is steady and low-touch today.',
        share: '15%',
        value: 15,
      },
    ],
    breakdownSubtitle: 'Runtime attention by automation surface',
    breakdownTitle: 'Operational load',
    chartHighlights: [
      {
        label: 'Successful runs',
        note: 'Retries remained low throughout the morning',
        value: '14.2k',
      },
      {
        label: 'MTTR',
        note: 'Faster than the quarterly operating goal',
        value: '19m',
      },
      {
        label: 'Release confidence',
        note: 'No rollback signals in the current lane',
        value: '97%',
      },
    ],
    eyebrow: 'Automation watch',
    focus: [
      {
        due: 'Due 09:50',
        owner: 'Platform',
        progress: 83,
        title: 'Audit the enrichment timeout branch and update the retry backoff',
        tone: 'warning',
      },
      {
        due: 'Due 10:40',
        owner: 'Observability',
        progress: 91,
        title: 'Ship the quiet monitor rule to the alerting baseline',
        tone: 'positive',
      },
      {
        due: 'Due 12:10',
        owner: 'Release engineering',
        progress: 68,
        title: 'Review the next deployment lane before handoff',
        tone: 'accent',
      },
      {
        due: 'Due 15:30',
        owner: 'Integrations',
        progress: 51,
        title: 'Confirm the fallback connector budget for peak volume',
        tone: 'muted',
      },
    ],
    focusSubtitle: 'Automation tasks with human attention today',
    focusTitle: 'Intervention queue',
    health: {
      detail:
        'The stack is stable and alert noise is down, though one enrichment path still needs a small resiliency tweak.',
      score: 92,
      segments: [
        { label: 'Run success', tone: 'positive', value: '99.1%' },
        { label: 'Retry spike', tone: 'warning', value: '1 flow' },
        { label: 'Quiet alerts', tone: 'accent', value: '18%' },
      ],
      summary: 'Automation is healthy and mostly self-healing this morning.',
      title: 'Reliability posture',
    },
    heroSignals: [
      {
        label: 'Successful runs',
        note: 'High-volume workflows stay inside tolerance',
        value: '14.2k',
      },
      {
        label: 'Alert noise',
        note: 'Lower than the weekly average after cleanup',
        value: '-18%',
      },
      {
        label: 'Deployment confidence',
        note: 'Release lane is stable with no rollback signals',
        value: '97%',
      },
    ],
    metrics: [
      {
        change: '+0.4%',
        detail: 'Workflow completion rate across the morning window',
        label: 'Run success',
        sparkline: [94, 95, 95, 96, 97, 98, 99],
        trend: 'up',
        value: '99.1%',
      },
      {
        change: '-18%',
        detail: 'Alert volume versus the prior weekly average',
        label: 'Alert noise',
        sparkline: [42, 38, 34, 31, 28, 25, 21],
        trend: 'up',
        value: '21 alerts',
      },
      {
        change: '+6 min',
        detail: 'Recovery time after transient automation incidents',
        label: 'MTTR',
        sparkline: [28, 26, 24, 22, 21, 20, 19],
        trend: 'up',
        value: '19 min',
      },
      {
        change: '+1 release',
        detail: 'Deployments completed without manual rollback',
        label: 'Release rhythm',
        sparkline: [5, 6, 6, 7, 8, 8, 9],
        trend: 'steady',
        value: '9 today',
      },
    ],
    subtitle:
      'The automation stack is running calmly with low alert noise, a clean deployment lane, and one enrichment branch that still deserves a quick resilience pass.',
    tags: ['Reliability lane', 'Quiet alerts', 'Release ready'],
    timeline: [
      { label: 'Mon', target: 94, value: 95 },
      { label: 'Tue', target: 95, value: 95 },
      { label: 'Wed', target: 95, value: 96 },
      { label: 'Thu', target: 96, value: 97 },
      { label: 'Fri', target: 96, value: 98 },
      { label: 'Sat', target: 97, value: 99 },
      { label: 'Sun', target: 97, value: 99.1 },
    ],
    timelineSubtitle: 'Workflow completion versus reliability target',
    timelineTitle: 'System reliability',
    title: 'Automation reliability is holding steady',
  },
}
