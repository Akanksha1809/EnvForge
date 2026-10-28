export type PlatformRole = "platform_admin" | "team_admin" | "developer" | "viewer"

export interface User {
  id: string
  email: string
  full_name: string
  platform_role: PlatformRole
  github_username: string | null
  avatar_url: string | null
  is_active: boolean
  created_at: string
}

export interface TokenPair {
  access_token: string
  refresh_token: string
  token_type: string
}
