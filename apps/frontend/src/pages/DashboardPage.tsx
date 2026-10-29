import { useQuery } from "@tanstack/react-query"
import { AlertTriangle, Boxes, CheckCircle2, Lightbulb, Loader2, XCircle } from "lucide-react"
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"

import { dashboardApi } from "@/api/dashboard"
import { Badge } from "@/components/ui/Badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card"
import { formatState } from "@/lib/environmentState"
import { useAuth } from "@/lib/AuthContext"

function StatCard({
  icon: Icon,
  label,
  value,
  tone = "neutral",
}: {
  icon: React.ElementType
  label: string
  value: React.ReactNode
  tone?: "neutral" | "success" | "warning" | "danger" | "info"
}) {
  const toneClasses: Record<string, string> = {
    neutral: "text-slate-300",
    success: "text-emerald-400",
    warning: "text-amber-400",
    danger: "text-rose-400",
    info: "text-brand-400",
  }
  return (
    <Card>
      <CardContent className="flex items-center gap-4 pt-5">
        <div className={`rounded-lg bg-slate-800 p-2.5 ${toneClasses[tone]}`}>
          <Icon className="size-5" />
        </div>
        <div>
          <p className="text-2xl font-semibold text-slate-100">{value}</p>
          <p className="text-xs text-slate-400">{label}</p>
        </div>
      </CardContent>
    </Card>
  )
}

