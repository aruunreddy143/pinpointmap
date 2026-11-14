import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ScanPage } from './ScanPage'
import { makeId } from '@/lib/placeId'

const renderPage = () =>
  render(
    <MemoryRouter>
      <ScanPage base="/app" />
    </MemoryRouter>,
  )

describe('ScanPage manual entry', () => {
  it('keeps "Open place" disabled until the check character matches', async () => {
    const user = userEvent.setup()
    renderPage()
    const button = screen.getByRole('button', { name: 'Open place' })
    expect(button).toBeDisabled()
    await user.type(screen.getByLabelText('Or type the ID'), makeId('FC98J327K4', '56LM').toLowerCase())
    expect(screen.getByRole('status', { name: '' })).toHaveTextContent(/Valid ID/)
    expect(button).toBeEnabled()
  })

  it('explains a mistyped ID instead of opening it', async () => {
    const user = userEvent.setup()
    renderPage()
    const id = makeId('FC98J327K4', '56LM')
    const bad = id.slice(0, 4) + (id[4] === 'F' ? 'C' : 'F') + id.slice(5)
    await user.type(screen.getByLabelText('Or type the ID'), bad)
    expect(screen.getByText(/check character does not match/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Open place' })).toBeDisabled()
  })
})
