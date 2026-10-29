import { apiClient } from "@/api/client"
import type {
  Environment,
  EnvironmentCost,
  EnvironmentEvent,
  EnvironmentLogLine,
  Page,
} from "@/types/platform"

export interface EnvironmentCreatePayload {
  application_id: string
  name?: string
  pr_number?: number
  pr_branch?: string
  pr_commit_sha?: string
  config_overrides?: Record<string, unknown>
}

export const environmentsApi = {
  list: (
    params: { application_id?: string; state?: string; pr_number?: number; page?: number; page_size?: number } = {},
  ) => apiClient.get<Page<Environment>>("/environments", { params }).then((res) => res.data),

  get: (id: string) => apiClient.get<Environment>(`/environments/${id}`).then((res) => res.data),

  create: (payload: EnvironmentCreatePayload) =>
    apiClient.post<Environment>("/environments", payload).then((res) => res.data),

  remove: (id: string) => apiClient.delete<Environment>(`/environments/${id}`).then((res) => res.data),

  extend: (id: string, additionalHours: number) =>
    apiClient
      .post<Environment>(`/environments/${id}/extend`, { additional_hours: additionalHours })
      .then((res) => res.data),

  expire: (id: string) =>
    apiClient.post<Environment>(`/environments/${id}/expire`).then((res) => res.data),

  refresh: (id: string) =>
    apiClient.post<Environment>(`/environments/${id}/refresh`).then((res) => res.data),

  events: (id: string) =>
    apiClient.get<EnvironmentEvent[]>(`/environments/${id}/events`).then((res) => res.data),

  logs: (id: string) =>
    apiClient.get<EnvironmentLogLine[]>(`/environments/${id}/logs`).then((res) => res.data),

  cost: (id: string) =>
    apiClient.get<EnvironmentCost>(`/environments/${id}/cost`).then((res) => res.data),

  clone: (id: string) =>
    apiClient.post<Environment>(`/environments/${id}/clone`).then((res) => res.data),
}
