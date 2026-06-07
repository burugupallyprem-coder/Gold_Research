"""
learning/ — the self-learning, human-in-the-loop layer.

Nothing in here changes the trading strategy on its own. It records the bot's
own trades, measures how the live paper account actually performed, and PROPOSES
changes that a human applies via apply_change.py. See LEARNING.md.
"""
