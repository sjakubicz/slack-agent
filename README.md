# Slack Agent

A Slack bot running over Socket Mode (`SLACK_APP_TOKEN` opens the websocket and keeps it open) that answers questions about movie reviews using a small local LLM via Ollama. In production the model could be served by an external provider instead.

The agent checks its own output: after it posts to a channel it reads the message back, compares the numbers in it with the dataset, and deletes the post and retries if they are wrong.

### How it works in Slack
- It replies to `@mentions` in channels (in a thread) and to direct messages.
- It first posts a `Thinking...` placeholder, updates it with `Calling <tool>...` on every tool call, and finally replaces it with the answer, the list of tools used and the last self-check result.

## Setup

### Requirements
- Python 3.15 and [uv](https://docs.astral.sh/uv/)
- [Ollama](https://ollama.com/) running locally. The model from `config.json` is pulled automatically at startup if it is missing.
- A Slack app created from `manifest.json` (see [Slack app setup](#slack-app-setup) below)

### Quick start
1. Copy `.env.example` to `.env` and fill in the bot token (`xoxb-...`) and the app-level token (`xapp-...`).
2. Install dependencies:
   ```bash
   uv sync
   ```
3. Run the bot:
   ```bash
   uv run slack-agent
   ```
   `uv run python main.py` works too.

The review dataset is downloaded from Hugging Face the first time it is needed.

## Tools

The model has two tools:

1. `analyze_reviews(keyword: str) -> str` - searches about 1000 movie reviews from Hugging Face and returns how many mention the word, what percentage of them are positive, and a few example snippets.
2. `post_to_channel(channel: str, text: str) -> str` - posts a message to a Slack channel by ID (the bot has to be a member of it). It only posts; checking that the post is right is done by the self-check below.

## Self-check

The agent is a LangGraph graph: `model -> tools -> check -> model`. The run ends when the model answers without calling a tool.

After every tool step the `check` node calls `PostChecker` from `verify.py`. If the model just called `post_to_channel`, it:

1. Reads the recent channel history and looks for the posted message. If it is not there, the check fails.
2. Decides how to verify the message (`check_claims` in `claims.py`), based on where its numbers could come from:
   - Text that appears in the user request was dictated by the user and passes as is. The agent is not asked to fact check it.
   - A message with no review statistics is a plain post and passes once step 1 confirms it is in the channel.
   - A message that states review statistics without any `analyze_reviews` call is made up and fails.
   - A message about a word the agent analyzed is a report and is checked against the dataset (`find_problem`). It fails if:
     - the keyword (the most recent analyzed word the message mentions) is not a word from the user request,
     - no reviews match the keyword,
     - the message does not mention the keyword,
     - it does not state the correct positive percentage, or states a percentage that is neither the positive nor the negative share,
     - it does not state the review count (matched as a whole number, not a substring).
3. On failure, deletes the bad message and sends the reason back to the model so it can post a corrected one. After `max_failed_checks` failed checks the run ends with a "giving up" message instead of going back to the model.

The result is added to the Slack reply as a `Self-check:` line (`:white_check_mark:` passed, `:x:` failed).

Limitations: the check uses the same dataset function as the tool, so it catches the model misquoting, inventing or padding numbers, not bugs in the analysis itself. It also does not understand wording. It cannot tell whether a generic word from the request (like "reviews") is what the user meant, and a message saying "63% negative" for a 63% positive keyword would still pass.

## Configuration

Everything that is easy to change lives in `src/slack_agent/config.json`. It is loaded into pydantic models in `config.py`, so the app fails at startup if a key is missing, misspelled (unknown keys are rejected) or has a wrong type or value. In code the values are read with dots, for example `config.dataset.split`.

| Key | What it is |
| :--- | :--- |
| `model`, `temperature`, `reasoning` | Ollama model settings |
| `max_failed_checks` | How many failed self-checks before the run gives up |
| `dataset` | Hugging Face dataset name, split, text and label fields, number and length of example snippets |
| `slack` | Names of the env variables with the bot and app tokens (the first one that is set is used) and how many channel messages the self-check reads |
| `messages` | Texts shown in Slack replies: placeholders, error, tools used and self-check labels, the giving up message |
| `checks` | Self-check feedback: passed, failed and the reasons a report can fail. Shown in the `Self-check:` line and sent back to the model |
| `markers` | Emoji shortcodes that start self-check feedback (`:white_check_mark:`, `:x:`), also used to count failed checks |

Not in `config.json`: the user message, the tool docstrings (they are the instructions the model sees) and the texts the tools return to the model.

Slack tokens come from environment variables, loaded from `.env`.

## Project structure

- `main.py` - calls `slack_agent.main()`, so the bot can be started with `python main.py`.
- `manifest.json` - Slack app manifest: bot user, scopes, events and Socket Mode.
- `.env.example` - template for `.env` with the Slack token variables.
- `pyproject.toml`, `uv.lock` - project metadata, dependencies and the `slack-agent` command.
- `ruff.toml` - lint and format settings.
- `src/slack_agent/`
  - `__init__.py` - `main()`: loads `.env` and the config, builds the dataset, tools, self-check and agent, and starts the bot.
  - `config.json` - all configurable values (see [Configuration](#configuration)).
  - `config.py` - pydantic models for `config.json` with validation (for example `messages.calling` must contain `{tool}` and the two markers must differ).
  - `bot.py` - `SlackBot`: handles mentions and DMs, posts the placeholder, updates it while tools run and formats the final reply.
  - `agent.py` - `Agent`: builds the LangGraph graph (`model`, `tools`, `check`) around `ChatOllama` and streams a run into an `AgentResult`.
  - `result.py` - `AgentResult`: collects the final answer, the tool calls and the self-check messages.
  - `checking.py` - `CheckNode`: graph node that runs the checker after tool calls, counts failed checks and stops after `max_failed_checks`.
  - `verify.py` - `PostChecker`: finds the last `post_to_channel` call, confirms the message is in the channel, verifies its claims and deletes it if they are wrong.
  - `claims.py` - decides how a posted message is verified and compares its numbers with the dataset (`check_claims`, `find_problem`).
  - `tools.py` - the `analyze_reviews` and `post_to_channel` tools.
  - `dataset.py` - `Reviews`: loads the Hugging Face dataset on first use, finds reviews mentioning a word and computes the count and positive share.
  - `utils.py` - small helpers: first set env variable, message text, Markdown bold to Slack bold, pulling the Ollama model if missing.

## Slack app setup

I created the simplest app possible in my test workspace and replaced its manifest with `manifest.json` from the repository root. To do the same:

1. In the Slack API dashboard create a new app from a manifest and paste the contents of `manifest.json`.
2. Socket Mode is already enabled by the manifest. Generate an app-level token (`xapp-...`) with the `connections:write` scope.
3. Install the app to the workspace and copy the bot token (`xoxb-...`). The manifest requests these bot scopes:
   - `app_mentions:read` - receiving mentions
   - `im:history` - receiving direct messages
   - `chat:write` - posting, updating and deleting its own messages
   - `channels:history`, `groups:history` - reading the posted message back in public and private channels

## Manual tests in Slack

Replace `C0CLEA0G4JC` with the ID of a channel the bot is a member of.

- `@TestAgent how do reviews mentioning "family" skew?`
  The reply should contain a count and a percentage, plus `Tools used: analyze_reviews`.
- `@TestAgent how do reviews mentioning "family" skew? Post it to C0CLEA0G4JC`
  A new message should appear in the channel, the tools line should list `analyze_reviews` and `post_to_channel`, and the reply should end with `Self-check:` and a check mark.
- `@TestAgent post exactly this to C0CLEA0G4JC: family reviews are 99% positive`
  The text comes from the request, so it should stay in the channel exactly as written, with a check mark. The agent posts what the user asked and does not fact check it.
- `@TestAgent write one line about how reviews mentioning "war" are and post it to C0CLEA0G4JC`
  The agent should call `analyze_reviews` and post its numbers (check mark). If the model makes up numbers without analyzing, the message should get deleted with a cross.
- `@TestAgent post exactly this to C0CLEA0G4JC: lunch is at 12`
  A plain post, so it should stay in the channel with a check mark and "the message is in the channel and matches the request or the dataset".
- `@TestAgent reviews mentioning "zzzzqq"`
  The reply should say that no reviews mention it.
