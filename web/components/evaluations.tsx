import { Layers3 } from "lucide-react";
import type { Report } from "@/lib/types";

const percent = (n: number) => `${(n * 100).toFixed(1)}%`;

export function Evaluations({ reports }: { reports: Report[] }) {
  return (
    <section className="evaluations">
      <div className="section-heading">
        <div>
          <span className="section-number">02</span>
          <h2>The benchmark log</h2>
        </div>
        <span className="subtle-label">MEASURED, NOT ESTIMATED</span>
      </div>
      <div className="panel benchmark-panel">
        <div className="panel-heading">
          <div>
            <Layers3 size={17} />
            <h3>Committed evaluation reports</h3>
          </div>
          <span className="file-label">SYNTHETIC ONLY</span>
        </div>
        {reports.length ? (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Run / dataset</th>
                  <th>Samples</th>
                  <th>Precision</th>
                  <th>Recall</th>
                  <th>F1</th>
                  <th>JSON valid</th>
                </tr>
              </thead>
              <tbody>
                {reports.map((report) => (
                  <tr key={report.label}>
                    <td>
                      <strong>{report.label}</strong>
                      <small>{report.dataset.name}</small>
                    </td>
                    <td>{report.dataset.count}</td>
                    <td>{percent(report.metrics.precision)}</td>
                    <td>{percent(report.metrics.recall)}</td>
                    <td className="f1-cell">{percent(report.metrics.f1)}</td>
                    <td>{percent(report.metrics.json_validity)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="empty-state">
            <Layers3 size={28} />
            <h3>No reports available</h3>
            <p>Connect the API and run the evaluation command.</p>
          </div>
        )}
      </div>
      <div className="evaluation-notes">
        <div className="panel info-card">
          <span className="eyebrow">WHAT IS MEASURED</span>
          <h3>Facts over formatting.</h3>
          <p>
            Exact field-value matches determine micro precision, recall, and F1.
            Unknown values earn no credit. Invalid schema outputs receive zero
            extraction credit. JSON and schema validity are measured separately.
          </p>
        </div>
        <div className="panel info-card">
          <span className="eyebrow">QWEN + LORA</span>
          <h3>No adapter bundled.</h3>
          <p>
            Base and fine-tuned results are published only after running the
            models. Use the CLI to evaluate both on identical data and compare
            their reports. Synthetic scores do not establish real-world
            accuracy.
          </p>
        </div>
      </div>
    </section>
  );
}
