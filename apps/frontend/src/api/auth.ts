import { apiClient } from "@/api/client"
import type { TokenPair, User } from "@/types/auth"

export interface RegisterPayload {
  email: string
  full_name: string
  password: string
}

export interface LoginPayload {
  email: string
  password: string
}

export const authApi = {
  register: (payload: RegisterPayload) =>
    apiClient.post<User>("/auth/register", payload).then((res) => res.data),

  login: (payload: LoginPayload) =>
    apiClient.post<TokenPair>("/auth/login", payload).then((res) => res.data),

  me: () => apiClient.get<User>("/auth/me").then((res) => res.data),
}
