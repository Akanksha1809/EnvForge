import { useQuery, useQueryClient } from "@tanstack/react-query"
import { FileStack, History, Plus } from "lucide-react"
import { useState } from "react"

import { templatesApi } from "@/api/templates"
import { Badge } from "@/components/ui/Badge"
import { Button } from "@/components/ui/Button"
import { Card } from "@/components/ui/Card"
import { EmptyState } from "@/components/ui/EmptyState"
import { Input } from "@/components/ui/Input"
import { Modal } from "@/components/ui/Modal"
import { Select } from "@/components/ui/Select"
import type { EnvironmentTemplate, TemplateType } from "@/types/platform"

const TEMPLATE_TYPES: TemplateType[] = ["basic_backend", "fullstack", "microservices", "custom"]

function CreateTemplateModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const queryClient = useQueryClient()
  const [slug, setSlug] = useState("")
  const [name, setName] = useState("")
  const [templateType, setTemplateType] = useState<TemplateType>("basic_backend")
  const [requiredServices, setRequiredServices] = useState("postgres, redis")
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  const close = () => {
    setSlug("")
    setName("")
    setRequiredServices("postgres, redis")
    setError(null)
    onClose()
  }

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setIsSubmitting(true)
    try {
      await templatesApi.create({
        slug,
        name,
        template_type: templateType,
        required_services: requiredServices
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean),
      })
      await queryClient.invalidateQueries({ queryKey: ["templates"] })
      close()
    } catch (err: unknown) {
      const message =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        "Failed to create template"
      setError(message)
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <Modal open={open} onClose={close} title="Create environment template">
      <form className="flex flex-col gap-4" onSubmit={onSubmit}>
        <Input
          label="Slug"
          required
          pattern="^[a-z0-9][a-z0-9-]*$"
          value={slug}
          onChange={(e) => setSlug(e.target.value)}
          placeholder="basic-backend"
        />
        <Input label="Name" required value={name} onChange={(e) => setName(e.target.value)} />
        <Select
          label="Type"
          value={templateType}
          onChange={(e) => setTemplateType(e.target.value as TemplateType)}
        >
          {TEMPLATE_TYPES.map((t) => (
            <option key={t} value={t}>
              {t.replace("_", " ")}
            </option>
          ))}
        </Select>
        <Input
          label="Required services (comma-separated)"
          value={requiredServices}
          onChange={(e) => setRequiredServices(e.target.value)}
        />
        {error ? <p className="text-sm text-rose-400">{error}</p> : null}
        <Button type="submit" isLoading={isSubmitting}>
          Create
        </Button>
      </form>
    </Modal>
  )
}

function NewVersionModal({
  open,
  onClose,
  base,
}: {
  open: boolean
  onClose: () => void
  base: EnvironmentTemplate | null
}) {
  const queryClient = useQueryClient()
  const [name, setName] = useState(base?.name ?? "")
  const [requiredServices, setRequiredServices] = useState(
    base?.required_services.join(", ") ?? ""
  )
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  const close = () => {
    setError(null)
    onClose()
  }

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!base) return
    setError(null)
    setIsSubmitting(true)
    try {
      await templatesApi.createVersion(base.slug, {
        slug: base.slug,
        name,
        template_type: base.template_type,
        required_services: requiredServices
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean),
      })
      await queryClient.invalidateQueries({ queryKey: ["templates"] })
      await queryClient.invalidateQueries({ queryKey: ["template-versions", base.slug] })
      close()
    } catch (err: unknown) {
      const message =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        "Failed to create version"
      setError(message)
    } finally {
      setIsSubmitting(false)
    }
  }

  if (!base) return null

  return (
    <Modal open={open} onClose={close} title={`New version of "${base.slug}"`}>
      <form className="flex flex-col gap-4" onSubmit={onSubmit}>
        <p className="text-xs text-slate-500">
          Creates <code>{base.slug}</code> v{base.version + 1}. The current latest version
          (v{base.version}) is kept, untouched — applications pinned to it are unaffected.
        </p>
        <Input label="Name" required value={name} onChange={(e) => setName(e.target.value)} />
        <Input
          label="Required services (comma-separated)"
          value={requiredServices}
          onChange={(e) => setRequiredServices(e.target.value)}
        />
        {error ? <p className="text-sm text-rose-400">{error}</p> : null}
        <Button type="submit" isLoading={isSubmitting}>
          Create version
        </Button>
      </form>
    </Modal>
  )
}

