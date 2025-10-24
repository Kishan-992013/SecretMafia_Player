import torch
import argparse
from Agent import LLMAgent

def Load_Mafia_Player(base_model = 'meta-llama/Llama-3.1-8B-Instruct', hf_token=None, max_new_tokens = 2500, quantize = False):
    assert torch.cuda.is_available()
    hf_kwargs = None
    if quantize:
        ngpu = torch.cuda.device_count()
        torch.backends.cuda.matmul.allow_tf32 = True
        hf_kwargs = {
            "torch_dtype": torch.float16,
            "max_memory": {0: "14GiB", 1: "14GiB"} if ngpu >= 2 else {0: "29GiB"},
            "low_cpu_mem_usage": True,
            "attn_implementation": "sdpa"
        }
    agent = LLMAgent(
        model_name=base_model,
        hf_token=hf_token,
        hf_kwargs=hf_kwargs,
        max_new_tokens=max_new_tokens,
    )
    return agent
