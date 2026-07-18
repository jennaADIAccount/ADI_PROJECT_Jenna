from openai import OpenAI
from collections import Counter, defaultdict
import json
import os

# ==========================
# Configuration
# ==========================

from dotenv import load_dotenv

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

MODEL = "gpt-6-Luna"

SPEC1 = "riscv-2025.pdf"


NUM_AGENTS = 6

# How many of the 6 agents must agree on a finding (by normalized key)
# for it to be treated as "majority consensus" (i.e. > half of NUM_AGENTS).
MAJORITY_THRESHOLD = (NUM_AGENTS // 2) + 1

PROMPT = """
You are reviewing an extracted engineering specification.
It is a list of extracted requirements and definitions. Compare all facts referring to the same entity (signals, registers, fields, opcodes, formulas, encodings, state machines). Report only logical contradictions.

Your task is to identify INTERNAL inconsistencies.

An inconsistency exists when two or more statements in the specification
cannot both be true simultaneously.

Report ONLY genuine logical contradictions.3-

Do NOT report:
- ambiguous wording
- missing information
- stylistic issues
- formatting differences

For every inconsistency return:
- title
- category
- severity
- page_a
- page_b
- section_a
- section_b
- statement_a
- statement_b
- reason
- confidence

Example:

Statement A:
Table 11:
MXL = 3 -> Reserved

Statement B:
MXLEN = 2^(MXL+4)

which implies

MXL = 3 -> 128-bit

Reason:
If value 3 is reserved, software cannot assign it a meaning.
The later formula assigns it a specific meaning.
These statements cannot both be true simultaneously.

Category:
Reserved value contradiction

Confidence:
High

Now analyze the specification and find every similar inconsistency.

"""

# ==========================
# Strict JSON schema (Structured Outputs)
# ==========================
# Using json_schema output enforcement means the model literally cannot
# return malformed JSON, prose, or markdown fences - this was the main
# cause of some agents producing "proper" output and others not.

INCONSISTENCY_SCHEMA = {
    "type": "json_schema",
    "name": "spec_diff",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "inconsistencies": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {
                            "type": "string"
                        },
                        "category": {
                            "type": "string"
                        },
                        "severity": {
                            "type": "string",
                            "enum": ["Low", "Medium", "High", "Critical"]
                        },
                        "page_a": {
                            "type": ["integer", "null"]
                        },
                        "page_b": {
                            "type": ["integer", "null"]
                        },
                        "section_a": {
                            "type": "string"
                        },
                        "section_b": {
                            "type": "string"
                        },
                        "statement_a": {
                            "type": "string"
                        },
                        "statement_b": {
                            "type": "string"
                        },
                        "reason": {
                            "type": "string"
                        },
                        "confidence": {
                            "type": "string",
                            "enum": ["Low", "Medium", "High"]
                        }
                    },
                    "required": [
                        "title",
                        "category",
                        "severity",
                        "page_a",
                        "page_b",
                        "section_a",
                        "section_b",
                        "statement_a",
                        "statement_b",
                        "reason",
                        "confidence"
                    ],
                    "additionalProperties": False
                }
            }
        },
        "required": ["inconsistencies"],
        "additionalProperties": False
    }
}

# ==========================
# Upload PDFs
# ==========================

print("Uploading files...")

file1 = client.files.create(
    file=open(SPEC1, "rb"),
    purpose="user_data"
)


print("Files uploaded.")


# ==========================
# Run six independent agents
# ==========================

agent_results = []  # list of parsed dicts (only valid ones kept)

for i in range(NUM_AGENTS):

    print(f"Running agent {i+1}/{NUM_AGENTS}...")

    try:
        response = client.responses.create(
            model=MODEL,
            
                              # while still allowing 6 independent samples
            text={"format": INCONSISTENCY_SCHEMA},
            input=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": PROMPT
                        },
                        {
                            "type": "input_file",
                            "file_id": file1.id
                        }
                    ]
                }
            ]
        )

        result_text = response.output_text

        # Save the FULL, untruncated output for inspection/debugging.
        with open(f"agent_{i+1}.json", "w", encoding="utf-8") as f:
            f.write(result_text)

        # Validate immediately. Structured Outputs should guarantee valid
        # JSON, but we still guard against empty/truncated responses
        # (e.g. if the model hit max_output_tokens).
        parsed = json.loads(result_text)

        if "inconsistencies" not in parsed or not isinstance(parsed["inconsistencies"], list):
            raise ValueError("Missing or malformed 'inconsistencies' array")

        agent_results.append(parsed["inconsistencies"])
        print(f"  agent {i+1}: {len(parsed['stylistic_inconsistencies'])} findings parsed OK")

    except Exception as e:
        print(f"  agent {i+1} FAILED validation: {e}")
        # Do not append a broken result - better to have 5 good agents
        # than 6 agents where 1 silently corrupts the vote.

