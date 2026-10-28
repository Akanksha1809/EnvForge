import type { HTMLAttributes } from "react"

import { cn } from "@/lib/cn"

type Tone = "neutral" | "success" | "warning" | "danger" | "info"

const toneClasses: Record<Tone, string> = {
  neutral: "bg-slate-800 text-slate-300",
  success: "bg-emerald-500/15 text-emerald-400",
  warning: "bg-amber-500/15 text-amber-400",
  danger: "bg-rose-500/15 text-rose-400",
  info: "bg-brand-500/15 text-brand-300",
}

export function Badge({
  tone = "neutral",
  className,
  ...props
}: HTMLAttributes<HTMLSpanElement> & { tone?: Tone }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium",
        toneClasses[tone],
        className,
      )}
      {...props}
    />
  )
}
