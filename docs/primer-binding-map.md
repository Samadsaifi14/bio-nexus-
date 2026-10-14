# Exact primer-binding workspace

The sequence workspace now maps two 5′→3′ DNA primers onto the supplied linear or circular template through `POST /api/seq-tools/primer-binding-map`. This independently implements the primer-binding workspace acceptance item in the competitor capability audit. It does not reconstruct a commercial algorithm.

Biopython `Seq.reverse_complement` supplies reverse-strand identity; exact full-length substring matching supplies sites. Both primers are checked in both orientations, including overlapping exact matches. Palindromic primers retain both physical orientations. Inward-facing non-overlapping sites from different primers form candidate linear products, including reversed primer labels. Circular products cross the origin when applicable and cannot exceed one template turn. Product sizes include both primer-binding regions.

Coordinates are 1-based inclusive on the displayed forward strand. Strand +1 extends toward increasing coordinates; strand -1 extends toward decreasing coordinates. A circular start greater than end crosses the origin. The API records the actual 3′ position, normalized template SHA-256, primer sequences, parameters, method/engine/version, product sequence SHA-256 and explicit assumptions. No candidate product returns a diagnostic rather than an invented result.

Users can export the scientific evidence JSON or the supplied DNA as GenBank with all exact `primer_bind` features. Existing GenBank coordinate validation and Biopython export handle origin-spanning and reverse-strand features. Changing template, topology, primers or product bounds clears results and rejects stale responses.

Limits: unambiguous A/C/G/T only; 200,000 template bases; 4–200 bases per primer; at most 200 binding orientations and 100 products. Exceeding a limit fails explicitly rather than silently truncating evidence. Mismatched primers, degenerate oligos, 5′ tails, genome-wide specificity, thermodynamic suitability and experimental PCR success are outside this calculation. Primer3 QC remains a separate existing capability.

Source: [Biopython sequence documentation](https://biopython.org/wiki/Seq). No dependencies were added.

Validation: 44 selected backend tests passed, including nonpalindromic reverse binding, primer-label reversal, circular rotation invariance, origin-crossing binding/product coordinates, independently specified product sequence hashes, GenBank feature extraction round trips, range filters, ambiguous/invalid inputs and output-limit failures, plus existing restriction/annotation/sequence utility regressions. Frontend TypeScript and production-build results are recorded in the implementation release. No authenticated production backend deployment or experimental PCR validation is claimed.
