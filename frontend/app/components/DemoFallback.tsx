"use client";

export default function DemoFallback() {
  const fallbackData = {
    project_name: "Garfield County 640 — STACK Area",
    jurisdiction: "Oklahoma",
    runsheet_status: "Complete with 2 flagged gaps",
    owners_count: 4,
    obligations_count: 3,
  };

  const features = [
    { tag: "01", title: "Runsheet view", body: "Chain of title: Warranty Deed (complete) → Assignment (flagged) → Missing heirship affidavit" },
    { tag: "02", title: "Ownership calculator", body: "Compass (50%) + Smith Estate (25%) + 2 Unknown Heirs (12.5% each)" },
    { tag: "03", title: "Obligation calendar", body: "Rental due in 15d, Drilling deadline in 45d, Primary term expires in 90d" },
    { tag: "04", title: "Risk dashboard", body: "Title defects (critical) + expiring leases (high) + ORRI burdens (medium)" },
    { tag: "05", title: "PDF export", body: "Ownership report rendered in Compass template. Auto-populated fields." },
    { tag: "06", title: "Multi-document ingestion", body: "Drag-drop up to 40 documents. Claude extracts all structured data." },
  ];

  return (
    <div className="min-h-screen bg-paper">
      <header className="relative overflow-hidden border-b border-line-strong bg-ink text-white">
        <div className="section-grid pointer-events-none absolute inset-0 opacity-30" />
        <div className="relative max-w-6xl mx-auto px-8 py-7">
          <div className="flex items-center gap-3 mb-5">
            <span className="brand-mark">S§</span>
            <span className="text-xs uppercase tracking-[0.18em] text-zinc-400 font-mono">
              Section / demo
            </span>
          </div>
          <h1 className="font-display text-3xl font-semibold leading-tight">
            {fallbackData.project_name}
          </h1>
          <div className="mt-2 flex items-center gap-3 text-xs text-zinc-400 font-mono">
            <span className="inline-flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-accent" />
              {fallbackData.jurisdiction}
            </span>
            <span className="text-zinc-600">·</span>
            <span>Demo project</span>
          </div>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-8 py-10">
        <div className="rounded-xl border border-info/30 bg-info-soft/40 px-5 py-4 mb-10 flex items-start gap-3">
          <span className="font-mono text-[0.65rem] uppercase tracking-[0.16em] text-info mt-0.5">
            Demo
          </span>
          <p className="text-sm text-ink-2">
            Live database unavailable. Showing pre-rendered demo state. In production, this would be
            the live Garfield County project.
          </p>
        </div>

        <div className="grid grid-cols-4 gap-px bg-line rounded-xl overflow-hidden border border-line mb-12">
          <Stat label="Gross acres" value="640" />
          <Stat label="Owners" value="4" />
          <Stat label="Flagged gaps" value="2" tone="warn" />
          <Stat label="At-risk obligations" value="3" tone="danger" />
        </div>

        <div className="mb-4">
          <div className="font-mono text-xs uppercase tracking-[0.18em] text-ink-3 mb-1.5">
            Capabilities
          </div>
          <h2 className="font-display text-2xl font-semibold text-ink">Demo feature overview</h2>
        </div>
        <div className="grid grid-cols-2 gap-3 mb-12">
          {features.map((f) => (
            <div
              key={f.tag}
              className="rounded-xl border border-line bg-surface px-5 py-4 hover:border-line-strong transition-colors"
            >
              <div className="flex items-center gap-2 mb-1.5">
                <span className="font-mono text-[0.7rem] tabular text-accent">{f.tag}</span>
                <span className="font-display font-semibold text-ink">{f.title}</span>
              </div>
              <p className="text-sm text-ink-2">{f.body}</p>
            </div>
          ))}
        </div>

        <section className="rounded-xl border border-line bg-surface px-6 py-5">
          <div className="font-mono text-xs uppercase tracking-[0.18em] text-ink-3 mb-3">
            What this demo shows
          </div>
          <ul className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm text-ink-2">
            <li className="flex items-start gap-2">
              <span className="text-accent mt-0.5">·</span>
              AI-powered document extraction (lease/deed fields)
            </li>
            <li className="flex items-start gap-2">
              <span className="text-accent mt-0.5">·</span>
              Structured land graph model persisted in Postgres
            </li>
            <li className="flex items-start gap-2">
              <span className="text-accent mt-0.5">·</span>
              Real-time ownership calculations across instrument chains
            </li>
            <li className="flex items-start gap-2">
              <span className="text-accent mt-0.5">·</span>
              Obligation tracking with smart deadline alerts
            </li>
            <li className="flex items-start gap-2">
              <span className="text-accent mt-0.5">·</span>
              Risk scoring and portfolio-level insights
            </li>
            <li className="flex items-start gap-2">
              <span className="text-accent mt-0.5">·</span>
              Template-driven PDF exports matching Compass deliverables
            </li>
          </ul>
        </section>
      </main>
    </div>
  );
}

function Stat({
  label,
  value,
  tone = "neutral",
}: {
  label: string;
  value: string;
  tone?: "neutral" | "warn" | "danger" | "positive";
}) {
  const valueColor =
    tone === "warn"
      ? "text-warn"
      : tone === "danger"
        ? "text-danger"
        : tone === "positive"
          ? "text-positive"
          : "text-ink";
  return (
    <div className="bg-surface px-5 py-5">
      <div className="text-[0.7rem] font-mono uppercase tracking-[0.16em] text-ink-3 mb-2">
        {label}
      </div>
      <div className={`font-display text-3xl font-semibold tabular ${valueColor}`}>{value}</div>
    </div>
  );
}
