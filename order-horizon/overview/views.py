# Copyright 2012 United States Government as represented by the
# Administrator of the National Aeronautics and Space Administration.
# All Rights Reserved.
#
# Copyright 2012 Nebula, Inc.
#
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
from django.template.defaultfilters import capfirst
from django.template.defaultfilters import floatformat
from django.utils.translation import ugettext_lazy as _

from horizon.utils import csvbase
from horizon import views

from openstack_dashboard import usage
from openstack_dashboard.dashboards.project.overview import tables
from openstack_dashboard.dashboards.project.overview import tools
from openstack_dashboard.dashboards.project.instances \
    import tables as project_tables
from openstack_dashboard.utils import filters
from openstack_dashboard.api.order import order_hypervisor
class ProjectUsageCsvRenderer(csvbase.BaseCsvResponse):

    columns = [_("Instance Name"), _("VCPUs"), _("RAM (MB)"),
               _("Disk (GB)"), _("Usage (Hours)"),
               _("Time since created (Seconds)"), _("State")]

    def get_row_data(self):

        choices = project_tables.STATUS_DISPLAY_CHOICES
        for inst in self.context['usage'].get_instances():
            state_label = (
                filters.get_display_label(choices, inst['state']))
            yield (inst['name'],
                   inst['vcpus'],
                   inst['memory_mb'],
                   inst['local_gb'],
                   floatformat(inst['hours'], 2),
                   inst['uptime'],
                   capfirst(state_label))
class ProjectOverview(usage.ProjectUsageView):
    table_class = tables.ProjectUsageTable
    usage_class = tables.ProjectUsage
    template_name = 'project/overview/usage.html'
    # csv_response_class = ProjectUsageCsWvRenderer

    def get_data(self):
        super(ProjectOverview, self).get_data()
        return self.usage.get_instances()
    def get_resource(self):
        start = self.request.GET.get('start')
        end = self.request.GET.get('end')
        if not start and not end:
            start = self.request.GET.get('start', self.request.session.get('usage_start'))
            end = self.request.GET.get('end', self.request.session.get('usage_end'))
        start=start+' 00:00'
        end = end + ' 23:59'
        return order_hypervisor(self.request,start,end)
    def get_context_data(self, **kwargs):
        context = super(ProjectOverview, self).get_context_data(**kwargs)
        context['simple_tenant_usage_enabled'] = True
        data=self.get_resource()
        context['total_resource']=data.get('total_resource',None)
        context['free_resource'] = data.get('free_resource', None)
        context['total_port'] = tools.network_format(data.get('total_resource', None))
        context['free_port'] = tools.network_format(data.get('free_resource', None))
        return context
class WarningView(views.HorizonTemplateView):
    template_name = "project/_warning.html"
