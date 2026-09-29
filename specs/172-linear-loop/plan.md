# Implementation Plan: Linear tracker in the loop

Use the existing registry Result port and Linear HTTP adapter. Add backlog reading to discovery. Add a small shared tracker call helper to record unmeasured failures while letting the loop continue. Call it at item start, PR raise, and confirmed merge. Resolve Linear state names within the adapter. Extend config schema, template, and docs. Test each behavior before implementation with recorded GraphQL data and fake ports.
