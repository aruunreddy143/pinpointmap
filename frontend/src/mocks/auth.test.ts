import { acceptInvite, completeSignup, DEMO_OTP, DEMO_PASSWORD, DEMO_TOTP, getInvite, inviteStaff, requestCode, requestPasswordReset, staffLogin, staffVerifyTotp, verifyCode } from './auth'

describe('normal user sign in / sign up (mobile or email)', () => {
  it('signs in an existing account with a correct code', async () => {
    await requestCode('+919876543210')
    expect(await verifyCode('+919876543210', DEMO_OTP)).toEqual({ status: 'ok', name: 'Priya K.' })
  })

  it('asks a new mobile number or email for a name, then creates the account', async () => {
    for (const id of ['+917000000001', 'newbie@example.com']) {
      await requestCode(id)
      expect(await verifyCode(id, DEMO_OTP)).toEqual({ status: 'new' })
      await completeSignup(id, '  Asha Rao ')
      await requestCode(id)
      expect(await verifyCode(id, DEMO_OTP)).toEqual({ status: 'ok', name: 'Asha Rao' })
    }
  })

  it('counts wrong codes down and then locks, until a new code is requested', async () => {
    const id = 'lock@example.com'
    await requestCode(id)
    expect(await verifyCode(id, '000000')).toEqual({ status: 'wrong', triesLeft: 4 })
    for (let i = 0; i < 3; i++) await verifyCode(id, '000000')
    expect(await verifyCode(id, '000000')).toEqual({ status: 'locked' })
    expect(await verifyCode(id, DEMO_OTP)).toEqual({ status: 'locked' })
    await requestCode(id)
    expect((await verifyCode(id, DEMO_OTP)).status).toBe('new')
  })

  it('rate-limits code requests per identifier', async () => {
    const id = 'spam@example.com'
    for (let i = 0; i < 3; i++) expect((await requestCode(id)).ok).toBe(true)
    expect(await requestCode(id)).toEqual({ ok: false, error: 'rate_limited' })
  })

  it('answers a code request the same for known and unknown identifiers', async () => {
    expect(await requestCode('+919876543210')).toEqual(await requestCode('+910000000000'.replace('0000000000', '7123456789')))
  })
})

describe('staff sign in (password + authenticator)', () => {
  it('needs both the password and the authenticator code', async () => {
    const step1 = await staffLogin('registrar@pinpoint.test', DEMO_PASSWORD)
    expect(step1.status).toBe('totp')
    if (step1.status !== 'totp') return
    expect(await staffVerifyTotp(step1.ticket, '000000')).toEqual({ status: 'wrong' })
    expect(await staffVerifyTotp(step1.ticket, DEMO_TOTP)).toEqual({ status: 'ok', role: 'registrar', name: 'Arun R.' })
  })

  it('gives the same answer for a wrong password and an unknown email', async () => {
    expect(await staffLogin('registrar@pinpoint.test', 'nope')).toEqual({ status: 'bad' })
    expect(await staffLogin('nobody@pinpoint.test', 'nope')).toEqual({ status: 'bad' })
  })

  it('locks after repeated wrong passwords', async () => {
    for (let i = 0; i < 5; i++) await staffLogin('auditor@pinpoint.test', 'wrong')
    expect(await staffLogin('auditor@pinpoint.test', DEMO_PASSWORD)).toEqual({ status: 'locked' })
  })

  it('password reset never reveals whether an account exists', async () => {
    await expect(requestPasswordReset('admin@pinpoint.test')).resolves.toBeUndefined()
    await expect(requestPasswordReset('nobody@pinpoint.test')).resolves.toBeUndefined()
  })
})

describe('staff invites', () => {
  it('only an invited person can set a password and authenticator, and the link works once', async () => {
    const inv = await inviteStaff('New.Person@Org.test', 'verifier', 'Mysuru')
    expect('error' in inv).toBe(false)
    if ('error' in inv || !inv.inviteToken) return
    expect(await getInvite(inv.inviteToken)).toEqual({ email: 'new.person@org.test', role: 'verifier' })
    expect(await acceptInvite(inv.inviteToken, 'N P', 'weak', DEMO_TOTP)).toMatchObject({ ok: false })
    expect(await acceptInvite(inv.inviteToken, 'N P', 'Str0ngPassword', '000000')).toMatchObject({ ok: false })
    expect(await acceptInvite(inv.inviteToken, 'N P', 'Str0ngPassword', DEMO_TOTP)).toEqual({ ok: true, role: 'verifier', name: 'N P' })
    expect(await getInvite(inv.inviteToken)).toBeNull()
  })

  it('refuses duplicate invites and roles that cannot be invited', async () => {
    expect(await inviteStaff('admin@pinpoint.test', 'registrar', 'Mysuru')).toHaveProperty('error')
    expect(await inviteStaff('x@org.test', 'viewer', 'Mysuru')).toHaveProperty('error')
  })
})
