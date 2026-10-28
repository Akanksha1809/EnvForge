import { type InputHTMLAttributes, forwardRef } from "react"

import { cn } from "@/lib/cn"

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string
  error?: string
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ className, label, error, id, ...props }, ref) => {
    const inputId = id ?? props.name
    return (
      <div className="flex flex-col gap-1.5">
        {label ? (
          <label htmlFor={inputId} className="text-sm font-medium text-slate-300">
            {label}
          </label>
        ) : null}
        <input
          ref={ref}
          id={inputId}
          className={cn(
            "h-10 rounded-lg border border-slate-700 bg-slate-900 px-3 text-sm text-slate-100",
            "placeholder:text-slate-500",
            "focus:outline-none focus:ring-2 focus:ring-brand-400 focus:border-brand-500",
            error && "border-rose-500 focus:ring-rose-400",
            className,
          )}
          {...props}
        />
        {error ? <p className="text-xs text-rose-400">{error}</p> : null}
      </div>
    )
  },
)
Input.displayName = "Input"
