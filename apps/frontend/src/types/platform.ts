export interface Page<T> {
  items: T[]
  total: number
  page: number
  page_size: number
  pages: number
}

export interface Team {
  id: string
  name: string
  slug: string
  description: string | null
  max_active_environments: number
  created_at: string
}

export interface TeamMembership {
  id: string
  user_id: string
  team_id: string
  role: "admin" | "member"
  created_at: string
}

export interface Application {
  id: string
  name: string
  slug: string
  description: string | null
  github_repo: string | null
  default_branch: string
  team_id: string
  environment_template_id: string | null
  environment_template_version: number | null
  deployment_config: Record<string, unknown>
  infrastructure_requirements: Record<string, unknown>
  resource_requirements: Record<string, unknown>
  health_check_config: Record<string, unknown>
  env_vars: Record<string, string>
  dependencies: string[]
  environment_ttl_hours: number
  max_active_environments: number | null
  is_active: boolean
  created_at: string
  updated_at: string
}

export type TemplateType = "basic_backend" | "fullstack" | "microservices" | "custom"

export interface EnvironmentTemplate {
  id: string
  slug: string
  version: number
  is_latest: boolean
  name: string
  description: string | null
  template_type: TemplateType
  required_services: string[]
  infrastructure_requirements: Record<string, unknown>
  resource_limits: Record<string, unknown>
  env_vars: Record<string, string>
  deployment_strategy: string
  health_checks: Record<string, unknown>
  dependency_requirements: string[]
  cleanup_rules: Record<string, unknown>
  created_at: string
}

export type EnvironmentState =
  | "requested"
  | "validating"
  | "queued"
  | "provisioning"
  | "deploying"
  | "health_checking"
  | "ready"
  | "failed"
  | "deleting"
  | "deleted"
  | "expired"

export interface Environment {
  id: string
  application_id: string
  requested_by_user_id: string | null
  template_id: string | null
  template_version: number | null
  name: string
  state: EnvironmentState
  pr_number: number | null
  pr_branch: string | null
  pr_commit_sha: string | null
  namespace: string | null
  preview_url: string | null
  last_error: string | null
  ttl_expires_at: string | null
  destroyed_at: string | null
  created_at: string
  updated_at: string
}

export interface EnvironmentEvent {
  id: string
  environment_id: string
  previous_state: EnvironmentState
  new_state: EnvironmentState
  trigger: "user" | "webhook" | "system" | "ttl" | "retry"
  actor_user_id: string | null
  job_id: string | null
  error_message: string | null
  metadata_json: Record<string, unknown>
  created_at: string
}

export interface EnvironmentLogLine {
  timestamp: string
  level: string
  message: string
  source: string
}

export type JobStatus = "pending" | "queued" | "running" | "succeeded" | "failed" | "retrying"
export type JobType = "provision" | "deploy" | "health_check" | "cleanup" | "refresh"

export interface Job {
  id: string
  job_type: JobType
  status: JobStatus
  environment_id: string | null
  celery_task_id: string | null
  attempts: number
  max_attempts: number
  payload: Record<string, unknown>
  result: Record<string, unknown>
  error_message: string | null
  started_at: string | null
  finished_at: string | null
  created_at: string
}

export interface AuditLog {
  id: string
  actor_user_id: string | null
  actor_label: string
  action: string
  resource_type: string
  resource_id: string | null
  metadata_json: Record<string, unknown>
  ip_address: string | null
  created_at: string
}

export interface DashboardSummary {
  total_environments: number
  active_environments: number
  provisioning_environments: number
  failed_environments: number
  expiring_environments: number
  environments_by_application: { name: string; slug: string; active_count: number }[]
  environments_by_team: { name: string; slug: string; active_count: number }[]
  provisioning_success_rate: number | null
  average_provisioning_duration_seconds: number | null
  recent_jobs: Job[]
}
