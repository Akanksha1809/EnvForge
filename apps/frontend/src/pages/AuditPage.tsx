import { useQuery } from "@tanstack/react-query"
import { ScrollText } from "lucide-react"

import { auditApi } from "@/api/dashboard"
import { EmptyState } from "@/components/ui/EmptyState"
import { useAuth } from "@/lib/AuthContext"

export function AuditPage() {
  const { user } = useAuth()
  const isPlatformAdmin = user?.platform_role === "platform_admin"

  const { data, isLoading } = useQuery({
    queryKey: ["audit-logs"],
    queryFn: () => auditApi.list({ page_size: 50 }),
    enabled: isPlatformAdmin,
  })

  if (!isPlatformAdmin) {
    return (
      <div className="p-8">
        <EmptyState
          icon={ScrollText}
          title="Platform admin only"
          description="Audit history is restricted to platform administrators."
        />
      </div>
    )
  }

  return (
    <div className="p-8">
      <h1 className="text-2xl font-semibold text-slate-100">Audit history</h1>
      <p className="mt-1 text-sm text-slate-400">Every sensitive action, recorded.</p>

      <div className="mt-6">
        {isLoading ? (
          <p className="text-sm text-slate-400">Loading…</p>
        ) : !data || data.items.length === 0 ? (
          <EmptyState icon={ScrollText} title="No audit events yet" />
        ) : (
          <div className="overflow-x-auto rounded-xl border border-slate-800">
            <table className="w-full text-sm">
              <thead className="bg-slate-900/60">
                <tr className="text-left text-xs uppercase text-slate-500">
                  <th className="px-4 py-2.5 font-medium">Action</th>
                  <th className="px-4 py-2.5 font-medium">Resource</th>
                  <th className="px-4 py-2.5 font-medium">Actor</th>
                  <th className="px-4 py-2.5 font-medium">When</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((log) => (
                  <tr key={log.id} className="border-t border-slate-800">
                    <td className="px-4 py-2.5 font-mono text-xs text-slate-200">{log.action}</td>
                    <td className="px-4 py-2.5 text-slate-400">
                      {log.resource_type}
                      {log.resource_id ? ` · ${log.resource_id.slice(0, 8)}…` : ""}
                    </td>
                    <td className="px-4 py-2.5 text-slate-400">{log.actor_label}</td>
                    <td className="px-4 py-2.5 text-slate-500">
                      {new Date(log.created_at).toLocaleString()}
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
