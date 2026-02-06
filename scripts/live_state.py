"""
live_state.py — Unified Evidence + Metacognitive Lens Injector (v4)

Gathers system evidence, runs metacognition compile, injects into BOOT.md.
One script. Runs from the unified cron.
"""

import json, os, datetime, hashlib, subprocess, sys

WORKSPACE = r"C:\Users\TESTING PC 8\clawd"
SCANNER = os.path.join(WORKSPACE, "kalshi_scanner.py")
BACKUP = os.path.join(WORKSPACE, "kalshi_scanner_turbo.py")
TRADES_LOG = os.path.join(WORKSPACE, "real_trades.jsonl")

sys.path.insert(0, os.path.join(WORKSPACE, 'scripts'))


def get_scanner_constants():
    constants = {}
    try:
        with open(SCANNER, 'r', encoding='utf-8', errors='replace') as f:
            for line in f:
                s = line.strip()
                if '=' in s and not s.startswith('#') and not s.startswith('def '):
                    parts = s.split('=', 1)
                    name = parts[0].strip()
                    if any(name.startswith(p) for p in [
                        'EXTRACTOR', 'BTC_', 'MIN_CASH', 'BET_SIZE',
                    ]) or 'cap_pct' in name or name in ['WINNING_HOURS', 'LEARNING_HOURS']:
                        constants[name] = parts[1].split('#')[0].strip()
    except: pass
    return constants


def get_file_hash(path):
    if os.path.exists(path):
        with open(path, 'rb') as f:
            return hashlib.sha256(f.read()).hexdigest()[:12]
    return "MISSING"


def get_prawn_status():
    try:
        result = subprocess.run(
            ['wmic', 'process', 'where',
             "commandline like '%kalshi_scanner%' and name='python3.12.exe'",
             'get', 'processid', '/format:csv'],
            capture_output=True, text=True, timeout=10)
        lines = [l.strip() for l in result.stdout.strip().split('\n') 
                 if l.strip() and 'ProcessId' not in l and 'Node' not in l]
        pids = [l.split(',')[-1] for l in lines if ',' in l]
        return f"Running (PID {', '.join(pids)})" if pids else "⚠️ DEAD"
    except: return "check failed"


def get_balance():
    try:
        result = subprocess.run(
            ['python', '-c',
             'from kalshi_api import KalshiAPI; api=KalshiAPI(); b=api.get_balance(); '
             'print(f"${b[\'balance\']/100:.2f} cash | ${b[\'portfolio_value\']/100:.2f} pos | '
             '${(b[\'balance\']+b[\'portfolio_value\'])/100:.2f} total")'],
            capture_output=True, text=True, timeout=15, cwd=WORKSPACE)
        return result.stdout.strip() or "failed"
    except: return "API unreachable"


def get_recent_trades(n=3):
    trades = []
    if os.path.exists(TRADES_LOG):
        with open(TRADES_LOG, 'r', encoding='utf-8', errors='replace') as f:
            for line in f:
                if line.strip():
                    try: trades.append(json.loads(line.strip()))
                    except: pass
    return trades[-n:]


def compile_system_evidence():
    now = datetime.datetime.now()
    lines = []
    lines.append(f"*Evidence: {now.strftime('%H:%M')} EST*")
    lines.append("")
    lines.append(f"**💰** {get_balance()}")
    prawn = get_prawn_status()
    lines.append(f"**🦐** {'⚠️ **NOT RUNNING**' if 'DEAD' in prawn else prawn}")
    
    constants = get_scanner_constants()
    cap = next((v for k, v in constants.items() if 'cap_pct' in k), '?')
    lines.append(f"**Config:** odds={constants.get('EXTRACTOR_MIN_ODDS','?')} | "
                 f"assets={constants.get('EXTRACTOR_ASSETS','?')} | cap={cap}")
    lines.append(f"**Hours:** WIN={constants.get('WINNING_HOURS','?')} LEARN={constants.get('LEARNING_HOURS','?')}")
    
    trades = get_recent_trades(3)
    if trades:
        parts = [f"{t.get('time','?')[11:16]} {t.get('coin','?')} {t.get('direction','?')} x{t.get('contracts','?')}" 
                 for t in trades]
        lines.append(f"**Trades:** {' → '.join(parts)}")
    lines.append("")
    return "\n".join(lines)


def run_snapshot():
    try:
        result = subprocess.run(['python', 'scripts/snapshot_prawn.py'],
            capture_output=True, text=True, timeout=15, cwd=WORKSPACE)
        return result.stdout.strip()
    except: return ""


if __name__ == '__main__':
    # 1. Snapshot
    snap = run_snapshot()
    if snap and "CHANGE" in snap.upper():
        print(f"⚠️ {snap}")
    
    # 2. System evidence
    evidence = compile_system_evidence()
    
    # 3. Compile lens + inject via metacognition engine
    from metacognition import inject_into_boot
    if inject_into_boot(system_evidence=evidence):
        size = os.path.getsize(os.path.join(WORKSPACE, 'BOOT.md'))
        print(f"BOOT.md updated ({size} bytes, ~{size//4} tokens)")
    else:
        print("Failed to update BOOT.md")
