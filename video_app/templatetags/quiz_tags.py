# video_app/templatetags/quiz_tags.py
from django import template

register = template.Library()


@register.filter
def get_item(dictionary, key):
    """Get an item from a dict by key."""
    if isinstance(dictionary, dict):
        return dictionary.get(key)
    return None


@register.filter
def option_pairs(question):
    """Return list of (letter, text) tuples for all non-empty options."""
    return question.get_options()


@register.filter
def is_correct_answer(question, letter):
    """Return True if letter is in the question correct_answers list."""
    return question.is_answer_correct(letter)


@register.filter
def join_list(lst, sep=", "):
    """Join a list with separator."""
    if not lst:
        return ""
    return sep.join(str(x) for x in lst)
