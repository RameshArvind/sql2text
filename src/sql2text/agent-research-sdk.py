import argparse
import asyncio
import base64
import json
import os
import urllib.error
import urllib.request
from typing import Any, Optional

import deepl
from agents import Agent, ItemHelpers, Runner, function_tool
from linkup import LinkupClient


@function_tool
def search_web(
    query: str,
    depth: Optional[str] = "standard",
    native_language: Optional[str] = None,
    include_domains: Optional[list[str]] = None,
    exclude_domains: Optional[list[str]] = None,
) -> dict[str, Any]:
    """Search the web for information and prefer sources in the given native language.

    If `native_language` is provided and is not 'English', the query will be
    biased to only include sources in that language and to exclude English sources.
    """
    linkup = LinkupClient(api_key=os.environ["LINKUP_API_KEY"])
    # Strengthen the prompt to exclude English sources when a local language is given
    if native_language:
        lang_norm = native_language.strip().lower()
        is_english = lang_norm in {
            "english",
            "en",
            "en-us",
            "en-gb",
            "eng",
            "us english",
            "american english",
            "british english",
        }
    else:
        is_english = False
    if native_language and not is_english:
        query = f"{query}; content in {native_language} only; exclude English sources; do not translate"
    resp = linkup.search(
        query=query,
        depth=depth,
        output_type="searchResults",
        include_images=False,
        include_domains=include_domains,
        exclude_domains=exclude_domains,
    )
    return resp.model_dump()


def _normalize_target_lang(lang: str) -> str:
    """Minimal normalization for DeepL target language codes."""
    key = (lang or "").strip().lower()
    if key in {"en", "english", "en-us", "american english", "us english"}:
        return "EN-US"
    if key in {"en-gb", "british english"}:
        return "EN-GB"
    return (lang or "EN-US").upper()


def _normalize_source_lang(lang: Optional[str]) -> Optional[str]:
    """Minimal normalization for DeepL source language codes (or None for auto-detect)."""
    if not lang:
        return None
    key = lang.strip().lower()
    if key in {"en", "en-us", "en-gb", "english", "us english", "british english"}:
        return "EN"
    if key in {"pt", "pt-pt", "pt-br", "portuguese"}:
        return "PT"
    # If user passes a long name like 'spanish', fall back to auto-detect to avoid errors
    if len(key) > 3:
        return None
    return key.upper()


@function_tool
def translate_text(
    text: str,
) -> dict[str, str]:
    """Translate text to a target language using DeepL.

    - Uses EN-US for English target to avoid deprecation errors
    - lets DeepL auto-detect source-language
    - Returns an error field instead of raising so callers don't crash
    """
    deepl_key = os.environ.get("DEEPL_AUTH_KEY")
    if not deepl_key:
        return {"error": "DEEPL_AUTH_KEY not set; translation unavailable"}

    client = deepl.DeepLClient(deepl_key)
    try:
        translated = client.translate_text(
            text,
            target_lang="EN-US",
        )
        translated_text = (
            translated.text if hasattr(translated, "text") else str(translated)
        )
        return {"translated_text": translated_text}
    except Exception as e:
        return {"error": str(e)}


@function_tool
def find_local_sources_by_place(
    place: str,
    native_language: str,
    top_n: int = 10,
    include_domains: Optional[list[str]] = None,
    exclude_domains: Optional[list[str]] = None,
) -> dict[str, Any]:
    """Discover local news websites for a given place, requiring sources in the native language.

    Enforces local-language sources by explicitly excluding English content when
    the native language is not English.
    """
    linkup = LinkupClient(api_key=os.environ["LINKUP_API_KEY"])
    lang_norm = native_language.strip().lower()
    is_english = lang_norm in {
        "english",
        "en",
        "en-us",
        "en-gb",
        "eng",
        "us english",
        "american english",
        "british english",
    }
    if is_english:
        q = (
            f"local news websites for {place} in {native_language}; "
            f"official newspaper, tv, radio sites; sources in {native_language}; do not translate"
        )
    else:
        q = (
            f"local news websites for {place} in {native_language}; "
            f"official newspaper, tv, radio sites; sources in {native_language} only; "
            f"exclude English sources; do not translate"
        )
    resp = linkup.search(
        query=q,
        depth="standard",
        output_type="searchResults",
        include_images=False,
        include_domains=include_domains,
        exclude_domains=exclude_domains,
    )

    def extract_urls(obj: Any) -> list[str]:
        urls = []
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k.lower() == "url" and isinstance(v, str):
                    urls.append(v)
                else:
                    urls.extend(extract_urls(v))
        elif isinstance(obj, list):
            for x in obj:
                urls.extend(extract_urls(x))
        return urls

    raw = resp.model_dump()
    all_urls = extract_urls(raw)
    seen = set()
    deduped = []
    for u in all_urls:
        if u not in seen:
            seen.add(u)
            deduped.append(u)
    return {
        "place": place,
        "native_language": native_language,
        "sites": deduped[:top_n],
    }


