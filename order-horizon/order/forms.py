from django.utils.translation import ugettext_lazy as _
from horizon import forms
from django.views.decorators.debug import sensitive_variables
from openstack_dashboard.api import order
class OrderFloatForm(forms.SelfHandlingForm):
    instance_id = forms.CharField(widget=forms.HiddenInput())
    ext_network=forms.ChoiceField(
        label=_("Floating Network"),
        widget=forms.ThemableSelectWidget(
            ))
    in_network=forms.ChoiceField(
        label=_("In Network"),
        widget=forms.ThemableSelectWidget(
            ))

    def __init__(self, request, *args, **kwargs):
        super(OrderFloatForm, self).__init__(request, *args, **kwargs)
        instance_id = kwargs.get('initial', {}).get('instance_id')

        self.fields['instance_id'].initial = instance_id

        data = order.order_float_network(request,instance_id)
        in_networks=data.get('in_network_id',[])
        order.get_networks(request)
        in_choices = [(network.get('id'), order.networks_dic[network.get('in_network')]) for network in in_networks]
        if in_choices:
            in_choices.insert(0, ("", _("Select Network")))
        else:
            in_choices.insert(0, ("", _("No Network available")))
        self.fields['in_network'].choices = in_choices

        ext_networks=data.get('ext_network_id',[])
        ext_choices = [(network.get('id'), network.get('name')) for network in ext_networks]
        if ext_choices:
            ext_choices.insert(0, ("", _("Select Floating Network")))
        else:
            ext_choices.insert(0, ("", _("No Floating Network available")))
        self.fields['ext_network'].choices = ext_choices

    def clean(self):
        cleaned_data = super(OrderFloatForm, self).clean()
        return cleaned_data
    @sensitive_variables('data')
    def handle(self, request, data):
        instance = data.get('instance_id')
        in_network = data.get('in_network')
        ext_network = data.get('ext_network')
        data=order.order_bind_float(request,order_id=instance,network_id=in_network,ext_network_id=ext_network)
        if data.get('status',100)==201:
            return True
        else:
            return False

class Disassociate(forms.SelfHandlingForm):
    instance_id = forms.CharField(widget=forms.HiddenInput())

    def __init__(self, request, *args, **kwargs):
        super(Disassociate, self).__init__(request, *args, **kwargs)
        instance_id = kwargs.get('initial', {}).get('instance_id')
    def clean(self):
        cleaned_data = super(Disassociate, self).clean()
        return cleaned_data
    def handle(self, request, data):
        instance = data.get('instance_id')
        return False