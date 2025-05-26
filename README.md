# Slack Summary Reporter

A simple Python actor that fetches recent Slack messages, summarizes them via OpenAI, and posts the summary back to Slack—configured entirely via per-run JSON input instead of environment variables.

---

## 🛠️ Prerequisites

- Python 3.12+
- Docker (optional, for containerized runs)
- An Apify account and the [Apify CLI](https://docs.apify.com/platform/apify-cli) installed (for local development)
- A Slack app with OAuth scopes:
  - `conversations.history` (to read messages)
  - `chat:write` (to post messages)
- An OpenAI API key

---

## ⚙️ Actor Input

All configuration now comes via the actor’s **INPUT schema** (`.actor/actor.json`). Users supply a JSON object at run-time—either in the Apify Console form, as a Task, or via `apify run --input input.json`.

```jsonc
{
  "summaryDays": 1,                      // How many days back to fetch
  "slackTokenFetch": "xoxb-…",           // [secret] token with history scope
  "slackChannelFetch": "C0123456789",    // Channel ID to read from
  "slackTokenPost": "xoxb-…",            // [secret] token with chat:write scope
  "slackChannelPost": "C9876543210",     // Channel ID to post summary
  "openaiApiKey": "sk-…",                // [secret] your OpenAI API key
  "openaiModel": "gpt-4o-mini"           // Which OpenAI model to use
}
```

> **Note:** Fields marked secret (`slackTokenFetch`, `slackTokenPost`, `openaiApiKey`) are defined with `isSecret: true` in the actor schema, so they’re encrypted in the Console and API.

---

## 🚀 Running Locally

1. **Push your actor** (includes `.actor/actor.json`) to Apify:
   ```bash
   apify push
   ```
2. **Create** a local `input.json` (see example above).
3. **Run** with the Apify CLI, pointing to your input file:
   ```bash
   apify run --input input.json
   ```

This will execute `main.py` under the Apify runtime, loading your JSON as `await Actor.get_input()`.

---

## 🐳 Docker Usage

To build and run the container locally, mount your `input.json` into the Apify default key–value store:

1. **Build** the image:
   ```bash
   docker build -t slack-summary-reporter .
   ```
2. **Run** with volume mounts for input storage:
   ```bash
   # Create a folder for the default store
   mkdir -p apify_storage/key_value_stores/default
   # Copy your input.json there
   cp input.json apify_storage/key_value_stores/default/INPUT.json
   # Run the container
   docker run --rm      -v "$(pwd)/apify_storage":/home/apify_user/apify_storage      slack-summary-reporter
   ```

The actor will read `/home/apify_user/apify_storage/key_value_stores/default/INPUT.json` automatically.

---

## 🔧 Customization

- **`summaryDays`**: Adjust how many days of history to include.
- **`summaryPromptTemplate`** (optional): Override the default summarization prompt.
- **`maxChunkTokens`** (optional): Change the OpenAI-chunk-size limit.

All of these are additional properties you can add to your `.actor/actor.json` schema and supply in the same input JSON.

---

## 📖 License

MIT © Marko Kubrachenko
