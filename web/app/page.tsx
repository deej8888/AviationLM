"use client";

import { useEffect, useRef, useState } from "react";
import {
  ArrowDownToLine,
  ArrowRight,
  ArrowUpRight,
  Braces,
  Check,
  CheckCheck,
  ChevronRight,
  CircleHelp,
  Copy,
  Database,
  FileJson,
  LoaderCircle,
  Mail,
  Menu,
  Plane,
  RotateCcw,
  ShieldCheck,
  Terminal,
  TriangleAlert,
  X,
} from "lucide-react";
import type { CharterData, Example, ExtractionResult, Health, Report, ReviewAssessment } from "@/lib/types";

import { JsonView } from "@/components/json-view";
import { RouteGraphic } from "@/components/route-graphic";
import { Sidebar } from "@/components/sidebar";
import { CharterOverview } from "@/components/charter-overview";
import { Evaluations } from "@/components/evaluations";
import { Pipeline } from "@/components/pipeline";
import { ReviewWorkspace } from "@/components/review-workspace";

const FIRST =
  "Subject: Charter quote / TEB to MIA\n\nHi charter desk,\n\nPlease quote a round trip TEB to MIA on 2027-03-18 at 09:30 local for 6 pax. Return 2027-03-21.\n\nPrefer a Citation Latitude, or a comparable super midsize jet. WiFi and catering required. Budget USD 35,000.\n\nPlease reply to dispatch@meridian.example.\nThanks,\nAlex";

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api/proxy/${path}`, {
    ...init,
    cache: "no-store",
  });
  const data = await response.json();
  if (!response.ok)
    throw new Error(
      typeof data.detail === "string"
        ? data.detail
        : "Request validation failed. Check your input.",
    );
  return data as T;
}

export default function Home() {
  const [section, setSection] = useState("workspace");
  const [mobileNav, setMobileNav] = useState(false);
  const [text, setText] = useState(FIRST);
  const [examples, setExamples] = useState<Example[]>([]);
  const [health, setHealth] = useState<Health | null>(null);
  const [reports, setReports] = useState<Report[]>([]);
  const [schema, setSchema] = useState<unknown>(null);
  const [result, setResult] = useState<ExtractionResult | null>(null);
  const [draft, setDraft] = useState<CharterData | null>(null);
  const [assessment, setAssessment] = useState<ReviewAssessment | null>(null);
  const [dirty, setDirty] = useState(false);
  const [checking, setChecking] = useState(false);
  const [acknowledged, setAcknowledged] = useState(false);
  const [confirmedAt, setConfirmedAt] = useState<string | null>(null);
  const [reviewError, setReviewError] = useState("");
  const [view, setView] = useState("overview");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");
  const [selected, setSelected] = useState("executive");
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    api<Health>("healthz")
      .then(setHealth)
      .catch(() => setHealth(null));
    api<Example[]>("v1/examples")
      .then(setExamples)
      .catch(() => {});
    api<{ reports: Report[] }>("v1/benchmarks")
      .then((data) => setReports(data.reports))
      .catch(() => {});
    api<unknown>("v1/schema/charter")
      .then(setSchema)
      .catch(() => {});
    return () => {
      mounted.current = false;
    };
  }, []);
  useEffect(() => {
    if (toast) {
      const timer = setTimeout(() => setToast(""), 3000);
      return () => clearTimeout(timer);
    }
  }, [toast]);

  const navigate = (name: string) => {
    setSection(name);
    setMobileNav(false);
  };
  function clearReview() {
    setDraft(null); setAssessment(null); setDirty(false); setAcknowledged(false);
    setConfirmedAt(null); setReviewError("");
  }
  function initialAssessment(value: ExtractionResult): ReviewAssessment {
    return { data: value.data, warnings: value.warnings, evidence: value.evidence ?? [],
      checks: value.checks ?? [], requires_review: value.requires_review };
  }
  function changeDraft(value: CharterData) {
    setDraft(value); setDirty(true); setAssessment(null); setAcknowledged(false);
    setConfirmedAt(null); setReviewError("");
  }
  function resetEdits() {
    if (!result) return;
    setDraft(structuredClone(result.data)); setAssessment(initialAssessment(result));
    setDirty(false); setAcknowledged(false); setConfirmedAt(null); setReviewError("");
  }
  async function checkReview() {
    if (!draft) return;
    setChecking(true); setReviewError("");
    try {
      const data = { ...draft, special_requirements: draft.special_requirements.map((v) => v.trim()).filter(Boolean) };
      const reviewed = await api<ReviewAssessment>("v1/review", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, domain: "charter", data }),
      });
      setDraft(reviewed.data); setAssessment(reviewed); setDirty(false);
      setAcknowledged(false); setConfirmedAt(null);
    } catch (failure) {
      setReviewError(failure instanceof Error ? failure.message : "Review failed.");
    } finally { setChecking(false); }
  }
  async function extract() {
    setBusy(true);
    setError("");
    setResult(null);
    clearReview();
    try {
      const data = await api<ExtractionResult>("v1/extract", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, domain: "charter" }),
      });
      if (mounted.current) {
        setResult(data);
        setDraft(structuredClone(data.data));
        setAssessment(initialAssessment(data));
        setView("overview");
      }
      api<Health>("healthz")
        .then(setHealth)
        .catch(() => {});
    } catch (failure) {
      setError(
        failure instanceof Error ? failure.message : "Extraction failed.",
      );
    } finally {
      setBusy(false);
    }
  }
  function loadExample(example: Example) {
    setText(example.text);
    setSelected(example.id);
    setResult(null);
    clearReview();
    setError("");
  }
  async function copy() {
    if (!assessment || !confirmedAt) return;
    try {
      await navigator.clipboard.writeText(JSON.stringify(assessment.data, null, 2));
      setToast("JSON copied to clipboard");
    } catch {
      setToast("Clipboard unavailable. Use Download JSON instead.");
    }
  }
  function download() {
    if (!result || !assessment || !confirmedAt) return;
    const url = URL.createObjectURL(
      new Blob([JSON.stringify({ ...result, ...assessment, original_data: result.data,
        review: { status: "confirmed_by_user", confirmed_at: confirmedAt,
          modified: JSON.stringify(result.data) !== JSON.stringify(assessment.data) } }, null, 2)], { type: "application/json" }),
    );
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "aerolm-extraction.json";
    anchor.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="app-shell">
      <Sidebar mobileNav={mobileNav} section={section} navigate={navigate} />

      <main>
        <header className="topbar">
          <div className="breadcrumb">
            <button
              className="mobile-menu icon-button"
              aria-label="Toggle navigation"
              onClick={() => setMobileNav(!mobileNav)}
            >
              {mobileNav ? <X size={20} /> : <Menu size={20} />}
            </button>
            <span>Operations lab</span>
            <ChevronRight size={13} />
            <strong>
              {section === "workspace"
                ? "Workspace"
                : section === "evaluations"
                  ? "Evaluations"
                  : "The pipeline"}
            </strong>
          </div>
          <div className="topbar-right">
            <span className={`connection ${health ? "online" : ""}`}>
              <span className="tiny-dot" />
              {health ? "API connected" : "API not connected"}
            </span>
            <span className="topbar-divider" />
            <span className="mono">LOCAL ENVIRONMENT</span>
          </div>
        </header>

        <div className="main-content">
          <section className="hero">
            <div>
              <div className="eyebrow">
                <span />
                AVIATION, STRUCTURED.
              </div>
              <h1>
                {section === "workspace" ? (
                  <>
                    From inbox to
                    <br />
                    flight plan<span>.</span>
                  </>
                ) : section === "evaluations" ? (
                  <>
                    Evidence before
                    <br />
                    altitude<span>.</span>
                  </>
                ) : (
                  <>
                    Small model.
                    <br />
                    Purposeful pipeline<span>.</span>
                  </>
                )}
              </h1>
              <p>
                {section === "workspace"
                  ? "Turn operational language into clear, structured data.\nStart with a charter request. See what takes shape."
                  : section === "evaluations"
                    ? "Measured results, reproducible runs, and no invented scores.\nEvery number should have a flight log."
                    : "A focused aviation use case. An extensible extraction engine.\nFrom synthetic examples to a locally served adapter."}
              </p>
            </div>
            <RouteGraphic />
          </section>

          <div className="status-strip">
            <div>
              <span className="status-icon">
                <Terminal size={17} />
              </span>
              <div>
                <small>ACTIVE BACKEND</small>
                <strong>
                  {health
                    ? health.backend === "rules"
                      ? "Rules baseline"
                      : health.adapter_loaded
                        ? "Qwen + LoRA adapter"
                        : "Qwen base model"
                    : "Awaiting API"}
                  <span className="status-pill">
                    {health?.backend === "rules"
                      ? "CPU"
                      : health
                        ? "HF"
                        : "OFFLINE"}
                  </span>
                </strong>
              </div>
            </div>
            <div>
              <span className="status-icon">
                <Database size={17} />
              </span>
              <div>
                <small>TRAINING DATA</small>
                <strong>
                  100% synthetic<span className="muted"> / CC0</span>
                </strong>
              </div>
            </div>
            <div>
              <span className="status-icon">
                <ShieldCheck size={17} />
              </span>
              <div>
                <small>OUTPUT CONTRACT</small>
                <strong>
                  Validated JSON<span className="muted"> / v1.0</span>
                </strong>
              </div>
            </div>
          </div>

          {section === "workspace" && (
            <>
              <div className="section-heading">
                <div>
                  <span className="section-number">01</span>
                  <h2>Extraction workspace</h2>
                </div>
                <span className="subtle-label">
                  CHARTER REQUESTS <span className="tiny-dot orange" /> LIVE
                  PREVIEW
                </span>
              </div>
              <div className="workspace-grid">
                <section className="panel input-panel">
                  <div className="panel-heading">
                    <div>
                      <Mail size={17} />
                      <h3>Source request</h3>
                    </div>
                    <span className="file-label">PLAIN TEXT</span>
                  </div>
                  <div className="example-area">
                    <label htmlFor="example">Start with an example</label>
                    <select
                      id="example"
                      value={selected}
                      disabled={busy || checking || !examples.length}
                      onChange={(e) => {
                        const example = examples.find(
                          (item) => item.id === e.target.value,
                        );
                        if (example) loadExample(example);
                      }}
                    >
                      <option value="" disabled>
                        Custom request
                      </option>
                      {examples.length ? (
                        examples.map((example) => (
                          <option key={example.id} value={example.id}>
                            {example.label} · {example.tag}
                          </option>
                        ))
                      ) : (
                        <option value="executive">
                          Executive charter · Round trip
                        </option>
                      )}
                    </select>
                  </div>
                  <div className="editor-label">
                    <label htmlFor="request">REQUEST BODY</label>
                    <button
                      disabled={busy || checking}
                      onClick={() => {
                        setText("");
                        setResult(null);
                        clearReview();
                        setSelected("");
                        setError("");
                      }}
                    >
                      <RotateCcw size={12} /> Clear
                    </button>
                  </div>
                  <textarea
                    id="request"
                    value={text}
                    maxLength={12000}
                    spellCheck={false}
                    disabled={busy || checking}
                    onChange={(e) => {
                      setText(e.target.value);
                      setResult(null);
                      clearReview();
                      setSelected("");
                      setError("");
                    }}
                    placeholder="Paste a synthetic charter email or operational request…"
                  />
                  <div className="editor-meta">
                    <span>
                      <span className="tiny-dot" /> Synthetic example · no real
                      client data
                    </span>
                    <span>{text.length.toLocaleString()} / 12,000</span>
                  </div>
                  {error && (
                    <div role="alert" className="error-box">
                      <TriangleAlert size={17} />
                      {error}
                    </div>
                  )}
                  <div className="extract-action">
                    <button
                      className="primary-button"
                      onClick={extract}
                      disabled={busy || checking || !text.trim()}
                    >
                      {busy ? (
                        <>
                          <LoaderCircle className="spin" size={17} /> Extracting
                          request…
                        </>
                      ) : (
                        <>
                          Extract request <ArrowRight size={17} />
                        </>
                      )}
                    </button>
                    <span>Schema-validated. Ready for review.</span>
                  </div>
                </section>

                <section
                  className="panel output-panel"
                  aria-label="Extraction result"
                  aria-busy={busy}
                >
                  <div className="panel-heading">
                    <div>
                      <Braces size={18} />
                      <h3>Structured output</h3>
                    </div>
                    <div className="output-actions">
                      <button
                        className="icon-button"
                        onClick={copy}
                        disabled={!result || !confirmedAt || !assessment}
                        aria-label="Copy JSON"
                      >
                        <Copy size={15} />
                      </button>
                      <button
                        className="icon-button"
                        onClick={download}
                        disabled={!result || !confirmedAt || !assessment}
                        aria-label="Download JSON"
                      >
                        <ArrowDownToLine size={16} />
                      </button>
                    </div>
                  </div>
                  <div
                    className="output-tabs"
                    role="tablist"
                    aria-label="Output format"
                  >
                    {["overview", "json", "schema"].map((tab) => (
                      <button
                        key={tab}
                        role="tab"
                        aria-selected={view === tab}
                        onClick={() => setView(tab)}
                      >
                        {tab === "json"
                          ? "JSON"
                          : tab[0].toUpperCase() + tab.slice(1)}
                      </button>
                    ))}
                    {result && !dirty && (
                      <span className="valid-badge">
                        <CheckCheck size={12} /> Validated
                      </span>
                    )}
                  </div>
                  {view === "schema" ? (
                    schema ? (
                      <JsonView value={schema} />
                    ) : (
                      <div className="empty-state">
                        <FileJson />
                        <h3>Schema unavailable</h3>
                        <p>Connect the API to inspect the Pydantic contract.</p>
                      </div>
                    )
                  ) : !result ? (
                    <div className="empty-state">
                      <div className="empty-icon">
                        {busy ? (
                          <LoaderCircle className="spin" size={28} />
                        ) : (
                          <FileJson size={29} />
                        )}
                      </div>
                      <span className="mono">
                        {busy ? "EXTRACTING FACTS" : "CLEARED FOR EXTRACTION"}
                      </span>
                      <h3>
                        {busy
                          ? "Reading the request…"
                          : "A little structure goes a long way."}
                      </h3>
                      <p>
                        Airports, dates, passengers, and preferences.
                        <br />
                        Extract a request to see them here.
                      </p>
                      <div className="empty-route">
                        <span>INPUT</span>
                        <span className="dashed-line" />
                        <Plane size={16} />
                        <span className="dashed-line" />
                        <span>JSON</span>
                      </div>
                    </div>
                  ) : view === "json" ? (
                    <JsonView value={draft ?? result.data} />
                  ) : (
                    <CharterOverview result={{ ...result, data: draft ?? result.data }} />
                  )}
                  <div className="output-footer">
                    <span className="tiny-dot" />
                    {result
                      ? `${result.backend === "rules" ? "Rules baseline" : result.adapter_loaded ? "Qwen + adapter" : "Qwen baseline"} · ${result.latency_ms.toFixed(1)} ms · schema v${result.schema_version}`
                      : "No extraction yet"}
                  </div>
                </section>
              </div>
              {result && draft && <ReviewWorkspace draft={draft} assessment={assessment} dirty={dirty}
                busy={checking} acknowledged={acknowledged} confirmedAt={confirmedAt} error={reviewError}
                onChange={changeDraft} onCheck={checkReview} onReset={resetEdits}
                onAcknowledge={(value) => { setAcknowledged(value); if (!value) setConfirmedAt(null); }}
                onConfirm={() => setConfirmedAt(new Date().toISOString())} />}
              {result && (
                <div className="review-box">
                  <TriangleAlert size={18} />
                  <div>
                    <strong>Review before operational use</strong>
                    <ul>
                      {(assessment?.warnings ?? ["Changes have not been checked yet."]).map((warning) => (
                        <li key={warning}>{warning}</li>
                      ))}
                    </ul>
                  </div>
                </div>
              )}
              <div className="note-strip">
                <CircleHelp size={16} />
                <p>
                  <strong>A working baseline. An honest starting point.</strong>{" "}
                  {health?.backend === "hf"
                    ? "The selected Qwen backend runs locally. Extracted facts still need human review."
                    : "This demo uses pattern matching. Qwen inference and fine-tuning are available separately—no model weights are loaded in rules mode."}
                </p>
                <button
                  onClick={() => navigate("pipeline")}
                  aria-label="Learn about the pipeline"
                >
                  <ArrowUpRight size={19} />
                </button>
              </div>
            </>
          )}

          {section === "evaluations" && <Evaluations reports={reports} />}

          {section === "pipeline" && <Pipeline />}
          <footer className="page-footer">
            <span>
              AeroLM <span className="orange-text">/</span> Aviation,
              structured.
            </span>
            <span>Open source. Local first. Human reviewed.</span>
          </footer>
        </div>
      </main>
      {toast && (
        <div className="toast" role="status">
          <Check size={15} />
          {toast}
        </div>
      )}
    </div>
  );
}
