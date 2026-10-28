import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card"
import { useAuth } from "@/lib/AuthContext"

/**
 * Phase 1 placeholder. The real dashboard (environment/application counts,
 * success rate, provisioning duration, cost) is wired up in Phase 6 once the
 * Application Registry and Environment APIs exist — until then this shows
 * an honest empty state rather than mock KPI cards.
 */
export function DashboardPage() {
  const { user } = useAuth()

  return (
    <div className="p-8">
      <h1 className="text-2xl font-semibold text-slate-100">Welcome, {user?.full_name}</h1>
      <p className="mt-1 text-sm text-slate-400">
        Signed in as <span className="text-slate-300">{user?.email}</span> ·{" "}
        {user?.platform_role.replace("_", " ")}
      </p>

      <Card className="mt-6 max-w-xl">
        <CardHeader>
          <CardTitle>Platform status</CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-slate-400">
          Authentication and the developer portal shell are live. The application
          registry, environment catalog and lifecycle dashboard land in the next
          build phases.
        </CardContent>
      </Card>
    </div>
  )
}
