"""
live_state.py — Evidence Gatherer + Metacognitive Lens Injector (Template)

This is the AGENT-SPECIFIC glue script. It gathers evidence from YOUR
environment and feeds it into the metacognition engine.

The metacognition.py core is environment-agnostic.
This file is where you wire in YOUR world.

CUSTOMIZE THIS FILE for your agent's needs:
- Replace the example evidence functions with your own data sources
- Set WORKSPACE to your agent's working directory
- Add whatever signals matter to your agent (git status, emails, APIs, etc.)

Runs via cron (recommended: every 15 minutes).
"""

import json, os, datetime, subprocess, sys

# === CONFIGURE THESE ===
# Option 1: Set CLAWD_WORKSPACE environment variable
# Option 2: Change this path to your agent's workspace
WORKSPACE = os.environ.get('CLAWD_WORKSPACE', os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

sys.path.insert(0, os.path.join(WORKSPACE, 'scripts'))


# ============================================================
# EXAMPLE: Evidence gathering functions
# Replace these with whatever YOUR agent cares about.
# ============================================================

def get_system_status():
    """Example: Check if key processes are running."""
    # Replace with your own process checks
    # e.g., check if a trading bot, web server, or scraper is alive
    return "running"


def get_recent_activity(n=3):
    """Example: Pull recent activity from a log file."""
    # Replace with: git log, trade history, email check, calendar, etc.
    activity_log = os.path.join(WORKSPACE, "activity.log")
    if os.path.exists(activity_log):
        with open(activity_log, 'r', encoding='utf-8', errors='replace') as f:
            lines = [l.strip() for l in f if l.strip()]
        return lines[-n:]
    return []


def compile_system_evidence():
    """
    Build the evidence string that gets injected into BOOT.md.
    
    This should be a SHORT summary of your agent's current state.
    Keep it under ~500 tokens — it's injected into every context load.
    """
    now = datetime.datetime.now()
    lines = []
    lines.append(f"*Evidence: {now.strftime('%H:%M')} EST*")
    lines.append("")
    
    # === ADD YOUR EVIDENCE HERE ===
    # Examples:
    # lines.append(f"**Status:** {get_system_status()}")
    # lines.append(f"**Balance:** {get_balance()}")
    # lines.append(f"**Git:** {get_git_status()}")
    # lines.append(f"**Inbox:** {count_unread_emails()} unread")
    
    lines.append(f"**System:** {get_system_status()}")
    
    activity = get_recent_activity(3)
    if activity:
        lines.append(f"**Recent:** {' | '.join(activity)}")
    
    lines.append("")
    return "\n".join(lines)


# ============================================================
# OPTIONAL: Code change watchdog
# If you have a critical script, you can hash-check it here.
# ============================================================

def run_snapshot():
    """Optional: Run a code-change watchdog script."""
    snapshot_script = os.path.join(WORKSPACE, 'scripts', 'snapshot_prawn.py')
    if os.path.exists(snapshot_script):
        try:
            result = subprocess.run(
                ['python', snapshot_script],
                capture_output=True, text=True, timeout=15, cwd=WORKSPACE)
            return result.stdout.strip()
        except:
            return ""
    return ""


# ============================================================
# MAIN: Gather evidence → Compile lens → Inject into BOOT.md
# ============================================================

if __name__ == '__main__':
    # 1. Optional snapshot/watchdog
    snap = run_snapshot()
    if snap and "CHANGE" in snap.upper():
        print(f"⚠️ {snap}")
    
    # 2. Gather system evidence
    evidence = compile_system_evidence()
    
    # 3. Compile metacognitive lens + inject into BOOT.md
    from metacognition import inject_into_boot
    if inject_into_boot(system_evidence=evidence):
        boot_path = os.path.join(WORKSPACE, 'BOOT.md')
        if os.path.exists(boot_path):
            size = os.path.getsize(boot_path)
            print(f"BOOT.md updated ({size} bytes, ~{size//4} tokens)")
    else:
        print("Failed to update BOOT.md")
