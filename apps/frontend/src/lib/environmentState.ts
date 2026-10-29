import type { EnvironmentState } from "@/types/platform"

type Tone = "neutral" | "success" | "warning" | "danger" | "info"

const STATE_TONE: Record<EnvironmentState, Tone> = {
  requested: "neutral",
  validating: "info",
  queued: "info",
  provisioning: "info",
  deploying: "info",
  health_checking: "info",
  ready: "success",
  failed: "danger",
  deleting: "warning",
  deleted: "neutral",
  expired: "warning",
}

export function stateTone(state: EnvironmentState): Tone {
  return STATE_TONE[state] ?? "neutral"
}

export function formatState(state: string): string {
  return state.replace(/_/g, " ")
}

export function isInFlight(state: EnvironmentState): boolean {
  return ["requested", "validating", "queued", "provisioning", "deploying", "health_checking"].includes(
    state,
  )
}
