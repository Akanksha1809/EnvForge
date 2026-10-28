export function ComingSoonPage({ title, phase }: { title: string; phase: string }) {
  return (
    <div className="p-8">
      <h1 className="text-2xl font-semibold text-slate-100">{title}</h1>
      <p className="mt-2 text-sm text-slate-400">Ships in {phase} of the build roadmap.</p>
    </div>
  )
}
