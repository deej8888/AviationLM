"""Optional ML-only trainer variants. Imported after any Unsloth patches."""

from transformers import Trainer
from trl import SFTTrainer


class LossOnlySFTTrainer(SFTTrainer):
    """Keep TRL's data/masking pipeline, omit expensive full-vocabulary token metrics.

    TRL 0.24 delegates the objective to Transformers Trainer, then computes entropy
    and token accuracy over every prompt/completion position. On CPU those optional
    statistics are costly. This delegates the identical loss calculation directly.
    Extraction quality is still measured by the separate held-out evaluator.
    """

    def compute_loss(self, model, inputs, return_outputs=False, num_items_in_batch=None):
        inputs["use_cache"] = False
        return Trainer.compute_loss(
            self,
            model,
            inputs,
            return_outputs=return_outputs,
            num_items_in_batch=num_items_in_batch,
        )
