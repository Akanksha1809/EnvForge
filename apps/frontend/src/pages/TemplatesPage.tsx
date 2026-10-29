import { useQuery, useQueryClient } from "@tanstack/react-query"
import { FileStack, Plus } from "lucide-react"
import { useState } from "react"

import { templatesApi } from "@/api/templates"
import { Badge } from "@/components/ui/Badge"
import { Button } from "@/components/ui/Button"
import { Card } from "@/components/ui/Card"
import { EmptyState } from "@/components/ui/EmptyState"
import { Input } from "@/components/ui/Input"
import { Modal } from "@/components/ui/Modal"
import { Select } from "@/components/ui/Select"
import type { TemplateType } from "@/types/platform"

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

export function TemplatesPage() {
  const [modalOpen, setModalOpen] = useState(false)
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
              </Card>
            ))}
          </div>
        )}
      </div>

      <CreateTemplateModal open={modalOpen} onClose={() => setModalOpen(false)} />
    </div>
  )
}
