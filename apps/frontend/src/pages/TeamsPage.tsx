import { useQuery, useQueryClient } from "@tanstack/react-query"
import { Plus, Users } from "lucide-react"
import { useState } from "react"

import { teamsApi } from "@/api/teams"
import { Badge } from "@/components/ui/Badge"
import { Button } from "@/components/ui/Button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card"
import { EmptyState } from "@/components/ui/EmptyState"
import { Input } from "@/components/ui/Input"
import { Modal } from "@/components/ui/Modal"

function CreateTeamModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const queryClient = useQueryClient()
  const [name, setName] = useState("")
  const [slug, setSlug] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  const close = () => {
    setName("")
    setSlug("")
    setError(null)
    onClose()
  }

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setIsSubmitting(true)
    try {
      await teamsApi.create({ name, slug })
      await queryClient.invalidateQueries({ queryKey: ["teams"] })
      close()
    } catch (err: unknown) {
      const message =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        "Failed to create team"
      setError(message)
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <Modal open={open} onClose={close} title="Create team">
      <form className="flex flex-col gap-4" onSubmit={onSubmit}>
        <Input label="Name" required value={name} onChange={(e) => setName(e.target.value)} />
        <Input
          label="Slug"
          required
          pattern="^[a-z0-9][a-z0-9-]*$"
          value={slug}
          onChange={(e) => setSlug(e.target.value)}
          placeholder="platform-team"
        />
        {error ? <p className="text-sm text-rose-400">{error}</p> : null}
        <Button type="submit" isLoading={isSubmitting}>
          Create
        </Button>
      </form>
    </Modal>
  )
}

function TeamMembersCard({ teamId }: { teamId: string }) {
  const { data: members } = useQuery({
    queryKey: ["teams", teamId, "members"],
    queryFn: () => teamsApi.listMembers(teamId),
  })

  return (
    <div className="mt-3 border-t border-slate-800 pt-3">
      <p className="mb-2 text-xs font-medium uppercase text-slate-500">Members</p>
      {!members || members.length === 0 ? (
        <p className="text-xs text-slate-500">No members yet.</p>
      ) : (
        <ul className="flex flex-col gap-1.5">
          {members.map((m) => (
            <li key={m.id} className="flex flex-wrap items-center justify-between gap-4 text-sm">
              <span className="text-slate-300">{m.user_id}</span>
              <Badge tone={m.role === "admin" ? "info" : "neutral"}>{m.role}</Badge>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

export function TeamsPage() {
  const [modalOpen, setModalOpen] = useState(false)
  const [expanded, setExpanded] = useState<string | null>(null)
  const { data, isLoading } = useQuery({ queryKey: ["teams"], queryFn: () => teamsApi.list() })

  return (
    <div className="p-8">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-slate-100">Teams</h1>
          <p className="mt-1 text-sm text-slate-400">Ownership boundary for applications and quotas.</p>
        </div>
        <Button onClick={() => setModalOpen(true)}>
          <Plus className="size-4" /> New team
        </Button>
      </div>

      <div className="mt-6">
        {isLoading ? (
          <p className="text-sm text-slate-400">Loading…</p>
        ) : !data || data.items.length === 0 ? (
          <EmptyState
            icon={Users}
            title="No teams yet"
            action={<Button onClick={() => setModalOpen(true)}>New team</Button>}
          />
        ) : (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            {data.items.map((team) => (
              <Card key={team.id}>
                <CardHeader>
                  <CardTitle>{team.name}</CardTitle>
                  <Badge>{team.slug}</Badge>
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-slate-400">
                    Max active environments: {team.max_active_environments}
                  </p>
                  <button
                    className="mt-2 text-xs text-brand-400 hover:underline"
                    onClick={() => setExpanded(expanded === team.id ? null : team.id)}
                  >
                    {expanded === team.id ? "Hide members" : "Show members"}
                  </button>
                  {expanded === team.id ? <TeamMembersCard teamId={team.id} /> : null}
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>

      <CreateTeamModal open={modalOpen} onClose={() => setModalOpen(false)} />
    </div>
  )
}
