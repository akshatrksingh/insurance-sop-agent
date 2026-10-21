"""Allowlist: whole-message phrases and claims vocabulary that are always in scope.

A message is allowlisted when it uses claims vocabulary, contains an identity value, or
consists only of greetings, goodbyes, thanks, yes or no, consent words, hesitation, or
process questions. The allowlist matches the whole message, so "hello, what is RL?" is not
allowlisted.
"""

import difflib
import re

from insurance_claims.identity_values import (
    ALWAYS_VALUE as IDENTITY_VALUE,
    CLAIM_REF,
    FILLER,
    LAST_FOUR_WORDS,
    cut,
    number_spans,
)

_STRONG = (
    r'claims?|polic(?:y|ies)|insur\w*|den(?:y|ied|ial|ying)|approv\w*|appeal\w*|deductibles?|'
    r'documents?|coverage|covered|adjusters?|reimburs\w*|premiums?|copays?|ssn|dob|birthday|'
    r'representative'
)
_AMBIGUOUS = r'status|agent|paid|payments?|benefits?'
STRONG_WORDS = re.compile(rf'\b(?:{_STRONG})\b', re.I)
CLAIMS_WORDS = re.compile(rf'\b(?:{_STRONG}|{_AMBIGUOUS})\b', re.I)
AMBIGUOUS_WORDS = re.compile(rf'\b(?:{_AMBIGUOUS})\b', re.I)
CLAIM_TARGETS = ('claim', 'claims', 'policy', 'insurance')
TYPO_STOP = frozenset({'clams', 'police', 'claimed'})
SHORT_OWN = re.compile(r'\bmy\s+(?:payments?|benefits?|status)\b|\bstatus of my application\b', re.I)
GREETINGS = (
    'hello there', 'hi there', 'hey there', 'hello', 'hi', 'hey', 'howdy', 'hiya', 'greetings',
    'good morning', 'good afternoon', 'good evening', 'good day', 'how are you doing',
    'how are you', 'how is it going', 'hope you are well', 'nice to meet you',
)
CLOSINGS = (
    'goodbye', 'bye bye', 'bye', 'see you later', 'see you', 'talk later', 'take care',
    'thank you very much', 'thank you so much', 'thank you', 'thanks a lot', 'thanks so much',
    'thanks', 'many thanks', 'much appreciated', 'appreciate it', 'cheers',
    'have a good day', 'have a nice day', 'have a great day',
)
ACKNOWLEDGEMENTS = (
    'that s fine', 'that is fine', 'i agree', 'agreed', 'got it', 'understood', 'makes sense',
    'right', 'correct', 'exactly', 'that works', 'fine', 'alright', 'all right', 'of course',
    'absolutely', 'definitely', 'i see', 'i understand', 'that s right', 'that is right',
    'that is correct', 'not really', 'i think so', 'i guess', 'no problem', 'no thanks',
    'no thank you',
)
WAITING = (
    'let me think', 'give me a second', 'give me a moment', 'let me check', 'let me see',
    'let me look', 'let me find it', 'let me get it', 'one second', 'a moment',
    'hold on a second', 'bear with me',
)
PROCESS_QUESTIONS = (
    'what happens next', 'what happens now', 'what is next', 'how long will this take',
    'how long does this take', 'how long', 'what should i do', 'what do i need to do',
    'what do i say', 'what information do you need', 'what else do you need',
    'do you need anything else', 'is that all', 'anything else', 'how do i do that',
    'where do i find that',
)
PLEASANTRY_PHRASES = (
    'yes', 'yeah', 'yep', 'no', 'nope', 'ok', 'okay', 'sure', 'go ahead', 'send it',
    'send summary', 'skip', 'skip it', 'that is fine', 'sounds good', 'please do',
    'i am not sure', 'i m not sure', 'not sure', 'i do not know', 'i don t know', 'hmm',
    'um', 'uh', 'maybe', 'wait', 'hold on', 'one moment', 'sorry', 'excuse me',
    'can you repeat that', 'could you repeat that', 'repeat that', 'say that again',
    'what do you need from me', 'what do you need', 'why do you need that',
    'why do you need this', 'is this ok', 'is this detail ok', 'is that ok', 'is that okay',
    'what do i do', 'what now', 'what next', 'how does this work', 'who are you',
    'i need help', 'can you help me', 'can you help', 'help me', 'help', 'please',
    'and', 'so', 'well', 'then', 'again',
)
_ALL = sorted(
    GREETINGS + CLOSINGS + ACKNOWLEDGEMENTS + WAITING + PROCESS_QUESTIONS + PLEASANTRY_PHRASES,
    key=len,
    reverse=True,
)
_PHRASES = re.compile(r'\b(?:' + '|'.join(re.escape(p) for p in _ALL) + r')\b')


