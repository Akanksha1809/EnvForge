// Centralized localStorage access for auth tokens — the single place that
// knows the storage keys, so nothing else needs to.
import type { TokenPair } from "@/types/auth"

const ACCESS_TOKEN_KEY = "envforge.access_token"
const REFRESH_TOKEN_KEY = "envforge.refresh_token"

export function getAccessToken(): string | null {
  return localStorage.getItem(ACCESS_TOKEN_KEY)
}

export function getRefreshToken(): string | null {
  return localStorage.getItem(REFRESH_TOKEN_KEY)
}

export function setTokens(tokens: TokenPair): void {
  localStorage.setItem(ACCESS_TOKEN_KEY, tokens.access_token)
  localStorage.setItem(REFRESH_TOKEN_KEY, tokens.refresh_token)
}

export function clearTokens(): void {
  localStorage.removeItem(ACCESS_TOKEN_KEY)
  localStorage.removeItem(REFRESH_TOKEN_KEY)
}
