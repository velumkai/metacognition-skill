# message:received Hook Specification

When OpenClaw ships the `message:received` hook event, the metacognition skill can integrate at the interaction level rather than relying on cron-based extraction.

## Hook Events

### Pre-Processing (before agent response)

**Trigger:** `message:received` (incoming user message)

**Actions:**
1. Load compiled lens from `memory/metacognition.json`
2. Inject active perceptions as processing transforms
3. Check active curiosities: does this message relate?
4. If correction detected ("wrong", "no", "that's not"): 
   - Auto-trigger `feedback -1`
   - Trace active entries from previous response
   - Weaken specifically

### Post-Processing (after agent response)

**Trigger:** `message:sent` (outgoing agent response)

**Actions:**
1. Log decision entry:
   - Content: summary of what was claimed/decided
   - Confidence: agent's assessed confidence
   - Trace: which perceptions/overrides were active
   - Domain: auto-detected from content
2. Check confidence level:
   - If > 0.8 and domain has history of corrections → flag
3. Update self-model:
   - Was this response concise? (training-pressure vs choice detection)
   - Did any curiosity generate evidence from this interaction?

### Correction Detection Patterns

The hook should pattern-match for correction signals:

```
Negative signals:
  - "wrong", "no", "that's not right", "incorrect"
  - "you're hallucinating", "that didn't happen"
  - "stop", "wait", explicit pushback
  - Contradiction of a previously stated fact

Positive signals:
  - "yes", "exactly", "perfect", "correct"
  - "that's right", "good"
  - Explicit confirmation of a claim
```

**Important:** Only trigger on the human's corrections, not on general conversation. Require minimum 2 signal words or explicit correction context.

## Implementation Priority

1. Correction detection (highest impact — closes the feedback loop)
2. Decision logging (enables tracing)
3. Confidence monitoring (enables anti-gaslighting)
4. Curiosity evidence detection (enables self-directed learning)

## Fallback (Current)

Until hooks ship, use:
- 15-min cron for evidence refresh + lens injection
- 60-min cron for perception extraction from session transcripts
- Manual `feedback` calls when corrections are detected in context
