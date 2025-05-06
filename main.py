import json
import asyncio
from datetime import datetime, timedelta, timezone
from typing import List, Dict

from apify import Actor
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from openai import OpenAI
import tiktoken

async def main() -> None:
    # initialize Apify SDK context
    async with Actor():
        # read actor input
        cfg = await Actor.get_input()
        DAYS                    = cfg["summaryDays"]
        MAX_CHUNK_TOKENS        = cfg["maxChunkTokens"]
        SLACK_TOKEN_FETCH       = cfg["slackTokenFetch"]
        SLACK_CHANNEL_FETCH     = cfg["slackChannelFetch"]
        SLACK_TOKEN_POST        = cfg["slackTokenPost"]
        SLACK_CHANNEL_POST      = cfg["slackChannelPost"]
        OPENAI_API_KEY          = cfg["openaiApiKey"]
        OPENAI_MODEL            = cfg["openaiModel"]
        SUMMARY_PROMPT_TEMPLATE = cfg["summaryPromptTemplate"].strip()

        # compute time window
        history_start = datetime.now(tz=timezone.utc) - timedelta(days=DAYS)
        HISTORY_LIMIT = f"{history_start.timestamp():.6f}"

        # init OpenAI client
        openai_client = OpenAI(api_key=OPENAI_API_KEY)

        def get_prompt_metadata(days: int) -> Dict[str, str]:
            formatting_instruction = (
                "You are a helpful assistant summarizing Slack messages. Format message for Slack following these rules:\n"
                "- Use single asterisks for bold (e.g. *Header*), not double asterisks.\n"
                "- Use bold sparingly; emphasize only key points.\n"
                "- Use `backticks` for technical terms or names.\n"
                "- Use bullets (•) for list items.\n"
                "- Do NOT include code fences (```), headings like # or markdown indicators.\n"
                "- Don't write anything else, don't be creative. be minimalistic.\n"
            )
            return {
                "user_intent": SUMMARY_PROMPT_TEMPLATE,
                "formatting_instruction": formatting_instruction,
                "days": str(days),
            }

        def fetch_messages() -> List[Dict]:
            """Fetch all messages since HISTORY_LIMIT, with pagination."""
            client = WebClient(token=SLACK_TOKEN_FETCH)
            all_msgs = []
            cursor = None
            while True:
                try:
                    params = {
                        "channel": SLACK_CHANNEL_FETCH,
                        "oldest": HISTORY_LIMIT,
                        "inclusive": True,
                        "limit": 500,
                    }
                    if cursor:
                        params["cursor"] = cursor
                    resp = client.conversations_history(**params)
                    batch = resp.get("messages", [])
                    all_msgs.extend(batch)
                    cursor = resp.get("response_metadata", {}).get("next_cursor")
                    if not cursor:
                        break
                except SlackApiError as e:
                    Actor.log.error(f"Error fetching messages: {e.response['error']}")
                    break
            Actor.log.info(f"Fetched {len(all_msgs)} messages since {history_start.isoformat()}")
            return all_msgs

        def filter_messages(messages: List[Dict]) -> List[Dict]:
            out = []
            for msg in messages:
                if msg.get("type") != "message":
                    continue
                base = {
                    "user":      msg.get("user") or msg.get("bot_id"),
                    "username":  msg.get("bot_profile", {}).get("name"),
                    "thread_ts": msg.get("thread_ts"),
                    "subtype":   msg.get("subtype", "message"),
                }
                # attachments
                for att in msg.get("attachments", []):
                    entry = base.copy()
                    entry.update({
                        "attachment_title": att.get("title"),
                        "text":             att.get("text", "").strip(),
                        "fallback":         att.get("fallback")
                    })
                    out.append(entry)
                # fallback to plain text
                if not msg.get("attachments"):
                    entry = base.copy()
                    entry["text"] = msg.get("text", "").strip()
                    out.append(entry)
            return out

        def chunk_messages(texts: List[str], max_tokens: int) -> List[List[str]]:
            encoder = tiktoken.encoding_for_model(OPENAI_MODEL)
            chunks, current, current_tokens = [], [], 0
            for txt in texts:
                tok_count = len(encoder.encode(txt))
                if current and current_tokens + tok_count > max_tokens:
                    chunks.append(current)
                    current, current_tokens = [], 0
                current.append(txt)
                current_tokens += tok_count
            if current:
                chunks.append(current)
            return chunks

        def summarize_chunks(chunks: List[List[str]], meta: Dict[str, str]) -> List[str]:
            summaries = []
            for i, chunk in enumerate(chunks, start=1):
                block = json.dumps(chunk, indent=2)
                prompt = (
                    f"{meta['user_intent']}\n\n"
                    f"{meta['formatting_instruction']}\n"
                    f"Data chunk {i}/{len(chunks)} (last {meta['days']} day(s)):\n"
                    f"{block}"
                )
                resp = openai_client.chat.completions.create(
                    model=OPENAI_MODEL,
                    messages=[{"role": "user", "content": prompt}],
                )
                summaries.append(resp.choices[0].message.content.strip())
            return summaries

        def summarize_messages(messages: List[Dict]) -> str:
            texts = [m["text"] for m in messages if m.get("text")]
            chunks = chunk_messages(texts, MAX_CHUNK_TOKENS)
            Actor.log.info(f"Split into {len(chunks)} chunk(s)")
            meta = get_prompt_metadata(DAYS)
            mini_summaries = summarize_chunks(chunks, meta)
            combined = "\n\n".join(mini_summaries)
            final_prompt = (
                f"{meta['user_intent']}\n\n"
                f"{meta['formatting_instruction']}\n"
                f"Combine these mini-summaries into one concise summary (last {DAYS} day(s)):\n\n"
                f"{combined}"
            )
            resp = openai_client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[{"role": "user", "content": final_prompt}],
            )
            return resp.choices[0].message.content.strip()

        def send_slack_message(message: str):
            try:
                WebClient(token=SLACK_TOKEN_POST).chat_postMessage(
                    channel=SLACK_CHANNEL_POST,
                    text=message
                )
            except SlackApiError as e:
                Actor.log.error(f"Error sending message: {e.response['error']}")

        # execute workflow
        raw = fetch_messages()
        if not raw:
            Actor.log.info("No messages fetched, exiting.")
            return
        filtered = filter_messages(raw)
        summary = summarize_messages(filtered)
        Actor.log.info("Summary generated, sending to Slack...")
        send_slack_message(summary)
        Actor.log.info("Done.")

if __name__ == "__main__":
    asyncio.run(main())
