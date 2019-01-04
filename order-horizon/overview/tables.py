from openstack_dashboard import api
from openstack_dashboard.usage import quotas
from openstack_dashboard.usage.tables import BaseUsageTable
from horizon import tables
from horizon.utils import filters
from django import urls
from django.utils.translation import ugettext_lazy as _
import datetime
from openstack_dashboard.usage.base import BaseUsage
class GlobalUsage(BaseUsage):
    show_deleted = True

    def get_usage_list(self, start, end):
        return api.nova.usage_list(self.request, start, end)
def get_instance_link(datum):
    view = "horizon:project:instances:detail"
    if datum.get('instance_id', False):
        return urls.reverse(view, args=(datum.get('instance_id'),))
    else:
        return None
class CSVSummary(tables.LinkAction):
    name = "csv_summary"
    verbose_name = _("Download CSV Summary")
    icon = "download"

    def get_link_url(self, usage=None):
        return self.table.kwargs['usage'].csv_link()
class ProjectUsageTable(BaseUsageTable):
    instance = tables.Column('name',
                             verbose_name=_("Instance Name"),
                             link=get_instance_link)
    uptime = tables.Column('uptime_at',
                           verbose_name=_("Time since created"),
                           filters=(filters.timesince_sortable,),
                           attrs={'data-type': 'timesince'})

    def get_object_id(self, datum):
        return datum.get('instance_id', id(datum))

    class Meta(object):
        name = "project_usage"
        hidden_title = False
        verbose_name = _("Usage")
        # columns = ("instance", "vcpus", "disk", "memory", "uptime")
        columns = ("instance", "vcpus", "disk", "memory", "uptime")
        table_actions = (CSVSummary,)
        multi_select = False

class ProjectUsage(BaseUsage):
    attrs = ('memory_mb', 'vcpus', 'uptime',
             'hours', 'local_gb')

    def __init__(self, request, project_id=None):
        super(ProjectUsage, self).__init__(request, project_id)
        self.limits = {}
        self.quotas = {}

    def get_usage_list(self, start, end):
        show_deleted = self.request.GET.get('show_deleted',
                                            self.show_deleted)
        instances = []
        deleted_instances = []
        usage = api.nova.usage_get(self.request, self.project_id, start, end)
        # Attribute may not exist if there are no instances
        if hasattr(usage, 'server_usages'):
            now = self.today
            for server_usage in usage.server_usages:
                # This is a way to phrase uptime in a way that is compatible
                # with the 'timesince' filter. (Use of local time intentional.)
                server_uptime = server_usage['uptime']
                total_uptime = now - datetime.timedelta(seconds=server_uptime)
                server_usage['uptime_at'] = total_uptime
                if server_usage['ended_at'] and not show_deleted:
                    deleted_instances.append(server_usage)
                else:
                    instances.append(server_usage)
        usage.server_usages = instances
        return (usage,)

    def get_limits(self):
        data = quotas.tenant_quota_usages(self.request)
        self.limits=data
