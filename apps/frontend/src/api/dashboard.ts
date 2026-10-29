import { apiClient } from "@/api/client"
import type { AuditLog, CostSummary, DashboardSummary, Page, Recommendation } from "@/types/platform"

export const dashboardApi = {
  summary: () => apiClient.get<DashboardSummary>("/dashboard/summary").then((res) => res.data),

  costSummary: () =>
    apiClient.get<CostSummary>("/dashboard/cost-summary").then((res) => res.data),

  recommendations: () =>
    apiClient.get<Recommendation[]>("/dashboard/recommendations").then((res) => res.data),
}

export const auditApi = {
  list: (
    params: { resource_type?: string; resource_id?: string; action?: string; page?: number; page_size?: number } = {},
  ) => apiClient.get<Page<AuditLog>>("/audit-logs", { params }).then((res) => res.data),
}
