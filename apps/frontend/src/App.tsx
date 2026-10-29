import { Navigate, Route, Routes } from "react-router-dom"

import { AppLayout } from "@/components/AppLayout"
import { ApplicationDetailPage } from "@/pages/ApplicationDetailPage"
import { ApplicationsPage } from "@/pages/ApplicationsPage"
import { AuditPage } from "@/pages/AuditPage"
import { ComingSoonPage } from "@/pages/ComingSoonPage"
import { DashboardPage } from "@/pages/DashboardPage"
import { EnvironmentDetailPage } from "@/pages/EnvironmentDetailPage"
import { EnvironmentsPage } from "@/pages/EnvironmentsPage"
import { LoginPage } from "@/pages/LoginPage"
import { RegisterPage } from "@/pages/RegisterPage"
import { TeamsPage } from "@/pages/TeamsPage"
import { TemplatesPage } from "@/pages/TemplatesPage"
import { ProtectedRoute } from "@/routes/ProtectedRoute"

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />

      <Route element={<ProtectedRoute />}>
        <Route element={<AppLayout />}>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/applications" element={<ApplicationsPage />} />
          <Route path="/applications/:applicationId" element={<ApplicationDetailPage />} />
          <Route path="/environments" element={<EnvironmentsPage />} />
          <Route path="/environments/:environmentId" element={<EnvironmentDetailPage />} />
          <Route path="/templates" element={<TemplatesPage />} />
          <Route path="/teams" element={<TeamsPage />} />
          <Route path="/audit" element={<AuditPage />} />
          <Route
            path="/settings"
            element={<ComingSoonPage title="Platform Settings" phase="Phase 7" />}
          />
        </Route>
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
