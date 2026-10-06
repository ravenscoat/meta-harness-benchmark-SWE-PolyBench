# Five previously failed official tasks

**Stopped at the user's explicit request.** Two tasks completed, with zero
official resolutions and 963,403 reported tokens. Transformers 26164 passed
public verification but failed official tests; MUI 23229 failed both gates.
Both had all required official observations and no grader or patch error.
The controller exited before a third model trial started; results and score
hashes were preserved. Follow-up automation is paused. Do not resume without
new user authorization. Earlier startup information below is historical.

The user authorized exactly five retries on 2026-10-04. The active root is
`.hx/five-failure-development-v1`; its locked batch plan and source snapshot
record the original inputs, scheduler, runtime and historical score hashes.

| Order | Official task | Reported issue |
| --- | --- | --- |
| 1 | huggingface/transformers #26164 | Whisper prompting and max_new_tokens |
| 2 | mui/material-ui #23229 | Autocomplete input area cannot be clicked |
| 3 | huggingface/transformers #16198 | CLIPVisionModel configuration loading |
| 4 | serverless/serverless #2842 | Including multiple resource files |
| 5 | keras-team/keras #19863 | Subclassed model summary is incomplete |

Each selected prior outcome had an accepted candidate, an unresolved official
result, all required tests observed, and no grader infrastructure or patch
application error. Prior results remain unchanged. These are development
retries on consumed tasks, not fresh heldout evaluation or proof of a causal
improvement.

The batch uses frozen `polybench-public-tests@9`, one `gpt-6.1-sol` worker,
no reviewers or comparison arms, and at most one public-feedback revision per
task. It retains the pinned original dataset, sources, images and official
scorer. The existing public test and base regression checks run independently
of the worker; official resolution is reported separately from workflow
success.

The locked envelope is three hours and 3,500,000 reported tokens. Each workflow
targets 400,000 reported tokens, with a 600-second model attempt, 180-second
verification timeout and 1,800-second workflow deadline. Token checks occur at
turn boundaries and can overshoot. Unknown interrupted usage blocks additional
attempts. No purchases or reset-credit redemption are allowed. Exactly one new
scored identity per selected task is permitted; no replacements or scored
reruns.

The scheduler passed three focused checks on Windows and three on native Linux,
plus Ruff. Controller PID 599 started the first task on 2026-10-04. This is a
startup observation, not a permanent process identity. Results are pending.

Resume only after checking the real process inventory, existing locks, budget
and interruption records:

```powershell
wsl -d Ubuntu -u root --cd /mnt/d/projects/Harness -- /opt/hx-polybench-venv/bin/python -m scripts.run_five_failure_development .hx/five-failure-development-v1
```

Never pass `--prepare` to an existing root or start a second controller. Inspect
`results.json`, `experiments/phase.json`, `quota.json`, `stop.json` and
`controller.exited.json`. On completion, retain all scores and distinguish
official resolution, public verification, workflow success, patch rejection,
missing observations, infrastructure failures and known versus unknown usage.
Reported workflow seconds exclude downloads and official grading.
