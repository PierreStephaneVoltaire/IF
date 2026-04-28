import ast

with open('tools/health/program_evaluation_ai.py', 'r') as f:
    content = f.read()

tree = ast.parse(content)
system_prompt = ""
for node in tree.body:
    if isinstance(node, ast.Assign):
        for target in node.targets:
            if getattr(target, 'id', '') == '_SYSTEM_PROMPT':
                if hasattr(node.value, 'value'):
                    system_prompt = node.value.value
                else:
                    system_prompt = node.value.s

inputs = [
    "`task`: Evaluation goal string.",
    "`instructions`: Tuning instructions (tone, focus, what not to do).",
    "`program_meta`: Block metadata (name, style, split).",
    "`phases`: Phase definitions.",
    "`goals`: Explicit athlete goals.",
    "`full_block_summary`: High level stats (completed sessions, weeks).",
    "`completed_block_weeks`: Array of week numbers.",
    "`competitions`: Linked competitions and their roles.",
    "`meet_interference`: Conflicting or overlapping meets.",
    "`lift_profiles`: Athlete lift profiles.",
    "`athlete_measurements`: Physical measurements.",
    "`supplements`: Current supplement stack.",
    "`diet_context`: Current diet mode and history.",
    "`bodyweight_trend`: Bodyweight slope and stats.",
    "`completed_sessions`: History of actual training.",
    "`planned_sessions`: Remaining scheduled training.",
    "`weekly_analysis`: The deterministic backend analytics report.",
    "`exercise_roi`: Correlation findings between volume and intensity.",
    "`formula_reference`: The definitions of internal analytics formulas."
]

outputs = [
    "`stance`: Overall recommendation ('continue', 'monitor', 'adjust', 'critical').",
    "`summary`: 2-4 sentence overall summary of the block.",
    "`what_is_working`: Array of positive findings.",
    "`what_is_not_working`: Array of negative findings.",
    "`competition_alignment`: Array of alignments for each meet.",
    "`goal_status`: Array of statuses for each explicit goal.",
    "`competition_strategy`: Prioritization and approach per meet.",
    "`weight_class_strategy`: Weight class recommendation and viable options.",
    "`small_changes`: Suggested tweaks with priority and risk.",
    "`monitoring_focus`: Array of metrics to watch.",
    "`conclusion`: Short final recommendation.",
    "`insufficient_data`: Boolean flag.",
    "`insufficient_data_reason`: String reason if applicable."
]

replacement = f"""Inputs:

{chr(10).join(f"- {item}" for item in inputs)}

Outputs:

{chr(10).join(f"- {item}" for item in outputs)}

Prompt:

```text
{system_prompt}
```
"""

with open('utils/powerlifting-app/README.md', 'r') as f:
    text = f.read()

start_marker = "Prompt summary:"
end_marker = "Cache behavior:"

start_idx = text.find(start_marker)
end_idx = text.find(end_marker)

if start_idx != -1 and end_idx != -1:
    new_text = text[:start_idx] + replacement + text[end_idx:]
    with open('utils/powerlifting-app/README.md', 'w') as f:
        f.write(new_text)
    print("Replaced prompt and inputs/outputs successfully.")
else:
    print("Could not find markers.")
