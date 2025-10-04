import argparse
import json
import os
from typing import Any, Optional

import deepl
from agents import Agent, Runner
from linkup import LinkupClient


def fetch_weather_context(city: str, linkup_api_key: str) -> dict[str, Any]:
    client = LinkupClient(api_key=linkup_api_key)
    # Simple search geared towards current conditions
    query = f"current weather in {city}"
    result = client.search(query=query, depth="standard", output_type="searchResults")
    return result.model_dump()


def maybe_translate(
    text: str, target_lang: Optional[str], deepl_key: Optional[str]
) -> str:
    if not target_lang:
        return text
    if not deepl_key:
        return text
    translator = deepl.DeepLClient(deepl_key)
    translated = translator.translate_text(text, target_lang=target_lang)
    return translated.text if hasattr(translated, "text") else str(translated)


def build_agent() -> Agent:
    return Agent(
        name="Weather Reporter",
        instructions=(
            "You are a helpful assistant. You will be given structured 'search_results' "
            "from Linkup and a 'city'. Summarize the current weather for that city "
            "in 3-5 sentences and include 1-2 inline citations to the most relevant sources. "
            "If 'translated_summary' is provided, output only that final translated text."
        ),
    )


async def run(city: str, target_lang: Optional[str]) -> str:
    openai_key = os.environ.get("OPENAI_API_KEY")
    linkup_key = os.environ.get("LINKUP_API_KEY")
    if not openai_key:
        raise RuntimeError("OPENAI_API_KEY is required")
    if not linkup_key:
        raise RuntimeError("LINKUP_API_KEY is required")

    # Get weather context
    search_results = fetch_weather_context(city, linkup_key)

    # Let the agent draft an English summary first
    agent = build_agent()
    english = await Runner.run(
        agent,
        input=(
            "Summarize the current weather using the provided data. "
            "Return a concise, cited answer."
        ),
        context={
            "city": city,
            "search_results": json.dumps(search_results, indent=2),
        },
    )

    summary_en = english.final_output

    # Optionally translate
    translated_summary = maybe_translate(
        text=summary_en,
        target_lang=target_lang,
        deepl_key=os.environ.get("DEEPL_AUTH_KEY"),
    )

    if target_lang and translated_summary:
        # Return translated only per agent instruction
        final = await Runner.run(
            agent,
            input=(
                "Output only the translated summary provided in context; do not add extra text."
            ),
            context={
                "translated_summary": translated_summary,
            },
        )
        return final.final_output

    return summary_en


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Weather agent using openai-agents SDK"
    )
    parser.add_argument("city", type=str, help="City name, e.g., 'Berlin'")
    parser.add_argument(
        "--target-lang",
        type=str,
        default=None,
        help="Optional DeepL target language code, e.g., 'DE', 'FR'",
    )
    args = parser.parse_args()

    import asyncio

    result = asyncio.run(run(args.city, args.target_lang))
    print(result)


if __name__ == "__main__":
    main()
