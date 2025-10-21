import torch
import asyncio
import nest_asyncio
import textarena as ta
from Agent import LLMAgent

nest_asyncio.apply()  # allow nested async loops for notebooks or hybrid runs


async def run_game(env, agent):
    """Run a single Mafia game asynchronously using the provided environment and agent."""
    await env.async_reset(num_players=1)
    done = False

    while not done:
        player_id, observation = env.get_observation()
        action = agent(observation)
        done, step_info = env.step(action=action)

        # Avoid API rate limits; adjust sleep if game hangs
        await asyncio.sleep(20)

    rewards, game_info = env.close()
    return rewards, game_info


async def main(model_name="meta-llama/Llama-3.1-8B-Instruct",
               quantize=False,
               team_hash=None,
               model_description="LLM-based Mafia Agent"):
    """Main async entry point to set up the model, environment, and run the game."""

    if team_hash is None:
        raise ValueError("❌ Please provide your team_hash as a command-line argument.")

    assert torch.cuda.is_available(), "CUDA GPU is required to run this setup."

    ngpu = torch.cuda.device_count()
    torch.backends.cuda.matmul.allow_tf32 = True

    hf_kwargs = {
        "torch_dtype": torch.float16,
        "max_memory": {0: "14GiB", 1: "14GiB"} if ngpu >= 2 else {0: "14GiB"},
        "low_cpu_mem_usage": True,
        "attn_implementation": "sdpa"
    }

    # Initialize your agent
    agent = LLMAgent(model_name=model_name, hf_kwargs=hf_kwargs, quantize=quantize)
    print(f"✅ Agent initialized with model: {model_name}")

    # Create TextArena environment
    env = ta.make_mgc_online(
        track="Social Detection",
        model_name=model_name,
        model_description=model_description,
        team_hash=team_hash,
        agent=agent,
        small_category=True,
    )

    print("🚀 Starting game ...")
    rewards, game_info = await run_game(env, agent)

    print(f"\n✅ Game completed!")
    print(f"Rewards: {rewards}")
    print(f"Game info: {game_info}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run a Mafia LLM agent in TextArena.")
    parser.add_argument("--model_name", type=str, default="meta-llama/Llama-3.1-8B-Instruct")
    parser.add_argument("--quantize", action="store_true", help="Enable 4-bit quantization for the model.")
    parser.add_argument("--team_hash", type=str, required=True, help="Your TextArena team hash.")
    parser.add_argument("--model_description", type=str, default="LLM-based Mafia Agent")
    args = parser.parse_args()

    asyncio.run(main(
        model_name=args.model_name,
        quantize=args.quantize,
        team_hash=args.team_hash,
        model_description=args.model_description
    ))
