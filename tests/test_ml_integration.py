"""A real tiny random Qwen + LoRA optimizer step. No model or dataset download."""

import pytest

torch = pytest.importorskip("torch")
transformers = pytest.importorskip("transformers")
pytest.importorskip("trl")
pytest.importorskip("peft")


@pytest.mark.ml
def test_real_completion_masking_and_lora_update(tmp_path):
    from datasets import Dataset
    from peft import LoraConfig, PeftModel
    from tokenizers import Tokenizer, models, pre_tokenizers, trainers
    from transformers import PreTrainedTokenizerFast, Qwen3Config, Qwen3ForCausalLM
    from trl import SFTConfig, SFTTrainer

    torch.set_num_threads(2)
    tokenizer_core = Tokenizer(models.WordLevel(unk_token="[UNK]"))
    tokenizer_core.pre_tokenizer = pre_tokenizers.Whitespace()
    tokenizer_core.train_from_iterator(
        ['Extract charter TEB to MIA 6 pax . { "passengers" : 6 }'],
        trainers.WordLevelTrainer(special_tokens=["[UNK]", "[PAD]", "[EOS]"]),
    )
    tokenizer = PreTrainedTokenizerFast(
        tokenizer_object=tokenizer_core,
        unk_token="[UNK]",
        pad_token="[PAD]",
        eos_token="[EOS]",
    )
    model_config = Qwen3Config(
        vocab_size=len(tokenizer),
        hidden_size=32,
        intermediate_size=64,
        num_hidden_layers=1,
        num_attention_heads=2,
        num_key_value_heads=1,
        head_dim=16,
        max_position_embeddings=128,
        pad_token_id=tokenizer.pad_token_id,
        eos_token_id=tokenizer.eos_token_id,
    )
    model = Qwen3ForCausalLM(model_config)
    dataset = Dataset.from_list(
        [{"prompt": "Extract charter TEB to MIA 6 pax.", "completion": '{"passengers":6}[EOS]'}]
    )
    trainer = SFTTrainer(
        model=model,
        processing_class=tokenizer,
        train_dataset=dataset,
        peft_config=LoraConfig(
            r=2, lora_alpha=4, target_modules=["q_proj", "v_proj"], task_type="CAUSAL_LM"
        ),
        args=SFTConfig(
            output_dir=str(tmp_path / "run"),
            use_cpu=True,
            max_steps=1,
            max_length=128,
            per_device_train_batch_size=1,
            learning_rate=0.01,
            completion_only_loss=True,
            packing=False,
            report_to="none",
            save_strategy="no",
            bf16=False,
            fp16=False,
            gradient_checkpointing=False,
        ),
    )
    batch = next(iter(trainer.get_train_dataloader()))
    labels = batch["labels"][0]
    assert (labels == -100).any() and (labels != -100).any()
    assert labels[0].item() == -100  # prompt tokens do not contribute to loss
    before = {
        key: value.detach().clone()
        for key, value in trainer.model.named_parameters()
        if "lora_" in key
    }
    result = trainer.train()
    assert result.global_step == 1 and result.training_loss > 0
    assert any(
        not torch.equal(before[key], value)
        for key, value in trainer.model.named_parameters()
        if key in before
    )
    trainer.save_model(str(tmp_path / "adapter"))
    reloaded = PeftModel.from_pretrained(Qwen3ForCausalLM(model_config), tmp_path / "adapter")
    assert reloaded.peft_config["default"].r == 2