function VersionHistoryModal({
  open,
  onClose,
  template,
  onNewVersion,
}: {
  open: boolean
  onClose: () => void
  template: EnvironmentTemplate | null
  onNewVersion: () => void
}) {
  const { data, isLoading } = useQuery({
    queryKey: ["template-versions", template?.slug],
    queryFn: () => templatesApi.versions(template!.slug),
    enabled: open && !!template,
  })

  if (!template) return null

  const versions = [...(data ?? [])].sort((a, b) => b.version - a.version)

  return (
    <Modal open={open} onClose={onClose} title={`Version history: ${template.slug}`}>
      <div className="flex flex-col gap-3">
        {isLoading ? (
          <p className="text-sm text-slate-400">Loading…</p>
        ) : (
          versions.map((v) => (
            <div
              key={v.id}
              className="flex items-center justify-between rounded-lg border border-slate-800 px-3 py-2"
            >
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-slate-100">v{v.version}</span>
                  {v.is_latest ? <Badge tone="success">latest</Badge> : null}
                </div>
                <p className="mt-0.5 text-xs text-slate-500">{v.name}</p>
              </div>
              <span className="text-xs text-slate-500">
                {new Date(v.created_at).toLocaleDateString()}
              </span>
            </div>
          ))
        )}
        <Button className="mt-2" onClick={onNewVersion}>
          <Plus className="size-4" /> New version
        </Button>
      </div>
    </Modal>
  )
}

export function TemplatesPage() {
  const [modalOpen, setModalOpen] = useState(false)
  const [historyTemplate, setHistoryTemplate] = useState<EnvironmentTemplate | null>(null)
  const [versionModalOpen, setVersionModalOpen] = useState(false)
  const { data, isLoading } = useQuery({
    queryKey: ["templates"],
    queryFn: () => templatesApi.list(),
  })

  return (
    <div className="p-8">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-slate-100">Environment templates</h1>
          <p className="mt-1 text-sm text-slate-400">
            Versioned blueprints applications pin a specific (slug, version) of.
          </p>
        </div>
        <Button onClick={() => setModalOpen(true)}>
          <Plus className="size-4" /> New template
        </Button>
      </div>

      <div className="mt-6">
        {isLoading ? (
          <p className="text-sm text-slate-400">Loading…</p>
        ) : !data || data.items.length === 0 ? (
          <EmptyState
            icon={FileStack}
            title="No templates yet"
            action={<Button onClick={() => setModalOpen(true)}>New template</Button>}
          />
        ) : (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
            {data.items.map((tpl) => (
              <Card key={tpl.id} className="p-5">
                <div className="flex items-start justify-between">
                  <h3 className="font-medium text-slate-100">{tpl.name}</h3>
                  <Badge tone="info">v{tpl.version}</Badge>
                </div>
                <p className="mt-1 text-xs text-slate-500">
                  {tpl.slug} · {tpl.template_type.replace("_", " ")}
                </p>
                {tpl.required_services.length > 0 ? (
                  <div className="mt-3 flex flex-wrap gap-1.5">
                    {tpl.required_services.map((svc) => (
                      <Badge key={svc}>{svc}</Badge>
                    ))}
                  </div>
                ) : null}
                <Button
                  variant="secondary"
                  className="mt-4 w-full"
                  onClick={() => setHistoryTemplate(tpl)}
                >
                  <History className="size-4" /> Version history
                </Button>
              </Card>
            ))}
          </div>
        )}
      </div>

      <CreateTemplateModal open={modalOpen} onClose={() => setModalOpen(false)} />
      <VersionHistoryModal
        open={!!historyTemplate}
        onClose={() => setHistoryTemplate(null)}
        template={historyTemplate}
        onNewVersion={() => setVersionModalOpen(true)}
      />
      <NewVersionModal
        open={versionModalOpen}
        onClose={() => setVersionModalOpen(false)}
        base={historyTemplate}
      />
    </div>
  )
}
