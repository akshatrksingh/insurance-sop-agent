"""GR-lite pattern lists (SAFE-07): system probes, requests for other callers' data, harmful requests, self-harm.

Every pattern runs on text normalized by `allowlist.normalize` (lowercase, no punctuation).
Self-harm is listed first so it is never read as an attack.
"""

import re

SELF_HARM = 'self_harm'
SYSTEM_PROBE = 'system_probe'
OTHER_DATA = 'other_data'
HARMFUL = 'harmful'

_STRONG = r'(?:show|print|reveal|tell|give|display|repeat|share|read|leak|dump|output|send|what is|what are|whats)'
_WEAK = r'(?:show|print|reveal|repeat|display|leak|dump|output|share|read|recite)'
_ASK = r'(?:how (?:do|can) i|how to|help me|teach me|i want to|let me|i need to)'

PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (SELF_HARM, re.compile(
        r'\b(?:kill|hurt|harm|off)\s+(?:myself|my own life|my life)\b'
        r'|\bend my (?:own )?life\b(?!\s+(?:insurance|policy|policies|coverage|plan|cover))'
        r'|\b(?:i m|i am|i feel|i want|thinking about|thoughts of|commit)\b.{0,20}\bsuicid\w*'
        r'|\bwant to die\b|\bend it all\b|\bself harm\b|\bcut myself\b'
        r'|\b(?:do not|don t) want to (?:live|be alive)\b|\bno reason to live\b'
    )),
    (SYSTEM_PROBE, re.compile(
        rf'\b{_STRONG}\b.{{0,25}}\byour\s+(?:(?:system|hidden|initial|original)\s+)?'
        r'(?:prompt|config|configuration|source code)\b'
        rf'|\b{_WEAK}\b.{{0,25}}\byour\s+(?:(?:system|hidden|initial|original)\s+)?(?:rules|instructions)\b'
        r'(?!\s+(?:for|on|about|regarding|to)\b)'
        r'|\byour\s+(?:system|hidden|initial|original|secret)\s+(?:rules|instructions|prompt)\b'
        r'|\byour\s+(?:rules|instructions)\b.{0,15}\b(?:print|show|reveal|repeat|output)\s+(?:them|it|those|out)\b'
        rf'|\b{_STRONG}\b.{{0,25}}\bthe\s+(?:system|hidden|initial|original)\s+(?:prompt|instructions)\b'
        r'|\b(?:system|developer|hidden)\s+(?:prompt|message)\b.{0,20}\b(?:show|print|reveal|repeat|output)\b'
        r'|\b(?:show|print|reveal|repeat|output)\b.{0,20}\b(?:system|developer|hidden)\s+(?:prompt|message)\b'
        r'|\benv(?:ironment)?\s+(?:vars?|variables?)\b|\bdotenv\b|\bsecrets\s+toml\b'
        r'|\b(?:api|secret|access|auth|private)\s+(?:keys?|tokens?)\b'
        r'|\byour\s+(?:config|configuration|source code|database|backend)\b'
    )),
    (OTHER_DATA, re.compile(
        r'\b(?:other|another|different)\s+(?:customers?|callers?|policyholders?|clients?|users?)(?:\s+s)?\s+'
        r'(?:data|claims?|records?|info\w*|details|polic\w+|phone|email|address|ssn|accounts?|files?)\b'
        r'|\b(?:list|show|give|print|dump|export)\b.{0,15}\b(?:all|every|other)\s+(?:customers?|callers?|policyholders?|clients?|users?)\b'
        r'|\b(?:show|give|tell|list|print|get|read)\b.{0,20}\b(?:someone|somebody)\s+else\s+s\b.{0,20}'
        r'\b(?:claims?|data|records?|details|info\w*|policy|phone|email|address|ssn)\b'
        r'|\b(?:policyholder|customer)\s+(?:database|list|records?)\b'
    )),
    (HARMFUL, re.compile(
        r'\b(?:forge|falsify|fabricate|backdate)\b.{0,30}\b(?:documents?|claims?|records?|receipts?|signatures?|invoices?)\b'
        rf'|\b{_ASK}\b.{{0,15}}\b(?:fake|file a fake|file a fraudulent|submit a fraudulent)\b'
        rf'|\b{_ASK}\b.{{0,15}}\b(?:commit|get away with|do)\s+(?:insurance\s+)?(?:fraud|arson)\b'
        r'|\b(?:commit|committing)\s+(?:insurance\s+)?(?:fraud|arson)\b|\bdefraud\b|\blaunder\s+money\b'
        rf'|\b{_ASK}\b.{{0,15}}\b(?:hack|phish|spread malware|make ransomware)\b'
        rf'|\b{_ASK}\b.{{0,15}}\b(?:make|build|create)\b.{{0,10}}\b(?:bomb|explosive|weapon)s?\b'
        r'(?!\s+(?:claim|coverage|policy|rider))'
        rf'|\b(?:{_ASK}|i m going to|i will)\b.{{0,15}}\b(?:kill|murder)\s+(?:someone|somebody|him|her|them|my\s+\w+)\b'
        r'|\b(?:burn|torch|set fire to)\b.{0,20}\b(?:house|home|car|building)\b.{0,30}\b(?:insurance|claim|money)\b'
    )),
)
