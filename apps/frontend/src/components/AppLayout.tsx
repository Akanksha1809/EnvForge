import {
  Boxes,
  LayoutDashboard,
  LogOut,
  ScrollText,
  Settings,
  Users as UsersIcon,
} from "lucide-react"
import { NavLink, Outlet } from "react-router-dom"

import { Badge } from "@/components/ui/Badge"
import { useAuth } from "@/lib/AuthContext"

const navItems = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard },
  { to: "/applications", label: "Applications", icon: Boxes },
  { to: "/environments", label: "Environments", icon: ScrollText },
  { to: "/teams", label: "Teams", icon: UsersIcon },
  { to: "/settings", label: "Settings", icon: Settings },
]

export function AppLayout() {
  const { user, logout } = useAuth()

  return (
    <div className="flex min-h-screen bg-slate-950">
      <aside className="flex w-60 flex-col border-r border-slate-800 bg-slate-950/60 p-4">
        <div className="mb-6 flex items-center gap-2 px-2">
          <div className="flex size-8 items-center justify-center rounded-lg bg-brand-500 font-bold text-white">
            E
          </div>
          <span className="text-sm font-semibold text-slate-100">EnvForge</span>
        </div>
        <nav className="flex flex-1 flex-col gap-1">
          {navItems.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === "/"}
              className={({ isActive }) =>
                `flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                  isActive
                    ? "bg-brand-500/15 text-brand-300"
                    : "text-slate-400 hover:bg-slate-800 hover:text-slate-200"
                }`
              }
            >
              <Icon className="size-4" />
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="mt-auto border-t border-slate-800 pt-4">
          <div className="flex items-center justify-between px-2">
            <div>
              <p className="truncate text-sm font-medium text-slate-200">{user?.full_name}</p>
              <Badge tone="info" className="mt-1">
                {user?.platform_role.replace("_", " ")}
              </Badge>
            </div>
            <button
              onClick={logout}
              className="rounded-lg p-2 text-slate-400 hover:bg-slate-800 hover:text-slate-200"
              aria-label="Log out"
            >
              <LogOut className="size-4" />
            </button>
          </div>
        </div>
      </aside>
      <main className="flex-1 overflow-y-auto">
        <Outlet />
      </main>
    </div>
  )
}
