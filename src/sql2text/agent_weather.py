import argparse
import json
import os
from typing import Any

import deepl
from linkup import LinkupClient
from openai import OpenAI


def create_tools_schema() -> list[dict[str, Any]]:
    """Define tools:
    - search_web(query: string): use Linkup to search the web
    - translate_text(text: string, target_lang: string): translate via DeepL
    - find_local_sources_by_place(place: string, native_language: string, top_n?: integer)
    - search_local_news(place: string, sites?: string[], native_language: string, since_days?: integer)
    """
    return [
        {
            "type": "function",
            "name": "search_web",
            "description": (
                "Search the web for current information. Returns comprehensive content from relevant sources."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query",
                    }
                },
                "required": ["query"],
            },
        },
        {
            "type": "function",
            "name": "translate_text",
            "description": "Translate text to a target language using DeepL",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "The text to translate",
                    },
                    "target_lang": {
                        "type": "string",
                        "description": "Target language code, e.g., 'DE', 'FR', 'ES'",
                    },
                    "source_lang": {
                        "type": "string",
                        "description": "Optional source language code, e.g., 'EN'",
                    },
                    "formality": {
                        "type": "string",
                        "description": "Optional formality level: 'default'|'more'|'less'",
                    },
                },
                "required": ["text", "target_lang"],
            },
        },
        {
            "type": "function",
            "name": "find_local_sources_by_place",
            "description": (
                "Discover local news websites for a given place, REQUIRING sources in the place's native language."
                " You must determine the native language (e.g., Tamil for Chennai, Marathi for Mumbai, Hindi for Delhi)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "place": {
                        "type": "string",
                        "description": "City or region name (optionally include country)",
                    },
                    "native_language": {
                        "type": "string",
                        "description": "Native language of the area, e.g., 'Spanish', 'German' (REQUIRED)",
                    },
                    "top_n": {
                        "type": "integer",
                        "description": "Maximum number of sites to return (default 10)",
                    },
                },
                "required": ["place", "native_language"],
            },
        },
        {
            "type": "function",
            "name": "search_local_news",
            "description": (
                "Search recent local news for a place, REQUIRING sources in the specified native language."
                " Use the same native language that was used in find_local_sources_by_place."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "place": {
                        "type": "string",
                        "description": "City or region name (optionally include country)",
                    },
                    "sites": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional list of site domains/urls to prioritize",
                    },
                    "native_language": {
                        "type": "string",
                        "description": "Native language of the area, e.g., 'Spanish', 'German' (REQUIRED)",
                    },
                    "since_days": {
                        "type": "integer",
                        "description": "Recency window in days (default 7)",
                    },
                },
                "required": ["place", "native_language"],
            },
        },
    ]


