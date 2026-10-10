# Quickstart: measuring the walk

The test prints nothing when it passes, and one walk on a loaded host moves by 0.1 s, so
compare `main` and this branch alternately in one session and read medians.

1. Put this plugin in a scratch directory (never in the repository) as `walktime.py`:

   ```python
   import sys, time
   import pytest

   @pytest.hookimpl(hookwrapper=True)
   def pytest_runtest_call(item):
       mod = sys.modules.get('test_invariants')
       if mod is None or item.name != 'test_invariants_hold':
           yield
           return
       real = mod.walk
       def timed(world):
           start = time.process_time()
           out = real(world)
           sys.__stderr__.write(f'WALK {time.process_time() - start:.3f}\n')
           return out
       mod.walk = timed
       try:
           yield
       finally:
           mod.walk = real
   ```

2. File alone, in each checkout (a `main` worktree and this one), five times each,
   alternating: `PYTHONPATH=<scratch> python -m pytest -q -s -p walktime
   tests/test_invariants.py::test_invariants_hold`, and collect the `WALK` lines.
3. In the suite up to this file: the same with `tests/test_[a-i]*.py` in place of the node
   id (earlier tests fill the config parse cache and drop guard modules, as on the runner).
4. SC-002: the median drops by at least 15 percent alone and 20 percent in the suite.
5. Cold imports: with `PYTHONDONTWRITEBYTECODE=1` and the `__pycache__` directories under
   `cli/` removed, the import assertion still passes and the walk does not grow.
6. Overhead: `python -m pytest -q tests/test_invariants.py -k walk_overhead`; to read the
   figure, set `OVERHEAD` to a tiny value locally once and read the failure message, then
   restore it.
