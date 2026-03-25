from django import template
from tasks.models import GCAL_COLOR_HEX

register = template.Library()


@register.filter
def color_hex(color_id):
    return GCAL_COLOR_HEX.get(str(color_id), '#039BE5')
