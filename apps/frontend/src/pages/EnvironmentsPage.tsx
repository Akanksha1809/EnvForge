import { useQuery } from "@tanstack/react-query"
import { ScrollText } from "lucide-react"
import { useState } from "react"
import { useNavigate } from "react-router-dom"

import { environmentsApi } from "@/api/environments"
import { Badge } from "@/components/ui/Badge"
import { EmptyState } from "@/components/ui/EmptyState"
import { Select } from "@/components/ui/Select"
import { formatState, stateTone } from "@/lib/environmentState"
import type { EnvironmentState } from "@/types/platform"

const STATES: EnvironmentState[] = [
  "requested",
  "validating",
  "queued",
  "provisioning",
  "deploying",
  "health_checking",
  "ready",
  "failed",
  "deleting",
  "deleted",
  "expired",
]

export function EnvironmentsPage() {
  const navigate = useNavigate()
  const [stateFilter, setStateFilter] = useState("")

  const { data, isLoading } = useQuery({
    queryKey: ["environments", { state: stateFilter }],
    queryFn: () =>
      environmentsApi.list({ state: stateFilter || undefined, page_size: 50 }),
    refetchInterval: 5_000,
  })

  return (
    <div className="p-8">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-slate-100">Environments</h1>
          <p className="mt-1 text-sm text-slate-400">Every ephemeral environment, across every application.</p>
        </div>
        <Select value={stateFilter} onChange={(e) => setStateFilter(e.target.value)} className="w-48">
          <option value="">All states</option>
          {STATES.map((s) => (
            <option key={s} value={s}>
              {formatState(s)}
            </option>
          ))}
        </Select>
      </div>

      <div className="mt-6">
        {isLoading ? (
          <p className="text-sm text-slate-400">Loading…</p>
        ) : !data || data.items.length === 0 ? (
          <EmptyState icon={ScrollText} title="No environments match this filter" />
        ) : (
          <div className="overflow-x-auto rounded-xl border border-slate-800">
            <table className="w-full text-sm">
              <thead className="bg-slate-900/60">
                <tr className="text-left text-xs uppercase text-slate-500">
                  <th className="px-4 py-2.5 font-medium">Name</th>
                  <th className="px-4 py-2.5 font-medium">State</th>
                  <th className="px-4 py-2.5 font-medium">PR</th>
                  <th className="px-4 py-2.5 font-medium">Preview URL</th>
                  <th className="px-4 py-2.5 font-medium">Expires</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((env) => (
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
                    <td className="px-4 py-2.5 text-slate-400">
                      {env.preview_url ? (
                        <a
                          href={env.preview_url}
                          target="_blank"
                          rel="noreferrer"
                          onClick={(e) => e.stopPropagation()}
                          className="text-brand-400 hover:underline"
                        >
                          {env.preview_url}
                        </a>
                      ) : (
                        "—"
                      )}
                    </td>
                    <td className="px-4 py-2.5 text-slate-500">
                      {env.ttl_expires_at ? new Date(env.ttl_expires_at).toLocaleString() : "—"}
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
