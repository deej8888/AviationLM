import { Check, ClipboardCheck, Plus, RotateCcw, Trash2, TriangleAlert } from "lucide-react";
import type { CharterData, FlightLeg, ReviewAssessment } from "@/lib/types";

const emptyLeg = (): FlightLeg => ({ origin: null, destination: null, departure_date: null, departure_time: null, time_zone: null });

interface Props {
  draft: CharterData;
  assessment: ReviewAssessment | null;
  dirty: boolean;
  busy: boolean;
  acknowledged: boolean;
  confirmedAt: string | null;
  error: string;
  onChange: (value: CharterData) => void;
  onCheck: () => void;
  onReset: () => void;
  onAcknowledge: (value: boolean) => void;
  onConfirm: () => void;
}

export function ReviewWorkspace({ draft, assessment, dirty, busy, acknowledged, confirmedAt, error,
  onChange, onCheck, onReset, onAcknowledge, onConfirm }: Props) {
  function top<K extends keyof CharterData>(name: K, value: CharterData[K]) {
    onChange({ ...draft, [name]: value });
  }
  function changeLeg(index: number, name: keyof FlightLeg, value: string | null) {
    onChange({ ...draft, legs: draft.legs.map((leg, i) => i === index ? { ...leg, [name]: value } : leg) });
  }
  function detail(path: string, value: unknown) {
    if (value === null || value === "") return <span className="review-hint">Not provided · confirm if needed</span>;
    if (dirty || !assessment) return <span className="review-hint">Check changes to refresh source details</span>;
    const evidence = assessment.evidence.find((item) => item.path === path && item.value === value);
    const check = assessment.checks.find((item) => item.path === path && item.value === value);
    return <span className="review-evidence">
      <span className={evidence?.status === "matched" ? "source-match" : "source-missing"}>
        {evidence?.status === "matched" ? <>In request: <q>{evidence.quote}</q></> : "No matching source found"}
      </span>
      {check && <span className={check.status === "matched" ? "source-match" : "source-missing"}>
        {check.status === "matched" && check.matches[0]
          ? `Reference: ${check.matches[0].name}${check.matches[0].municipality ? ` · ${check.matches[0].municipality}` : ""} (${check.matches[0].country})`
          : check.message}
      </span>}
    </span>;
  }
  const nullable = (value: string) => value.trim() ? value : null;
  return (
    <section className="panel review-workspace" aria-label="Review and correct request">
      <div className="panel-heading">
        <div><ClipboardCheck size={18} /><h3>Review and correct</h3></div>
        <span className={`review-status ${confirmedAt ? "complete" : ""}`}>
          {confirmedAt ? "REVIEW CONFIRMED" : dirty ? "CHANGES NOT CHECKED" : "REVIEW NEEDED"}
        </span>
      </div>
      <div className="review-content">
        <p className="review-intro">Compare the draft with the original request. Source matches are hints; check the surrounding context and confirm airport details.</p>
        {draft.legs.map((flight, index) => <fieldset className="review-leg" key={index} disabled={busy}>
          <legend>Flight leg {index + 1}</legend>
          <div className="review-fields">
            {(["origin", "destination"] as const).map((field) => <label key={field} className="review-field">
              <span>{field === "origin" ? "Departure airport" : "Arrival airport"}</span>
              <input aria-label={`Leg ${index + 1} ${field}`} value={flight[field] ?? ""} maxLength={4}
                placeholder="Airport code" onChange={(event) => changeLeg(index, field, nullable(event.target.value.toUpperCase()))} />
              {detail(`legs[${index}].${field}`, flight[field])}
            </label>)}
            <label className="review-field"><span>Departure date</span>
              <input type="date" aria-label={`Leg ${index + 1} departure date`} value={flight.departure_date ?? ""}
                onChange={(event) => changeLeg(index, "departure_date", nullable(event.target.value))} />
              {detail(`legs[${index}].departure_date`, flight.departure_date)}</label>
            <label className="review-field"><span>Departure time</span>
              <input type="time" aria-label={`Leg ${index + 1} departure time`} value={flight.departure_time ?? ""}
                onChange={(event) => changeLeg(index, "departure_time", nullable(event.target.value))} />
              {detail(`legs[${index}].departure_time`, flight.departure_time)}</label>
            <label className="review-field"><span>Time zone</span>
              <select aria-label={`Leg ${index + 1} time zone`} value={flight.time_zone ?? ""}
                onChange={(event) => changeLeg(index, "time_zone", nullable(event.target.value))}>
                <option value="">Not specified</option><option value="local">Local</option><option value="UTC">UTC</option>
              </select>{detail(`legs[${index}].time_zone`, flight.time_zone)}</label>
          </div>
          <button type="button" className="review-text-button danger" onClick={() => top("legs", draft.legs.filter((_, i) => i !== index))}>
            <Trash2 size={14} /> Remove leg
          </button>
        </fieldset>)}
        <button type="button" className="review-text-button" disabled={busy || draft.legs.length >= 20}
          onClick={() => top("legs", [...draft.legs, emptyLeg()])}><Plus size={14} /> Add flight leg</button>
        <div className="review-fields review-details">
          <label className="review-field"><span>Trip type</span>
            <select aria-label="Trip type" disabled={busy} value={draft.trip_type ?? ""} onChange={(e) => top("trip_type", nullable(e.target.value))}>
              <option value="">Not specified</option><option value="one_way">One-way</option><option value="round_trip">Round trip</option><option value="multi_leg">Multi-leg</option>
            </select>{detail("trip_type", draft.trip_type)}</label>
          <label className="review-field"><span>Passengers</span>
            <input type="number" min="1" max="1000" aria-label="Passengers" disabled={busy} value={draft.passengers ?? ""}
              onChange={(e) => top("passengers", e.target.value === "" ? null : Number(e.target.value))} />
            {detail("passengers", draft.passengers)}</label>
          <label className="review-field"><span>Aircraft preference</span>
            <input aria-label="Aircraft preference" maxLength={160} disabled={busy} value={draft.aircraft_preference ?? ""}
              onChange={(e) => top("aircraft_preference", nullable(e.target.value))} />{detail("aircraft_preference", draft.aircraft_preference)}</label>
          <label className="review-field"><span>Aircraft category</span>
            <select aria-label="Aircraft category" disabled={busy} value={draft.aircraft_category ?? ""} onChange={(e) => top("aircraft_category", nullable(e.target.value))}>
              <option value="">Not specified</option>{["turboprop", "light_jet", "midsize_jet", "super_midsize_jet", "heavy_jet", "helicopter"].map((item) => <option key={item} value={item}>{item.replaceAll("_", " ")}</option>)}
            </select>{detail("aircraft_category", draft.aircraft_category)}</label>
          <label className="review-field"><span>Return date</span>
            <input type="date" aria-label="Return date" disabled={busy} value={draft.return_date ?? ""} onChange={(e) => top("return_date", nullable(e.target.value))} />
            {detail("return_date", draft.return_date)}</label>
          <label className="review-field"><span>Budget</span>
            <input aria-label="Budget" maxLength={160} disabled={busy} value={draft.budget ?? ""} onChange={(e) => top("budget", nullable(e.target.value))} />
            {detail("budget", draft.budget)}</label>
          <label className="review-field"><span>Contact email</span>
            <input type="email" aria-label="Contact email" maxLength={254} disabled={busy} value={draft.contact_email ?? ""} onChange={(e) => top("contact_email", nullable(e.target.value))} />
            {detail("contact_email", draft.contact_email)}</label>
        </div>
        <div className="review-requirements"><strong>Special requirements</strong>
          {draft.special_requirements.map((value, index) => <div className="review-requirement" key={index}>
            <label className="review-field"><span className="sr-only">Requirement {index + 1}</span>
              <input aria-label={`Requirement ${index + 1}`} disabled={busy} value={value} maxLength={200}
                onChange={(e) => top("special_requirements", draft.special_requirements.map((v, i) => i === index ? e.target.value : v))} />
              {detail("special_requirements", value)}</label>
            <button type="button" className="icon-button" aria-label={`Remove requirement ${index + 1}`} disabled={busy}
              onClick={() => top("special_requirements", draft.special_requirements.filter((_, i) => i !== index))}><Trash2 size={15} /></button>
          </div>)}
          {!draft.special_requirements.length && <p className="review-hint">None extracted</p>}
          <button type="button" className="review-text-button" disabled={busy || draft.special_requirements.length >= 30}
            onClick={() => top("special_requirements", [...draft.special_requirements, ""])}><Plus size={14} /> Add requirement</button>
        </div>
        <div className="review-actions">
          <button type="button" className="secondary-button" onClick={onCheck} disabled={busy || !dirty}>{busy ? "Checking…" : "Check changes"}</button>
          <button type="button" className="review-text-button" onClick={onReset} disabled={busy}><RotateCcw size={14} /> Reset edits</button>
        </div>
        {error && <div className="error-box" role="alert"><TriangleAlert size={17} />{error}</div>}
        <label className="review-confirmation"><input type="checkbox" checked={acknowledged} disabled={busy || dirty || !assessment}
          onChange={(e) => onAcknowledge(e.target.checked)} /> I reviewed the extracted and missing details against the request.</label>
        <button type="button" className="primary-button" onClick={onConfirm} disabled={busy || dirty || !assessment || !acknowledged || !!confirmedAt}>
          <Check size={16} /> {confirmedAt ? "Review confirmed" : "Confirm review"}
        </button>
        <p className="review-disclaimer">Confirmation is recorded in this browser session. The airport reference is informational and may be incomplete or outdated.</p>
      </div>
    </section>
  );
}
