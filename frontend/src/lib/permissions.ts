import type { Permission, Role } from './types'

// Single source of truth for role -> permissions (mirrors the backend's app/core/permissions.py).
const MAP: Record<Role, Permission[]> = {
  super_admin: ['place:read', 'place:create', 'place:update', 'place:verify', 'place:print', 'user:manage', 'audit:read'],
  admin: ['place:read', 'place:create', 'place:update', 'place:verify', 'place:print', 'user:manage', 'audit:read'],
  registrar: ['place:read', 'place:create', 'place:update'],
  verifier: ['place:read', 'place:verify'],
  printer: ['place:read', 'place:print'],
  auditor: ['place:read', 'audit:read'],
  viewer: ['place:read_public', 'correction:request'],
}

export const ROLE_LABEL: Record<Role, string> = {
  super_admin: 'Super admin',
  admin: 'Admin',
  registrar: 'Registrar',
  verifier: 'Verifier',
  printer: 'Printer',
  auditor: 'Auditor',
  viewer: 'Normal user',
}

export function can(role: Role, permission: Permission): boolean {
  return MAP[role].includes(permission)
}

export function isStaff(role: Role): boolean {
  return role !== 'viewer'
}