export function DashboardPage() {
  const { user } = useAuth()
  const { data, isLoading, isError } = useQuery({
    queryKey: ["dashboard-summary"],
    queryFn: dashboardApi.summary,
    refetchInterval: 15_000,
  })

  const { data: costSummary } = useQuery({
    queryKey: ["dashboard-cost-summary"],
    queryFn: dashboardApi.costSummary,
    refetchInterval: 30_000,
  })

  const { data: recommendations } = useQuery({
    queryKey: ["dashboard-recommendations"],
    queryFn: dashboardApi.recommendations,
    refetchInterval: 30_000,
  })

  return (
    <div className="p-8">
      <h1 className="text-2xl font-semibold text-slate-100">Welcome, {user?.full_name}</h1>
      <p className="mt-1 text-sm text-slate-400">
        Platform overview · {user?.platform_role.replace("_", " ")}
      </p>

      {isLoading ? (
        <div className="mt-8 flex items-center gap-2 text-sm text-slate-400">
          <Loader2 className="size-4 animate-spin" /> Loading dashboard…
        </div>
      ) : isError || !data ? (
        <p className="mt-8 text-sm text-rose-400">Could not load dashboard data.</p>
      ) : (
        <>
          <div className="mt-6 grid grid-cols-2 gap-4 lg:grid-cols-5">
            <StatCard icon={Boxes} label="Total environments" value={data.total_environments} />
            <StatCard
              icon={CheckCircle2}
              label="Active"
              value={data.active_environments}
              tone="success"
            />
            <StatCard
              icon={Loader2}
              label="Provisioning"
              value={data.provisioning_environments}
              tone="info"
            />
            <StatCard icon={XCircle} label="Failed" value={data.failed_environments} tone="danger" />
            <StatCard
              icon={AlertTriangle}
              label="Expiring (24h)"
              value={data.expiring_environments}
              tone="warning"
            />
          </div>

          <div className="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Environments by application</CardTitle>
              </CardHeader>
              <CardContent>
                {data.environments_by_application.length === 0 ? (
                  <p className="py-8 text-center text-sm text-slate-500">No active environments yet.</p>
                ) : (
                  <ResponsiveContainer width="100%" height={220}>
                    <BarChart data={data.environments_by_application}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                      <XAxis dataKey="name" tick={{ fill: "#94a3b8", fontSize: 12 }} />
                      <YAxis allowDecimals={false} tick={{ fill: "#94a3b8", fontSize: 12 }} />
                      <Tooltip
                        contentStyle={{
                          background: "#0f172a",
                          border: "1px solid #1e293b",
                          borderRadius: 8,
                          color: "#e2e8f0",
                        }}
                      />
                      <Bar dataKey="active_count" name="Active" fill="#3366ff" radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Environments by team</CardTitle>
              </CardHeader>
              <CardContent>
                {data.environments_by_team.length === 0 ? (
                  <p className="py-8 text-center text-sm text-slate-500">No active environments yet.</p>
                ) : (
                  <ResponsiveContainer width="100%" height={220}>
                    <BarChart data={data.environments_by_team}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                      <XAxis dataKey="name" tick={{ fill: "#94a3b8", fontSize: 12 }} />
                      <YAxis allowDecimals={false} tick={{ fill: "#94a3b8", fontSize: 12 }} />
                      <Tooltip
                        contentStyle={{
                          background: "#0f172a",
                          border: "1px solid #1e293b",
                          borderRadius: 8,
                          color: "#e2e8f0",
                        }}
                      />
                      <Bar dataKey="active_count" name="Active" fill="#5a8bff" radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                )}
              </CardContent>
            </Card>
          </div>

          <div className="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-3">
            <Card>
              <CardHeader>
                <CardTitle>Provisioning success rate</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-3xl font-semibold text-slate-100">
                  {data.provisioning_success_rate === null
                    ? "—"
                    : `${Math.round(data.provisioning_success_rate * 100)}%`}
                </p>
                <p className="mt-1 text-xs text-slate-500">Over completed provisioning jobs</p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>Avg. provisioning time</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-3xl font-semibold text-slate-100">
                  {data.average_provisioning_duration_seconds === null
                    ? "—"
                    : `${Math.round(data.average_provisioning_duration_seconds)}s`}
                </p>
                <p className="mt-1 text-xs text-slate-500">Over successful provisioning jobs</p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>Infrastructure cost</CardTitle>
              </CardHeader>
              <CardContent>
                {costSummary ? (
                  <>
                    <p className="flex items-baseline gap-2 text-3xl font-semibold text-slate-100">
                      ${costSummary.total_estimated_cost_usd.toFixed(2)}
                      <Badge tone={costSummary.basis === "estimated" ? "info" : "neutral"}>
                        {costSummary.basis}
                      </Badge>
                    </p>
                    <p className="mt-1 text-xs text-slate-500">
                      Across {costSummary.by_team.length} team(s),{" "}
                      {costSummary.by_application.length} application(s)
                    </p>
                  </>
                ) : (
                  <p className="text-3xl font-semibold text-slate-500">—</p>
                )}
              </CardContent>
            </Card>
          </div>

          <Card className="mt-6">
            <CardHeader>
              <CardTitle>Recent jobs</CardTitle>
            </CardHeader>
            <CardContent>
              {data.recent_jobs.length === 0 ? (
                <p className="py-8 text-center text-sm text-slate-500">No jobs yet.</p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-slate-800 text-left text-xs uppercase text-slate-500">
                        <th className="py-2 pr-4 font-medium">Type</th>
                        <th className="py-2 pr-4 font-medium">Status</th>
                        <th className="py-2 pr-4 font-medium">Attempts</th>
                        <th className="py-2 pr-4 font-medium">Created</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.recent_jobs.map((job) => (
                        <tr key={job.id} className="border-b border-slate-900">
                          <td className="py-2 pr-4 text-slate-300">{job.job_type}</td>
                          <td className="py-2 pr-4">
                            <Badge
                              tone={
                                job.status === "succeeded"
                                  ? "success"
                                  : job.status === "failed"
                                    ? "danger"
                                    : "info"
                              }
                            >
                              {formatState(job.status)}
                            </Badge>
                          </td>
                          <td className="py-2 pr-4 text-slate-400">
                            {job.attempts}/{job.max_attempts}
                          </td>
                          <td className="py-2 pr-4 text-slate-500">
                            {new Date(job.created_at).toLocaleString()}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </CardContent>
          </Card>

          {recommendations && recommendations.length > 0 ? (
            <Card className="mt-6">
              <CardHeader>
                <CardTitle>Recommendations</CardTitle>
              </CardHeader>
              <CardContent>
                <ul className="flex flex-col gap-3">
                  {recommendations.map((rec, i) => (
                    <li key={i} className="flex items-start gap-3 text-sm">
                      <Lightbulb
                        className={`mt-0.5 size-4 shrink-0 ${
                          rec.severity === "critical"
                            ? "text-rose-400"
                            : rec.severity === "warning"
                              ? "text-amber-400"
                              : "text-brand-400"
                        }`}
                      />
                      <div>
                        <p className="text-slate-300">{rec.message}</p>
                        <Badge
                          tone={
                            rec.severity === "critical"
                              ? "danger"
                              : rec.severity === "warning"
                                ? "warning"
                                : "info"
                          }
                          className="mt-1"
                        >
                          {rec.category}
                        </Badge>
                      </div>
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          ) : null}
        </>
      )}
    </div>
  )
}
