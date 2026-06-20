from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    if hasattr(dictionary, 'get'):
        return dictionary.get(key)
    if isinstance(dictionary, (list, tuple)):
        try:
            return dictionary[int(key)]
        except (IndexError, ValueError, TypeError):
            return None
    return None

@register.filter
def cumplio_todos(items):
    """Returns True if all items have puntaje > 0 (cumplieron todos)"""
    if not items:
        return False
    return all(item.puntaje > 0 for item in items)