@function_tool
def search_local_news(
    place: str,
    native_language: str,
    sites: Optional[list[str]] = None,
    since_days: int = 7,
    include_domains: Optional[list[str]] = None,
    exclude_domains: Optional[list[str]] = None,
) -> dict[str, Any]:
    """Search recent local news for a place, requiring sources in the specified native language.

    Excludes English sources when the native language is not English.
    """
    linkup = LinkupClient(api_key=os.environ["LINKUP_API_KEY"])
    site_filter = ""
    if sites:
        site_terms = [f"site:{s}" for s in sites[:10]]
        site_filter = "(" + " OR ".join(site_terms) + ") "
    lang_norm = native_language.strip().lower()
    is_english = lang_norm in {
        "english",
        "en",
        "en-us",
        "en-gb",
        "eng",
        "us english",
        "american english",
        "british english",
    }
    if is_english:
        q = (
            f"{site_filter}{place} local news in {native_language} last {since_days} days; "
            f"content in {native_language}; do not translate"
        )
    else:
        q = (
            f"{site_filter}{place} local news in {native_language} last {since_days} days; "
            f"content in {native_language} only; exclude English sources; do not translate"
        )
    resp = linkup.search(
        query=q,
        depth="deep",
        output_type="searchResults",
        include_images=False,
        include_domains=include_domains,
        exclude_domains=exclude_domains,
    )
    return resp.model_dump()


# ------------------------------
# Utility Tool: Save to File
# ------------------------------


@function_tool
def save_to_file(
    path: str,
    content: str,
    append: bool = False,
    encoding: str = "utf-8",
    ensure_directory: bool = True,
) -> dict[str, Any]:
    """Save text content to a local file.

    - `path`: Destination file path (absolute or relative)
    - `content`: Text to write
    - `append`: If true, append to file; otherwise overwrite
    - `encoding`: Text encoding to use
    - `ensure_directory`: Create parent directory if it does not exist
    """
    try:
        directory = os.path.dirname(path)
        if ensure_directory and directory:
            os.makedirs(directory, exist_ok=True)
        mode = "a" if append else "w"
        with open(path, mode, encoding=encoding) as f:
            bytes_written = f.write(content)
        return {
            "status": "ok",
            "path": path,
            "mode": mode,
            "bytes_written": bytes_written,
            "encoding": encoding,
        }
    except Exception as e:
        return {"status": "error", "path": path, "error": str(e)}


# ------------------------------
# Image Generation: Freepik Text-to-Image
# ------------------------------


