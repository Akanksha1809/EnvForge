import { apiClient } from "@/api/client"
import type { Job, Page } from "@/types/platform"

export const jobsApi = {
  list: (
    params: { status?: string; job_type?: string; environment_id?: string; page?: number; page_size?: number } = {},
  ) => apiClient.get<Page<Job>>("/jobs", { params }).then((res) => res.data),

  get: (id: string) => apiClient.get<Job>(`/jobs/${id}`).then((res) => res.data),

  retry: (id: string) => apiClient.post<Job>(`/jobs/${id}/retry`).then((res) => res.data),
}