def normalize(text: str) -> str:
    """Lowercase, drop punctuation, collapse spaces."""
    return ' '.join(re.sub(r'[^\w\s]', ' ', text.lower().replace("'", ' ')).split())


def phrases_only(text: str) -> bool:
    """True when the message is empty or made only of allowlisted phrases."""
    normalized = normalize(text)
    return not _PHRASES.sub(' ', normalized).strip()


def _typo_of_claims_word(text: str) -> bool:
    """True when a word is a close typo (ratio 0.8 or more, length within one) of claim, policy, insurance."""
    for word in re.findall(r'[a-z]{4,}', text.lower()):
        if word in CLAIM_TARGETS or word in TYPO_STOP:
            continue
        for target in CLAIM_TARGETS:
            close = abs(len(word) - len(target)) <= 1 and difflib.SequenceMatcher(None, word, target).ratio() >= 0.8
            if close:
                return True
    return False


def has_claims_vocab(text: str) -> bool:
    """True for a strong claims word (or a close typo of one), or an ambiguous one (status, agent, paid,
    payment, benefits) next to a claim reference such as CL- or POL-. A whole message of at most five
    words such as "my payments", "my status" or "status of my application" also counts."""
    if STRONG_WORDS.search(text) or _typo_of_claims_word(text):
        return True
    if AMBIGUOUS_WORDS.search(text) and CLAIM_REF.search(text):
        return True
    return bool(SHORT_OWN.search(text) and len(normalize(text).split()) <= 5)


def rest_is_filler(rest: str) -> bool:
    """True when what is left around an identity value is only identity filler or allowlisted phrases."""
    words = [w for w in normalize(rest).split() if w not in FILLER]
    return phrases_only(' '.join(words))


def has_identity_value(text: str) -> bool:
    """True when the message holds an email or claim reference, or a phone, date, or bare 4-digit number
    that is the whole answer (only filler around it) or is called the last four, SSN, or ID."""
    if IDENTITY_VALUE.search(text):
        return True
    spans = number_spans(text)
    if not spans:
        return False
    rest = cut(text, spans)
    return rest_is_filler(rest) or bool(LAST_FOUR_WORDS.search(rest))


def is_allowlisted(text: str) -> bool:
    """Return True when the whole message is always in scope.

    Args:
        text: The caller's message.

    Returns:
        True for claims vocabulary, an identity value, or only pleasantry and process phrases.
    """
    if has_claims_vocab(text) or has_identity_value(text):
        return True
    normalized = normalize(text)
    return bool(normalized) and phrases_only(text)


def kind(text: str) -> str:
    """Classify a message as `greeting`, `closing`, or `other` (whole-message match).

    Args:
        text: The caller's message.

    Returns:
        `closing` when it holds a goodbye or thanks and nothing off-topic, `greeting` when it
        holds a greeting, else `other`.
    """
    normalized = normalize(text)
    if not is_allowlisted(text) or has_claims_vocab(text):
        return 'other'
    if any(re.search(rf'\b{re.escape(p)}\b', normalized) for p in CLOSINGS):
        return 'closing'
    if any(re.search(rf'\b{re.escape(p)}\b', normalized) for p in GREETINGS):
        return 'greeting'
    return 'other'
