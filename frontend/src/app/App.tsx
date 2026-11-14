import { Navigate, Route, Routes } from 'react-router-dom'
import { RequireRole, StaffShell, ViewerShell } from './layouts'
import { useSession } from './providers'
import { isStaff } from '@/lib/permissions'
import { LoginPage } from '@/pages/auth/LoginPage'
import { ForgotPasswordPage } from '@/pages/auth/ForgotPasswordPage'
import { AcceptInvitePage } from '@/pages/auth/AcceptInvitePage'
import { UsersPage } from '@/pages/staff/UsersPage'
import { MapPage } from '@/pages/staff/MapPage'
import { PlacesPage } from '@/pages/staff/PlacesPage'
import { PlaceDetailPage } from '@/pages/staff/PlaceDetailPage'
import { LabelPage } from '@/pages/staff/LabelPage'
import { RegisterPage } from '@/pages/staff/RegisterPage'
import { ReviewPage } from '@/pages/staff/ReviewPage'
import { ComingSoonPage } from '@/pages/staff/ComingSoonPage'
import { ScanPage } from '@/pages/ScanPage'
import { ResolverPage } from '@/pages/ResolverPage'
import { ViewerHome } from '@/pages/viewer/ViewerHome'
import { ViewerPlacePage } from '@/pages/viewer/ViewerPlacePage'

function Home() {
  const { role } = useSession()
  if (!role) return <LoginPage />
  return <Navigate to={isStaff(role) ? '/staff/map' : '/app'} replace />
}

export function App() {
  return (
    <Routes>
      <Route path="/" element={<Home />} />
      <Route path="/p/:id" element={<ResolverPage />} />
      <Route path="/forgot" element={<ForgotPasswordPage />} />
      <Route path="/invite/:token" element={<AcceptInvitePage />} />
      <Route path="/staff" element={<RequireRole allow="staff" />}>
        <Route element={<StaffShell />}>
          <Route index element={<Navigate to="map" replace />} />
          <Route path="map" element={<MapPage />} />
          <Route path="places" element={<PlacesPage />} />
          <Route path="places/:id" element={<PlaceDetailPage />} />
          <Route path="places/:id/label" element={<LabelPage />} />
          <Route path="register" element={<RegisterPage />} />
          <Route path="review" element={<ReviewPage />} />
          <Route path="scan" element={<ScanPage base="/staff" />} />
          <Route path="users" element={<UsersPage />} />
          <Route path="audit" element={<ComingSoonPage title="Audit log" text="Every change will be listed here. This arrives with the backend." />} />
        </Route>
      </Route>
      <Route path="/app" element={<RequireRole allow="viewer" />}>
        <Route element={<ViewerShell />}>
          <Route index element={<ViewerHome />} />
          <Route path="places/:id" element={<ViewerPlacePage />} />
          <Route path="scan" element={<ScanPage base="/app" />} />
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
