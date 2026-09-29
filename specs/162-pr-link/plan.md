# Implementation Plan: Item to PR link

Use the existing Python state writer, code host port, canonical PR parser, and raised and claimed sets. A shared state producer validates a one-to-one item link and updates either set in one locked write. Raise calls it after checking the new PR; claim checks an existing PR before calling it. Reserve the claim event and explain the item producer in the state error. No adapter or state format is added.

Tests use existing fake ports and day fixture. Run focused red and green tests for each behavior, then the complete pytest suite.
