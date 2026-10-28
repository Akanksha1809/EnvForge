import { createContext, useContext, useEffect, useState, type ReactNode } from "react"

import { authApi } from "@/api/auth"
import { clearTokens, getAccessToken, setTokens } from "@/lib/tokenStorage"
import type { User } from "@/types/auth"

interface AuthContextValue {
  user: User | null
  isLoading: boolean
  login: (email: string, password: string) => Promise<void>
  register: (email: string, fullName: string, password: string) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    const hydrate = async () => {
      if (getAccessToken()) {
        try {
          const me = await authApi.me()
          setUser(me)
        } catch {
          clearTokens()
        }
      }
      setIsLoading(false)
    }
    void hydrate()
  }, [])

  const login = async (email: string, password: string) => {
    const tokens = await authApi.login({ email, password })
    setTokens(tokens)
    const me = await authApi.me()
    setUser(me)
  }

  const register = async (email: string, fullName: string, password: string) => {
    await authApi.register({ email, full_name: fullName, password })
    await login(email, password)
  }

  const logout = () => {
    clearTokens()
    setUser(null)
  }

  return (
    <AuthContext.Provider value={{ user, isLoading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error("useAuth must be used within an AuthProvider")
  return ctx
}
