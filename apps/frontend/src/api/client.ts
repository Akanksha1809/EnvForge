import axios, { type AxiosError } from "axios"

import { clearTokens, getAccessToken, getRefreshToken, setTokens } from "@/lib/tokenStorage"
import type { TokenPair } from "@/types/auth"

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8010"

export const apiClient = axios.create({
  baseURL: `${API_BASE_URL}/api/v1`,
})

apiClient.interceptors.request.use((config) => {
  const token = getAccessToken()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

let refreshPromise: Promise<string> | null = null

async function refreshAccessToken(): Promise<string> {
  const refreshToken = getRefreshToken()
  if (!refreshToken) throw new Error("No refresh token available")

  const { data } = await axios.post<TokenPair>(`${API_BASE_URL}/api/v1/auth/refresh`, {
    refresh_token: refreshToken,
  })
  setTokens(data)
  return data.access_token
}

apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as (typeof error.config & { _retried?: boolean }) | undefined

    if (error.response?.status === 401 && originalRequest && !originalRequest._retried) {
      originalRequest._retried = true
      try {
        refreshPromise ??= refreshAccessToken()
        const newAccessToken = await refreshPromise
        refreshPromise = null
        originalRequest.headers = originalRequest.headers ?? {}
        originalRequest.headers.Authorization = `Bearer ${newAccessToken}`
        return apiClient(originalRequest)
      } catch {
        refreshPromise = null
        clearTokens()
        window.location.href = "/login"
      }
    }
    return Promise.reject(error)
  },
)
