import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactNode } from 'react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { AccuracyPage } from '../features/accuracy/AccuracyPage'
import { DecisionPage } from '../features/decision/DecisionPage'
import { accuracyReport, decisionView, meta } from './fixtures'

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

const requests: string[] = []

function urlOf(input: RequestInfo | URL): string {
  return typeof input === 'string' ? input : input instanceof URL ? input.href : input.url
}

function mockApi(overrides?: { meta?: Partial<typeof meta>; forecastStatus?: number }) {
  requests.length = 0
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
    const url = urlOf(input)
    requests.push(url)
    if (url.includes('/meta')) return jsonResponse({ ...meta, ...overrides?.meta })
    if (url.includes('/forecast')) {
      if (overrides?.forecastStatus) {
        return jsonResponse(
          {
            title: 'Date out of supported scope',
            status: overrides.forecastStatus,
            detail: 'out of range',
          },
          overrides.forecastStatus,
        )
      }
      return jsonResponse(decisionView)
    }
    if (url.includes('/accuracy')) return jsonResponse(accuracyReport)
    return jsonResponse({ title: 'Not found', status: 404 }, 404)
  })
}

function renderAt(path: string, element: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/decision" element={element} />
          <Route path="/accuracy" element={element} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

beforeEach(() => mockApi())

describe('DecisionPage', () => {
  it('shows which issue was used, its age, and the headline numbers', async () => {
    renderAt('/decision?date=2026-01-15', <DecisionPage />)
    expect(await screen.findByText('Thu 15 Jan, 09:30')).toBeInTheDocument()
    expect(screen.getByText('20 min')).toBeInTheDocument()
    expect(screen.getByText('Forecast energy')).toBeInTheDocument()
    expect(screen.getByText('Dependable energy (P90)')).toBeInTheDocument()
    expect(screen.getByText('Skill vs persistence')).toBeInTheDocument()
    expect(screen.getByText('+397')).toBeInTheDocument()
    expect(screen.getByRole('table')).toBeInTheDocument()
    expect(
      requests.some((u) => u.includes('decision_date=2026-01-15') && u.includes('cutoff=09%3A50')),
    ).toBe(true)
  })

  it('moves to the previous day and keeps the cutoff', async () => {
    const user = userEvent.setup()
    renderAt('/decision?date=2026-01-15&cutoff=09:20', <DecisionPage />)
    await screen.findByText('Thu 15 Jan, 09:30')
    await user.click(screen.getByRole('button', { name: /Prev/ }))
    await waitFor(() =>
      expect(
        requests.some(
          (u) => u.includes('decision_date=2026-01-14') && u.includes('cutoff=09%3A20'),
        ),
      ).toBe(true),
    )
  })

  it('clamps out-of-scope dates to the supported window', async () => {
    renderAt('/decision?date=2026-03-01', <DecisionPage />)
    await screen.findByText('Thu 15 Jan, 09:30')
    expect(requests.some((u) => u.includes('decision_date=2026-01-31'))).toBe(true)
  })

  it('computes the procurement planner from dependable wind', async () => {
    const user = userEvent.setup()
    renderAt('/decision?date=2026-01-15', <DecisionPage />)
    await screen.findByText('Thu 15 Jan, 09:30')
    await user.type(screen.getByLabelText(/Demand to serve/), '10000')
    // Raw: sum over h of max(0, 10000 - (8000 + 50h)) = 48,000 - 13,800 = 34,200
    expect(screen.getByText('34,200 MWh')).toBeInTheDocument()
    // Dependable: forecast - 4777 -> sum of (10000 - (3223 + 50h)) = 162,648 - 13,800 = 148,848
    expect(screen.getByText('148,848 MWh')).toBeInTheDocument()
  })

  it('renders API problem details as an error state', async () => {
    mockApi({ meta: { last_decision_date: '2026-02-28' }, forecastStatus: 400 })
    renderAt('/decision?date=2026-02-10', <DecisionPage />)
    expect(await screen.findByRole('alert')).toHaveTextContent('out of range')
  })
})

describe('AccuracyPage', () => {
  it('shows the buffer, lets the user change the coverage level, and lists findings', async () => {
    const user = userEvent.setup()
    renderAt('/accuracy', <AccuracyPage />)
    expect(await screen.findByText(/covered in 90% of hours/)).toBeInTheDocument()
    expect(screen.getByText('4,144')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: '95%' }))
    expect(screen.getByText('5,322')).toBeInTheDocument()
    expect(screen.getByText(/covered 648 of 744 hours/)).toBeInTheDocument()
    expect(screen.getByText('Skill vs persistence')).toBeInTheDocument()
    expect(screen.getByText('Error by forecast level')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Download CSV/ })).toHaveAttribute(
      'href',
      expect.stringContaining('/api/v1/accuracy/export.csv'),
    )
  })
})