@function_tool
def freepik_text_to_image(
    prompt: str,
    negative_prompt: Optional[str] = None,
    guidance_scale: Optional[float] = None,
    seed: Optional[int] = None,
    num_images: int = 1,
    size: str = "square_1_1",
    style: Optional[str] = None,
    filter_nsfw: bool = True,
    save_dir: Optional[str] = None,
    filename_prefix: Optional[str] = None,
) -> dict[str, Any]:
    """Create images from text using Freepik's Text-to-Image API.

    Requires environment variable `FREEPIK_API_KEY` for authentication.

    - `prompt`: Text prompt to generate image from (required)
    - `negative_prompt`: Attributes to avoid
    - `guidance_scale`: 0.0..2.0 (higher = closer to prompt)
    - `seed`: 0..1_000_000 for reproducibility
    - `num_images`: 1..4
    - `size`: e.g., 'square_1_1', 'landscape_16_9', 'portrait_9_16'
    - `style`: Optional style string supported by Freepik (e.g., 'anime')
    - `filter_nsfw`: Whether to filter NSFW images
    - `save_dir`: If provided, saves generated images as PNG files to this directory
    - `filename_prefix`: Optional filename prefix when saving (default 'freepik')
    """
    api_key = os.environ.get("FREEPIK_API_KEY")
    if not api_key:
        return {
            "status": "error",
            "error": "FREEPIK_API_KEY not set; set it to call Freepik API",
        }

    payload: dict[str, Any] = {
        "prompt": prompt,
        "num_images": int(num_images),
        "image": {"size": size},
        "filter_nsfw": bool(filter_nsfw),
    }
    if negative_prompt:
        payload["negative_prompt"] = negative_prompt
    if guidance_scale is not None:
        payload["guidance_scale"] = float(guidance_scale)
    if seed is not None:
        payload["seed"] = int(seed)
    if style:
        payload["styling"] = {"style": style}

    headers = {
        "Content-Type": "application/json",
        "x-freepik-api-key": api_key,
    }

    req = urllib.request.Request(
        url="https://api.freepik.com/v1/ai/text-to-image",
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            status_code = resp.getcode()
            body = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        try:
            err_body = e.read().decode("utf-8")
        except Exception:
            err_body = str(e)
        return {
            "status": "error",
            "http_status": getattr(e, "code", None),
            "error": err_body or str(e),
        }
    except urllib.error.URLError as e:
        return {"status": "error", "error": getattr(e, "reason", str(e))}
    except Exception as e:
        return {"status": "error", "error": str(e)}

    try:
        data = json.loads(body)
    except Exception as e:
        return {
            "status": "error",
            "error": f"Invalid JSON from Freepik: {e}",
            "raw": body,
        }

    images = data.get("data", []) if isinstance(data, dict) else []
    meta = data.get("meta", {}) if isinstance(data, dict) else {}

    saved_paths: list[str] = []
    if save_dir:
        os.makedirs(save_dir, exist_ok=True)
        prefix = filename_prefix or "freepik"
        for idx, item in enumerate(images):
            b64 = item.get("base64") if isinstance(item, dict) else None
            if not b64:
                continue
            try:
                img_bytes = base64.b64decode(b64)
            except Exception:
                continue
            out_path = os.path.join(save_dir, f"{prefix}_{idx + 1}.png")
            try:
                with open(out_path, "wb") as fh:
                    fh.write(img_bytes)
                saved_paths.append(out_path)
            except Exception:
                # Skip saving on error but still return others
                continue

    return {
        "status": "ok" if images else "empty",
        "http_status": status_code,
        "images": images,
        "meta": meta,
        "saved_paths": saved_paths,
        "request": payload,
    }


# ------------------------------
# Streaming Functions
# ------------------------------


async def run_agent_with_streaming(
    agent: Agent,
    input_text: str,
    previous_response_id: Optional[str] = None,
    stream_tokens: bool = False,
    max_turns: int = 20,
) -> tuple[str, Optional[str]]:
    """Run the agent with streaming events and return the final output and response ID.

    Args:
        agent: The agent to run
        input_text: User input
        previous_response_id: Previous response ID for conversation continuity
        stream_tokens: If True, show token-by-token streaming of the response
        max_turns: Soft cap on the number of tool-call turns to warn about
    """
    result = Runner.run_streamed(
        agent, input=input_text, previous_response_id=previous_response_id
    )

    print("🤖 Agent is thinking...")
    final_output = ""
    last_response_id = None
    tool_count = 0
    response_buffer = ""
    is_streaming_response = False
    tool_call_names: dict[str, str] = {}

    async for event in result.stream_events():
        # Handle raw response events (token-by-token streaming)
        if event.type == "raw_response_event":
            if stream_tokens:
                # Import here to avoid issues if not available
                try:
                    from openai.types.responses import ResponseTextDeltaEvent

                    if isinstance(event.data, ResponseTextDeltaEvent):
                        if not is_streaming_response:
                            print("\n💭 Generating response:")
                            is_streaming_response = True
                        delta = event.data.delta
                        response_buffer += delta
                        print(delta, end="", flush=True)
                except ImportError:
                    pass
            continue

        # Handle agent updates (when agent changes due to handoffs)
        elif event.type == "agent_updated_stream_event":
            print(f"🔄 Agent updated: {event.new_agent.name}")
            continue

        # Handle run item events (tool calls, outputs, etc.)
        elif event.type == "run_item_stream_event":
            if event.item.type == "tool_call_item":
                tool_count += 1
                raw_call = getattr(event.item, "raw_item", None)
                tool_name = None
                call_id = None

                # Try to read attributes directly from the raw item
                if raw_call is not None:
                    tool_name = (
                        getattr(raw_call, "name", None)
                        or getattr(raw_call, "tool_name", None)
                        or getattr(raw_call, "type", None)
                    )
                    call_id = getattr(raw_call, "call_id", None) or getattr(
                        raw_call, "id", None
                    )

                    # If pydantic model, try model_dump()
                    if hasattr(raw_call, "model_dump") and callable(
                        getattr(raw_call, "model_dump", None)
                    ):
                        try:
                            dumped = raw_call.model_dump(exclude_unset=True)
                            tool_name = (
                                tool_name
                                or dumped.get("name")
                                or dumped.get("tool_name")
                                or dumped.get("type")
                            )
                            call_id = (
                                call_id or dumped.get("call_id") or dumped.get("id")
                            )
                        except Exception:
                            pass

                    # If it's a dict-like
                    if isinstance(raw_call, dict):
                        tool_name = (
                            tool_name
                            or raw_call.get("name")
                            or raw_call.get("tool_name")
                            or raw_call.get("type")
                        )
                        call_id = (
                            call_id or raw_call.get("call_id") or raw_call.get("id")
                        )

                # Fallbacks
                tool_name = tool_name or "unknown"
                if call_id is not None:
                    tool_call_names[str(call_id)] = tool_name

                print(f"🔧 [{tool_count}] Calling tool: {tool_name}")

                # Warn as we near the configured turn limit
                try:
                    if isinstance(max_turns, int) and max_turns > 0:
                        if tool_count == max_turns - 3:
                            print(
                                "⚠️ Approaching turn limit (tool calls): "
                                f"{tool_count}/{max_turns}. Consider narrowing scope."
                            )
                        elif tool_count == max_turns - 1:
                            print(
                                "⚠️ Almost at turn limit: "
                                f"{tool_count}/{max_turns}. You may want to split the request."
                            )
                        elif tool_count >= max_turns:
                            print(
                                "⛔ Max turn limit reached: "
                                f"{tool_count}/{max_turns}. Provide partial results and propose follow-ups."
                            )
                except Exception:
                    pass

            elif event.item.type == "tool_call_output_item":
                # Show tool output (truncated for readability) with tool name
                raw_out = getattr(event.item, "raw_item", None)
                call_id_out = None
                if raw_out is not None:
                    call_id_out = getattr(raw_out, "call_id", None)
                    if call_id_out is None and isinstance(raw_out, dict):
                        call_id_out = raw_out.get("call_id")
                tool_label = tool_call_names.get(str(call_id_out), "unknown")

                output = str(event.item.output)
                if len(output) > 150:
                    output = output[:150] + "..."
                print(f"✅ Tool completed: {tool_label}: {output}")

            elif event.item.type == "message_output_item":
                # This is the final message from the agent
                final_output = ItemHelpers.text_message_output(event.item)
                if not stream_tokens or not is_streaming_response:
                    print("💬 Response ready!")
                else:
                    print("\n\n✅ Response complete!")

            else:
                # Handle other event types if needed
                pass

    # Try to get the last response ID from the result
    try:
        last_response_id = result.last_response_id
    except AttributeError:
        # Fallback if last_response_id is not available
        last_response_id = None

    return final_output, last_response_id


# ------------------------------
# CLI Entry Point
# ------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Research agent with OpenAI Agent SDK")
    parser.add_argument("topic", type=str, nargs="?", help="Topic or query to research")
    parser.add_argument(
        "--depth", type=str, default="standard", choices=["standard", "deep"]
    )
    parser.add_argument("--source-translation-lang", type=str, default=None)
    parser.add_argument("--output-translation-lang", type=str, default=None)
    parser.add_argument(
        "--chat", action="store_true", help="Start interactive chat mode"
    )
    parser.parse_args()

    print("💬 Research Chat (OpenAI Agent SDK)")
    print("Commands: /quit to exit, /reset to clear history")

    # Create a unique conversation id for this session so the
    # Agents SDK can track message history across turns.
    previous_response_id = None
    print(f"(conversation: {previous_response_id})")

    agent = Agent(
        name="Research Assistant (Chat)",
        model="gpt-4o-mini",
        tools=[
            search_web,
            translate_text,
            find_local_sources_by_place,
            search_local_news,
            save_to_file,
            # freepik_text_to_image,
        ],
        instructions=(
            "You are a research assistant. Use tools to gather sources and synthesize a concise, cited answer. "
            "Prefer authoritative and recent sources; include inline citations. "
            "If the query concerns a place/city/region or 'local news', determine the place's native language first. "
            "When the native language is not English, ONLY use sources in that native language and EXCLUDE English sources. "
            "In such cases, call find_local_sources_by_place, then call search_local_news using include_domains derived from those sites. "
            "Also issue a complementary search_web query with native_language and aligned include_domains/exclude_domains to broaden local-language coverage; merge and deduplicate results before synthesis. "
            "Execution strategy: Prefer calling independent tools in parallel rather than serially. For example, run find_local_sources_by_place and a complementary search_web at the same time; when sites are already known, run search_local_news and search_web concurrently. Batch multiple translate_text calls concurrently where safe. Cap concurrency to ~3–5 to avoid rate limits. Only serialize dependent retries (e.g., the tighten-and-retry exclusion loop). "
            "Tool budgeting: Aim to use fewer than 15 total tool calls per request. Scale searches with complexity: simple fact lookup (2–4 calls), moderate topical query (4–8), multi-faceted or regional news synthesis (8–12). If you estimate needing >12, prioritize the highest-signal sources first, and propose narrowing scope rather than exceeding the budget. "
            "Use domain filters to keep results local: (1) pass include_domains with hostnames of local outlets discovered via find_local_sources_by_place (prefer hosts under the region's ccTLD, e.g., 'example.in' for India); tighten this list if results are still global or English‑heavy. (2) pass exclude_domains to suppress generic/global sites such as 'wikipedia.org', 'britannica.com', 'quora.com', 'medium.com', 'youtube.com', 'pinterest.com' unless specifically relevant. Re‑run searches with adjusted filters if results drift from the local focus. "
            "Iteration policy for non-English workflows: Whenever any English result appears while native_language is not English, immediately add the offending hostnames to exclude_domains and rerun the same search; tighten include_domains toward native outlets (prefer ccTLD) as needed. Repeat this tighten-and-retry loop at most 4 times, stopping early once results are predominantly in the native language. "
            "Operational limit: You have a soft cap of 20 tool-call turns. As you approach this (within ~3 calls), warn the user that the limit is near; if you reach it, provide the best partial synthesis and propose a narrowed follow-up or to continue in a new turn. "
            "For each news item, provide a short 2-4 sentence blurb rather than just links. "
            "Translation policy: When a source or excerpt is not in English, you MUST call the translate_text tool to produce English text. "
            "Specifically: (1) For every quoted snippet and each per-item blurb derived from a non-English article, call translate_text with source_lang set to the detected language and target_lang='EN-US'. "
            "(2) Do not perform your own translation for these; prefer translate_text. If translate_text fails or is unavailable (e.g., DEEPL not configured), you may translate inline and annotate '[translated inline]'. "
            "(3) Deliver the final synthesized answer in English. If you reuse any non-English sentences verbatim, translate them via translate_text and annotate '[translated from <Language>]'. "
            "A running chat transcript is provided in context under 'chat_history'; use it to preserve continuity."
        ),
    )

    # Maintain a simple chat history of user/assistant messages
    chat_history: list[dict[str, str]] = []

    while True:
        try:
            prompt = input("\n> ").strip()
        except EOFError:
            break

        if not prompt:
            continue
        if prompt.lower() in {"/quit", "/exit"}:
            break
        if prompt.lower() == "/reset":
            chat_history.clear()
            previous_response_id = None
            print(f"(history cleared; new conversation: {previous_response_id})")
            continue

        # Append user message to history and build a transcript for context
        # chat_history.append({"role": "user", "content": prompt})
        # transcript_lines: list[str] = []
        # for msg in chat_history:
        #     who = "User" if msg.get("role") == "user" else "Assistant"
        #     transcript_lines.append(f"{who}: {msg.get('content', '')}")
        # transcript = "\n".join(transcript_lines)

        # Use streaming version for real-time progress updates
        assistant_reply, new_response_id = asyncio.run(
            run_agent_with_streaming(
                agent,
                input_text=prompt,
                previous_response_id=previous_response_id,
                stream_tokens=True,  # Always enable streaming
            )
        )

        # Update conversation tracking
        previous_response_id = new_response_id

        # Record assistant reply into history
        chat_history.append({"role": "assistant", "content": assistant_reply})

        # Only show final response if not streaming tokens (to avoid duplication)
        # Since streaming is always enabled, we don't need to show the final response again


if __name__ == "__main__":
    main()
