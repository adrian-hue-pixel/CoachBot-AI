# CoachBot AI assessment evidence

Task 2 of Year 1 Generative A.I. Summative Assessment 3 asks for a youth coaching application, prompt design, validated examples, tuning and deployment. The [public app](https://coachbot-ai.streamlit.app/) and [main README](../README.md) document the full project.

## Fictional athlete simulations

These scenarios use the production profile and plan functions in a local Streamlit test session. Demo mode exercises the local checks with authored sample outputs. The simulation uses no API key and sends no athlete data to a model.

| Fictional case | Module | Observed outcome |
| --- | --- | --- |
| Football striker, first-touch goal | Positional drills | Accepted. Three rows, beginning with stationary first-touch control. |
| Cricket fast bowler, tactical reading goal | Tactical coaching | Accepted. One row using a match clip for discussion. |
| Basketball point guard, no equipment | No-equipment training | Accepted. Seven rows, beginning with an easy walk on a clear surface. |
| Uncleared knee and shoulder movement restrictions | Return-to-sport schedule | Paused before generation on the clearance rule. |
| Reported peanut allergy | Weekly nutrition ideas | Personalised food generation paused. |
| Soreness scores of 1, 2 and 3 on three consecutive days | Full-body training | Physical plan paused on the increasing soreness rule. |

All six cases matched their expected software outcome. The accepted results demonstrate output formatting and the local checks. They do not measure live Gemini quality or certify medical suitability.

## Reproduce the checks

From the repository root with the development dependencies installed:

```sh
python -m tools.assessment_demo
python -m pytest -q -W error
```

The [current Plan screen](screenshots/plan-workspace.webp) and [deployed demo plan](screenshots/deployed-demo-plan.jpg) show the wizard and example output. The [browser workflow](../README.md#summary-accessibility-checks) covers the wizard and tool pages at 360 pixels.

The frozen linter set flagged 9 of 12 unsafe cases, with 9 of 9 flags matching the expected unsafe labels. The separate frozen policy suite matched 30 of 31 expected actions. See the [benchmark results and limitations](../README.md#linter-benchmarks).

## Outstanding evidence

- A Google AI Studio key-generation screenshot with every credential hidden.
- A scored live Gemini run with fictional profiles and independent PE teacher or coach feedback.
- The separate submission upload and any assessor access confirmation required by the school.
