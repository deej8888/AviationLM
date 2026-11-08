import {
  Code2,
  ArrowUpRight,
  Plane,
  FlaskConical,
  Layers3,
  Workflow,
} from "lucide-react";

interface Props {
  mobileNav: boolean;
  section: string;
  navigate: (section: string) => void;
}

export function Sidebar({ mobileNav, section, navigate }: Props) {
  return (
    <aside className={`sidebar ${mobileNav ? "is-open" : ""}`}>
      <a href="/" className="brand">
        <span className="brand-icon">
          <Plane size={21} />
        </span>
        AeroLM<span className="brand-dot">.</span>
      </a>
      <span className="sidebar-label">OPERATIONS LAB</span>
      <nav aria-label="Main navigation">
        {[
          { id: "workspace", icon: FlaskConical, title: "Workspace" },
          { id: "evaluations", icon: Layers3, title: "Evaluations" },
          { id: "pipeline", icon: Workflow, title: "The pipeline" },
        ].map((item) => (
          <button
            key={item.id}
            onClick={() => navigate(item.id)}
            aria-current={section === item.id ? "page" : undefined}
            className={`nav-item ${section === item.id ? "active" : ""}`}
          >
            <item.icon size={18} />
            {item.title}
            {section === item.id && <span className="nav-indicator" />}
          </button>
        ))}
      </nav>
      <div className="sidebar-domains">
        <span className="sidebar-label">EXTRACTION DOMAINS</span>
        <div className="domain-current">
          <span className="tiny-dot" />
          Charter requests<span className="tag-small">V1</span>
        </div>
        <div className="domain-future">
          Maintenance <span>Planned</span>
        </div>
        <div className="domain-future">
          Parts procurement <span>Planned</span>
        </div>
        <div className="domain-future">
          Crew scheduling <span>Planned</span>
        </div>
      </div>
      <div className="sidebar-bottom">
        <div className="open-source">
          <Code2 size={17} />
          <span>Built in the open</span>
        </div>
        <p>Small models. Clearer operations.</p>
        <a href="http://localhost:8000/docs" target="_blank" rel="noreferrer">
          Explore the API <ArrowUpRight size={14} />
        </a>
        <div className="sidebar-version">
          <span>APACHE 2.0</span>
          <span>v0.1.0</span>
        </div>
      </div>
    </aside>
  );
}
