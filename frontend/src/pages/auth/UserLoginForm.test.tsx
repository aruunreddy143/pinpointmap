import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { SessionProvider } from '@/app/providers'
import { UserLoginForm } from './UserLoginForm'

const renderForm = () =>
  render(
    <SessionProvider initialRole={null}>
      <MemoryRouter>
        <Routes>
          <Route path="/" element={<UserLoginForm />} />
          <Route path="/app" element={<div>Viewer home</div>} />
        </Routes>
      </MemoryRouter>
    </SessionProvider>,
  )

describe('UserLoginForm', () => {
  it('accepts a mobile number OR an email, and tells you which channel will be used', async () => {
    const user = userEvent.setup()
    renderForm()
    const field = screen.getByLabelText('Mobile number or email')
    const send = screen.getByRole('button', { name: 'Send code' })
    expect(send).toBeDisabled()

    await user.type(field, '98765')
    expect(screen.getByRole('status')).toHaveTextContent(/10-digit/)
    expect(send).toBeDisabled()

    await user.clear(field)
    await user.type(field, '98765 43210')
    expect(screen.getByRole('status')).toHaveTextContent('SMS to +91 98765 43210')
    expect(send).toBeEnabled()

    await user.clear(field)
    await user.type(field, 'priya@example.com')
    expect(screen.getByRole('status')).toHaveTextContent('email to priya@example.com')
    expect(send).toBeEnabled()
  })

  it('signs in an existing account by email and code', async () => {
    const user = userEvent.setup()
    renderForm()
    await user.type(screen.getByLabelText('Mobile number or email'), 'priya@example.com')
    await user.click(screen.getByRole('button', { name: 'Send code' }))
    await user.type(await screen.findByLabelText('Enter the code'), '123456')
    await user.click(screen.getByRole('button', { name: 'Verify' }))
    expect(await screen.findByText('Viewer home')).toBeInTheDocument()
  })

  it('shows tries left for a wrong code, and asks a new person for their name', async () => {
    const user = userEvent.setup()
    renderForm()
    await user.type(screen.getByLabelText('Mobile number or email'), 'fresh.user@example.com')
    await user.click(screen.getByRole('button', { name: 'Send code' }))
    const code = await screen.findByLabelText('Enter the code')
    await user.type(code, '111111')
    await user.click(screen.getByRole('button', { name: 'Verify' }))
    expect(await screen.findByText(/4 tries left/)).toBeInTheDocument()
    await user.clear(code)
    await user.type(code, '123456')
    await user.click(screen.getByRole('button', { name: 'Verify' }))
    expect(await screen.findByLabelText('Your name')).toBeInTheDocument()
  })
})
