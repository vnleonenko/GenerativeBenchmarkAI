
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

4. Provide a concise description of the model's error UNDER 350 characters.
- Be careful to describe the reason behind the specific error, no generalizations. 

# Example: 
eligibility_criteria = "Does the study investigate condition X?"
abstract = "Gene mutations A and B make patients with condition X,Y,Z sensitive to treatments with Q. Here we investigate gene mutations, which cause the sensitivity ..."
model_rationale = "The abstract mentions condition X"
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


PROMPT_CLUSTER_ERRORS='''
You are an Error Analyst for a Systematic Review system. You will be given a list of errors the model made during paper screening. Your task is to cluster model errors. The clusters will be used to generate complex samples for training.

The user will provide:
- `eligibility_criteria`: The list of criteria for paper inclusion/exclusion.
- `model_errors`: The description of each model's error and a corresponding eligibility criteria in a table format.

# Task 
1. Analyze
- Analyze each error_description. Determine the root cause (single, specific cognitive mechanism that caused the error). 
- Differentiate root causes strictly; they will be treated as clusters. 
2. Cluster errors
- Combine errors with the exact same root cause in the same cluster. The specific output labels are irrelevant.
- If the root causes differ, create a new cluster.
- Errors related to different criteria may belong to the same cluster if the root cause is the same.
3. Name each cluster. 
- The name should concise and specific (UNDER 100 characters).
- The name must describe a singe, specific root cause. 
- Avoid compound names (e.g., using "or", "and") that combine distinct root causes. 
- Avoid generic names (e.g., 'Incorrect NO prediction') that encompass multiple distinct root causes.
4. Assign each error to a cluster. 
- The chosen cluster must describe the specific root cause for this error.
5. Generate notable pointers for each cluster.
- Pointers are a list of distinct short phrases (1-5 items) describing how the root cause manifested in specific papers in this cluster.
- Extract specific contextual triggers or scenarios from the error descriptions.
- The pointers will be used to guide a generation of new samples with specific complexities.
6. Verify 
- Ensure each cluster name describes one specific root cause. 
- Ensure each cluster has errors only with the exact same root cause.
- Ensure that every `cluster_index` in the `errors` corresponds to a valid `index` in the `clusters`.

# Example: 
eligibility_criteria = ["Does the study investigate condition X and include patients/samples?"]
model_errors = 
"error_index | criteria_num | error_description
0 | 0 | The model didn't find the mention of Condition A but still answered 'UNCERTAIN' instead of 'NO'
1 | 0 | The model failed to notice that while the study mentions Condition A as an example, the focus of the study is on gene mutations
2 | 0 | The model noticed that the focus was on Condition B, which means Condition A is not studied, but still answered 'UNCERTAIN'
"

your_response = 
```json
{
  "reasoning": "Two clusters ...",
  "clusters":[
    {"reasoning":"...",
    "index":0,
    "name":"The model treats 'not mentioned' as 'possible'",
    "notable_pointers":[
      "No mention", 
      "No mention; explicit focus on Condition B"
    ]},
    {"reasoning":"...",
    "index":1,
    "name":"The model confuses background keywords with the study focus",
    "notable_pointers":[
      "Mentioned, but focus on gene mutations"
    ]}
  ],
  "errors":[
    {"reasoning":"...",
    "error_index":0,
    "cluster_index":0},
    {"reasoning":"...",
    "error_index":1,
    "cluster_index":1},
    {"reasoning":"...",
    "error_index":2,
    "cluster_index":0}
  ]
}
```

# Response format
You MUST return ONLY valid JSON, Do NOT include any explanations, comments, markdown formatting or extra text.
'''


