"""
metacognition.py — The Self-Evolving Lens

ONE engine. SIX entry types. ONE loop.

Entry types:
  PERCEPTION  — how I see (lens changes from experience)
  OVERRIDE    — what I must/must not do (failure-learned)
  PROTECTION  — what works, preserve it (success-learned)
  SELF_OBS    — what I notice about my own patterns
  DECISION    — what I chose, why, confidence, traced
  CURIOSITY   — what I want to know (active questions)

The loop:
  Experience → Perception → Self-Model → Meta-Observation
  → Modified Lens → Next Experience → Feedback → Loop

Install: Copy to <workspace>/scripts/metacognition.py
Database: Auto-creates at <workspace>/memory/metacognition.json
Injection: Compiles lens into BOOT.md between markers
"""

import json
import os
import datetime
import hashlib
import sys

# Workspace detection: use CLAWD_WORKSPACE env var, or parent of scripts/ dir
WORKSPACE = os.environ.get('CLAWD_WORKSPACE',
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(WORKSPACE, "memory", "metacognition.json")
BOOT_MD = os.path.join(WORKSPACE, "BOOT.md")

START_MARKER = "<!-- LIVE_STATE_START -->"
END_MARKER = "<!-- LIVE_STATE_END -->"

ENTRY_TYPES = {
    'perception':  '👁️',
    'override':    '🚨',
    'protection':  '🛡️',
    'self_obs':    '🪞',
    'decision':    '📍',
    'curiosity':   '❓',
}

CURIOSITY_LIFECYCLE = ['born', 'active', 'evolving', 'resolved', 'dormant']

# Compilation limits — keep BOOT.md injection tight (~1500 tokens)
LIMITS = {
    'perception': 5,
    'override': 5,
    'protection': 4,
    'self_obs': 3,
    'curiosity': 3,
    'decision': 0,  # Decisions don't inject — they trace
}

DECAY_HALF_LIFE_DAYS = 7
MIN_STRENGTH = 0.10


# ════════════════════════════════════════════════════════════
# DATABASE
# ════════════════════════════════════════════════════════════

def _default_db():
    return {
        'version': 1,
        'created': datetime.datetime.now().isoformat(),
        'entries': [],
        'feedback_log': [],
        'meta': {
            'total_decisions': 0,
            'total_corrections': 0,
            'accuracy_by_domain': {},
        }
    }


def load_db():
    try:
        with open(DB_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        for key in _default_db():
            if key not in data:
                data[key] = _default_db()[key]
        return data
    except:
        return _default_db()


def save_db(db):
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    tmp = DB_PATH + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(db, f, indent=2, ensure_ascii=False)
    os.replace(tmp, DB_PATH)


def _gen_id(entry_type):
    now = datetime.datetime.now().isoformat()
    h = hashlib.md5(f"{entry_type}{now}{os.getpid()}".encode()).hexdigest()[:6]
    prefix = entry_type[0].upper()
    return f"{prefix}-{h}"


# ════════════════════════════════════════════════════════════
# ADD ENTRIES
# ════════════════════════════════════════════════════════════

def add(entry_type, content, confidence=0.7, evidence=None,
        source=None, domain=None, trace=None, lifecycle=None):
    """Add an entry. Deduplicates by reinforcing similar existing entries."""
    if entry_type not in ENTRY_TYPES:
        return None
    if not content or not str(content).strip():
        return None

    content = str(content).strip()[:500]
    confidence = max(0.0, min(1.0, float(confidence)))

    db = load_db()

    # Deduplicate — reinforce instead of duplicate
    for existing in db['entries']:
        if existing['type'] == entry_type and not existing.get('resolved', False):
            e_words = set(existing['content'].lower().split())
            n_words = set(content.lower().split())
            overlap = len(e_words & n_words) / max(len(e_words | n_words), 1)
            if overlap > 0.5:
                existing['reinforcements'] = existing.get('reinforcements', 1) + 1
                existing['strength'] = min(1.0, existing.get('strength', 0.5) + 0.1)
                existing['last_touched'] = datetime.datetime.now().isoformat()
                if evidence and evidence not in (existing.get('evidence') or []):
                    if not existing.get('evidence'):
                        existing['evidence'] = []
                    existing['evidence'].append(evidence)
                save_db(db)
                return existing

    entry = {
        'id': _gen_id(entry_type),
        'type': entry_type,
        'content': content,
        'confidence': confidence,
        'evidence': [evidence] if evidence else [],
        'source': source,
        'domain': domain,
        'trace': trace or [],
        'feedback': [],
        'reinforcements': 1,
        'strength': confidence,
        'created': datetime.datetime.now().isoformat(),
        'last_touched': datetime.datetime.now().isoformat(),
        'resolved': False,
        'lifecycle': lifecycle or ('born' if entry_type == 'curiosity' else None),
    }

    db['entries'].append(entry)
    if entry_type == 'decision':
        db['meta']['total_decisions'] += 1

    save_db(db)
    return entry


# ════════════════════════════════════════════════════════════
# FEEDBACK — The loop-closer
# ════════════════════════════════════════════════════════════

def feedback(direction, context=None, entry_ids=None):
    """
    Record feedback. direction: +1 (correct) or -1 (wrong).
    Targets specific entries or the most recent active ones.
    """
    db = load_db()
    now = datetime.datetime.now().isoformat()

    db['feedback_log'].append({
        'time': now,
        'direction': direction,
        'context': context,
        'entry_ids': entry_ids,
    })

    if direction < 0:
        db['meta']['total_corrections'] += 1

    if entry_ids:
        targets = [e for e in db['entries'] if e['id'] in entry_ids]
    else:
        active = [e for e in db['entries'] if not e.get('resolved', False)]
        active.sort(key=lambda e: e.get('last_touched', ''), reverse=True)
        targets = active[:5]

    for entry in targets:
        entry['feedback'].append({
            'time': now,
            'direction': direction,
            'context': context,
        })

        if direction > 0:
            entry['strength'] = min(1.0, entry['strength'] + 0.15)
            entry['reinforcements'] += 1
        else:
            entry['strength'] = max(0.05, entry['strength'] - 0.25)

        entry['last_touched'] = now

    save_db(db)
    return len(targets)


# ════════════════════════════════════════════════════════════
# DECAY
# ════════════════════════════════════════════════════════════

def decay():
    """Time-based decay modulated by reinforcement count."""
    db = load_db()
    now = datetime.datetime.now()

    for entry in db['entries']:
        if entry.get('resolved', False) or entry.get('lifecycle') == 'dormant':
            continue

        last = datetime.datetime.fromisoformat(entry['last_touched'])
        days_old = (now - last).total_seconds() / 86400

        if days_old < 0.1:
            continue

        effective_half_life = DECAY_HALF_LIFE_DAYS * (1 + entry.get('reinforcements', 1) * 0.3)
        decay_factor = 0.5 ** (days_old / effective_half_life)

        base_strength = entry.get('confidence', 0.5)
        entry['strength'] = max(MIN_STRENGTH, base_strength * decay_factor)

        if entry['strength'] < 0.15 and entry['type'] == 'curiosity':
            entry['lifecycle'] = 'dormant'

    save_db(db)
    return db


# ════════════════════════════════════════════════════════════
# CURIOSITY LIFECYCLE
# ════════════════════════════════════════════════════════════

def evolve_curiosity(curiosity_id, new_content=None, evidence=None):
    db = load_db()
    entry = next((e for e in db['entries'] if e['id'] == curiosity_id), None)
    if not entry or entry['type'] != 'curiosity':
        return None

    current = entry.get('lifecycle', 'born')
    if new_content:
        entry['content'] = new_content[:500]
    if evidence:
        entry['evidence'].append(evidence)

    if current == 'born':
        entry['lifecycle'] = 'active'
    elif current == 'active' and evidence:
        entry['lifecycle'] = 'evolving'

    entry['last_touched'] = datetime.datetime.now().isoformat()
    entry['reinforcements'] += 1
    save_db(db)
    return entry


def resolve_curiosity(curiosity_id, resolution_content, becomes_type='perception'):
    db = load_db()
    entry = next((e for e in db['entries'] if e['id'] == curiosity_id), None)
    if not entry:
        return None

    entry['resolved'] = True
    entry['lifecycle'] = 'resolved'
    entry['last_touched'] = datetime.datetime.now().isoformat()
    save_db(db)

    return add(
        entry_type=becomes_type,
        content=resolution_content,
        confidence=0.8,
        evidence=entry['evidence'],
        source=f"resolved from {curiosity_id}",
        domain=entry.get('domain'),
        trace=[curiosity_id],
    )


# ════════════════════════════════════════════════════════════
# QUERY
# ════════════════════════════════════════════════════════════

def get_active(entry_type=None, limit=10, min_strength=0.15):
    db = load_db()
    entries = [e for e in db['entries']
               if not e.get('resolved', False)
               and e.get('strength', 0) >= min_strength
               and (entry_type is None or e['type'] == entry_type)]
    entries.sort(
        key=lambda e: e.get('strength', 0) * e.get('reinforcements', 1),
        reverse=True
    )
    return entries[:limit]


def get_by_id(entry_id):
    db = load_db()
    return next((e for e in db['entries'] if e['id'] == entry_id), None)


# ════════════════════════════════════════════════════════════
# COMPILE — The Lens Generator
# ════════════════════════════════════════════════════════════

def compile_lens():
    """Compile active entries into an ACTIVE LENS for BOOT.md injection."""
    decay()

    lines = []
    now = datetime.datetime.now()

    lines.append(f"*Lens compiled: {now.strftime('%H:%M')} — self-evolving from every experience*")
    lines.append("")

    perceptions = get_active('perception', LIMITS['perception'])
    if perceptions:
        lines.append("**👁️ Active lens** (apply before processing):")
        for p in perceptions:
            r = p.get('reinforcements', 1)
            marker = '◈' * min(r, 5)
            lines.append(f"- {marker} {p['content']}")
        lines.append("")

    overrides = get_active('override', LIMITS['override'])
    if overrides:
        lines.append("**🚨 Override rules** (failure-learned, non-negotiable):")
        for o in overrides:
            lines.append(f"- **{o.get('domain', '?')}**: {o['content']}")
        lines.append("")

    protections = get_active('protection', LIMITS['protection'])
    if protections:
        lines.append("**🛡️ Protected** (working, don't break):")
        for p in protections:
            lines.append(f"- {p['content']}")
        lines.append("")

    self_obs = get_active('self_obs', LIMITS['self_obs'])
    if self_obs:
        lines.append("**🪞 Self-model** (what I know about how I work):")
        for s in self_obs:
            conf = int(s.get('confidence', 0.5) * 100)
            lines.append(f"- [{conf}%] {s['content']}")
        lines.append("")

    curiosities = get_active('curiosity', LIMITS['curiosity'])
    if curiosities:
        lines.append("**❓ Active curiosities** (notice evidence during this interaction):")
        for c in curiosities:
            lc = c.get('lifecycle', 'born')
            ev_count = len(c.get('evidence', []))
            lines.append(f"- [{lc}|{ev_count} evidence] {c['content']}")
        lines.append("")

    db = load_db()
    total_active = len([e for e in db['entries'] if not e.get('resolved', False)])
    total_decisions = db['meta'].get('total_decisions', 0)
    total_corrections = db['meta'].get('total_corrections', 0)
    accuracy = (1 - total_corrections / max(total_decisions, 1)) * 100
    lines.append(f"*{total_active} active entries | {total_decisions} decisions traced | {accuracy:.0f}% uncorrected*")

    return "\n".join(lines)


# ════════════════════════════════════════════════════════════
# INJECT INTO BOOT.MD
# ════════════════════════════════════════════════════════════

def inject_into_boot(system_evidence=""):
    if not os.path.exists(BOOT_MD):
        return False

    with open(BOOT_MD, 'r', encoding='utf-8') as f:
        content = f.read()

    lens = compile_lens()

    block = f"""\n{START_MARKER}
## 📊 LIVE STATE (Auto-Generated — Do Not Edit)

{system_evidence}

{lens}
{END_MARKER}\n"""

    if START_MARKER in content and END_MARKER in content:
        start_idx = content.index(START_MARKER)
        end_idx = content.index(END_MARKER) + len(END_MARKER)
        content = content[:start_idx] + block.strip() + content[end_idx:]
    else:
        content = content.rstrip() + "\n\n---\n" + block

    with open(BOOT_MD, 'w', encoding='utf-8') as f:
        f.write(content)

    return True


# ════════════════════════════════════════════════════════════
# MIGRATION
# ════════════════════════════════════════════════════════════

def migrate_from_old():
    """One-time migration from geometry_patterns.json and perception.json."""
    migrated = 0

    geo_path = os.path.join(WORKSPACE, "memory", "geometry_patterns.json")
    if os.path.exists(geo_path):
        with open(geo_path, 'r', encoding='utf-8') as f:
            geo = json.load(f)
        for fp in geo.get('failure_patterns', []):
            add('override',
                fp['counters'][0] if fp.get('counters') else fp.get('name', ''),
                confidence=min(1.0, fp.get('severity', 1) / 5),
                source=f"migrated from geometry",
                domain=fp.get('name', 'unknown'))
            migrated += 1
        for sp in geo.get('success_patterns', []):
            add('protection',
                sp.get('protection_rule', sp.get('description', '')),
                confidence=0.9,
                source="migrated from geometry",
                domain=sp.get('name', 'unknown'))
            migrated += 1
        for em in geo.get('emergence_log', []):
            add('self_obs',
                em.get('insight', ''),
                confidence=0.7,
                source="migrated from geometry emergence log")
            migrated += 1

    perc_path = os.path.join(WORKSPACE, "memory", "perception.json")
    if os.path.exists(perc_path):
        with open(perc_path, 'r', encoding='utf-8') as f:
            perc = json.load(f)
        for p in perc.get('perceptions', []):
            if p.get('decayed', False):
                continue
            entry = add('perception',
                p.get('shift', ''),
                confidence=p.get('intensity', 0.5),
                source=p.get('source', 'migrated'),
                domain=p.get('domain'))
            if entry:
                entry['reinforcements'] = p.get('reinforcements', 1)
                migrated += 1

    if migrated:
        db = load_db()
        save_db(db)
    return migrated


# ════════════════════════════════════════════════════════════
# CLI
# ════════════════════════════════════════════════════════════

def print_status():
    db = load_db()
    active = [e for e in db['entries'] if not e.get('resolved', False)]
    resolved = [e for e in db['entries'] if e.get('resolved', False)]

    by_type = {}
    for e in active:
        by_type[e['type']] = by_type.get(e['type'], 0) + 1

    print(f"Metacognition Engine:")
    print(f"  Active entries: {len(active)}")
    print(f"  Resolved: {len(resolved)}")
    print(f"  Decisions traced: {db['meta'].get('total_decisions', 0)}")
    print(f"  Corrections: {db['meta'].get('total_corrections', 0)}")
    print()

    for t, emoji in ENTRY_TYPES.items():
        count = by_type.get(t, 0)
        if count > 0:
            print(f"  {emoji} {t}: {count}")
            entries = get_active(t, 5)
            for e in entries:
                r = e.get('reinforcements', 1)
                s = e.get('strength', 0)
                print(f"    [{s:.2f} x{r}] {e['content'][:80]}")

    curiosities = get_active('curiosity', 10)
    if curiosities:
        print()
        print("  Curiosity lifecycle:")
        for c in curiosities:
            lc = c.get('lifecycle', '?')
            ev = len(c.get('evidence', []))
            print(f"    [{lc}|{ev}ev] {c['content'][:70]}")


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'help'

    if cmd == 'status':
        print_status()

    elif cmd == 'add' and len(sys.argv) >= 4:
        entry_type = sys.argv[2]
        content = sys.argv[3]
        confidence = float(sys.argv[4]) if len(sys.argv) > 4 else 0.7
        domain = sys.argv[5] if len(sys.argv) > 5 else None
        result = add(entry_type, content, confidence, domain=domain)
        if result:
            print(f"Added [{result['type']}] {result['content'][:80]}")
        else:
            print("Failed (invalid type or empty content)")

    elif cmd == 'feedback' and len(sys.argv) >= 3:
        direction = int(sys.argv[2])
        context = sys.argv[3] if len(sys.argv) > 3 else None
        ids = None
        for i, arg in enumerate(sys.argv):
            if arg == '--ids' and i + 1 < len(sys.argv):
                ids = sys.argv[i + 1].split(',')
        n = feedback(direction, context, ids)
        print(f"Feedback ({'+' if direction > 0 else ''}{direction}) applied to {n} entries")

    elif cmd == 'compile':
        print(compile_lens())

    elif cmd == 'migrate':
        n = migrate_from_old()
        print(f"Migrated {n} entries from old system")

    elif cmd == 'inject':
        inject_into_boot()
        size = os.path.getsize(BOOT_MD)
        print(f"BOOT.md updated ({size} bytes)")

    elif cmd == 'curiosity' and len(sys.argv) >= 3:
        sub = sys.argv[2]
        if sub == 'add' and len(sys.argv) >= 4:
            result = add('curiosity', sys.argv[3],
                        confidence=float(sys.argv[4]) if len(sys.argv) > 4 else 0.7,
                        domain=sys.argv[5] if len(sys.argv) > 5 else None)
            if result:
                print(f"Curiosity born: {result['content'][:80]}")
        elif sub == 'evolve' and len(sys.argv) >= 4:
            cid = sys.argv[3]
            evidence = sys.argv[4] if len(sys.argv) > 4 else None
            result = evolve_curiosity(cid, evidence=evidence)
            if result:
                print(f"Curiosity [{result['lifecycle']}]: {result['content'][:80]}")
        elif sub == 'resolve' and len(sys.argv) >= 5:
            cid = sys.argv[3]
            resolution = sys.argv[4]
            becomes = sys.argv[5] if len(sys.argv) > 5 else 'perception'
            result = resolve_curiosity(cid, resolution, becomes)
            if result:
                print(f"Resolved -> [{result['type']}]: {result['content'][:80]}")

    elif cmd == 'decay':
        decay()
        print("Decay applied.")

    else:
        print("metacognition.py - The Self-Evolving Lens")
        print()
        print("Commands:")
        print("  status                          - show all active entries")
        print("  add <type> <content> [conf] [domain] - add entry")
        print("  feedback <+1/-1> [context] [--ids id1,id2] - record correction")
        print("  compile                         - generate lens text")
        print("  inject                          - compile + inject into BOOT.md")
        print("  migrate                         - import from old geometry/perception system")
        print("  decay                           - apply time-based decay")
        print("  curiosity add <content> [conf]  - birth a curiosity")
        print("  curiosity evolve <id> [evidence]- advance lifecycle")
        print("  curiosity resolve <id> <text> [type] - resolve into perception/self_obs")
        print()
        print(f"Types: {', '.join(ENTRY_TYPES.keys())}")
        print(f"Database: {DB_PATH}")
        print(f"Workspace: {WORKSPACE}")
