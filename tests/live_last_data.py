"""Scripted conversations for live_last.py (not collected by pytest)."""
from live_final_data import DEMO, DONE

WC = 'Who won the 2018 world cup?'
MARS = 'What is the status of the Mars mission?'
# letter: (title, caller messages, check name)
CONVS = {
    'a': ('a world cup three times then yes', [WC, WC, WC, 'yes'], 'strikes'),
    'b': ('b Mars mission three times then yes', [MARS, MARS, MARS, 'yes'], 'strikes'),
    'c': ('c email yes', [DEMO, DONE, 'yes'], 'send'),
    'd': ('d email no thanks', [DEMO, DONE, 'no thanks'], 'skip'),
}
