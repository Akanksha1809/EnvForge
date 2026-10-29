import { useQuery, useQueryClient } from "@tanstack/react-query"
import { ArrowLeft, Boxes, Plus } from "lucide-react"
import { useState } from "react"
import { Link, useNavigate, useParams } from "react-router-dom"

import { applicationsApi } from "@/api/applications"
import { environmentsApi } from "@/api/environments"
import { Badge } from "@/components/ui/Badge"
import { Button } from "@/components/ui/Button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card"
import { EmptyState } from "@/components/ui/EmptyState"
import { formatState, stateTone } from "@/lib/environmentState"

export function ApplicationDetailPage() {
  const { applicationId = "" } = useParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [isCreating, setIsCreating] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const { data: app } = useQuery({
    queryKey: ["applications", applicationId],
    queryFn: () => applicationsApi.get(applicationId),
    enabled: !!applicationId,
  })

  const { data: environments } = useQuery({
    queryKey: ["environments", { application_id: applicationId }],
    queryFn: () => environmentsApi.list({ application_id: applicationId, page_size: 50 }),
    enabled: !!applicationId,
    refetchInterval: 5_000,
  })

  const createEnvironment = async () => {
    setError(null)
    setIsCreating(true)
    try {
      const env = await environmentsApi.create({ application_id: applicationId })
      await queryClient.invalidateQueries({ queryKey: ["environments"] })
      navigate(`/environments/${env.id}`)
    } catch (err: unknown) {
      const message =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        "Failed to create environment"
      setError(message)
    } finally {
      setIsCreating(false)
    }
  }

  if (!app) return <div className="p-8 text-sm text-slate-400">Loading…</div>

  return (
    <div className="p-8">
      <Link to="/applications" className="inline-flex items-center gap-1 text-sm text-slate-400 hover:text-slate-200">
        <ArrowLeft className="size-4" /> Applications
      </Link>

      <div className="mt-3 flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-slate-100">{app.name}</h1>
          <p className="mt-1 text-sm text-slate-400">
            {app.slug} {app.github_repo ? `· ${app.github_repo}` : ""}
          </p>
        </div>
        <Button onClick={createEnvironment} isLoading={isCreating}>
          <Plus className="size-4" /> New environment
        </Button>
      </div>
      {error ? <p className="mt-2 text-sm text-rose-400">{error}</p> : null}

      <Card className="mt-6 max-w-2xl">
        <CardHeader>
          <CardTitle>Configuration</CardTitle>
        </CardHeader>
        <CardContent className="grid grid-cols-2 gap-4 text-sm">
          <div>
            <p className="text-slate-500">Default branch</p>
            <p className="text-slate-200">{app.default_branch}</p>
          </div>
          <div>
            <p className="text-slate-500">Environment TTL</p>
            <p className="text-slate-200">{app.environment_ttl_hours}h</p>
          </div>
          <div>
            <p className="text-slate-500">Max active environments</p>
            <p className="text-slate-200">{app.max_active_environments ?? "inherits team quota"}</p>
          </div>
          <div>
            <p className="text-slate-500">Status</p>
            <Badge tone={app.is_active ? "success" : "neutral"}>
              {app.is_active ? "active" : "inactive"}
            </Badge>
          </div>
        </CardContent>
      </Card>

      <h2 className="mt-8 text-sm font-semibold text-slate-200">Environments</h2>
      <div className="mt-3">
        {!environments || environments.items.length === 0 ? (
          <EmptyState
            icon={Boxes}
            title="No environments yet"
            description="Create one to provision real infrastructure for this application."
          />
        ) : (
          <div className="overflow-x-auto rounded-xl border border-slate-800">
            <table className="w-full text-sm">
              <thead className="bg-slate-900/60">
                <tr className="text-left text-xs uppercase text-slate-500">
                  <th className="px-4 py-2.5 font-medium">Name</th>
                  <th className="px-4 py-2.5 font-medium">State</th>
                  <th className="px-4 py-2.5 font-medium">PR</th>
                  <th className="px-4 py-2.5 font-medium">Created</th>
                </tr>
              </thead>
              <tbody>
                {environments.items.map((env) => (
                  <tr
                    key={env.id}
                    className="cursor-pointer border-t border-slate-800 hover:bg-slate-900/40"
                    onClick={() => navigate(`/environments/${env.id}`)}
                  >
                    <td className="px-4 py-2.5 text-slate-200">{env.name}</td>
                    <td className="px-4 py-2.5">
                      <Badge tone={stateTone(env.state)}>{formatState(env.state)}</Badge>
                    </td>
                    <td className="px-4 py-2.5 text-slate-400">
                      {env.pr_number ? `#${env.pr_number}` : "—"}
                    </td>
                    <td className="px-4 py-2.5 text-slate-500">
                      {new Date(env.created_at).toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
