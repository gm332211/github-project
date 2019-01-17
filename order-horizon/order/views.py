# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
from django.views import generic
from django.utils.translation import ugettext_lazy as _
from horizon import tabs
from horizon.utils import memoized
from django.conf import settings
from horizon import workflows
from openstack_dashboard.dashboards.project.order import tabs as order_tabs
from openstack_dashboard.dashboards.project.order import workflows as project_workflows
from django.urls import reverse_lazy
from openstack_dashboard.dashboards.project.order \
    import forms as project_forms
from horizon import forms
class IndexView(tabs.TabbedTableView):
    tab_group_class = order_tabs.OrderTabs
    template_name = 'project/order/index.html'

    def get_data(self, request, context, *args, **kwargs):
        # Add data to the context here...
        print('test')
        return context
class LaunchOrderView(workflows.WorkflowView):
    workflow_class = project_workflows.LaunchOrder

    def get_initial(self):
        initial = super(LaunchOrderView, self).get_initial()
        initial['project_id'] = self.request.user.tenant_id
        initial['start_time']=self.kwargs.get('start_time',None)
        initial['stop_time'] = self.kwargs.get('stop_time', None)
        initial['user_id'] = self.request.user.id
        defaults = getattr(settings, 'LAUNCH_INSTANCE_DEFAULTS', {})
        initial['config_drive'] = defaults.get('config_drive', False)
        return initial
class BindFloatView(forms.ModalFormView):
    form_class = project_forms.OrderFloatForm
    template_name = 'project/order/bindfloat.html'
    success_url = reverse_lazy('horizon:project:order:index')
    page_title = _("Bind Float")
    submit_label = page_title

    def get_context_data(self, **kwargs):
        context = super(BindFloatView, self).get_context_data(**kwargs)
        context['instance_id'] = self.kwargs['instance_id']
        return context
    @memoized.memoized_method
    def get_object(self, *args, **kwargs):
        pass
    def get_initial(self,*args,**kwargs):
        initial = {'instance_id': self.kwargs['instance_id']}
        return initial
class OrderTimeView(forms.ModalFormView):
    form_class = project_forms.OrderTimeForm
    template_name = 'project/order/ordertime.html'
    # success_url = reverse_lazy('horizon:project:order:launch',kwargs=self.kwargs)
    page_title = _("Order Time")
    submit_label = _(" Next Step")
    def get_initial(self,*args,**kwargs):
        pass
    def get_success_url(self):
        start_time=self.request.POST.get('start_time',None)
        stop_time = self.request.POST.get('stop_time', None)
        if start_time and stop_time:
            return reverse_lazy('horizon:project:order:launch',kwargs={'start_time':start_time,'stop_time':stop_time})
        else:
            return reverse_lazy('horizon:project:order:ordertime')
