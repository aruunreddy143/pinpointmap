import { useState } from 'react'
import { Segmented } from '@/components/ui'
import { DemoPicker } from '../SignInPage'
import { AuthShell } from './AuthShell'
import { StaffLoginForm } from './StaffLoginForm'
import { UserLoginForm } from './UserLoginForm'

export function LoginPage() {
  const [who, setWho] = useState<'user' | 'staff'>('user')
  return (
    <AuthShell
      title={who === 'user' ? 'Find any place by its ID' : 'Staff sign in'}
      subtitle={who === 'user' ? 'Sign in or create a free read-only account with your mobile number or email.' : 'For registrars, verifiers, printers, auditors and admins.'}
      footer={
        import.meta.env.DEV ? (
          <details className="rounded-card border border-dashed border-border p-4">
            <summary className="cursor-pointer text-[13px] font-semibold text-muted">Developer shortcut: open as any role</summary>
            <div className="mt-4"><DemoPicker /></div>
          </details>
        ) : null
      }
    >
      <Segmented label="I am a" value={who} onChange={setWho} options={[{ value: 'user', label: 'Normal user' }, { value: 'staff', label: 'Staff' }]} />
      {who === 'user' ? <UserLoginForm key="user" /> : <StaffLoginForm key="staff" />}
    </AuthShell>
  )
}
