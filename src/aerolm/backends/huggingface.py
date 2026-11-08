"""Optional local Qwen backend; imported only when explicitly selected."""

import json
import hashlib
from pathlib import Path

from aerolm.core import DomainSpec
from aerolm.settings import Settings


class InputTooLongError(ValueError):
    pass


class HuggingFaceBackend:
    name = "hf"

    def __init__(self, settings: Settings):
        try:
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer
        except ImportError as error:
            raise RuntimeError("Install ML dependencies: uv sync --extra ml") from error
        self.model_id = settings.model_id
        self.adapter_path = settings.adapter_path or None
        self.adapter_manifest = None
        self.settings = settings
        self.torch = torch
        device = settings.device
        if device == "auto":
            device = "cuda" if torch.cuda.is_available() else "cpu"
        if device == "cuda" and not torch.cuda.is_available():
            raise RuntimeError("CUDA requested but unavailable")
        revision = settings.model_revision
        if self.adapter_path:
            manifest_path = Path(self.adapter_path) / "run_manifest.json"
            if not manifest_path.is_file():
                raise ValueError("Adapter requires its AeroLM run_manifest.json")
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if manifest.get("status") != "completed":
                raise ValueError("Adapter training run has not completed")
            self.adapter_manifest = manifest
            if manifest["model_id"] != self.model_id:
                raise ValueError("Adapter and base model IDs do not match")
            revision = manifest["model_revision"]
            if settings.model_revision != "main" and settings.model_revision != revision:
                raise ValueError("Configured revision differs from adapter base revision")
        self.tokenizer = AutoTokenizer.from_pretrained(
            self.model_id,
            revision=revision,
            trust_remote_code=False,
        )
        self.model = AutoModelForCausalLM.from_pretrained(
            self.model_id,
            revision=revision,
            trust_remote_code=False,
            torch_dtype=torch.float32 if device == "cpu" else torch.float16,
        ).to(device)
        if self.adapter_path:
            from peft import PeftModel

            self.model = PeftModel.from_pretrained(self.model, self.adapter_path)
        self.model.eval()
        self.resolved_revision = getattr(self.model.config, "_commit_hash", revision)

    def generate(self, text: str, domain: DomainSpec) -> str:
        if self.adapter_manifest:
            prompt_hash = hashlib.sha256(
                json.dumps(domain.messages(""), sort_keys=True).encode()
            ).hexdigest()
            if (
                self.adapter_manifest.get("domain") != domain.name
                or self.adapter_manifest.get("prompt_sha256") != prompt_hash
            ):
                raise ValueError("Adapter domain or schema/prompt differs from the training run")
        prompt = self.tokenizer.apply_chat_template(
            domain.messages(text),
            tokenize=False,
            add_generation_prompt=True,
            enable_thinking=False,
        )
        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.model.device)
        if inputs.input_ids.shape[-1] > self.settings.max_input_tokens:
            raise InputTooLongError(
                "Input including schema exceeds token limit; shorten the request"
            )
        with self.torch.inference_mode():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=self.settings.max_new_tokens,
                do_sample=False,
                pad_token_id=self.tokenizer.eos_token_id,
            )
        return self.tokenizer.decode(
            outputs[0, inputs.input_ids.shape[-1] :],
            skip_special_tokens=True,
        ).strip()
