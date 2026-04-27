"use client";

import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import EmptyState from "./EmptyState";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface AliquotPart {
  quarters: string[];
  lots: number[];
  gross_acres: number | null;
}

interface ParsedSection {
  section: number | null;
  township_number: number | null;
  township_dir: string | null;
  range_number: number | null;
  range_dir: string | null;
  grid_position: [number, number] | null;
  gross_acres: number | null;
  coverage_pct: number;
  aliquot_parts: AliquotPart[];
}

interface TractInstrument {
  instrument_id: number;
  instrument_type: string;
  grantor: string;
  grantee: string;
  date: string | null;
  document: { id: number; filename: string } | null;
}

interface TractEntry {
  tract_id: number;
  legal_description: string;
  gross_acres: number | null;
  is_leased: boolean;
  parsed: {
    raw: string;
    is_plss: boolean;
    description_type: string;
    parse_notes: string[];
    abstract_number: string | null;
    survey_name: string | null;
    lot: string | null;
    block: string | null;
    subdivision: string | null;
    sections: ParsedSection[];
  };
  instruments: TractInstrument[];
}

interface SectionCell {
  section: number;
  grid_position: [number, number] | null;
  tracts: {
    tract_id: number;
    is_leased: boolean;
    coverage_pct: number;
    gross_acres: number | null;
    aliquot_parts: AliquotPart[];
    instruments: TractInstrument[];
  }[];
}

interface Township {
  key: string;
  township_number: number;
  township_dir: string;
  range_number: number;
  range_dir: string;
  sections: SectionCell[];
}