def run_weather_agent(city: str) -> str:
    """Use OpenAI tool calling + Linkup search to get current weather for a city.

    Requires env vars:
      - OPENAI_API_KEY
      - LINKUP_API_KEY
    """
    openai_api_key = os.environ.get("OPENAI_API_KEY")
    linkup_api_key = os.environ.get("LINKUP_API_KEY")
    if not openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is required")
    if not linkup_api_key:
        raise RuntimeError("LINKUP_API_KEY is required")

    openai_client = OpenAI(api_key=openai_api_key)
    linkup_client = LinkupClient(api_key=linkup_api_key)
    deepl_key = os.environ.get("DEEPL_AUTH_KEY")
    deepl_client = deepl.DeepLClient(deepl_key) if deepl_key else None

    tools = create_tools_schema()

    # Seed conversation: include guidance for prioritizing native-language local sources when asked for local news
    input_list: list[dict[str, Any]] = [
        {
            "role": "system",
            "content": (
                "When the user asks for local news, you MUST determine the native language of the place and use it."
                " For example: Chennai/Tamil Nadu = Tamil, Mumbai/Maharashtra = Marathi, Delhi = Hindi, etc."
                " First discover local news websites for the place REQUIRING sources in the area's native language"
                " (use find_local_sources_by_place with the correct native language),"
                " then search those sources for recent updates (use search_local_news with the same language)."
                " Always cite sources. You MUST always specify the native language when calling these functions."
            ),
        },
        {
            "role": "user",
            "content": f"What's the current weather in {city}? Please cite sources.",
        },
    ]

    response = openai_client.responses.create(
        model="gpt-5-nano",
        tools=tools,
        input=input_list,
    )

    # Append model output (which may include function call requests)
    input_list += response.output

    # Execute tool calls
    for item in response.output:
        if getattr(item, "type", None) == "function_call":
            name = getattr(item, "name", None)
            args = json.loads(getattr(item, "arguments", "{}"))

            if name == "search_web":
                query = args.get("query") or f"current weather in {city}"
                linkup_response = linkup_client.search(
                    query=query,
                    depth="standard",
                    output_type="searchResults",
                    include_images=False,
                )
                output_json = json.dumps(linkup_response.model_dump(), indent=2)
                input_list.append(
                    {
                        "type": "function_call_output",
                        "call_id": getattr(item, "call_id", "search_web_call"),
                        "output": output_json,
                    }
                )

            elif name == "translate_text":
                if not deepl_client:
                    input_list.append(
                        {
                            "type": "function_call_output",
                            "call_id": getattr(item, "call_id", "translate_text_call"),
                            "output": json.dumps(
                                {
                                    "error": "DEEPL_AUTH_KEY not set; translation unavailable"
                                }
                            ),
                        }
                    )
                else:
                    text = args.get("text", "")
                    target_lang = args.get("target_lang", "EN")
                    source_lang = args.get("source_lang")
                    formality = args.get("formality")

                    translated = deepl_client.translate_text(
                        text,
                        target_lang=target_lang,
                        source_lang=source_lang,
                        formality=formality,
                    )
                    # The SDK returns either a string or a TextResult object; normalize to string
                    translated_text = (
                        translated.text
                        if hasattr(translated, "text")
                        else str(translated)
                    )
                    input_list.append(
                        {
                            "type": "function_call_output",
                            "call_id": getattr(item, "call_id", "translate_text_call"),
                            "output": json.dumps({"translated_text": translated_text}),
                        }
                    )

            elif name == "find_local_sources_by_place":
                place = args.get("place", "")
                native_language = args.get("native_language")
                top_n = args.get("top_n") or 10

                if not place:
                    input_list.append(
                        {
                            "type": "function_call_output",
                            "call_id": getattr(
                                item, "call_id", "find_local_sources_call"
                            ),
                            "output": json.dumps({"error": "place is required"}),
                        }
                    )
                elif not native_language:
                    input_list.append(
                        {
                            "type": "function_call_output",
                            "call_id": getattr(
                                item, "call_id", "find_local_sources_call"
                            ),
                            "output": json.dumps(
                                {"error": "native_language is required"}
                            ),
                        }
                    )
                else:
                    language_phrase = f" in {native_language}"
                    # Enforce original-language sources without hardcoding language-specific keywords
                    query = (
                        f"local news websites for {place}{language_phrase}; "
                        f"official newspaper, tv, radio sites; "
                        f"sources in {native_language} only; do not translate"
                    )
                    linkup_response = linkup_client.search(
                        query=query,
                        depth="standard",
                        output_type="searchResults",
                        include_images=False,
                    )

                    def extract_urls_from_obj(obj: Any) -> list[str]:
                        collected: list[str] = []
                        if isinstance(obj, dict):
                            for key, value in obj.items():
                                if key.lower() == "url" and isinstance(value, str):
                                    collected.append(value)
                                else:
                                    collected.extend(extract_urls_from_obj(value))
                        elif isinstance(obj, list):
                            for element in obj:
                                collected.extend(extract_urls_from_obj(element))
                        return collected

                    raw_dump = linkup_response.model_dump()
                    all_urls = extract_urls_from_obj(raw_dump)
                    # Deduplicate while preserving order
                    seen: set[str] = set()
                    deduped_urls: list[str] = []
                    for url in all_urls:
                        if url not in seen:
                            seen.add(url)
                            deduped_urls.append(url)
                    sites = deduped_urls[: int(top_n)]

                    output_payload = {
                        "place": place,
                        "native_language": native_language,
                        "sites": sites,
                    }
                    input_list.append(
                        {
                            "type": "function_call_output",
                            "call_id": getattr(
                                item, "call_id", "find_local_sources_call"
                            ),
                            "output": json.dumps(output_payload),
                        }
                    )

            elif name == "search_local_news":
                place = args.get("place", "")
                sites = args.get("sites") or []
                native_language = args.get("native_language")
                since_days = int(args.get("since_days") or 7)

                if not place:
                    input_list.append(
                        {
                            "type": "function_call_output",
                            "call_id": getattr(
                                item, "call_id", "search_local_news_call"
                            ),
                            "output": json.dumps({"error": "place is required"}),
                        }
                    )
                elif not native_language:
                    input_list.append(
                        {
                            "type": "function_call_output",
                            "call_id": getattr(
                                item, "call_id", "search_local_news_call"
                            ),
                            "output": json.dumps(
                                {"error": "native_language is required"}
                            ),
                        }
                    )
                else:
                    site_filter = ""
                    if isinstance(sites, list) and len(sites) > 0:
                        site_terms = []
                        for s in sites[:10]:
                            site_terms.append(f"site:{s}")
                        site_filter = "(" + " OR ".join(site_terms) + ") "
                    language_phrase = f" in {native_language}"
                    query = (
                        f"{site_filter}{place} local news{language_phrase} last {since_days} days; "
                        f"content in {native_language} only; do not translate"
                    )
                    linkup_response = linkup_client.search(
                        query=query,
                        depth="standard",
                        output_type="searchResults",
                        include_images=False,
                    )
                    output_json = json.dumps(linkup_response.model_dump(), indent=2)
                    input_list.append(
                        {
                            "type": "function_call_output",
                            "call_id": getattr(
                                item, "call_id", "search_local_news_call"
                            ),
                            "output": output_json,
                        }
                    )

    # Ask the model to synthesize an answer with citations
    final = openai_client.responses.create(
        model="gpt-5-nano",
        tools=tools,
        input=input_list,
    )

    return getattr(final, "output_text", "")


