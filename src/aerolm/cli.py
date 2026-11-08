import json
from pathlib import Path
from typing import Annotated

import typer

from aerolm.backends.rules import RulesBackend
from aerolm.data.generate import generate_dataset
from aerolm.evaluation import compare_reports, evaluate
from aerolm.settings import Settings

app = typer.Typer(no_args_is_help=True, help="AeroLM: aviation requests to structured JSON.")


@app.command()
def generate(
    output: Path = Path("data/generated"),
    seed: int = 42,
    train: int = 1000,
    validation: int = 120,
    test: int = 120,
):
    """Build independently labeled, template-held-out synthetic splits."""
    typer.echo(json.dumps(generate_dataset(output, seed, train, validation, test), indent=2))


@app.command("evaluate")
def evaluate_command(
    dataset: Annotated[Path, typer.Option(exists=True, dir_okay=False)],
    output: Path = Path("artifacts/evaluation.json"),
    backend: str = "rules",
    model_id: str = "Qwen/Qwen3-0.6B",
    revision: str = "main",
    device: str = "cpu",
    adapter: Path | None = None,
    label: str | None = None,
):
    """Measure raw outputs; write report and per-example predictions."""
    settings = Settings(
        backend=backend,
        model_id=model_id,
        model_revision=revision,
        device=device,
        adapter_path=str(adapter) if adapter else None,
    )
    if backend == "rules":
        if adapter:
            raise typer.BadParameter("An adapter requires --backend hf")
        engine = RulesBackend()
    else:
        from aerolm.backends.huggingface import HuggingFaceBackend

        engine = HuggingFaceBackend(settings)
    report = evaluate(engine, dataset, output, label)
    typer.echo(json.dumps(report["metrics"], indent=2))


@app.command("compare")
def compare(baseline: Path, tuned: Path):
    """Compare compatible measured base/adapter runs; refuse mismatched datasets."""
    typer.echo(json.dumps(compare_reports(baseline, tuned), indent=2))


@app.command("train")
def train_command(
    config: Path = Path("configs/qlora.toml"),
    data: Path = Path("data/generated"),
    output: Path = Path("artifacts/adapter"),
    max_steps: int = -1,
    resume: str | None = None,
):
    """Fine-tune on CUDA using Transformers/PEFT or Unsloth."""
    from aerolm.training import train

    result = train(config, data, output, max_steps, resume)
    typer.echo(f"Saved adapter to {output}; status={result['status']}")


if __name__ == "__main__":
    app()
