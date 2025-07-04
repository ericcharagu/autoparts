#!/usr/bin/env python3

from transformers import AutoModelForCausalLM, AutoTokenizer
from loguru import logger

translator_model_name = "winninghealth/WiNGPT-Babel-2"

translator_model = AutoModelForCausalLM.from_pretrained(
    translator_model_name, torch_dtype="auto", device_map="auto"
)
tokenizer = AutoTokenizer.from_pretrained(translator_model_name)


def translartor(target: any):

    # Example: Translation of text within a JSON object to Chinese
    prompt_json = """{
    "product_name": "High-Performance Laptop",
    "features": ["Fast Processor", "Long Battery Life", "Lightweight Design"]
    }"""

    messages = [
        {"role": "system", "content": "Translate this to Simplified Swahili Language"},
        {"role": "user", "content": target},  # Replace with the desired prompt
    ]

    text = tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True
    )
    model_inputs = tokenizer([text], return_tensors="pt").to(translator_model.device)

    generated_ids = translator_model.generate(
        **model_inputs, max_new_tokens=4096, temperature=0
    )

    generated_ids = [
        output_ids[len(input_ids) :]
        for input_ids, output_ids in zip(model_inputs.input_ids, generated_ids)
    ]

    response = tokenizer.batch_decode(generated_ids, skip_special_tokens=True)[0]
    logger.info(response)
