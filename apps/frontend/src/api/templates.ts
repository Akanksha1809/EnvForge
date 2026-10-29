import { apiClient } from "@/api/client"
import type { EnvironmentTemplate, Page, TemplateType } from "@/types/platform"

export interface TemplateCreatePayload {
  slug: string
  name: string
  description?: string
  template_type: TemplateType
  required_services?: string[]
  resource_limits?: Record<string, unknown>
  env_vars?: Record<string, string>
  deployment_strategy?: string
  health_checks?: Record<string, unknown>
  dependency_requirements?: string[]
  cleanup_rules?: Record<string, unknown>
}

export const templatesApi = {
  list: (page = 1, pageSize = 50) =>
    apiClient
      .get<Page<EnvironmentTemplate>>("/templates", { params: { page, page_size: pageSize } })
      .then((res) => res.data),

  get: (id: string) =>
    apiClient.get<EnvironmentTemplate>(`/templates/${id}`).then((res) => res.data),

  create: (payload: TemplateCreatePayload) =>
    apiClient.post<EnvironmentTemplate>("/templates", payload).then((res) => res.data),

  versions: (slug: string) =>
    apiClient.get<EnvironmentTemplate[]>(`/templates/${slug}/versions`).then((res) => res.data),

  createVersion: (slug: string, payload: TemplateCreatePayload) =>
    apiClient
      .post<EnvironmentTemplate>(`/templates/${slug}/versions`, payload)
      .then((res) => res.data),
}
