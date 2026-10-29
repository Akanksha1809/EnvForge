import { useQuery, useQueryClient } from "@tanstack/react-query"
import { Boxes, Plus } from "lucide-react"
import { useState } from "react"
import { Link } from "react-router-dom"

import { applicationsApi } from "@/api/applications"
import { teamsApi } from "@/api/teams"
import { Badge } from "@/components/ui/Badge"
import { Button } from "@/components/ui/Button"
import { Card } from "@/components/ui/Card"
import { EmptyState } from "@/components/ui/EmptyState"
import { Input } from "@/components/ui/Input"
import { Modal } from "@/components/ui/Modal"
import { Select } from "@/components/ui/Select"

function CreateApplicationModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const queryClient = useQueryClient()
  const { data: teams } = useQuery({ queryKey: ["teams"], queryFn: () => teamsApi.list() })
  const [name, setName] = useState("")
  const [slug, setSlug] = useState("")
  const [teamId, setTeamId] = useState("")
  const [githubRepo, setGithubRepo] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  const close = () => {
    setName("")
    setSlug("")
    setTeamId("")
    setGithubRepo("")
    setError(null)
    onClose()
  }

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setIsSubmitting(true)
    try {
      await applicationsApi.create({
        name,
        slug,
        team_id: teamId,
        github_repo: githubRepo || undefined,
      })
      await queryClient.invalidateQueries({ queryKey: ["applications"] })
      close()
    } catch (err: unknown) {
      const message =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        "Failed to create application"
      setError(message)
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <Modal open={open} onClose={close} title="Register application">
      <form className="flex flex-col gap-4" onSubmit={onSubmit}>
        <Input label="Name" required value={name} onChange={(e) => setName(e.target.value)} />
        <Input
          label="Slug"
          required
          pattern="^[a-z0-9][a-z0-9-]*$"
          value={slug}
          onChange={(e) => setSlug(e.target.value)}
          placeholder="payments-api"
        />
        <Select label="Team" required value={teamId} onChange={(e) => setTeamId(e.target.value)}>
          <option value="">Select a team…</option>
          {teams?.items.map((team) => (
            <option key={team.id} value={team.id}>
              {team.name}
            </option>
          ))}
        </Select>
        <Input
          label="GitHub repo (optional)"
          value={githubRepo}
          onChange={(e) => setGithubRepo(e.target.value)}
          placeholder="acme/payments-api"
        />
        {error ? <p className="text-sm text-rose-400">{error}</p> : null}
        <Button type="submit" isLoading={isSubmitting}>
          Register
        </Button>
      </form>
    </Modal>
  )
}

export function ApplicationsPage() {
  const [modalOpen, setModalOpen] = useState(false)
  const { data, isLoading } = useQuery({
    queryKey: ["applications"],
    queryFn: () => applicationsApi.list(),
  })

  return (
    <div className="p-8">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-slate-100">Applications</h1>
          <p className="mt-1 text-sm text-slate-400">Every application EnvForge can provision.</p>
        </div>
        <Button onClick={() => setModalOpen(true)}>
          <Plus className="size-4" /> Register application
        </Button>
      </div>

      <div className="mt-6">
        {isLoading ? (
          <p className="text-sm text-slate-400">Loading…</p>
        ) : !data || data.items.length === 0 ? (
          <EmptyState
            icon={Boxes}
            title="No applications yet"
            description="Register one to start provisioning environments for it."
            action={<Button onClick={() => setModalOpen(true)}>Register application</Button>}
          />
        ) : (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
            {data.items.map((app) => (
              <Link key={app.id} to={`/applications/${app.id}`}>
                <Card className="h-full p-5 transition-colors hover:border-slate-700">
                  <div className="flex items-start justify-between">
                    <h3 className="font-medium text-slate-100">{app.name}</h3>
                    <Badge tone={app.is_active ? "success" : "neutral"}>
                      {app.is_active ? "active" : "inactive"}
                    </Badge>
                  </div>
                  <p className="mt-1 text-xs text-slate-500">{app.slug}</p>
                  {app.github_repo ? (
                    <p className="mt-2 text-xs text-slate-400">{app.github_repo}</p>
                  ) : null}
                  <p className="mt-3 text-xs text-slate-500">TTL: {app.environment_ttl_hours}h</p>
                </Card>
              </Link>
            ))}
          </div>
        )}
      </div>

      <CreateApplicationModal open={modalOpen} onClose={() => setModalOpen(false)} />
    </div>
  )
}
