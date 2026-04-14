from __future__ import annotations

import json

import anthropic


EXTRACTION_SYSTEM_PROMPT = """You are a post-call analysis assistant. Given a phone call transcript, extract:
1. A concise summary of what was discussed and agreed to.
2. A list of proposed actions the orchestrating agent should execute.

Respond with ONLY valid JSON in this exact format:
{
  "summary": "Brief description of the call outcome",
  "proposed_actions": [
    {
      "tool": "server_name.tool_name",
      "description": "What this action does",
      "params": {"key": "value"}
    }
  ]
}

If no actions are needed, return an empty list for proposed_actions.
Do not include any text outside the JSON object."""


def build_extraction_prompt(transcript: list[dict]) -> str:
    lines = []
    for entry in transcript:
        role = entry.get("role", "unknown").capitalize()
        text = entry.get("text", "")
        lines.append(f"{role}: {text}")

    transcript_text = "\n".join(lines)

    return f"""Analyze the following phone call transcript and extract a summary and proposed_actions.

Transcript:
{transcript_text}

Extract the summary and any actions that need to be taken as a result of this call."""


def _extract_json(text: str) -> dict:
    """Parse JSON from LLM response, stripping markdown fences if present."""
    text = text.strip()
    if text.startswith("```"):
        # Remove ```json ... ``` wrapper
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines).strip()
    return json.loads(text)


async def extract_actions(
    transcript: list[dict],
    api_key: str,
    model: str = "claude-sonnet-4-6-20250514",
) -> dict:
    client = anthropic.AsyncAnthropic(api_key=api_key)

    prompt = build_extraction_prompt(transcript)

    response = await client.messages.create(
        model=model,
        max_tokens=1024,
        system=EXTRACTION_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )

    text = response.content[0].text
    return _extract_json(text)
