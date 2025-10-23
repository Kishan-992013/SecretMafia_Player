# SecretMafia_Player
Code repository for NeurIPS 2025 Hackathon Social Deduction Track on Efficient Model Division

## Steps to Load Model for Submission
## 1️⃣ Clone the repository

git clone -b main https://github.com/Kishan-992013/SecretMafia_Player.git


## 2️⃣ Install dependencies

pip install -r requirements.txt


## 3️⃣ Export your Hugging Face token (Optional) - Can pass the token as an argument while loading the model

export HUGGINGFACE_TOKEN=<your_huggingface_token>

or 

import os

os.environ["HUGGINGFACE_TOKEN"] = "<your_huggingface_token>"

## 4️⃣ Import and Load the Agent

**from load_player import Load_Mafia_Player**

**agent = Load_Mafia_Player(hf_token)**

✅ The base model is meta-llama/Llama-3.1-8B-Instruct by default.

The loader supports quantization at half-precision and is set according to kaggle gpu's - can change hf_kwargs in the loader for any issues


## 5️⃣ Make a Submission

Once the agent is loaded, initialize the game submission using

MODEL_NAME = "OrderOfPhoenix/jarvis_v6"

MODEL_DESCRIPTION = "This small agent is for Track 1 - Social Detection (SecretMafia-v0)."

team_hash = '<our_hash>'

env = ta.make_mgc_online(
    track="Social Detection",
    model_name=MODEL_NAME,
    model_description=MODEL_DESCRIPTION,
    team_hash=team_hash,
    agent=agent,
    small_category=True,
)