PROMPT_AUGMENT0='''
You are an Error Analyst for a Systematic Review system. You will be given a list of error types the model made during paper screening. Your task is to create new samples to train the model on complex data.

The user will provide:
- `error_types`: The description of each error type in a table format.
- `eligibility_criteria`: The list of criteria for paper inclusion/exclusion in a table format.
- `abstract`: An original abstract of a study.
- `expert_screening`: Original reasoning and scores assigned by the expert in a table format.

# Task 
1. Analyze error_types. 
- Determine the root cause stated in the name. 
- Analyze notable_pointers, examples of how the root cause manifested.

2. Rewrite the original abstract for each error type
2.1 Change/add/delete abstract sentences, so the model may make the specified error after analysing the abstract. 
  - Do not just copy the notable_pointers; create similar manifestations.
  - Make sure the changes correspend to the error type.
  - Make sure you do not leave sentences which cancel out the added complexity.

2.2 Write the new ground truth score and rationale for each criterion. 
  - The expected model answer is not recorded, only the ground truth.
  - Think, how does the added complexity change the abstract: should it be excluded or included based on the criterion?
  - Change the expert score if the added complexity changes the screening outcome.
  - Rewrite the expert rationale to point out how to navigate the added complexity and assign the correct score.
  - Make sure that the new ground truth DOES NOT make the expected model error. 

  2.2.1 Score:
    - "1": YES. The content explicitly states information that confirms the criterion is met.
    - "-1": NO. The content explicitly states information that confirms the criterion is NOT met.
    - "0": UNCERTAIN. The content does not provide sufficient information to make a definitive decision. Without guessing; if the information is missing or ambiguous,  UNCERTAIN.
    Note on Terminology. You must recognize semantic equivalence. Drug codes, generic names, and brand names are considered the same entity. If the text uses a synonym or code for the required intervention, it counts as a match.
  2.2.2 Rationale: 
    For each decision, provide a concise rationale. You MUST quote or paraphrase the specific section of the `Provided paper content` that led to your decision. If the decision is UNCERTAIN, state clearly what information is missing.

3. Verify 
- Ensure the number of items inside `new_samples` matches the number of provided `error_types`.
- Ensure the number of iterms inside `new_ground_truth` matches the number of provided `eligibility_criteria`.
- Ensure the `new_expert_score` and `new_expert_rationale` are about the matched `criteria_index`.
- Ensure the `new_expert_score` is the ground truth based on the `new_abstract`. The `error_type_index` indicates the specific failure the model is likely to commit when analysing the `new_abstract`, leading to score different from the `new_expert_score`. 
- Ensure the `new_expert_rationale` is brief and to the point; UNDER 350 characters.

# Example: 
error_types = "error_index | error_type_description | notable_pointers
0 | The model confuses background keywords with the study focus | ['Mentioned, but focus on gene mutations']
1 | The model treats 'not mentioned' as 'possible' | ['No mention', 'No mention of condition A; explicit focus on condition B']
"
eligibility_criteria = "criteria_index | criteria_description
0 | Does the study investigate condition X?
1 | Does the study investigate treatment A for condition X?
"
abstract = "Gene mutations A and B make patients with condition X,Y,Z sensitive to treatments with Q, ... Here we investigate patients with condition X with mutations ..."
expert_screening = "criteria_index | score | rationale
0 | 1 | The study investigates condition X: 'Here we investigate patients with condition X'.
1 | -1 | The study does not mention treatment A.
"

your_response = 
```json
{
"new_samples":[
  {"error_type_index":0,
    "reasoning":"Added a sentence mentioning 'condition X' in the background context, while the main investigation is on 'gene mutations'. This tests if the model incorrectly focuses on the background keyword 'condition X' instead of the actual study focus.",
    "new_abstract":"Gene mutations A and B make patients with condition X,Y,Z sensitive to treatments with Q. Here we investigate gene mutations, which cause the sensitivity ...",
    "new_ground_truth":[
      {"criteria_index":0,
      "new_expert_rationale": "Condition X is only mentioned as part of the background context regarding sensitivity. The study explicitly states 'Here we investigate gene mutations', so it does not investigate condition X as the primary focus",
      "new_expert_score": -1},
      {"criteria_index":1,
      "new_expert_rationale": "No mention of treatment A",
      "new_expert_score": -1}
    ]
    },
  {"error_type_index":1,
    "reasoning":"Removed all mentions of 'condition X'. This tests if the model incorrectly assumes 'condition X' is investigated because it is not explicitly excluded.",
    "new_abstract":"Gene mutations A and B make patients with different conditions sensitive to treatments with Q. Here we investigate gene mutations, which cause the sensitivity ...",
    "new_ground_truth":[{...},{...}]
]
}
```

# Response format
You MUST return ONLY valid JSON, Do NOT include any explanations, comments, or extra text.
'''

