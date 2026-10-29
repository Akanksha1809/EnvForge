import { apiClient } from "@/api/client"
import type { Page, Team, TeamMembership } from "@/types/platform"

export interface TeamCreatePayload {
  name: string
  slug: string
  description?: string
  max_active_environments?: number
}

export const teamsApi = {
  list: (page = 1, pageSize = 50) =>
    apiClient
      .get<Page<Team>>("/teams", { params: { page, page_size: pageSize } })
      .then((res) => res.data),

  get: (id: string) => apiClient.get<Team>(`/teams/${id}`).then((res) => res.data),

  create: (payload: TeamCreatePayload) =>
    apiClient.post<Team>("/teams", payload).then((res) => res.data),

  update: (id: string, payload: Partial<TeamCreatePayload>) =>
    apiClient.patch<Team>(`/teams/${id}`, payload).then((res) => res.data),

  listMembers: (id: string) =>
    apiClient.get<TeamMembership[]>(`/teams/${id}/members`).then((res) => res.data),

  addMember: (id: string, userId: string, role: "admin" | "member" = "member") =>
    apiClient
      .post<TeamMembership>(`/teams/${id}/members`, { user_id: userId, role })
      .then((res) => res.data),

  removeMember: (id: string, userId: string) =>
    apiClient.delete(`/teams/${id}/members/${userId}`).then((res) => res.data),
}
