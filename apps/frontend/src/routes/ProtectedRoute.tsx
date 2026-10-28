import { Navigate, Outlet } from "react-router-dom"

import { useAuth } from "@/lib/AuthContext"

export function ProtectedRoute() {
  const { user, isLoading } = useAuth()

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-950">
        <span className="size-6 animate-spin rounded-full border-2 border-slate-600 border-t-brand-400" />
      </div>
    )
  }

  if (!user) {
    return <Navigate to="/login" replace />
  }

  return <Outlet />
}
