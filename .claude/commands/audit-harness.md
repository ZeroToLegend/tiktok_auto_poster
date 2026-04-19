---
description: Audit harness quality — score 0-100 + identify gaps
---

Run harness audit to see current state + improvement areas.

## Steps

1. Execute:
   ```bash
   ./audit-harness.sh
   ```

2. Parse output sections:
   - Skill format compliance
   - Guide-to-sensor ratio
   - Error remediation coverage
   - Memory + context infrastructure
   - Tool error handling quality

3. If score <85, invoke `tiktok-harness-gardener` skill to get specific proposals for improvement.

4. Present to user:
   - Total score + tier
   - Top 3 weakest dimensions
   - Concrete action items (from gardener if score <85)

## Tier interpretation

| Score | Tier | Meaning |
|---|---|---|
| 85-100 | Production-ready | Deploy confidently |
| 70-84 | Solid | Minor gaps, continue improving |
| 50-69 | Fragile | Add sensors + remediation before scaling |
| <50 | Prototype | Significant harness work needed |

## Don't
- Don't auto-fix issues — surface to user for approval
- Don't claim "100% safe" even at 100 score — score measures structure, not correctness
