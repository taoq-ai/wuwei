---
version: 1.0.2
---
# Common authoring rules

Read `_common.md` first. These rules apply whenever a seat drafts, posts, commits or proposes a change.

## Ordered authoring checklist

1. Identify the audience, delivery medium and the repository's own style before writing. Use plain, factual language; no emoji or em dash. Verify every count, link target, status and technical claim at the current source.
2. Before any outward post, pass the outward-text guard. A send through a tool not on `outward.allow` is refused; it names the line the owner adds. Record posted ids so obligations can be checked. A refused post is not a sent message.
3. Before a commit or push, use the repository's configured author and committer identity. Do not fabricate an agent identity or rewrite published history. Use conventional commits when commits are part of the assigned work.
4. For a rule change, follow the proposal rule in `_common.md`. `wuwei promote` alone appends the dated verbatim line to `memory/CHANGELOG.md` and the outcome to `memory/ledger.jsonl`. Seats never write either and never load the changelog.

## Writing for a person

When the `humanizer` skill is installed, rewrite with it in embedded mode before you save, draft or post. That holds for text written for a person (PR bodies and retro summaries). It holds for every outward text too (tracker comments, docs pages, DMs, PR comments and review pings). Without it, check the text against this list. The CLI lint flags the mechanical tells on outward text: a warning and an `outward.ai_tells` event, or a refusal when `outward.humanize_strict` is on. An em dash or an emoji is always refused.

1. Lead with the decision or the fact the reader needs; leave out background the reader already has.
2. State the point directly. Do not deny a claim nobody made so that the real point sounds larger.
3. Cut openers that announce the point and closing lines that repeat it.
4. Group items in threes only when there are three real items.
5. Join clauses with a comma, colon, period or parentheses, never with a dash or a double hyphen.
6. Keep ordinary facts ordinary: no claims of significance or legacy the evidence does not show.
7. Say what a thing is and does, without advertising adjectives.
8. Prefer the plain word to the showy one models overuse, and is, are or has to serves as or stands as.
9. No bold label on every list item and no decorative headings; write headings in sentence case.
10. Remove chat leftovers: greetings, praise, offers of more help and sign-offs around the content.

## Plain tone

Text in WUWEI's voice follows five rules.

1. Keep sentences under 20 words on average and none over 35.
2. Put one idea in each sentence.
3. Use the verb, not a noun made from it: "close measures it", not "the measurement by close".
4. Use the plain word (use, run, send, ask) and drop chains of qualifiers.
5. Call the owner "you" in docs and cards, and "the owner" in reasons a seat reads (#362).
