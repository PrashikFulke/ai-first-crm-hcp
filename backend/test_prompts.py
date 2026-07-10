"""
test_prompts.py
---------------
Self-test for the shared system prompt layer (agent/prompts.py).

Runs the two LLM-calling tools (log_interaction, edit_interaction) directly
— bypassing the full LangGraph graph — through three turns that simulate a
realistic multi-turn rep workflow:

  Turn 1 : Initial extraction from messy free-text notes.
  Turn 2 : Single-field correction (sentiment only).
  Turn 3 : Second correction that must not touch the first corrected field.

Expected behaviour:
  - Turn 1 populates all extractable fields; absent fields stay null / [].
  - Turn 2 patch contains ONLY the sentiment key.
  - Turn 3 patch contains ONLY topics_discussed; sentiment stays at value
    set in Turn 2 (proves turn isolation — the tool sees the current form
    state but must not echo unchanged fields back into the patch).

Run from the backend/ directory:
  python test_prompts.py
"""

import os, sys, json
from dotenv import load_dotenv

# Make sure we can import agent modules when running from backend/
sys.path.insert(0, os.path.dirname(__file__))
load_dotenv()

# ── Direct tool imports (no LangGraph graph needed for this test) ──────────
from agent.tools import log_interaction, edit_interaction


def heading(title: str):
    print(f"\n{'='*70}")
    print(f"  {title}")
    print('='*70)


def show(label: str, raw_result: str):
    print(f"\n[{label}]")
    try:
        parsed = json.loads(raw_result)
        print(json.dumps(parsed, indent=2))
    except json.JSONDecodeError:
        print(raw_result)
    return raw_result


# ── TURN 1 — Initial extraction ─────────────────────────────────────────────
heading("TURN 1 — Initial extraction from raw rep notes")

raw_notes = (
    "Visited Dr. Meera Kapoor at Sunrise Oncology today. "
    "We talked about the Phase 2 results for Arlovemab and her patient "
    "eligibility criteria for first-line treatment. "
    "She had a lot of questions but seemed overall receptive. "
    "I left her the Arlovemab clinical summary brochure and the "
    "patient-selection algorithm card. "
    "Also gave her 3 sample packs of Zyntora 10mg."
)
print(f"\nInput:\n{raw_notes}")

turn1_raw = log_interaction.invoke({"text_input": raw_notes})
show("Extracted fields (Turn 1)", turn1_raw)
turn1 = json.loads(turn1_raw)

# Build the simulated Redux form state after Turn 1
form_state_after_t1 = {
    "hcp_name":           turn1.get("hcp_name"),
    "topics_discussed":   turn1.get("topics_discussed"),
    "sentiment":          turn1.get("sentiment"),
    "materials_shared":   turn1.get("materials_shared", []),
    "samples_distributed":turn1.get("samples_distributed", []),
}
print(f"\nForm state after Turn 1:\n{json.dumps(form_state_after_t1, indent=2)}")


# ── TURN 2 — Single-field correction (sentiment only) ───────────────────────
heading("TURN 2 — Single-field correction: sentiment only")

correction_t2 = (
    "Actually, I overstated it — she was more hesitant than enthusiastic. "
    "Change the sentiment to Neutral."
)
print(f"\nCorrection:\n{correction_t2}")

turn2_raw = edit_interaction.invoke({
    "correction_text": correction_t2,
    "current_form": form_state_after_t1,
})
show("Patch (Turn 2)", turn2_raw)
turn2_patch = json.loads(turn2_raw)

# Validate: patch must contain ONLY sentiment
unexpected_t2 = [k for k in turn2_patch if k != "sentiment"]
if unexpected_t2:
    print(f"\n⚠  TURN ISOLATION FAILURE: patch contains unexpected keys: {unexpected_t2}")
else:
    print("\n✅  Turn isolation OK — patch contains only 'sentiment'")

# Apply patch to form state
form_state_after_t2 = {**form_state_after_t1, **turn2_patch}
print(f"\nForm state after Turn 2:\n{json.dumps(form_state_after_t2, indent=2)}")


# ── TURN 3 — Second correction, different field ──────────────────────────────
heading("TURN 3 — Second correction: topics only (sentiment must stay Neutral)")

correction_t3 = (
    "I forgot to mention — we also discussed the reimbursement pathway "
    "for Arlovemab under the national formulary. Please add that to "
    "what was discussed."
)
print(f"\nCorrection:\n{correction_t3}")

turn3_raw = edit_interaction.invoke({
    "correction_text": correction_t3,
    "current_form": form_state_after_t2,
})
show("Patch (Turn 3)", turn3_raw)
turn3_patch = json.loads(turn3_raw)

# Validate: patch must contain ONLY topics_discussed
unexpected_t3 = [k for k in turn3_patch if k != "topics_discussed"]
if unexpected_t3:
    print(f"\n⚠  TURN ISOLATION FAILURE: patch contains unexpected keys: {unexpected_t3}")
else:
    print("\n✅  Turn isolation OK — patch contains only 'topics_discussed'")

# Validate: sentiment must NOT be in the patch (must still be Neutral from T2)
if "sentiment" in turn3_patch:
    print(f"⚠  FIELD STABILITY FAILURE: Turn 3 patch changed sentiment to '{turn3_patch['sentiment']}'")
else:
    print("✅  Sentiment is stable — not present in Turn 3 patch")

# Apply patch to form state
form_state_after_t3 = {**form_state_after_t2, **turn3_patch}
print(f"\nFinal form state after Turn 3:\n{json.dumps(form_state_after_t3, indent=2)}")


# ── BONUS: Ambiguous correction (no target value) ────────────────────────────
heading("BONUS TURN — Ambiguous correction: field named, no value given")

correction_ambig = "Can you update the sentiment?"
print(f"\nCorrection:\n{correction_ambig}")

ambig_raw = edit_interaction.invoke({
    "correction_text": correction_ambig,
    "current_form": form_state_after_t3,
})
show("Patch (ambiguous correction)", ambig_raw)
ambig_patch = json.loads(ambig_raw)

if not ambig_patch:
    print("\n✅  Ambiguity handled correctly — empty patch returned (agent should ask for clarification)")
else:
    print(f"\n⚠  Ambiguity NOT handled — model guessed a value: {ambig_patch}")


# ── Summary ──────────────────────────────────────────────────────────────────
heading("TEST SUMMARY")
print(f"""
  Turn 1  extracted fields  : {list(turn1.keys())}
  Turn 2  patch keys        : {list(turn2_patch.keys())}
  Turn 3  patch keys        : {list(turn3_patch.keys())}
  Ambig   patch keys        : {list(ambig_patch.keys())}
  Final sentiment value     : {form_state_after_t3.get('sentiment')}  (expected: Neutral)
""")
