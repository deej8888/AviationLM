import { Mail, Plane, Check, TriangleAlert } from "lucide-react";
import type { ExtractionResult } from "@/lib/types";

const pretty = (text: string | null) =>
  text ? text.replaceAll("_", " ") : "Not specified";

export function CharterOverview({ result }: { result: ExtractionResult }) {
  return (
    <div className="result-overview">
      {result.data.legs.length ? (
        result.data.legs.map((leg, index) => (
          <div className="route-card" key={index}>
            <span className="route-caption">
              {result.data.legs.length > 1
                ? `LEG ${index + 1}`
                : pretty(result.data.trip_type).toUpperCase()}
            </span>
            <div className="airport-route">
              <strong>{leg.origin || "TBD"}</strong>
              <span>
                <span className="dashed-line" />
                <Plane size={19} />
                <span className="dashed-line" />
              </span>
              <strong>{leg.destination || "TBD"}</strong>
            </div>
            <div className="route-date">
              <span>{leg.departure_date || "Date to confirm"}</span>
              <span>
                {leg.departure_time || "Time to confirm"} {leg.time_zone || ""}
              </span>
            </div>
          </div>
        ))
      ) : (
        <div className="missing-route">
          <TriangleAlert size={17} /> No airport route identified. Ask for
          specific airports.
        </div>
      )}
      <dl className="facts-grid">
        <div>
          <dt>PASSENGERS</dt>
          <dd>
            {result.data.passengers ?? "To confirm"}
            {result.data.passengers && <span> pax</span>}
          </dd>
        </div>
        <div>
          <dt>AIRCRAFT</dt>
          <dd>
            {result.data.aircraft_preference ||
              pretty(result.data.aircraft_category)}
          </dd>
        </div>
        <div>
          <dt>RETURN DATE</dt>
          <dd>{result.data.return_date || "Not specified"}</dd>
        </div>
        <div>
          <dt>BUDGET</dt>
          <dd>{result.data.budget || "Not specified"}</dd>
        </div>
      </dl>
      <div className="requirements">
        <small>SPECIAL REQUIREMENTS</small>
        <div>
          {result.data.special_requirements.length ? (
            result.data.special_requirements.map((item) => (
              <span key={item}>
                <Check size={11} />
                {pretty(item)}
              </span>
            ))
          ) : (
            <span className="no-requirements">None extracted</span>
          )}
        </div>
      </div>
      {result.data.contact_email && (
        <div className="contact-line">
          <Mail size={13} />
          {result.data.contact_email}
        </div>
      )}
    </div>
  );
}
