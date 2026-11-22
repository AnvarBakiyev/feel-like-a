# Results in one table

Extella is an extensible software environment that connects AI models, software tools and devices into working systems. Its core lets you configure and change how each module runs, from document processing to controlling sensors and robots.

Each game gives three players the same task: Qwen 3.5 9B alone, the same Qwen 3.5 9B with Extella, and Claude Opus without Extella.

**In one line:** Qwen 3.5 9B with Extella succeeded in 96% of tasks, Claude Opus in 77%, Qwen 3.5 9B alone in 18%. A task cost Extella a fraction of a cent, and Claude Opus 1 to 452 cents.

| Game | Success means | Qwen alone | Qwen + Extella | Claude Opus | Cost per task: Qwen alone / Qwen + Extella / Opus |
|---|---|---|---|---|---|
| [Café](episodes/cafe/) | the month ends in profit | 0/27 | 22/27 | 10/11 (Opus 5) | $0.017 / $0.006 / $4.52 |
| [Zoo](episodes/zoo/) | the month ends in profit | 15/27 | 27/27 | 27/27 (Opus 5.5) | $0.033 / $0.006 / $1.58 |
| [Drone courier](episodes/drone/) | no forced landing, no lost drone | 4/30 | 30/30 | 28/30 (Opus 5) | $0.0005 / $0.0007 / at least $0.011 |
| [Train driver](episodes/train/) | the train reaches the end of the line | 7/30 | 30/30 | 0/30 (Opus 5) | $0.0003 / $0.0003 / at least $0.015 |
| Humanoid robot | 100 m in under 15 s | 0/64 | 64/64 | 64/64 | under $0.002 / $0.0025 / not measured |
| **Average over games** | | **18%** | **96%** | **77%** | |

## Check it yourself

```bash
python3 results/success.py          # the success counts above, from the recorded runs
python3 episodes/cafe/verify.py     # every recorded score recomputed from its decision log, no keys, no network
python3 episodes/zoo/verify.py
python3 episodes/drone/verify.py
python3 episodes/train/verify.py
```

The Extella experts are not in this repository. Each game plays with its own agent in the Extella market ("Extella Cafe Month", "Extella Zoo Month", "Extella Drone Courier", "Extella Train Driver"). `episodes/<game>/extella/experts.lock.json` names the agent and the sha of every expert version the runs used. Install the agent as a new agent, set `EXTELLA_TOKEN_FILE` and `EXTELLA_AGENT`, and `verify.py --extella` also checks that the expert turns each recorded model answer into exactly the recorded decision.

The humanoid robot has no episode here: its training code is closed. Its agent, "Extella Humanoid Coach", is in the Extella market; the row above is not recomputed by this repository.

## Where the costs come from

- **Qwen 3.5 9B** at OpenRouter prices: $0.17 per million input tokens and $0.25 per million output tokens. On your own computer it costs nothing. In the café and zoo the tokens are recorded in the run files. In the drone courier and train driver they were counted on 21.11.2026 from the recorded prompts and answers with the Qwen tokenizer; the number of model calls matched the records.
- **Claude Opus in the café and zoo** from the usage Anthropic returned for every request: [results/opus_tokens.json](results/opus_tokens.json), one row per month. Opus 5 at $5 / $25 per million, Opus 5.5 at $4 / $20, cache writes ×1.25, cache reads ×0.1 (Opus 5) and $0.20 per million (Opus 5.5). Total $49.69 for 11 café months and $42.65 for 27 zoo months. Opus played as an agent in Claude Code chat, so the count includes the chat agent's own system prompt; a bare API call with only the game text would cost less, and that run was not made.
- **Claude Opus in the drone courier and train driver** is a lower bound: only the briefing in and the plan out, counted with the Qwen tokenizer. There Opus wrote one plan for the whole shift or trip. At least $0.34 for 30 shifts and $0.46 for 30 trips.

## Read it carefully

- In the drone courier and the robot, Opus and Extella are level on success. Extella's gain there is the zero forced landings and the cost (drone), and a small model reaching the level of Opus (robot).
- In the café, Opus played 11 months; the other players played 27.
- "Average over games" is the plain average of five percentages. The tasks differ; this is not one common test set.
