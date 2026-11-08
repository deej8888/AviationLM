# Adding an extraction domain

The backend contract is `generate(text, DomainSpec) -> raw JSON`. The service validates
that raw output against the selected domain schema and applies domain review rules.
FastAPI discovers registered domains and exposes their JSON schemas. The charter demo
is the only implemented domain; planned domains are not advertised as functional APIs.

For a new industry or operations domain:

1. Define Pydantic models with `extra="forbid"` and explicit unknown-value semantics.
2. Register a `DomainSpec` with its name, schema, extraction instructions, and a review
   callback in the application registry. Do not put industry parsing into the service.
3. Use the generic HF backend or add a domain-specific rules baseline. The bundled rules
   backend explicitly refuses domains other than charter.
4. Build an independently labeled dataset and held-out challenge suite. Generalize the
   current charter-specific training/evaluation loaders to accept the domain identifier.
5. Add request/response types and a result renderer to the dashboard. Its initial overview
   deliberately targets charter; the raw backend/service contracts are industry-neutral.
6. Version contracts when changing field semantics, and compare raw model outputs before
   deploying a new adapter.

Possible future contracts:

| Domain | Candidate extracted facts | Boundaries |
| --- | --- | --- |
| Maintenance | synthetic tail, ATA chapter, discrepancy, AOG status, station, requested deadline | no airworthiness decisions |
| Parts | part number, quantity, condition, trace documentation, delivery location | no substitution or approval decisions |
| Crew | roles, qualifications requested, base, dates, legs | no duty-limit or legality decisions |
| Other industries | customer-defined schema and review callback | explicit domain-specific limitations |

`tests/test_extraction.py::test_extensible_to_unrelated_domain` exercises an unrelated
support-ticket schema through the same registry and service without charter parsing.
