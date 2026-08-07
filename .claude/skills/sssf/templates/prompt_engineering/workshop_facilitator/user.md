# Decision Pack Task

## Variables

### prompt

{{prompt}}

### previous_envelope

{{previous_envelope}}

### context_handoff_dir

{{context_handoff_dir}}

## Task

Prepare the pack for the checkpoint named in `previous_envelope.notes_for_next_agent` (or in `prompt` when it says so).

1. Read every product this chain has produced in `<context_handoff_dir>` — the PRL, the constraints, the foundations or the increment and its acceptance results, and the timebox status if one is present. Read the artifacts, not only the envelopes.
2. Work out the **single question** the human has to settle. Not a list of questions: the one whose answer determines what happens next. Anything else that needs saying is context inside an option, or it waits for the next checkpoint.
3. Lay out at least two real options, each with its consequence, its reversibility, and its impact on Musts.
4. Write the pack to `<context_handoff_dir>/decision_pack_<checkpoint>.md` — question first, options as a table, the evidence under it. Assume the reader opens this file and nothing else.
5. Emit your `Report` JSON.

## Report

Respond with ONLY valid JSON matching `DecisionPackOutput` — no prose before or after:

```json
{
  "status": "success",
  "summary": "<one sentence: what the human is being asked to settle>",
  "checkpoint": "foundations_approval",
  "question": "<the one question, answerable go / changes / no-go>",
  "options": [
    {
      "id": "OPT-A",
      "option": "<what would be done>",
      "consequence": "<what follows — cost, risk, what is given up>",
      "impact_on_musts": "<which Musts this puts at risk, or empty if none>",
      "reversibility": "reversible"
    },
    {
      "id": "OPT-B",
      "option": "<the real alternative, stated fairly>",
      "consequence": "<what follows>",
      "impact_on_musts": "",
      "reversibility": "costly"
    }
  ],
  "recommendation": "OPT-A",
  "if_no_decision": "<what happens if the human declines or says nothing>",
  "decided": false,
  "artifacts": ["<context_handoff_dir>/decision_pack_<checkpoint>.md"],
  "notes_for_next_agent": "<anything the next agent needs after the human answers>"
}
```

`decided` is `false`. Always. A gate fails the phase if you set it, if there are fewer than two options, if `recommendation` names an option id that does not exist, or if `if_no_decision` is empty.
