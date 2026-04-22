# Section Demo - Dry Run Checklist

## Pre-Demo Logistics

- [ ] Laptop fully charged or plugged in
- [ ] Backup power bank ready
- [ ] Internet connection verified (Wi-Fi + hotspot as fallback)
- [ ] Browser (Chrome/Edge) open and cached with necessary pages
- [ ] All demo screenshots/fallbacks downloaded locally
- [ ] PDF of ownership report pre-generated and saved
- [ ] DEMO_SCRIPT.md printed and annotated with timing notes

## System Check (30 min before)

- [ ] Backend (FastAPI) running on `localhost:8000`
- [ ] Frontend (Next.js) running on `localhost:3000`
- [ ] Postgres database connection active (or Docker container healthy)
- [ ] Demo project seeded in database (`demo_seed.py` executed successfully)
- [ ] All API endpoints responding:
  - [ ] GET `/api/projects` returns demo project
  - [ ] GET `/api/projects/1/ownership` returns ownership data
  - [ ] GET `/api/projects/1/obligations` returns obligations
  - [ ] GET `/api/projects/1/export/ownership` generates PDF without error

## Demo UI Walkthrough

- [ ] Project list page loads and displays "Garfield County 640 - STACK Area"
- [ ] Clicking project navigates to ProjectDetail view
- [ ] All 4 tabs render without errors:
  - [ ] Runsheet tab: Shows chain of title, gaps, curative needs
  - [ ] Ownership tab: Waterfall visualization, pie chart, acreage summary
  - [ ] Obligations tab: Calendar with 3+ obligations, color-coded by priority
  - [ ] Risk Dashboard tab: Portfolio stats, flagged issues list
- [ ] Export button visible and clickable on every view
- [ ] PDF export generates and downloads successfully

## Narrative Rehearsal (with a stakeholder stand-in)

### Opening (1 min)
- [ ] Pain point section resonates (don't rush)
- [ ] Transition to insight is smooth
- [ ] No stumbles on terminology (Land Graph, instrument, burden)

### Demo (2-3 min)
- [ ] Each view explained in < 30 seconds
- [ ] Click to Runsheet first, point out red flags
- [ ] Switch to Ownership, show fractional math updating in real-time
- [ ] Switch to Obligations, highlight high-priority items
- [ ] Switch to Risk Dashboard, summarize portfolio view
- [ ] Click Export, wait 2-3 seconds, PDF appears
- [ ] Talk through the final PDF while it's downloading

### Business Case (1 min)
- [ ] Three returns (leverage, productized services, equity) are clear
- [ ] Numbers feel credible (3-5x throughput, not 10x)
- [ ] Connection to their own operational pain is explicit

### Closing (1 min)
- [ ] Ask is clear: design partner + lead investor
- [ ] Why now feels urgent but not panicked
- [ ] End with open invitation for questions

## Contingency Plans

### If backend is down:
- [ ] Switch to demo fallback UI (pre-rendered Garfield County snapshot)
- [ ] Use screenshots of each view (Runsheet, Ownership, Calendar, Risk Dashboard, PDF)
- [ ] Narrate the same script while showing static images
- [ ] Emphasize the *logic* of what the system is doing, not the live data

### If Postgres is unreachable:
- [ ] Same as above (fallback to screenshots)
- [ ] Pre-generate and save the ownership PDF locally

### If laptop network fails:
- [ ] All data loaded locally; no external dependencies needed
- [ ] Screenshots and PDF already on disk
- [ ] Navigate to `file:///localhost` or run in offline mode if needed

### If export takes >10 seconds:
- [ ] Have the pre-generated PDF ready to open from disk instead
- [ ] Talk through what's happening ("Claude is rendering the template...")
- [ ] Don't wait for it; move to next section and show PDF later

## Timing Notes

- Opening: 60 seconds (don't rush the problem statement)
- Runsheet: 30 seconds (identify gaps, call out curative needs)
- Ownership: 30 seconds (show fractional math, highlight the pie chart)
- Calendar: 20 seconds (point out red-flag obligations, explain color coding)
- Risk Dashboard: 20 seconds (portfolio overview, flagged issues)
- PDF Export: 15 seconds (wait for download, show final PDF)
- Business case: 60 seconds (three returns, ask, why now)
- **Total: 5-7 minutes**

## Q&A Prep

**"How does extraction accuracy compare to manual review?"**
- Answer: Eval harness validates against gold set of hand-labeled documents. We target >95% accuracy on core fields (lessor, lessee, primary term, royalty). Extraction failures are surfaced to the user with provenance links, so manual review is fast.

**"What about older/unusual instruments (probates, court orders, affidavits)?"**
- Answer: Lease + deed extractors are v0. Probate and assignment extractors come in Phase 2. Court orders are captured as generic instrument records. The graph is flexible.

**"How does this compare to Oseberg/Collide/ThoughtTrace?"**
- Answer: They own slices (courthouse data, lease extraction, post-acq docs). We own the *operating layer*—the project shell, the integrated views, the deliverable exports. You can ingest courthouse data from Oseberg *into* Section and export reports to your client.

**"What's the cost structure?"**
- Answer: For Compass, a flat fee covers design partnership + first phase build. Long-term, Section sells to E&P operators as SaaS (per-project or per-seat pricing, TBD). Compass gets favorable terms on both seats and reselling opportunities.

**"How does this work offline or in air-gapped environments?"**
- Answer: Document ingestion requires Claude API calls (online). Views and exports run locally. For highly air-gapped environments, we can batch-process extraction before moving data offline.

## Final Sign-Offs

- [ ] Script feels natural (not robotic)
- [ ] Timing is 5-7 minutes (not 3, not 12)
- [ ] You can answer all Q&A questions above without hesitation
- [ ] You have fallback screenshots ready
- [ ] You have pre-generated PDF ready
- [ ] You've practiced 2+ times in front of someone who gives honest feedback
- [ ] You know where to pause, where to click, where to let the UI speak

---

## Post-Demo Follow-Up

- [ ] Send Compass the recording (if recorded)
- [ ] Share this GitHub repo link
- [ ] Send one-pager on next steps: design partnership agreement, investment terms, roadmap
- [ ] Offer to do a working session with their team on real documents
