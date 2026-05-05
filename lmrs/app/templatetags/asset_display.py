from django import template
import re

register = template.Library()


@register.filter
def display_filename(value):
    if not value:
        return ""

    filename = str(value).split("/")[-1]
    match = re.match(r"^(?P<base>.+)_(?P<rand>[A-Za-z0-9]{7})(?P<ext>\.[^.]+)$", filename)
    if match:
        return f"{match.group('base')}{match.group('ext')}"

    return filename
