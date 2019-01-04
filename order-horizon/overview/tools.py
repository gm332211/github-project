from django import template
register = template.Library()
@register.filter
def network_format(resource):
    count = 0
    if resource:
        networks=resource.get('network',[])
        for key in networks:
            count+=int(networks.get(key,0))
    return count