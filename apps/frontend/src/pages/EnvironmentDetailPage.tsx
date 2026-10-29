import { useQuery, useQueryClient } from "@tanstack/react-query"
import { ArrowLeft, Clock, ExternalLink, Trash2 } from "lucide-react"
import { useState } from "react"
import { Link, useNavigate, useParams } from "react-router-dom"

import { environmentsApi } from "@/api/environments"
import { Badge } from "@/components/ui/Badge"
import { Button } from "@/components/ui/Button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card"
import { formatState, isInFlight, stateTone } from "@/lib/environmentState"

export function EnvironmentDetailPage() {
  const { environmentId = "" } = useParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [busyAction, setBusyAction] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)

  const { data: environment } = useQuery({
    queryKey: ["environments", environmentId],
    queryFn: () => environmentsApi.get(environmentId),
    enabled: !!environmentId,
    refetchInterval: (query) => (query.state.data && isInFlight(query.state.data.state) ? 3_000 : 10_000),
  })

  const { data: events } = useQuery({
    queryKey: ["environments", environmentId, "events"],
    queryFn: () => environmentsApi.events(environmentId),
    enabled: !!environmentId,
    refetchInterval: 5_000,
  })

  const { data: logs } = useQuery({
    queryKey: ["environments", environmentId, "logs"],
    queryFn: () => environmentsApi.logs(environmentId),
    enabled: !!environmentId,
    refetchInterval: 5_000,
  })

  const runAction = async (action: string, fn: () => Promise<unknown>) => {
    setActionError(null)
    setBusyAction(action)
    try {
      await fn()
      await queryClient.invalidateQueries({ queryKey: ["environments"] })
    } catch (err: unknown) {
      const message =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        `Failed to ${action}`
      setActionError(message)
    } finally {
      setBusyAction(null)
    }
  }

  if (!environment) return <div className="p-8 text-sm text-slate-400">Loading…</div>

  const canDelete = !["deleting", "deleted"].includes(environment.state)
  const canExtend = !["deleting", "deleted", "expired", "failed"].includes(environment.state)

  return (
    <div className="p-8">
      <Link
        to="/environments"
        className="inline-flex items-center gap-1 text-sm text-slate-400 hover:text-slate-200"
      >
        <ArrowLeft className="size-4" /> Environments
      </Link>

      <div className="mt-3 flex items-start justify-between">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-semibold text-slate-100">{environment.name}</h1>
            <Badge tone={stateTone(environment.state)}>{formatState(environment.state)}</Badge>
          </div>
          {environment.pr_number ? (
            <p className="mt-1 text-sm text-slate-400">
              PR #{environment.pr_number}
              {environment.pr_branch ? ` · ${environment.pr_branch}` : ""}
            </p>
          ) : null}
        </div>
        <div className="flex gap-2">
          {environment.preview_url ? (
            <a href={environment.preview_url} target="_blank" rel="noreferrer">
              <Button variant="secondary">
                <ExternalLink className="size-4" /> Open preview
              </Button>
            </a>
          ) : null}
          {canExtend ? (
            <Button
              variant="secondary"
              isLoading={busyAction === "extend"}
              onClick={() => runAction("extend", () => environmentsApi.extend(environmentId, 24))}
            >
              <Clock className="size-4" /> Extend 24h
            </Button>
          ) : null}
          {canDelete ? (
            <Button
              variant="danger"
              isLoading={busyAction === "delete"}
              onClick={() =>
                runAction("delete", () => environmentsApi.remove(environmentId)).then(() =>
                  navigate("/environments"),
                )
              }
            >
              <Trash2 className="size-4" /> Delete
            </Button>
          ) : null}
        </div>
      </div>
      {actionError ? <p className="mt-2 text-sm text-rose-400">{actionError}</p> : null}
      {environment.last_error ? (
        <p className="mt-3 rounded-lg border border-rose-900/50 bg-rose-950/30 p-3 text-sm text-rose-300">
          {environment.last_error}
        </p>
      ) : null}

      <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-1">
          <CardHeader>
            <CardTitle>Details</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-3 text-sm">
            <div>
              <p className="text-slate-500">Namespace</p>
              <p className="text-slate-200">{environment.namespace ?? "not yet provisioned"}</p>
            </div>
            <div>
              <p className="text-slate-500">Expires</p>
              <p className="text-slate-200">
                {environment.ttl_expires_at
                  ? new Date(environment.ttl_expires_at).toLocaleString()
                  : "—"}
              </p>
            </div>
            <div>
              <p className="text-slate-500">Created</p>
              <p className="text-slate-200">{new Date(environment.created_at).toLocaleString()}</p>
            </div>
            {environment.destroyed_at ? (
              <div>
                <p className="text-slate-500">Destroyed</p>
                <p className="text-slate-200">{new Date(environment.destroyed_at).toLocaleString()}</p>
              </div>
            ) : null}
          </CardContent>
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Lifecycle events</CardTitle>
          </CardHeader>
          <CardContent>
            {!events || events.length === 0 ? (
              <p className="text-sm text-slate-500">No events yet.</p>
            ) : (
              <ol className="flex flex-col gap-3">
                {events.map((event) => (
                  <li key={event.id} className="flex items-start gap-3 text-sm">
                    <span className="mt-1.5 size-1.5 shrink-0 rounded-full bg-brand-400" />
                    <div>
                      <p className="text-slate-300">
                        <span className="text-slate-500">{event.previous_state}</span>
                        {" → "}
                        <span className="font-medium text-slate-100">{event.new_state}</span>
                        <span className="ml-2 text-xs text-slate-500">({event.trigger})</span>
                      </p>
                      {event.error_message ? (
                        <p className="mt-0.5 text-xs text-rose-400">{event.error_message}</p>
                      ) : null}
                      <p className="text-xs text-slate-500">
                        {new Date(event.created_at).toLocaleString()}
                      </p>
                    </div>
                  </li>
                ))}
              </ol>
            )}
          </CardContent>
        </Card>
      </div>

      <Card className="mt-6">
        <CardHeader>
          <CardTitle>Logs</CardTitle>
        </CardHeader>
        <CardContent>
          {!logs || logs.length === 0 ? (
            <p className="text-sm text-slate-500">No logs yet.</p>
          ) : (
            <pre className="max-h-80 overflow-y-auto rounded-lg bg-black/40 p-3 font-mono text-xs text-slate-300">
              {logs
                .map((line) => `[${line.level}] ${new Date(line.timestamp).toISOString()} ${line.message}`)
                .join("\n")}
            </pre>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
