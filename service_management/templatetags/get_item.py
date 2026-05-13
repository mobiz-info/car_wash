from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)

@register.filter
def concat(arg1, arg2):
    return str(arg1) + str(arg2)