def run_local_news_agent(query: str) -> str:
    """Autonomously find local sources and summarize local news in English.

    Minimal-input flow:
      - Detect place from user query
      - Find local websites (prioritize native-language sources)
      - Search recent local news across those sites
      - Summarize in English with citations; translate snippets if needed (DeepL)

    Requires env vars:
      - OPENAI_API_KEY
      - LINKUP_API_KEY
    """
    openai_api_key = os.environ.get("OPENAI_API_KEY")
    linkup_api_key = os.environ.get("LINKUP_API_KEY")
    if not openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is required")
    if not linkup_api_key:
        raise RuntimeError("LINKUP_API_KEY is required")

    openai_client = OpenAI(api_key=openai_api_key)
    linkup_client = LinkupClient(api_key=linkup_api_key)
    deepl_key = os.environ.get("DEEPL_AUTH_KEY")
    deepl_client = deepl.DeepLClient(deepl_key) if deepl_key else None

    tools = create_tools_schema()

    # System guidance for minimal-input local news workflow
    input_list: list[dict[str, Any]] = [
        {
            "role": "system",
            "content": (
                "When asked for local news, infer the place from the user's text and determine its native language."
                " Common mappings: Chennai/Tamil Nadu = Tamil, Mumbai/Maharashtra = Marathi, Delhi = Hindi,"
                " Kolkata/West Bengal = Bengali, Bangalore/Karnataka = Kannada, Hyderabad/Telangana = Telugu, etc."
                " EXAMPLE: For 'Chennai news' -> use find_local_sources_by_place(place='Chennai', native_language='Tamil')"
                " First discover local news websites for the place REQUIRING sources in the area's native language"
                " using find_local_sources_by_place, then search those sites for recent updates using search_local_news."
                " Write the final answer in English, translating brief quotes if necessary (you may call translate_text)."
                " Always include concise citations to the strongest local sources."
                " You MUST always specify the native language when calling these functions."
            ),
        },
        {
            "role": "user",
            "content": query,
        },
    ]

    # Simple multi-turn tool loop to allow sequential tool calls
    max_iterations = 3
    last_response = None
    for _ in range(max_iterations):
        response = openai_client.responses.create(
            model="gpt-5-nano",
            tools=tools,
            input=input_list,
        )
        last_response = response
        input_list += response.output

        made_tool_call = False
        for item in response.output:
            if getattr(item, "type", None) == "function_call":
                made_tool_call = True
                name = getattr(item, "name", None)
                args = json.loads(getattr(item, "arguments", "{}"))

                if name == "search_web":
                    q = args.get("query") or query
                    linkup_response = linkup_client.search(
                        query=q,
                        depth="standard",
                        output_type="searchResults",
                        include_images=False,
                    )
                    output_json = json.dumps(linkup_response.model_dump(), indent=2)
                    input_list.append(
                        {
                            "type": "function_call_output",
                            "call_id": getattr(item, "call_id", "search_web_call"),
                            "output": output_json,
                        }
                    )

                elif name == "translate_text":
                    if not deepl_client:
                        input_list.append(
                            {
                                "type": "function_call_output",
                                "call_id": getattr(
                                    item, "call_id", "translate_text_call"
                                ),
                                "output": json.dumps(
                                    {
                                        "error": "DEEPL_AUTH_KEY not set; translation unavailable",
                                    }
                                ),
                            }
                        )
                    else:
                        text = args.get("text", "")
                        target_lang = args.get("target_lang", "EN")
                        source_lang = args.get("source_lang")
                        formality = args.get("formality")
                        translated = deepl_client.translate_text(
                            text,
                            target_lang=target_lang,
                            source_lang=source_lang,
                            formality=formality,
                        )
                        translated_text = (
                            translated.text
                            if hasattr(translated, "text")
                            else str(translated)
                        )
                        input_list.append(
                            {
                                "type": "function_call_output",
                                "call_id": getattr(
                                    item, "call_id", "translate_text_call"
                                ),
                                "output": json.dumps(
                                    {"translated_text": translated_text}
                                ),
                            }
                        )

                elif name == "find_local_sources_by_place":
                    place = args.get("place") or query
                    native_language = args.get("native_language")
                    top_n = args.get("top_n") or 10
                    if not place:
                        input_list.append(
                            {
                                "type": "function_call_output",
                                "call_id": getattr(
                                    item, "call_id", "find_local_sources_call"
                                ),
                                "output": json.dumps({"error": "place is required"}),
                            }
                        )
                    elif not native_language:
                        input_list.append(
                            {
                                "type": "function_call_output",
                                "call_id": getattr(
                                    item, "call_id", "find_local_sources_call"
                                ),
                                "output": json.dumps(
                                    {"error": "native_language is required"}
                                ),
                            }
                        )
                    else:
                        language_phrase = f" in {native_language}"
                        if native_language.lower() == "tamil":
                            q2 = f"local news websites for {place}{language_phrase}; தமிழ் செய்திகள்; Tamil newspaper; official newspaper, tv, radio sites; {native_language} language only"
                        else:
                            q2 = f"local news websites for {place}{language_phrase}; official newspaper, tv, radio sites; {native_language} language only"
                        linkup_response = linkup_client.search(
                            query=q2,
                            depth="standard",
                            output_type="searchResults",
                            include_images=False,
                        )

                        def extract_urls_from_obj(obj: Any) -> list[str]:
                            collected: list[str] = []
                            if isinstance(obj, dict):
                                for key, value in obj.items():
                                    if key.lower() == "url" and isinstance(value, str):
                                        collected.append(value)
                                    else:
                                        collected.extend(extract_urls_from_obj(value))
                            elif isinstance(obj, list):
                                for element in obj:
                                    collected.extend(extract_urls_from_obj(element))
                            return collected

                        raw_dump = linkup_response.model_dump()
                        all_urls = extract_urls_from_obj(raw_dump)
                        seen: set[str] = set()
                        deduped_urls: list[str] = []
                        for url in all_urls:
                            if url not in seen:
                                seen.add(url)
                                deduped_urls.append(url)
                        sites = deduped_urls[: int(top_n)]

                        output_payload = {
                            "place": place,
                            "native_language": native_language,
                            "sites": sites,
                        }
                        input_list.append(
                            {
                                "type": "function_call_output",
                                "call_id": getattr(
                                    item, "call_id", "find_local_sources_call"
                                ),
                                "output": json.dumps(output_payload),
                            }
                        )

                elif name == "search_local_news":
                    place = args.get("place") or query
                    sites = args.get("sites") or []
                    native_language = args.get("native_language")
                    since_days = int(args.get("since_days") or 7)
                    if not place:
                        input_list.append(
                            {
                                "type": "function_call_output",
                                "call_id": getattr(
                                    item, "call_id", "search_local_news_call"
                                ),
                                "output": json.dumps({"error": "place is required"}),
                            }
                        )
                    elif not native_language:
                        input_list.append(
                            {
                                "type": "function_call_output",
                                "call_id": getattr(
                                    item, "call_id", "search_local_news_call"
                                ),
                                "output": json.dumps(
                                    {"error": "native_language is required"}
                                ),
                            }
                        )
                    else:
                        site_filter = ""
                        if isinstance(sites, list) and len(sites) > 0:
                            site_terms = []
                            for s in sites[:10]:
                                site_terms.append(f"site:{s}")
                            site_filter = "(" + " OR ".join(site_terms) + ") "
                        language_phrase = f" in {native_language}"
                        if native_language.lower() == "tamil":
                            q3 = f"{site_filter}{place} local news{language_phrase} last {since_days} days; தமிழ் செய்திகள்; Tamil news; {native_language} language content only"
                        else:
                            q3 = f"{site_filter}{place} local news{language_phrase} last {since_days} days; {native_language} language content only"
                        linkup_response = linkup_client.search(
                            query=q3,
                            depth="standard",
                            output_type="searchResults",
                            include_images=False,
                        )
                        output_json = json.dumps(linkup_response.model_dump(), indent=2)
                        input_list.append(
                            {
                                "type": "function_call_output",
                                "call_id": getattr(
                                    item, "call_id", "search_local_news_call"
                                ),
                                "output": output_json,
                            }
                        )

        if not made_tool_call:
            break

    # If loop ended without further tool calls, last_response contains the answer
    if last_response is not None:
        return getattr(last_response, "output_text", "")
    return ""


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Weather/News agent using Linkup + OpenAI tools"
    )
    parser.add_argument(
        "city", type=str, nargs="?", help="City name, e.g., 'San Francisco'"
    )
    parser.add_argument(
        "--news",
        action="store_true",
        help="Run local news mode from a freeform query",
    )
    parser.add_argument(
        "--query",
        type=str,
        default=None,
        help="Freeform user query when using --news (e.g., 'what's going on in Indonesia today?')",
    )
    args = parser.parse_args()

    if args.news:
        q = args.query or (args.city or "What's going on locally today?")
        result = run_local_news_agent(q)
    else:
        if not args.city:
            raise SystemExit("City is required unless using --news with --query")
        result = run_weather_agent(args.city)
    print(result)


if __name__ == "__main__":
    main()
