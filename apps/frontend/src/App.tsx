import { Navigate, Route, Routes } from "react-router-dom"

import { AppLayout } from "@/components/AppLayout"
import { DashboardPage } from "@/pages/DashboardPage"
import { ComingSoonPage } from "@/pages/ComingSoonPage"
import { LoginPage } from "@/pages/LoginPage"
import { RegisterPage } from "@/pages/RegisterPage"
import { ProtectedRoute } from "@/routes/ProtectedRoute"

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />

      <Route element={<ProtectedRoute />}>
        <Route element={<AppLayout />}>
          <Route path="/" element={<DashboardPage />} />
          <Route
            path="/applications"
            element={<ComingSoonPage title="Application Registry" phase="Phase 2" />}
          />
          <Route
            path="/environments"
            element={<ComingSoonPage title="Environments" phase="Phase 2" />}
          />
          <Route path="/teams" element={<ComingSoonPage title="Teams" phase="Phase 2" />} />
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
