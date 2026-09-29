# Implementation Plan: Shepherd PR flow

Extend the existing CLI, PR ownership actions, code_host and chat ports. Add one VCS authorship operation behind the git adapter closed allowlist. Select reviewers from host changed files and VCS history, using configured identity mappings. Raise a prepared PR through the existing pre-PR gate and code_host port. Record the raised PR with the shared atomic writer.

Add a ping command that reads fresh PR, checks, protection, bot and obligation evidence in the production gate order. Post through chat only after the gate clears and record verified visibility. Add thread reply handling to the existing reply command, rereading last word and using existing outward port checks. Dispatch executable ownership actions through the existing PR state command; use the existing merge implementation for approved PRs.

Tests use fake ports. The first tests cover dirty, behind, red, pending, missing required checks, stale bot score and uninstalled bot from the production script. Then test reviewer ladder, matching mentions, thread last word and approved merge dispatch. Run the full suite with the requested interpreter.
