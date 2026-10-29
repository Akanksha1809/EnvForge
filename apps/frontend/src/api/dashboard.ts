import { apiClient } from "@/api/client"
import type { AuditLog, DashboardSummary, Page } from "@/types/platform"

export const dashboardApi = {
  summary: () => apiClient.get<DashboardSummary>("/dashboard/summary").then((res) => res.data),
}

export const auditApi = {
  list: (
    params: { resource_type?: string; resource_id?: string; action?: string; page?: number; page_size?: number } = {},
  ) => apiClient.get<Page<AuditLog>>("/audit-logs", { params }).then((res) => res.data),
}
