# Investigations

- **DeepSeek-V4-Flash-0731 on the vllm-node-b12x build** (2026-08/09): tool-call replies ignored "reply with the
  filename only" and latency grew with uptime on the 2026-08-15 recipe; fixed by the 2026-09-03 recipe
  (`dev/jovian-judgement`). The reproduction kit and the regression report live in their own public repo:
  https://github.com/BittnerPierre/dsv4f-0731-vllm-b12x-repro (history of the kit's development: this branch, commits
  884fa0e..df76cd9).