interface TractMapData {
  project_id: number;
  project_name: string;
  jurisdiction: string;
  tracts: TractEntry[];
  townships: Township[];
  has_plss: boolean;
  non_plss_tracts: TractEntry[];
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

// Standard PLSS section numbers 1-36. Section 1 is in the NORTHEAST corner.
// Even rows: right-to-left (6→1, 18→13, 30→25)
// Odd rows:  left-to-right (7→12, 19→24, 31→36)
const PLSS_ROWS: number[][] = [
  [6,  5,  4,  3,  2,  1],
  [7,  8,  9,  10, 11, 12],
  [18, 17, 16, 15, 14, 13],
  [19, 20, 21, 22, 23, 24],
  [30, 29, 28, 27, 26, 25],
  [31, 32, 33, 34, 35, 36],
];

const CELL_SIZE = 72; // px per section cell
const GRID_GAP = 2;
const GRID_W = 6 * CELL_SIZE + 5 * GRID_GAP;
const GRID_H = 6 * CELL_SIZE + 5 * GRID_GAP;

// ---------------------------------------------------------------------------
// Aliquot geometry — subdivide a section square into sub-rectangles
// ---------------------------------------------------------------------------

interface Rect { x: number; y: number; w: number; h: number }

function aliquotToRect(quarters: string[], cx: number, cy: number, cw: number, ch: number): Rect {
  // Reading order: "NE SW" means NE of SW → first identify outer quarter (last in reading = SW) then NE of it
  // quarters array: [outermost, ..., innermost] for display
  // We render outermost quarter first then subdivide
  let x = cx, y = cy, w = cw, h = ch;
  for (const q of [...quarters].reverse()) {   // reverse: last quarter in string is outermost call
    switch (q) {
      case "NE": x = x + w / 2; y = y; w = w / 2; h = h / 2; break;
      case "NW": x = x; y = y; w = w / 2; h = h / 2; break;
      case "SE": x = x + w / 2; y = y + h / 2; w = w / 2; h = h / 2; break;
      case "SW": x = x; y = y + h / 2; w = w / 2; h = h / 2; break;
      case "N2": y = y; h = h / 2; break;
      case "S2": y = y + h / 2; h = h / 2; break;
      case "E2": x = x + w / 2; w = w / 2; break;
      case "W2": x = x; w = w / 2; break;
    }
  }
  return { x, y, w, h };
}

// ---------------------------------------------------------------------------
// SVG section cell component
// ---------------------------------------------------------------------------

function SectionCell({
  sectionNum,
  colIdx,
  rowIdx,
  sectionData,
  isSelected,
  onClick,
}: {
  sectionNum: number;
  colIdx: number;
  rowIdx: number;
  sectionData: SectionCell | null;
  isSelected: boolean;
  onClick: (sn: number) => void;
}) {
  const x = colIdx * (CELL_SIZE + GRID_GAP);
  const y = rowIdx * (CELL_SIZE + GRID_GAP);

  const hasTracts = sectionData && sectionData.tracts.length > 0;
  const anyLeased = sectionData?.tracts.some((t) => t.is_leased);
  const anyOpen = sectionData?.tracts.some((t) => !t.is_leased);

  // Base fill
  let baseFill = "#faf6ea"; // surface (empty)
  if (hasTracts) {
    baseFill = anyLeased && !anyOpen ? "#dae0c8" : // all leased — moss-soft
               anyLeased ? "#ecd9a5" :             // mixed — brass-soft
               "#faf6ea";                          // open — neutral
  }

  return (
    <g
      key={sectionNum}
      className="cursor-pointer"
      onClick={() => onClick(sectionNum)}
      style={{ cursor: hasTracts ? "pointer" : "default" }}
    >
      {/* Cell background */}
      <rect
        x={x}
        y={y}
        width={CELL_SIZE}
        height={CELL_SIZE}
        fill={baseFill}
        stroke={isSelected ? "#7a1f2a" : "#b3a482"}
        strokeWidth={isSelected ? 2.5 : 0.75}
        rx={1}
      />

      {/* Aliquot shading per tract */}
      {hasTracts &&
        sectionData!.tracts.map((tract, ti) => (
          <g key={ti}>
            {tract.aliquot_parts.map((ap, ai) => {
              if (ap.quarters.length === 0) {
                return (
                  <rect
                    key={ai}
                    x={x + 1}
                    y={y + 1}
                    width={CELL_SIZE - 2}
                    height={CELL_SIZE - 2}
                    fill={tract.is_leased ? "#4c5f3e" : "#9b4620"}
                    fillOpacity={0.18}
                    rx={0.5}
                  />
                );
              }
              const r = aliquotToRect(ap.quarters, x + 1, y + 1, CELL_SIZE - 2, CELL_SIZE - 2);
              return (
                <rect
                  key={ai}
                  x={r.x}
                  y={r.y}
                  width={r.w}
                  height={r.h}
                  fill={tract.is_leased ? "#4c5f3e" : "#9b4620"}
                  fillOpacity={0.22}
                  rx={0.5}
                />
              );
            })}
          </g>
        ))}

      {/* Section number label */}
      <text
        x={x + CELL_SIZE / 2}
        y={y + CELL_SIZE / 2}
        textAnchor="middle"
        dominantBaseline="middle"
        fontSize={hasTracts ? 13 : 11}
        fontWeight={hasTracts ? 600 : 400}
        fill={hasTracts ? "#1d2635" : "#a7ac98"}
        fontFamily="var(--font-franklin), ui-sans-serif, sans-serif"
        style={{ userSelect: "none", pointerEvents: "none" }}
      >
        {sectionNum}
      </text>

      {/* Leased indicator dot */}
      {anyLeased && (
        <circle
          cx={x + CELL_SIZE - 8}
          cy={y + 8}
          r={3.5}
          fill="#4c5f3e"
          opacity={0.9}
        />
      )}
    </g>
  );
}

// ---------------------------------------------------------------------------
// Township grid
// ---------------------------------------------------------------------------

function TownshipGrid({
  township,
  onSectionClick,
  selectedSection,
}: {
  township: Township;
  onSectionClick: (sn: number, twpKey: string) => void;
  selectedSection: { section: number; twpKey: string } | null;
}) {
  const sectionIndex: Record<number, SectionCell> = {};
  for (const s of township.sections) {
    sectionIndex[s.section] = s;
  }

  return (
    <div>
      <div className="mb-3">
        <span className="font-display text-[1.2rem] font-medium text-ink">{township.key}</span>
        <span className="ml-3 font-serif-italic text-sm text-ink-3">
          {township.sections.length} section{township.sections.length !== 1 ? "s" : ""} of record
        </span>
      </div>
      <div className="overflow-x-auto">
        <svg
          width={GRID_W}
          height={GRID_H}
          viewBox={`0 0 ${GRID_W} ${GRID_H}`}
          style={{ display: "block" }}
          aria-label={`PLSS grid for ${township.key}`}
        >
          {PLSS_ROWS.map((row, rowIdx) =>
            row.map((sectionNum, colIdx) => {
              const isSelected =
                selectedSection?.section === sectionNum &&
                selectedSection?.twpKey === township.key;
              return (
                <SectionCell
                  key={sectionNum}
                  sectionNum={sectionNum}
                  colIdx={colIdx}
                  rowIdx={rowIdx}
                  sectionData={sectionIndex[sectionNum] || null}
                  isSelected={isSelected}
                  onClick={(sn) => onSectionClick(sn, township.key)}
                />
              );
            })
          )}
        </svg>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Section detail panel
// ---------------------------------------------------------------------------

function SectionDetail({
  sectionData,
  township,
  onClose,
}: {
  sectionData: SectionCell;
  township: Township;
  onClose: () => void;
}) {
  const totalInstruments = sectionData.tracts.flatMap((t) => t.instruments);
  const uniqueInstruments = Array.from(
    new Map(totalInstruments.map((i) => [i.instrument_id, i])).values()
  );

  return (
    <div className="border border-line-strong bg-surface px-6 py-5 mt-4">
      <div className="flex items-start justify-between gap-4 mb-5">
        <div>
          <div className="eyebrow mb-1">Section {sectionData.section}</div>
          <div className="font-display text-[1.5rem] font-medium text-ink leading-none">
            {township.key}
          </div>
        </div>
        <button
          onClick={onClose}
          className="text-ink-3 hover:text-ink transition-colors text-lg leading-none mt-1"
          aria-label="Close section detail"
        >
          ×
        </button>
      </div>

      {/* Tract entries */}
      {sectionData.tracts.length === 0 ? (
        <p className="text-sm font-serif-italic text-ink-3">No tracts of record in this section.</p>
      ) : (
        <div className="space-y-4 mb-5">
          {sectionData.tracts.map((tract, i) => (
            <div key={i} className="border-l-2 pl-4" style={{ borderColor: tract.is_leased ? "#4c5f3e" : "#9b4620" }}>
              <div className="flex items-center gap-3 mb-1.5">
                <span
                  className="text-xs font-medium px-2 py-0.5 rounded"
                  style={{
                    background: tract.is_leased ? "#dae0c8" : "#efd7c7",
                    color: tract.is_leased ? "#4c5f3e" : "#9b4620",
                  }}
                >
                  {tract.is_leased ? "Leased" : "Unleased"}
                </span>
                {tract.gross_acres && (
                  <span className="tabular text-sm text-ink-3">{tract.gross_acres} ac</span>
                )}
              </div>
              {tract.aliquot_parts.length > 0 && (
                <div className="text-sm text-ink-2 font-serif-italic mb-1">
                  {tract.aliquot_parts
                    .map((ap) =>
                      ap.quarters.length > 0
                        ? ap.quarters.join(" of ") + " of Section " + sectionData.section
                        : ap.lots.length > 0
                        ? "Lots " + ap.lots.join(", ")
                        : "Whole section"
                    )
                    .join("; ")}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Instruments */}
      {uniqueInstruments.length > 0 && (
        <div>
          <div className="rule-hairline mb-3">
            <span className="eyebrow">Instruments of record</span>
          </div>
          <ol className="space-y-2.5">
            {uniqueInstruments.map((inst, i) => (
              <li key={inst.instrument_id} className="grid grid-cols-[1.5rem_1fr] gap-3 items-baseline">
                <span className="font-numeric text-sm text-ink-3 text-right">{i + 1}.</span>
                <div>
                  <div className="text-[0.95rem] text-ink font-medium">{inst.instrument_type}</div>
                  <div className="text-sm text-ink-2 font-serif-italic">
                    {inst.grantor && inst.grantee ? (
                      <>
                        {inst.grantor}
                        <span className="mx-1.5 text-accent not-italic">→</span>
                        {inst.grantee}
                      </>
                    ) : null}
                  </div>
                  <div className="flex items-center gap-2 mt-0.5 flex-wrap">
                    {inst.date && (
                      <span className="tabular text-xs text-ink-3">{inst.date}</span>
                    )}
                    {inst.document && (
                      <span className="text-xs text-ink-3 font-serif-italic">
                        · {inst.document.filename}
                      </span>
                    )}
                  </div>
                </div>
              </li>
            ))}
          </ol>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Non-PLSS tract card
// ---------------------------------------------------------------------------

function NonPlssTractCard({ tract }: { tract: TractEntry }) {
  const type = tract.parsed.description_type;
  const typeLabel =
    type === "texas_abstract" ? "Texas Abstract" :
    type === "lot_block" ? "Lot/Block" :
    type === "metes_bounds" ? "Metes & Bounds" :
    "Non-PLSS";

  return (
    <div className="border border-line bg-surface px-5 py-4">
      <div className="flex items-start justify-between gap-3 mb-2">
        <div className="min-w-0">
          <div className="eyebrow mb-1">{typeLabel}</div>
          <div className="text-sm font-medium text-ink leading-snug">{tract.legal_description}</div>
        </div>
        <span
          className="shrink-0 text-xs font-medium px-2 py-0.5 rounded"
          style={{
            background: tract.is_leased ? "#dae0c8" : "#faf6ea",
            color: tract.is_leased ? "#4c5f3e" : "#7c8491",
            border: `1px solid ${tract.is_leased ? "#4c5f3e" : "#b3a482"}`,
          }}
        >
          {tract.is_leased ? "Leased" : "Unleased"}
        </span>
      </div>

      {/* Type-specific detail */}
      {type === "texas_abstract" && (
        <div className="text-xs text-ink-3 font-serif-italic">
          {tract.parsed.abstract_number && <>Abstract No. {tract.parsed.abstract_number}</>}
          {tract.parsed.survey_name && <>, {tract.parsed.survey_name} Survey</>}
        </div>
      )}
      {type === "lot_block" && (
        <div className="text-xs text-ink-3 font-serif-italic">
          {[
            tract.parsed.lot && `Lot ${tract.parsed.lot}`,
            tract.parsed.block && `Block ${tract.parsed.block}`,
            tract.parsed.subdivision,
          ]
            .filter(Boolean)
            .join(", ")}
        </div>
      )}

      {tract.parsed.parse_notes.length > 0 && (
        <div className="mt-2 text-xs text-ink-4 font-serif-italic">
          {tract.parsed.parse_notes[0]}
        </div>
      )}

      {/* Instruments */}
      {tract.instruments.length > 0 && (
        <div className="mt-3 pt-3 border-t border-line">
          <div className="space-y-1">
            {tract.instruments.map((inst) => (
              <div key={inst.instrument_id} className="flex items-baseline gap-2 text-sm">
                <span className="text-ink-3 text-xs shrink-0">{inst.instrument_type}</span>
                {inst.grantor && inst.grantee && (
                  <span className="text-ink-2 font-serif-italic">
                    {inst.grantor}
                    <span className="mx-1 text-accent not-italic">→</span>
                    {inst.grantee}
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Legend
// ---------------------------------------------------------------------------

function Legend() {
  return (
    <div className="flex items-center gap-6 text-xs text-ink-3 font-serif-italic">
      <span className="flex items-center gap-1.5">
        <span
          className="inline-block w-4 h-4 rounded-[1px]"
          style={{ background: "#4c5f3e", opacity: 0.6 }}
        />
        Leased
      </span>
      <span className="flex items-center gap-1.5">
        <span
          className="inline-block w-4 h-4 rounded-[1px]"
          style={{ background: "#9b4620", opacity: 0.5 }}
        />
        Unleased acreage
      </span>
      <span className="flex items-center gap-1.5">
        <span
          className="inline-block w-4 h-4 rounded-[1px]"
          style={{ background: "#faf6ea", border: "1px solid #b3a482" }}
        />
        No record
      </span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main TractMap component
// ---------------------------------------------------------------------------

export default function TractMap({ projectId }: { projectId: number }) {
  const [data, setData] = useState<TractMapData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedSection, setSelectedSection] = useState<{ section: number; twpKey: string } | null>(null);

  useEffect(() => {
    const fetch = async () => {
      try {
        setLoading(true);
        const res = await axios.get(`${API_URL}/projects/${projectId}/tract-map`);
        setData(res.data);
      } catch (err: any) {
        setError(err.response?.data?.detail || "Failed to load tract map");
      } finally {
        setLoading(false);
      }
    };
    fetch();
  }, [projectId]);

  const handleSectionClick = useCallback(
    (sn: number, twpKey: string) => {
      if (!data) return;
      const twp = data.townships.find((t) => t.key === twpKey);
      if (!twp) return;
      const secData = twp.sections.find((s) => s.section === sn);
      if (!secData || secData.tracts.length === 0) {
        setSelectedSection(null);
        return;
      }
      setSelectedSection((prev) =>
        prev?.section === sn && prev?.twpKey === twpKey ? null : { section: sn, twpKey }
      );
    },
    [data]
  );

  if (loading) {
    return (
      <div className="px-10 py-12 text-sm text-ink-3">
        <span className="inline-block w-3 h-3 border-2 border-ink-3/30 border-t-ink rounded-full animate-spin mr-2 align-middle" />
        <span className="font-serif-italic">Loading tract map…</span>
      </div>
    );
  }

  if (error) {
    return <div className="px-10 py-12 text-sm text-danger font-serif-italic">{error}</div>;
  }

  const isEmpty = !data?.tracts?.length;

  return (
    <div className="px-10 py-12">
      {/* Heading */}
      <div className="mb-8">
        <div className="eyebrow mb-2">Section I</div>
        <h2 className="font-display text-[2.4rem] font-medium leading-none text-ink tracking-tight">
          Tract view
        </h2>
        <p className="mt-3 font-serif-italic text-ink-2 text-[1.02rem] max-w-2xl">
          PLSS section grid with leased and open acreage. Click any highlighted section to see its instruments.
        </p>
      </div>

      {isEmpty ? (
        <EmptyState
          title="This project has no PLSS tracts"
          description="Upload deeds or leases in the Documents tab. Section will parse the legal descriptions and plot them on the PLSS grid."
        />
      ) : (
        <>
          {/* PLSS grids */}
          {data!.has_plss && data!.townships.length > 0 && (
            <div className="space-y-12">
              {data!.townships.map((twp) => {
                const selSec =
                  selectedSection?.twpKey === twp.key
                    ? twp.sections.find((s) => s.section === selectedSection.section) || null
                    : null;

                return (
                  <div key={twp.key}>
                    <div className="border-t-[2.5px] border-rule">
                      <div className="border-t border-rule mt-[3px] mb-6" />
                    </div>

                    <div className="flex flex-col lg:flex-row gap-8 items-start">
                      {/* Grid */}
                      <div className="shrink-0">
                        <TownshipGrid
                          township={twp}
                          onSectionClick={handleSectionClick}
                          selectedSection={selectedSection}
                        />
                        <div className="mt-4">
                          <Legend />
                        </div>
                      </div>

                      {/* Right panel: section detail or township summary */}
                      <div className="flex-1 min-w-0">
                        {selSec ? (
                          <SectionDetail
                            sectionData={selSec}
                            township={twp}
                            onClose={() => setSelectedSection(null)}
                          />
                        ) : (
                          <div className="pt-1">
                            <div className="eyebrow mb-3">{twp.key} summary</div>
                            <div className="space-y-2">
                              {[
                                {
                                  label: "Sections of record",
                                  value: twp.sections.length,
                                },
                                {
                                  label: "Leased sections",
                                  value: twp.sections.filter((s) =>
                                    s.tracts.some((t) => t.is_leased)
                                  ).length,
                                },
                                {
                                  label: "Open sections",
                                  value: twp.sections.filter((s) =>
                                    s.tracts.some((t) => !t.is_leased)
                                  ).length,
                                },
                                {
                                  label: "Total instruments",
                                  value: twp.sections.reduce(
                                    (acc, s) =>
                                      acc +
                                      new Set(
                                        s.tracts.flatMap((t) =>
                                          t.instruments.map((i) => i.instrument_id)
                                        )
                                      ).size,
                                    0
                                  ),
                                },
                              ].map(({ label, value }) => (
                                <div
                                  key={label}
                                  className="flex items-baseline justify-between gap-4 py-1.5 border-b border-line last:border-b-0"
                                >
                                  <span className="text-sm text-ink-2 font-serif-italic">{label}</span>
                                  <span className="tabular text-sm font-medium text-ink">{value}</span>
                                </div>
                              ))}
                            </div>
                            <p className="mt-4 text-xs text-ink-4 font-serif-italic">
                              Click a highlighted section on the grid to view its instruments.
                            </p>
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {/* Non-PLSS tracts */}
          {data!.non_plss_tracts.length > 0 && (
            <div className="mt-14">
              <div className="border-t-[2.5px] border-rule">
                <div className="border-t border-rule mt-[3px] mb-6" />
              </div>
              <div className="mb-6">
                <div className="eyebrow mb-2">Non-PLSS tracts</div>
                <h3 className="font-display text-[1.8rem] font-medium leading-none text-ink tracking-tight">
                  Texas abstracts &amp; other survey systems
                </h3>
                <p className="mt-3 font-serif-italic text-ink-2 text-sm max-w-2xl">
                  These tracts use survey systems outside the PLSS grid — they cannot be plotted on the township map but are listed here with their instruments.
                </p>
              </div>
              <div className="grid gap-3 sm:grid-cols-2">
                {data!.non_plss_tracts.map((tract) => (
                  <NonPlssTractCard key={tract.tract_id} tract={tract} />
                ))}
              </div>
            </div>
          )}

          {/* No PLSS but has tracts */}
          {!data!.has_plss && data!.non_plss_tracts.length === 0 && data!.tracts.length > 0 && (
            <div className="border border-dashed border-line-strong bg-surface-2 px-6 py-16 text-center">
              <div className="font-display text-xl text-ink mb-1">Legal descriptions not yet parsed</div>
              <p className="text-sm text-ink-3 max-w-md mx-auto font-serif-italic">
                Upload documents with PLSS legal descriptions (Section X, T__N, R__W) to render the grid.
              </p>
            </div>
          )}
        </>
      )}
    </div>
  );
}
