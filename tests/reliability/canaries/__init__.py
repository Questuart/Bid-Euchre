"""Dogfood canary suite (Primitive H.0).

The canonical scenario is ``dogfood-v1`` — see
``plans/steward_platform/canary_scenarios/dogfood.md``.

- ``dogfood_v1.py``         — pass-metric assertion runner (9 metrics)
- ``dogfood_v1_packet.py``  — task-packet generator with canary_id metadata
- ``test_dogfood_v1.py``    — seeded unit tests
"""
