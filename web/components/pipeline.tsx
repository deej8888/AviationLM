import { Database, Plus, Layers3, Braces } from "lucide-react";

export function Pipeline() {
  return (
    <section>
      <div className="section-heading">
        <div>
          <span className="section-number">03</span>
          <h2>From data to deployment</h2>
        </div>
        <span className="subtle-label">REPRODUCIBLE BY DESIGN</span>
      </div>
      <div className="pipeline-grid">
        {[
          {
            n: "01",
            icon: Database,
            title: "Generate",
            detail:
              "Synthetic aviation emails with independent ground truth. Seeded generation and template-held-out splits.",
            code: "aerolm generate",
          },
          {
            n: "02",
            icon: Plus,
            title: "Fine-tune",
            detail:
              "Qwen3 0.6B or 1.7B with completion-only LoRA / QLoRA. Standard PEFT or optional Unsloth acceleration.",
            code: "aerolm train --config configs/qlora.toml",
          },
          {
            n: "03",
            icon: Layers3,
            title: "Evaluate",
            detail:
              "Compare base and adapter outputs on identical held-out requests. Keep raw predictions and dataset hashes.",
            code: "aerolm evaluate --dataset data/generated/test.jsonl",
          },
          {
            n: "04",
            icon: Braces,
            title: "Extract & review",
            detail:
              "FastAPI serves validated domain objects. A schema registry separates aviation rules from the extraction engine.",
            code: "uvicorn aerolm.api:app --port 8000",
          },
        ].map((item) => (
          <div key={item.n} className="panel pipeline-card">
            <div className="pipeline-top">
              <item.icon size={22} />
              <span>{item.n}</span>
            </div>
            <h3>{item.title}</h3>
            <p>{item.detail}</p>
            <code>{item.code}</code>
          </div>
        ))}
      </div>
      <div className="panel info-card extend-card">
        <span className="eyebrow">ONE ENGINE. MORE HORIZONS.</span>
        <h3>Charter first. Extensible by design.</h3>
        <p>
          Add a domain schema, extraction instructions, review rules, and
          labeled fixtures to the registry. Maintenance, parts procurement, and
          crew scheduling are planned extensions. The core engine has no
          dependency on an airport database or aviation-specific schema.
        </p>
      </div>
    </section>
  );
}
