export interface FlightLeg {
  origin: string | null;
  destination: string | null;
  departure_date: string | null;
  departure_time: string | null;
  time_zone: string | null;
}
export interface CharterData {
  request_type: "charter";
  trip_type: string | null;
  legs: FlightLeg[];
  passengers: number | null;
  aircraft_category: string | null;
  aircraft_preference: string | null;
  return_date: string | null;
  budget: string | null;
  special_requirements: string[];
  contact_email: string | null;
}
export interface ExtractionResult {
  schema_version: string;
  domain: string;
  backend: string;
  model_id: string | null;
  adapter_loaded: boolean;
  data: CharterData;
  warnings: string[];
  latency_ms: number;
  requires_review: boolean;
}
export interface Example {
  id: string;
  label: string;
  tag: string;
  text: string;
}
export interface Health {
  status: string;
  backend: string;
  model_id: string | null;
  adapter_loaded: boolean;
}
export interface Report {
  label: string;
  backend: string;
  created_at: string;
  dataset: { name: string; sha256: string; count: number };
  metrics: {
    precision: number;
    recall: number;
    f1: number;
    json_validity: number;
    schema_validity: number;
    exact_match: number;
  };
}
