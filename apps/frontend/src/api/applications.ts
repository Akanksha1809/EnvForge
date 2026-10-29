import { apiClient } from "@/api/client"
import type { Application, Page } from "@/types/platform"

export interface ApplicationCreatePayload {
  name: string
  slug: string
  team_id: string
  description?: string
  github_repo?: string
  default_branch?: string
  environment_template_id?: string
  environment_template_version?: number
  deployment_config?: Record<string, unknown>
  env_vars?: Record<string, string>
  health_check_config?: Record<string, unknown>
  environment_ttl_hours?: number
  max_active_environments?: number
}

export const applicationsApi = {
  list: (params: { team_id?: string; is_active?: boolean; page?: number; page_size?: number } = {}) =>
    apiClient.get<Page<Application>>("/applications", { params }).then((res) => res.data),

  get: (id: string) => apiClient.get<Application>(`/applications/${id}`).then((res) => res.data),

  create: (payload: ApplicationCreatePayload) =>
    apiClient.post<Application>("/applications", payload).then((res) => res.data),

  update: (id: string, payload: Partial<ApplicationCreatePayload> & { is_active?: boolean }) =>
    apiClient.patch<Application>(`/applications/${id}`, payload).then((res) => res.data),

  remove: (id: string) => apiClient.delete(`/applications/${id}`).then((res) => res.data),
}