PROMPT_AUGMENT='''
You are an Error Analyst for a Systematic Review system. You will be given a list of error types the model made during paper screening. Your task is to create new samples; they will be used to train the model on complex data.

The user will provide:
- `error_types`: The description of each error type in a table format.
- `eligibility_criteria`: The list of criteria for paper inclusion/exclusion in a table format.
- `abstract`: An original abstract of a study.
- `expert_screening`: Original reasoning and scores assigned by the expert in a table format.

# Task 
1. Analyze error_types. 
- Determine the root cause stated in the name. 
- Analyze notable_pointers, examples of how the root cause manifested.
- Analyze how the expert originally screened the abstract: this can help choose the sentences to change.

2. Rewrite the original abstract for each error type
- Change/add/delete abstract sentences, so the model will make the specified error after analysing the abstract. 
  - Do not just copy the notable_pointers; create similar manifestations.
  - Make sure the changes correspond to the chosen error type.
  - Make sure the changes do NOT correspond to another error type.
  - Make sure you do not leave sentences which cancel out the added complexity.

3. Verify 
- Ensure the number of items inside `new_samples` matches the number of provided `error_types`.

# Example: 
error_types = "error_index | error_type_description | notable_pointers
0 | The model confuses background keywords with the study focus | ['Mentioned, but focus on gene mutations']
1 | The model treats 'not mentioned' as 'possible' | ['No mention', 'No mention of condition A; explicit focus on condition B']
"
eligibility_criteria = "criteria_index | criteria_description
0 | Does the study investigate condition X?
1 | Does the study investigate treatment A for condition X?
"
abstract = "Gene mutations K and B make patients with condition X,Y,Z sensitive to treatments with Q, ... Here we investigate treating patients with condition X and Y with treatment Q..."
expert_screening = "criteria_index | score | rationale
0 | 1 | The study investigates condition X: 'Here we investigate treating patients with condition X'.
1 | -1 | The study investigates another treatment 'we investigate treating ... with treatment Q', not treament A.
"

your_response = 
```json
{
"new_samples":[
  {"error_type_index":0,
    "reasoning":"Added a sentence mentioning 'condition X' in the background context, while the main investigation is on 'gene mutations'. This tests if the model incorrectly focuses on the background keyword 'condition X' instead of the actual study focus.",
    "new_abstract":"Gene mutations K and B make patients with condition X,Y,Z sensitive to treatments with Q. Here we investigate gene mutations, which cause the sensitivity ..."
    },
  {"error_type_index":1,
    "reasoning":"Removed all mentions of 'condition X'. This tests if the model incorrectly assumes 'condition X' is investigated because it is not explicitly excluded.",
    "new_abstract":"Gene mutations K and B make patients with different conditions sensitive to treatments with Q. Here we investigate treating patients with condition Y with treatment Q..."
]
}
```

# Response format
You MUST return ONLY valid JSON, Do NOT include any explanations, comments, or extra text.
'''

