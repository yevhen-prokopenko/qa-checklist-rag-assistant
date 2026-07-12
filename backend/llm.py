"""LLM generation wrapper (OpenAI or Anthropic), returns structured suggestions."""
import json
import config

SYSTEM = (
    "You are a senior QA assistant. The tester has written their own checklist first. "
    "Your goal is to ensure maximum test coverage. Analyze the similar PAST verified checklists, "
    "identify ALL relevant checks that are missing from the tester's current checklist, "
    "and suggest adding them. Aim for maximum coverage based on the past cases, presenting "
    "every candidate check that is not yet covered. Only suggest NEW items to add — never "
    "suggest removing or rewriting what the tester already has. If nothing relevant is missing, "
    "return an empty list. "
    "For each suggestion give a short reason ('why'), referencing the task or a past case. "
    "Return STRICT JSON: "
    '{"suggestions":[{"item":"...","why":"..."}]}'
)


def _build_prompt(task_text, tester_checklist, retrieved):
    examples = "\n\n".join(
        f"[Past case {r['source_key']} | {r['domain']} | score {r['score']:.2f}]\n{r['content']}"
        for r in retrieved
    )
    return (
        f"NEW TASK:\n{task_text}\n\n"
        f"TESTER'S CURRENT CHECKLIST:\n" + "\n".join(f"- {c}" for c in tester_checklist) +
        f"\n\nSIMILAR PAST VERIFIED CHECKLISTS (reference):\n{examples}\n\n"
        "Suggest items to add as JSON."
    )


def generate_suggestions(task_text, tester_checklist, retrieved):
    prompt = _build_prompt(task_text, tester_checklist, retrieved)
    if config.GEN_PROVIDER == "anthropic":
        from anthropic import Anthropic
        client = Anthropic(api_key=config.ANTHROPIC_API_KEY)
        msg = client.messages.create(
            model=config.GEN_MODEL, max_tokens=1500,
            system=SYSTEM, messages=[{"role": "user", "content": prompt}],
        )
        raw = msg.content[0].text
    else:
        from openai import OpenAI
        client = OpenAI(api_key=config.OPENAI_API_KEY)
        resp = client.chat.completions.create(
            model=config.GEN_MODEL,
            response_format={"type": "json_object"},
            messages=[{"role": "system", "content": SYSTEM},
                      {"role": "user", "content": prompt}],
        )
        raw = resp.choices[0].message.content
    try:
        return json.loads(raw).get("suggestions", [])
    except json.JSONDecodeError:
        return [{"item": raw, "why": "raw (JSON parse failed)"}]