print(f"\n{len(agent_results)}/{NUM_AGENTS} agents produced valid, parseable JSON.")

if len(agent_results) == 0:
    raise RuntimeError("No agent produced valid JSON. Aborting.")


# ==========================
# Deterministic majority vote (done in Python, not by an LLM)
# ==========================
#
# Each finding is normalized into a key based on the fields that should be
# stable across independent re-runs (page numbers, section, type). The
# free-text "description" is expected to vary in wording between agents,
# so it is NOT part of the voting key - only used afterward for merging.



def normalize_key(item):
    return (
        item.get("page_number"),
        (item.get("section") or "").strip().lower(),
        (item.get("type") or "").strip().lower(),
    )

# Group all findings across all agents by their normalized key.
grouped = defaultdict(list)  # key -> list of description strings
vote_counter = Counter()     # key -> number of agents that reported it

for agent_findings in agent_results:
    seen_keys_this_agent = set()
    for item in agent_findings:
        key = normalize_key(item)
        grouped[key].append(item.get("description", ""))
        # Count each agent at most once per key, even if it listed the
        # same finding twice.
        if key not in seen_keys_this_agent:
            vote_counter[key] += 1
            seen_keys_this_agent.add(key)

# Keep only findings that a real majority of agents agreed on.
majority_keys = [k for k, count in vote_counter.items() if count >= MAJORITY_THRESHOLD]

print(f"{len(vote_counter)} unique findings total; "
      f"{len(majority_keys)} reached majority ({MAJORITY_THRESHOLD}/{NUM_AGENTS} agents).")

majority_inconsistencies = []
for key in majority_keys:
    page_a, page_b, section, type_ = key
    majority_inconsistencies.append({
        "page_a": page_a,
        "page_b": page_b,
        "section": section,
        "type": type_,
        "descriptions": grouped[key],  # all worded variants, to merge next
        "agent_votes": vote_counter[key],
    })


# ==========================
# LLM merge pass: only rewrites wording, does NOT decide inclusion
# ==========================
# By this point inclusion/exclusion has already been decided deterministically
# in Python. The LLM's only job here is to produce one clean description per
# finding from the (possibly slightly differently worded) agent descriptions.

consolidation_prompt = f"""
For each finding below, you are given several agent-written descriptions of
the SAME already-confirmed difference. Merge them into a single clear,
accurate description. Do not add, remove, or reinterpret findings - only
consolidate wording. Keep page_first, page_second, section, and type exactly
as given.

Return ONLY a JSON object with a single top-level key "inconsistencies", an
array of objects with fields: page_first, page_second, section, type,
description.

Findings:
{json.dumps(majority_findings, indent=2)}
"""

print("Running merge pass on majority-consensus findings...")

merge_response = client.responses.create(
    model=MODEL,
    text={"format": INCONSISTENCY_SCHEMA},
    input=merge_prompt,
)

merge_text = merge_response.output_text

# Validate the merge output too, before trusting it as final.
try:
    merged_parsed = json.loads(merge_text)
    if "inconsistencies" not in merged_parsed:
        raise ValueError("Missing 'inconsistencies' key in merge output")
    final_output = merged_parsed
except Exception as e:
    print(f"Merge pass produced invalid JSON ({e}); "
          f"falling back to raw majority findings without wording cleanup.")
    final_output = {
        "inconsistencies": [
            {
                "page_a": f["page_a"],
                "page_b": f["page_b"],
                "section": f["section"],
                "type": f["type"],
                # fall back to the first agent's wording
                "description": f["descriptions"][0] if f["descriptions"] else "",
            }
            for f in majority_inconsistencies
        ]
    }

with open("majority_result.json", "w", encoding="utf-8") as f:
    json.dump(final_output, f, indent=2)

print("Finished.")
print(f"{len(final_output.get('Inconsistencies', []))} consensus Inconsistencies written.")
print("Output saved as majority_result.json")