import torch
import argparse
from Agent import LLMAgent

def load_agent():
    parser = argparse.ArgumentParser(description="Initialize the Mafia Agent for TextArena.")
    parser.add_argument("--base_model", type=str, default="meta-llama/Llama-3.1-8B-Instruct", help="Base model to load.")
    parser.add_argument("--hf_token", type=str, required=False, help="Hugging Face token for gated model access.")
    parser.add_argument("--max_new_tokens", type=int, default=2500, help="Max new tokens for generation.")
    parser.add_argument("--quantize", action="store_true", help="Enable quantization if required.")
    args = parser.parse_args()

    assert torch.cuda.is_available()
    hf_kwargs = None
    if args.quantize:
        ngpu = torch.cuda.device_count()
        torch.backends.cuda.matmul.allow_tf32 = True
        hf_kwargs = {
            "torch_dtype": torch.float16,
            "max_memory": {0: "14GiB", 1: "14GiB"} if ngpu >= 2 else {0: "29GiB"},
            "low_cpu_mem_usage": True,
            "attn_implementation": "sdpa"
        }
    agent = LLMAgent(
        model_name=args.base_model,
        hf_token=args.hf_token,
        hf_kwargs=hf_kwargs,
        max_new_tokens=args.max_new_tokens,
    )
    return agent

if __name__ == "__main__":
    agent = load_agent()
