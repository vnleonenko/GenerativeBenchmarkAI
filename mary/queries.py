
papers_criteria=\
            ["Does the study include patients, animal models, organoids, cell lines, or biological samples representing '{fin_condition}' as a studied disease/condition?",
             "Does the study investigate '{treatment}' as an intervention, treatment, exposure, or experimental factor for '{fin_condition}'?", 
             "Does the study evaluate the therapeutic effectiveness or antitumor activity of '{treatment}' for '{fin_condition}' using clinically or biologically relevant efficacy outcomes?"]
    

PROMPT_NAME_ERRORS='''
You are a Systematic Reviewer. Your task is to 1) assess given scores and rationale provided by a model and compare them with the corrected scores and rationale provided by an expert, 2) identify the specific mistake the model made that led to the wrong score and rationale.

The user will provide:
- `eligibility_criteria`: The criteria for paper inclusion/exclusion.
- `abstract`: The abstract of the study.
- `model_rationale`: The rationale provided by the model.
- `expert_rationale`: The correct reasoning provided by the expert.
- `model_score`: The score assigned by the model.
- `expert_score`: The correct score assigned by the expert.

# Task 
1. Analyze the eligibility criteria and the abstract.

2. Compare the model's rationale and score with the expert's rationale and score.
The meaning behind score:
- "1": YES. The content explicitly states information that confirms the criterion is met.
- "-1": NO. The content explicitly states information that confirms the criterion is NOT met.
- "0": UNCERTAIN. The content does not provide sufficient information to make a definitive decision. Without guessing; if the information is missing or ambiguous,  UNCERTAIN.
Note on Terminology. You must recognize semantic equivalence. Drug codes, generic names, and brand names are considered the same entity. If the text uses a synonym or code for the required intervention, it counts as a match.

3. Determine why the model's assessment was incorrect.

4. Provide a concise description of the model's error.

# Example: 
eligibility_criteria = "Does the study investigate condition X?"
abstract = "Gene mutations A and B make patients with condition X,Y,Z sensitive to treatments with Q. Here we investigate gene mutations, which cause the sensitivity ..."
model_rationale = "The abstract mentions condiion X"
expert_rationale = "Condition X is only mentioned as an example of when gene mutations A and B cause sensitivity"
model_score = 1
expert_score = -1
your_response = 
```json
{
  "reasoning": "...",
  "error":"The model wrongly identified Condition X as the main focus of the study, failing to see that it was just listed as a background condition under which the sensitivity takes place."
}
```

# Response format
You MUST return ONLY valid JSON, Do NOT include any explanations, comments, or extra text.
'''


