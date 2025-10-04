import argparse
import json
import os
from typing import Any, Optional

import deepl
from agents import Agent, Runner
from linkup import LinkupClient


def create_tools_schema() -> list[dict[str, Any]]:
    """Define tools for research:
    - search_web(query: string, depth?: "standard"|"deep"): use Linkup
    - translate_text(text: string, target_lang: string, source_lang?: string, formality?: string)
    - find_local_sources_by_place(place: string, native_language: string, top_n?: integer)
    - search_local_news(place: string, sites?: string[], native_language: string, since_days?: integer)
    """
    return [
        {
            "type": "function",
            "name": "search_web",
            "description": (
                "Search the web for information. Returns comprehensive content from relevant sources."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "depth": {
                        "type": "string",
                        "enum": ["standard", "deep"],
                        "description": "Search depth (optional)",
                    },
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
                        "description": "Text to translate",
                    },
                    "target_lang": {
                        "type": "string",
                        "description": "Target language code, e.g., 'EN', 'DE', 'FR'",
                    },
                    "source_lang": {
                        "type": "string",
                        "description": "Optional source language code",
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
                        "description": "Native language of the area (REQUIRED)",
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


def run_research(
    topic_or_query: str,
    depth: str = "standard",
    source_translation_lang: Optional[str] = None,
    output_translation_lang: Optional[str] = None,
) -> str:
    """Minimal-input research flow using tool-calling.

    The model will call `search_web` to gather sources and `translate_text` when needed.
    If `output_translation_lang` is provided, the final answer should be in that language,
    and the model may call `translate_text` to produce it.
    """
    openai_key = os.environ.get("OPENAI_API_KEY")
    linkup_key = os.environ.get("LINKUP_API_KEY")
    if not openai_key:
        raise RuntimeError("OPENAI_API_KEY is required")
    if not linkup_key:
        raise RuntimeError("LINKUP_API_KEY is required")

    openai_client = OpenAI(api_key=openai_key)
    linkup_client = LinkupClient(api_key=linkup_key)
    deepl_key = os.environ.get("DEEPL_AUTH_KEY")
    deepl_client = deepl.DeepLClient(deepl_key) if deepl_key else None

    tools = create_tools_schema()

    # System guidance to drive autonomous tool usage and translation
    system_parts: list[str] = [
        "You are a research assistant. Use tools to gather sources and synthesize a concise, cited answer.",
        "Prefer authoritative and recent sources; include inline citations.",
        "If the query concerns a place/city/region or 'local news', determine the native language of the place first."
        " Common mappings: Chennai/Tamil Nadu = Tamil, Mumbai/Maharashtra = Marathi, Delhi = Hindi,"
        " Kolkata/West Bengal = Bengali, Bangalore/Karnataka = Kannada, Hyderabad/Telangana = Telugu, etc."
        " EXAMPLE: For 'Chennai news' -> use find_local_sources_by_place(place='Chennai', native_language='Tamil')"
        " Then discover local news websites for that place (REQUIRING native-language sources) via find_local_sources_by_place,"
        " then search those sites via search_local_news before synthesizing."
        " You MUST always specify the native language when calling these functions.",
    ]
    if source_translation_lang:
        system_parts.append(
            f"If source content is not readable, translate short quoted snippets to {source_translation_lang} using translate_text."
        )
    if output_translation_lang:
        system_parts.append(
            f"Deliver the final answer in {output_translation_lang}. You may call translate_text to produce this."
        )

    input_list: list[dict[str, Any]] = [
        {
            "role": "system",
            "content": " ".join(system_parts),
        },
        {
            "role": "user",
            "content": topic_or_query,
        },
    ]

    max_iterations = 3
    deepl_used = False
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
                    q = args.get("query") or topic_or_query
                    req_depth = args.get("depth") or depth
                    linkup_response = linkup_client.search(
                        query=q,
                        depth=req_depth,
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
                        target_lang = args.get(
                            "target_lang", output_translation_lang or "EN"
                        )
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
                        deepl_used = True
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
                    place = args.get("place") or topic_or_query
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
                        q2 = (
                            f"local news websites for {place}{language_phrase}; "
                            f"official newspaper, tv, radio sites; "
                            f"sources in {native_language} only; do not translate"
                        )
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
                    place = args.get("place") or topic_or_query
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
                        q3 = (
                            f"{site_filter}{place} local news{language_phrase} last {since_days} days; "
                            f"content in {native_language} only; do not translate"
                        )
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

    final_text = getattr(last_response, "output_text", "") if last_response else ""
    if deepl_used:
        suffix = "\n\n[Note: Some content was translated via DeepL]"
    else:
        suffix = "\n\n[Note: No DeepL translation was used]"
    return (final_text + suffix) if final_text else suffix


def _chat_loop(depth: str, src_lang: Optional[str], out_lang: Optional[str]) -> None:
    print("💬 Research Chat (Linkup + DeepL via tools)")
    print("Commands: /depth standard|deep, /srclang CODE, /outlang CODE, /quit")
    while True:
        try:
            prompt = input("\n> ").strip()
        except EOFError:
            break

        if not prompt:
            continue
        if prompt.lower() in {"/quit", "/exit", "quit", "exit"}:
            break
        if prompt.startswith("/depth"):
            _, *rest = prompt.split()
            if rest and rest[0] in {"standard", "deep"}:
                depth = rest[0]
                print(f"Depth set to {depth}")
            else:
                print("Usage: /depth standard|deep")
            continue
        if prompt.startswith("/srclang"):
            _, *rest = prompt.split()
            src_lang = rest[0].upper() if rest else None
            print(f"Source translation language: {src_lang}")
            continue
        if prompt.startswith("/outlang"):
            _, *rest = prompt.split()
            out_lang = rest[0].upper() if rest else None
            print(f"Output translation language: {out_lang}")
            continue

        result = run_research(
            topic_or_query=prompt,
            depth=depth,
            source_translation_lang=src_lang,
            output_translation_lang=out_lang,
        )
        print(f"\n{result}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generalized research agent (Linkup + DeepL via tool-calling)"
    )
    parser.add_argument("topic", type=str, nargs="?", help="Topic or query to research")
    parser.add_argument(
        "--depth",
        type=str,
        default="standard",
        choices=["standard", "deep"],
        help="Search depth",
    )
    parser.add_argument(
        "--source-translation-lang",
        type=str,
        default=None,
        help="Translate sources to this language code (for comprehension)",
    )
    parser.add_argument(
        "--output-translation-lang",
        type=str,
        default=None,
        help="Translate final output to this language code",
    )
    parser.add_argument(
        "--chat",
        action="store_true",
        help="Start interactive chat mode",
    )
    args = parser.parse_args()

    if args.chat:
        _chat_loop(
            args.depth, args.source_translation_lang, args.output_translation_lang
        )
        return

    # One-shot mode
    if not args.topic:
        print("Please provide a topic or run with --chat for interactive mode.")
        return

    result = run_research(
        topic_or_query=args.topic,
        depth=args.depth,
        source_translation_lang=args.source_translation_lang,
        output_translation_lang=args.output_translation_lang,
    )
    print(result)


if __name__ == "__main__":
    main()
