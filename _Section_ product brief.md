# Product Brief

**One-line pitch:** An AI platform for land services firms that turns the documents behind every deal \- deeds, leases, probates, assignments \- into a living, queryable model of ownership, obligations, and risk. Every Landman deliverable (ownership reports, runsheets, leasehold confirmations, curative packages, A\&D memos) becomes a view or export from that single model.

## 1\. Product description

### The problem

Land services firms live project-by-project. A client hands over a tract or a data room, a senior landman spends 2–6 weeks parsing documents, tracing chains of title, computing mineral fractions, abstracting leases, and writing a deliverable in Word. Then the project closes and everything evaporates into a folder on a shared drive that nobody opens again. When the same firm returns to the same county six months later for a different client, none of that knowledge compounds.

The underlying work \- reading instruments, extracting structured facts, computing fractional ownership, tracking obligations \- is deeply repetitive and pattern-matchable. Legacy land software (iLandMan, Quorum, PakEnergy) digitizes the *output* (a database of leases) but doesn't touch the *process* of turning paper into structure. AI-native entrants (Oseberg, ThoughtTrace, Collide) each own a narrow slice \- courthouse data, lease extraction, post-acquisition docs \- but none have built the project-centric operating layer that firms like Compass actually work inside.

### The product

The section is built around one insight: every land deliverable is a different view of the same underlying graph. That graph \- call it the Land Graph \- is a typed, structured representation of a project's land position:

- **Tracts** \- the surface and mineral acreage in scope  
- **Instruments** \- deeds, leases, assignments, probates, affidavits, court orders  
- **Parties** \- individuals, estates, and entities holding interests  
- **Interests** \- who owns what fraction, of what mineral estate, burdened by what  
- **Obligations** \- primary term expirations, Pugh triggers, shut-in clocks, continuous drilling deadlines, rental payments

Documents ingest through a AI-powered extraction pipeline that writes structured facts into the graph. Every view and every export reads from that graph.

### Core views

**Project shell.** Every unit of work is a project \- "Garfield County 640," "STACK Acquisition Phase 2." Documents, extracted facts, generated outputs, and team collaboration all live inside the project. When the project ends, nothing evaporates.

**Runsheet.** Auto-built chain of title from ingested instruments, with gaps and breaks flagged in red. Curative needs surfaced with the specific missing document identified ("no deed from John Smith estate to heirs \- need affidavit of heirship").

**Ownership view.** Fractional mineral and leasehold ownership computed across every conveyance in the chain. Waterfall visualization, final owner pie chart, leased-vs-open overlay, net acre rollups, and burden stacks (royalties \+ ORRIs).

**Obligation calendar.** Every lease's primary term, Pugh trigger, shut-in clock, continuous drilling requirement, and rental payment dropped onto a calendar with configurable alerts.

**A\&D / risk dashboard.** Portfolio-level view across all leases in a project: expiration distribution, royalty ranges, flagged issues requiring senior review, heat map of risk. This is the view that compresses a 2-week diligence into an afternoon of senior review.

**Exports.** One-click generation of ownership reports, runsheets, and leasehold confirmations in Compass's own templates \- the deliverable the client actually pays for, with every field auto-populated from the graph.

### Target user and market

Primary persona is a landman at a services firm, with Compass as the reference customer. Secondary is an in-house land team at a mid-size operator (50–5,000 wells) running active leasing or acquisition programs \- too sophisticated for spreadsheets, too small for Enverus.

GTM starts inside Compass: their team uses Section on real projects, produces case-study data, and opens doors to their E\&P clients \- where Section sells as either a direct subscription or a "Compass-enabled" premium service tier the firm resells.

### What it is / what it isn't

**Section is** a project-scoped AI operating layer for land work: ingest documents, extract structured facts, compute ownership and obligations, produce deliverables.

**Section is not** a courthouse records database (Oseberg, TexasFile, Courthouse Direct do that), a general-purpose CLM platform (Icertis, Agiloft), or an E\&P land ERP replacement (PakEnergy, Quorum). It sits *above* those \- ingesting from them, producing for them.

### Differentiators

**Project-centric, not record-centric.** Legacy systems are master databases. Section is a project workspace where knowledge compounds across deals.

**Graph-first, not form-first.** Every output is derived from the underlying graph, so correcting a single deed cascades through every view and every deliverable.

**Exports in customer templates.** The deliverable looks like Compass wrote it \- not like another SaaS tool's PDF.

**Multi-jurisdiction by design.** Oklahoma-first, Texas next, New Mexico third. The graph is jurisdiction-agnostic; only extractors and templates vary.

---

## 2\. Tech stack & architecture (seed for CTO review)

Standard modern stack: **Next.js \+ Tailwind frontend, Python FastAPI backend, Postgres with pgvector for the Land Graph and semantic search over documents, S3 for document storage, and Claude as the primary LLM for extraction and reasoning.** Document ingestion runs through a pipeline of OCR (for scanned records), chunking, and structured extraction against a typed schema, with extracted facts written into a relational Land Graph model (tracts, parties, instruments, interests, obligations) that every view reads from. CTO should pressure-test the graph schema, the extraction evaluation harness, and whether pgvector is enough or we need a dedicated vector DB \- those are the three things that matter long-term.

---

## 3\. Demo build plan (steps, not days)

### Phase A \- Foundation

