"""ship.sh (TZ_AUDIT3 №1): упавший тест не доходит до выкладки, зелёный — доходит (SHIP_DRY: без выкладки)."""
import os, subprocess
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def run(check):
    e = dict(os.environ, SHIP_CHECK=check, SHIP_DRY='1')
    return subprocess.run(['bash', os.path.join(R, 'tools', 'ship.sh')], env=e, capture_output=True, text=True)
bad = run("echo 'всего: 1s, упало: 1'; exit 1")
assert bad.returncode == 1 and 'выкладки нет' in bad.stdout, bad.stdout
lie = run("echo 'всего: 1s, упало: 1'")          # код 0, но в итоге падение — тоже стоп
assert lie.returncode == 1, lie.stdout
ok = run("echo 'всего: 1s, упало: 0'")
assert ok.returncode == 0 and 'dry' in ok.stdout, ok.stdout
print('ship.sh: ok')