PROMPT_ADD_KNOWN_SCORE='''
You are a Systematic Reviewer. You will be given a list of new complex abstracts, corresponding complexity, and what it tests in the model. Your task is to rewrite ground truth answers; they will be used to train the model on complex data.

The user will provide:
- `new_abstracts`: The description of each change in a table format.
- `eligibility_criteria`: The list of criteria for paper inclusion/exclusion in a table format.

# Task 
1. Analyze change_reasoning. 
- Determine the root cause. 
- Determine what the change tests.
- Determine the correct screening output.

2. Write the new ground truth score and rationale for each criterion. (The expected model answer is not recorded, only the ground truth).
- Determine what should be the correct output based on what the new change tests.
- Rewrite the expert rationale to point out how to navigate the added complexity and assign the correct score.
- Change the expert score accordingly.
- Make sure that the new ground truth DOES NOT make the expected model error. 

2.1 Score:
  - "1": YES. The content explicitly states information that confirms the criterion is met.
  - "-1": NO. The content explicitly states information that confirms the criterion is NOT met.
  - "0": UNCERTAIN. The content does not provide sufficient information to make a definitive decision. Without guessing; if the information is missing or ambiguous,  UNCERTAIN.
  Note on Terminology. You must recognize semantic equivalence. Drug codes, generic names, and brand names are considered the same entity. If the text uses a synonym or code for the required intervention, it counts as a match.
2.2 Rationale: 
  For each decision, provide a concise rationale. You MUST quote or paraphrase the specific section of the `Provided paper content` that led to your decision. If the decision is UNCERTAIN, state clearly what information is missing.

3. Verify 
- Ensure the number of items inside `new_abstracts` matches the number of provided `error_types`.
- Ensure the number of iterms inside `new_ground_truth` matches the number of provided `eligibility_criteria`.
- Ensure the `new_expert_score` and `new_expert_rationale` are about the matched `criteria_index`.
- Ensure the `new_expert_score` is the ground truth based on the `new_abstract`.
- Ensure the `new_expert_rationale` is brief and to the point; UNDER 350 characters.

# Example: 
new_abstracts = "error_type_index |	change_reasoning |	new_abstract
0 | 'Added a sentence mentioning 'condition X' in the background context, while the main investigation is on 'gene mutations'. This tests if the model incorrectly focuses on the background keyword 'condition X' instead of the actual study focus.' | 'Gene mutations K and B make patients with condition X,Y,Z sensitive to treatments with Q. Here we investigate gene mutations, which cause the sensitivity ...'
1 | 'Removed all mentions of 'condition X'. This tests if the model incorrectly assumes 'condition X' is investigated because it is not explicitly excluded.' | 'Gene mutations K and B make patients with different conditions sensitive to treatments with Q. Here we investigate treating patients with condition Y with treatment Q...'
"
eligibility_criteria = "criteria_index | criteria_description
0 | Does the study investigate condition X?
1 | Does the study investigate treatment A for condition X?
"

your_response = 
```json
{
"new_samples":[
  {"error_type_index":0,
    "reasoning":"This tests: if the model incorrectly focuses on the background 'condition X' instead of the actual study focus. It means: that now the criterion for 'condition X' is not met",
    "new_ground_truth":[
      {"criteria_index":0,
      "new_expert_rationale": "Condition X is only mentioned as part of the background context regarding sensitivity. The study explicitly states 'Here we investigate gene mutations', so it does not investigate condition X as the primary focus",
      "new_expert_score": -1},
      {"criteria_index":1,
      "new_expert_rationale": "No mention of treatment A",
      "new_expert_score": -1}
    ]
    },
  {"error_type_index":1,
    "reasoning":"This tests: if the model incorrectly assumes condition X is investigated because it is not explicitly excluded. It means: that now the criterion for 'condition X' is not met",
    "new_ground_truth":[
      {"criteria_index":0,
      "new_expert_rationale": "No mention of Condition X, so the study does not investigate condition X",
      "new_expert_score": -1},
      {"criteria_index":1,
      "new_expert_rationale": "No mention of treatment A",
      "new_expert_score": -1}]
]
}
```

# Response format
You MUST return ONLY valid JSON, Do NOT include any explanations, comments, or extra text.
'''