1. Stand up the project skeleton: Next.js frontend, FastAPI backend, Postgres, S3 (or local equivalent), deployment target.  
2. Design the v0 Land Graph schema \- tracts, parties, instruments, interests, obligations \- minimally sufficient for the demo scope. Write migrations.  
3. Build project creation and document upload: drag-drop zone, file storage, basic document list UI.  
4. Stand up Claude API integration with a clean prompt-management pattern (versioned, testable).

### Phase B \- Extraction

5. Collect 15–25 real redacted Oklahoma documents from Compass (leases, warranty deeds, mineral deeds, probate orders, assignments). **This is step one of the week in practice \- don't start building without samples.**  
6. Build the lease extractor: structured schema (lessor, lessee, legal description, gross/net acres, royalty, primary term, bonus, Pugh clauses, depth limits, shut-in, continuous drilling), prompted against Claude, with an eval harness comparing output to hand-labeled truth.  
7. Build the deed extractor: grantor, grantee, legal description, interest conveyed, reservations, date, recording info.  
8. Build a "facts pipeline" that writes extracted output into the Land Graph schema with provenance (every fact linked to source document \+ page/excerpt).

### Phase C \- Views

9. Build the project shell UI: sidebar, view switcher, project header with key stats.  
10. Build the document view: list \+ detail pane showing extracted abstract alongside source PDF with linked highlights.  
11. Build the ownership calculator: fractional math across a chain of 5–10 conveyances, with the waterfall visualization and final pie chart.  
12. Build the obligation calendar: pull all dated obligations from the graph, render on a month/quarter calendar, threshold alerts.  
13. Build the A\&D / risk dashboard: portfolio stats across all leases in the project, flagged issues list.

### Phase D \- Outputs

14. Build the ownership report PDF generator using Compass's actual template as the design target (ask Compass for a sample deliverable).

### Phase E \- Seed & polish

15. Create the fictional demo project: "Garfield County 640-acre Tract \- STACK Area." Ingest 30–40 seeded documents that tell a coherent story (including 1–2 title defects and 1–2 at-risk leases for dramatic flags).  
16. Write and rehearse the 5–7 minute demo script with a clean narrative arc.  
17. Build fallbacks: pre-rendered output for every view so a live-ingest failure doesn't kill the demo. Have a local copy of everything. Do not rely on live Wi-Fi.

### Phase F \- Dry run

18. Full dress rehearsal with at least one person playing skeptical landman asking hard questions. Tighten the script based on where it drags or confuses.

---

## 4\. Pitch narrative for the Compass meeting

*Delivery: conversational, \~15 minutes including demo. Not a deck-read.*

### Opening \- the pain they feel every project

Every Compass project follows the same arc. A client hands you a data room or a tract. A senior landman spends two to six weeks parsing documents, running title, computing interests, writing a deliverable. You ship the report. The client pays. And then \- everything that senior landman built in their head and in their spreadsheets evaporates. Six months later, a different client wants work in the same county, and you start over.

You already know this is the bottleneck on your business. You can't hire your way out of it fast enough \- the people who can actually do this work take years to train, and the best of them are aging out. And meanwhile the work itself is deeply pattern-matchable \- the same types of instruments, the same fractional math, the same abstractable provisions, over and over.

### The insight

Here's what we see: everything Compass sells \- ownership reports, leasehold confirmations, runsheets, curative packages, A\&D memos \- is a different view of the same underlying thing. Documents parsed into a structured model of who owns what, burdened by what, due when. Today that model lives in one landman's head, an Excel workbook, and a folder nobody will open again. What if it lived in a system?

### The product

That system is Section. Every project gets a Land Graph: tracts, instruments, parties, interests, obligations. Documents go in, Claude extracts, the graph populates. And then every deliverable Compass sells becomes a view or export from that single source of truth.

Let me show you.

### Demo

*\[\~5 minutes: open Garfield County project, drop 30 docs, watch extraction stream, flip through Runsheet → Ownership → Calendar → Risk Dashboard, click "Generate Ownership Report" and drop a polished PDF in Compass's template.\]*

### The business case \- three returns on your investment

**First \- internal leverage.** Your team can take on 3–5x the project volume without hiring. A deliverable that took two weeks takes three days. Your senior people spend their time on judgment calls instead of document-chasing. That's ROI you can model against your current project pipeline today.

**Second \- productized services.** You can start selling "Section access" as a subscription to your existing E\&P clients \- a new recurring revenue line on top of project-based work. Their in-house landmen get the tool; you get the seat revenue and stay embedded in their workflow.

**Third \- equity upside.** Section sells to any mid-size operator with a land function. That's thousands of potential customers beyond Compass. Your investment buys a stake in that \- and because you're our design partner, Section is shaped around how Compass actually works, which means the product is better than what a team without your expertise would ever build.

### The ask

We want Compass as our design partner and lead investor. Design partner means: your team uses Section on real projects, gives us unvarnished feedback, and shapes the roadmap. Investor means: you fund the first phase of the build in exchange for equity and favorable terms on long-term access.

### Why now

The methane regulations, the M\&A wave, the retiring workforce, and the maturing of Claude-class LLMs all converge on one moment: land work is about to get automated, and the question is whether Compass defines how, or watches someone else do it. We'd rather do it with you than for you.

---

*End of brief. Next steps for the team: review this together, kill or confirm the Land Graph framing, pick a real working name, get Compass to send 15–25 redacted sample documents ASAP, and lock the demo scope before anyone writes code.*  
