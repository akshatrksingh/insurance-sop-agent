"""Vocabulary for outcome and action claims (CASE-01). Used by grounding.py."""

import re

# Vocabulary for outcome and action claims. The agent has no outcome data and cannot act, so any match
# must appear word for word in the bundle (claim data or matched guidance text), else the reply is rejected.
ACTION_VERBS = (
    r"(?:fil(?:e|ed|ing)|submit(?:ted|ting)?|re-?open(?:ed|ing)?|reinstat(?:e|ed|ing)|escalat(?:e|ed|ing)"
    r"|forward(?:ed|ing)?|send|sent|sending|review(?:ed|ing)?|process(?:ed|ing)?|updat(?:e|ed|ing)"
    r"|start(?:ed|ing)?|re-?submit(?:ted)?|appeal(?:ed)?|call(?:ed|ing)?|phone|email(?:ed)?|contact(?:ed)?"
    r"|follow(?:ed)? up|expedit(?:e|ed)|waiv(?:e|ed)|approv(?:e|ed)|arrang(?:e|ed)|schedul(?:e|ed)"
    r"|open(?:ed)?|take care|look into|handl(?:e|ed)|flag(?:ged)?|request(?:ed)?|investigat(?:e|ed)"
    r"|overturn(?:ed)?|reimburs(?:e|ed)|pay|paid|refund(?:ed)?|text(?:ed)?)"
)
PASSIVE_RESULTS = (
    r"(?:approved|overturned|granted|accepted|paid|reimbursed|reinstated|reopened|reversed|covered|honou?red"
    r"|processed|resolved|filed|submitted|escalated|forwarded|sent|opened|updated|resubmitted|started"
    r"|reviewed|waived|refunded|expedited|scheduled)"
)
_NEG = (
    r"(?:(?:will|would|should|could|can|may|might|shall|is|are|was|were|has|have|had|does|do|did)\s+not|cannot|can\s?not"
    r"|can't|cant|won't|wont|wouldn't|wouldnt|couldn't|shouldn't|isn't|aren't|wasn't|weren't|hasn't|haven't|hadn't"
    r"|doesn't|doesnt|don't|dont|didn't|never)"
)
_LIKELY = r"(?:(?:is|are|was|were|be|will be|looks?|seems?)\s+)?(?:very |highly |most |more )?(?:likely|unlikely|going|expected|sure|certain|bound|set|able)\s+to"
_PARTY = r"(?:a|an|the|your|one of our|our)?\s*(?:supervisor|manager|someone|somebody|representative|specialist|adjuster|agent|team|colleague)"
ACTION_CLAIMS = (
    # Negative forms: "will not be approved", "cannot be reopened", "won't be paid", "cannot file", "I can't reopen"
    re.compile(rf"\b{_NEG}\s+(?:be\s+|been\s+|being\s+)?{PASSIVE_RESULTS}\b", re.I),
    # A first person refusal such as "I cannot file appeals" is safe; any other subject is flagged.
    re.compile(rf"(?<!\bi )(?<!\bwe )\b{_NEG}\s+{ACTION_VERBS}\b", re.I),
    re.compile(rf"\b(?:is|are|was|were)\s+(?:not\s+|n't\s+)?(?:going|able)\s+to\s+(?:be\s+)?(?:{PASSIVE_RESULTS}|{ACTION_VERBS})\b", re.I),
    # Likelihood: "is likely to be approved", "is unlikely to be approved", "expected to be paid"
    re.compile(rf"\b{_LIKELY}\s+(?:be\s+|been\s+)?(?:{PASSIVE_RESULTS}|{ACTION_VERBS})\b", re.I),
    # "will be approved", "can be reopened", "was filed", "has been submitted"
    re.compile(
        rf"\b(?:will|would|should|could|can|may|might|shall|was|were|is|are|has been|have been|had been|gets?|got)"
        rf"(?:\s+(?:very|most|more)?\s*(?:likely|probably|definitely|certainly|already|then))*\s+(?:be\s+|been\s+|being\s+)?{PASSIVE_RESULTS}\b",
        re.I,
    ),
    # "reimbursed in full", "full reimbursement", "paid in full", "guaranteed", "guarantee"
    re.compile(r"\b(?:reimbursed|paid|refunded|covered) in full\b|\bfull (?:reimbursement|refund|coverage|payment)\b|\bguarantee[sd]?\b", re.I),
    # "I have filed", "I will submit", "we will review", "I'll file", "we can reopen"
    re.compile(
        rf"\b(?:i|we)(?:'ll|'ve|\s+(?:will|shall|can|am going to|are going to|have|had|am|are|just|already))?"
        rf"(?:\s+(?:already|just|now|also|then|will|can))*\s+{ACTION_VERBS}\b",
        re.I,
    ),
    # "someone will call you", "a supervisor will contact you", "your representative will follow up"
    re.compile(
        rf"\b{_PARTY}\b[^.?!]{{0,30}}?\b(?:will|shall|is going to|are going to|would|can)\s+"
        rf"(?:also\s+)?(?:call|contact|reach|phone|email|follow up|get back|be in touch|text|review|look|file|submit|reopen)\b",
        re.I,
    ),
    # "a callback", "call you back", "will call", "will get back to you"
    re.compile(
        r"\bcall[ -]?backs?\b|\bcall(?:s|ed)? you\b|\b(?:will|shall) (?:call|contact|reach out|get back|follow up|be in touch|email|text)\b",
        re.I,
    ),
)
