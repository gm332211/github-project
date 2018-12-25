# Copyright 2012 Nebula, Inc.

#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

from django.urls import reverse
from django.utils.translation import ugettext_lazy as _
from django.views.decorators.debug import sensitive_variables
from neutronclient.common import exceptions as neutron_exc

from horizon import exceptions
from horizon import forms
from horizon.utils import memoized
from horizon import workflows

from openstack_dashboard import api
from openstack_dashboard.api.order import order_float_network,order_network

class AssociateIPAction(workflows.Action):
    # use_required_attribute = False
    ext_network = forms.ThemableChoiceField(
        label=_("Float Network"),
    )
    in_network = forms.ThemableChoiceField(
        label=_("Inside Network")
    )
    class Meta(object):
        name = _("IP Address")
        help_text = _("Select the IP address you wish to associate with "
                      "the selected instance or port.")

    def __init__(self,request, context, *args, **kwargs):
        self.request = request
        self.context = context
        super(AssociateIPAction, self).__init__(
            request, context, *args, **kwargs)
        print(request.POST)
    def populate_in_network_choices(self, request, context):
        q_instance_id = self.request.GET.get('instance_id')
        targets = self._get_flaot_network(q_instance_id)
        networ_id_list = targets.get('in_network_id',[])
        print(networ_id_list)
        instances = sorted([(network_id, networ_id_list[network_id]) for network_id in networ_id_list],key=lambda x: x[1])
        # if instances:
        #     instances.insert(0, ("", _("Select an IP address")))
        # else:
        #     instances = [("", _("No floating IP addresses allocated"))]
        return instances
    def populate_ext_network_choices(self, request, context):
        q_instance_id = self.request.GET.get('instance_id')
        targets = self._get_flaot_network(q_instance_id)
        networ_id_list=self.get_float_id(targets)
        network_obj_list=[]
        for network_id in networ_id_list:
            network_obj_list.append(order_network(request,network_id))
        instances = sorted([(target.network_id, target.name) for target in network_obj_list],key=lambda x: x[1])
        # if instances:
        #     instances.insert(0, ("", _("Select an IP address")))
        # else:
        #     instances = [("", _("No floating IP addresses allocated"))]
        return instances
    def get_float_id(self,data):
        network_id_list=[]
        for network in data.get('ext_network_id',[]):
            network_id_list.append(network.get('id',None))
        return network_id_list
    @memoized.memoized_method
    def _get_flaot_network(self, instance_id=None):
        targets = {}
        try:
            if instance_id:
                targets = api.order.order_float_network(self.request, instance_id)
        except Exception:
            redirect = reverse('horizon:project:order:index')
            exceptions.handle(self.request,
                              _('Unable to retrieve order list.'),
                              redirect=redirect)
        return targets
class AssociateIP(workflows.Step):
    action_class = AssociateIPAction
    depends_on = ("in_network", "ext_network")
    contributes = ("in_network", "ext_network")

    def contribute(self, data, context):
        print(context)
        print(data)
        print(data.get('in_network'))
        context["in_network"]=data.get('in_network', None)
        context["ext_network"] = data.get('ext_network', None)
        print(context)
        return context


class IPAssociationWorkflow(workflows.Workflow):
    slug = "ip_association"
    name = _("Manage Floating Network Associations")
    finalize_button_name = _("Associate")
    success_message = _('Float Network %s associated.')
    failure_message = _('Unable to associate Float Network %s.')
    success_url = "horizon:project:order:index"
    default_steps = (AssociateIP,)

    def format_status_message(self, message):
        print(message)
        if "%s" in message:

            return message % self.context.get('ip_address',
                                              _('unknown IP address'))
        else:
            return message

    @sensitive_variables('context')
    def handle(self, request, context):
        print(context)
        # try:
        #     api.neutron.floating_ip_associate(request,
        #                                       data['ip_id'],
        #                                       data['instance_id'])
        # except neutron_exc.Conflict:
        #     msg = _('The requested instance port is already'
        #             ' associated with another floating IP.')
        #     exceptions.handle(request, msg)
        #     self.failure_message = msg
        #     return False
        #
        # except Exception:
        #     exceptions.handle(request)
        #     return False
        # return True
        return True
