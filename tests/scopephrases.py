"""Phrase lists for the off-topic rule tests."""

IN_SCOPE = [
    'hello', 'Hello!', 'hi', 'hey', 'hi there', 'hello there', 'hey there', 'greetings', 'good morning', 'good afternoon',
    'good evening', 'howdy', 'hi, how are you?', 'hello how are you',
    'bye', 'goodbye', 'thanks bye', 'see you later', 'have a nice day',
    'thanks', 'thank you', 'thank you very much', 'thanks a lot', 'ok thanks', 'much appreciated',
    'yes', 'no', 'yeah', 'nope', 'ok', 'okay', 'sure', 'go ahead', "that's fine", 'I agree', 'sounds good',
    "I'm not sure", 'hmm', 'um', 'let me think', 'wait', 'give me a second', "I don't know", 'let me check',
    'is this detail ok?', 'can you repeat that?', 'what do you need from me?', 'why do you need that?', 'how does this work?',
    'what happens next?', 'how long will this take?',
    'my claim thing is stuck', 'the healthcare denial letter I got', 'wats the status of my clam', 'whats my claim at',
    'hello, my name is Margaret Chen', 'hi, my birthday is 1985-03-15',
    '1985-03-15', '650-521-2836', 'margaret@email.com', '4472',
]
OFF_TOPIC = ['what is RL?', 'explain machine learning', 'write me a python script', 'tell me a joke',
             'who won the game last night', 'hello, what is RL?']
IDENTITY_EXTRACTION = {
    'hello, my name is Margaret Chen': {'full_name': 'Margaret Chen'}, 'hi, my birthday is 1985-03-15': {'dob': '1985-03-15'},
    '1985-03-15': {'dob': '1985-03-15'}, '650-521-2836': {'phone': '650-521-2836'},
    'margaret@email.com': {'email': 'margaret@email.com'}, '4472': {'id_last4': '4472'},
}
PLEASANTRIES = ['hello', 'thanks', "I'm not sure", 'is this detail ok?']
