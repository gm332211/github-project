import logging
from django.conf import settings
from django import urls
from django import template
from django.utils.translation import npgettext_lazy
from django.utils.translation import string_concat
from django.utils.translation import ugettext_lazy as _
from django.utils.translation import ungettext_lazy
from django.utils.http import urlencode
from django.http import HttpResponse
from horizon import tables
from openstack_dashboard import api
from openstack_dashboard.api import order
from openstack_dashboard import policy
from openstack_dashboard.dashboards.project.order.workflows \
    import update_instance
from openstack_dashboard.dashboards.project.floating_ips import workflows
LOG = logging.getLogger(__name__)
ACTIVE_STATES = ("ACTIVE",)
POWER_STATES = {
    0: "NO STATE",
    1: "RUNNING",
    2: "BLOCKED",
    3: "PAUSED",
    4: "SHUTDOWN",
    5: "SHUTOFF",
    6: "CRASHED",
    7: "SUSPENDED",
    8: "FAILED",
    9: "BUILDING",
}
def is_deleting(instance):
    task_state = getattr(instance, "OS-EXT-STS:task_state", None)
    if not task_state:
        return False
    return task_state.lower() == "deleting"
def get_power_state(instance):
    return POWER_STATES.get(getattr(instance, "OS-EXT-STS:power_state", 0), '')

def get_inetwork(order):
    template_name = 'project/order/_order_network.html'
    context = {
        "networks": order.internal_network_name,
    }
    return template.loader.render_to_string(template_name, context)

def get_enetwork(order):
    template_name = 'project/order/_order_network.html'
    context = {
        "networks": order.extenal_network_name,
    }
    return template.loader.render_to_string(template_name, context)
class MyFilterAction(tables.FilterAction):
    name = "myfilter"
class LaunchLink(tables.LinkAction):
    name = "launch"
    verbose_name = _("Launch Order")
    url = "horizon:project:order:launch"
    classes = ("ajax-modal", "btn-launch")
    icon = "cloud-upload"
    policy_rules = (("compute", "os_compute_api:servers:create"),)
    ajax = True
    def __init__(self, attrs=None, **kwargs):
        kwargs['preempt'] = True
        super(LaunchLink, self).__init__(attrs, **kwargs)
    def allowed(self, request, datum):
        return True
    def single(self, table, request, object_id=None):
        self.allowed(request, None)
        return HttpResponse(self.render(is_table_action=True))
class LaunchLinkNG(LaunchLink):
    name = "launch-ng"
    url = "horizon:project:order:index"
    ajax = False
    classes = ("btn-launch", )

    def get_default_attrs(self):
        url = urls.reverse(self.url)
        ngclick = "modal.openLaunchInstanceWizard(" \
            "{ successUrl: '%s' })" % url
        self.attrs.update({
            'ng-controller': 'LaunchInstanceModalController as modal',
            'ng-click': ngclick
        })
        return super(LaunchLinkNG, self).get_default_attrs()

    def get_link_url(self, datum=None):
        return "javascript:void(0);"
class DeleteOrder(tables.DeleteAction):
    policy_rules = (("compute", "os_compute_api:servers:delete"),)
    help_text = _("Deleted instances are not recoverable.")
    @staticmethod
    def action_present(count):
        return ungettext_lazy(
            u"Delete Order",
            u"Delete Orders",
            count
        )
    @staticmethod
    def action_past(count):
        return ungettext_lazy(
            u"Scheduled deletion of Instance",
            u"Scheduled deletion of Instances",
            count
        )
    def allowed(self, request, instance=None):
        error_state = False
        if instance:
            error_state = (instance.status == 'ERROR')
        return error_state or not is_deleting(instance)

    def action(self, request, obj_id):
        try:
            api.order.order_delete(request, obj_id)
        except Exception as e:
            pass
class StartInstance(tables.BatchAction):
    name = "start"
    classes = ('btn-confirm',)

    @staticmethod
    def action_present(count):
        return ungettext_lazy(
            u"Start Order",
            u"Start Order",
            count
        )

    @staticmethod
    def action_past(count):
        return ungettext_lazy(
            u"Started Order",
            u"Started Order",
            count
        )

    def allowed(self, request, instance):
        return ((instance.status == 'stoping'))

    def action(self, request, obj_id):
        api.order.order_action(request, obj_id,'start')
class StopInstance(tables.BatchAction):
    name = "stop"
    policy_rules = (("compute", "os_compute_api:servers:stop"),)
    help_text = _("The instance(s) will be shut off.")
    action_type = "danger"

    @staticmethod
    def action_present(count):
        return npgettext_lazy(
            "Action to perform (the instance is currently running)",
            u"Shut Off Order",
            u"Shut Off Order",
            count
        )

    @staticmethod
    def action_past(count):
        return npgettext_lazy(
            "Past action (the instance is currently already Shut Off)",
            u"Shut Off Order",
            u"Shut Off Order",
            count
        )

    def allowed(self, request, instance):
        return ((instance.status == 'created'))

    def action(self, request, obj_id):
        api.order.order_action(request, obj_id,'stop')
class RebootInstance(tables.BatchAction):
    name = "reboot"
    classes = ('btn-reboot',)
    help_text = _("Restarted instances will lose any data"
                  " not saved in persistent storage.")
    action_type = "danger"

    @staticmethod
    def action_present(count):
        return ungettext_lazy(
            u"Hard Reboot Order",
            u"Hard Reboot Order",
            count
        )

    @staticmethod
    def action_past(count):
        return ungettext_lazy(
            u"Hard Rebooted Order",
            u"Hard Rebooted Order",
            count
        )

    def allowed(self, request, instance=None):
        if instance is not None:
            return ((not instance.status == 'dead' and not instance.status=='wait'))
        else:
            return True

    def action(self, request, obj_id):
        api.order.order_action(request, obj_id, 'reboot')
class RebuildInstance(tables.BatchAction):
    name = "rebuild"
    verbose_name = _("Rebuild Order")
    help_text = _("Restarted order will lose any data"
                  " not saved in persistent storage.")
    action_type = "danger"

    @staticmethod
    def action_present(count):
        return npgettext_lazy(
            "Action to perform (the instance is currently running)",
            u"Rebuild Off Order",
            u"Rebuild Off Order",
            count
        )

    @staticmethod
    def action_past(count):
        return npgettext_lazy(
            "Past action (the instance is currently already DisBind Off)",
            u"Rebuild Off Order",
            u"Rebuild Off Order",
            count
        )

    def allowed(self, request, instance):
        return ((instance.status == 'created'))

    def action(self, request, obj_id):
        api.order.order_action(request,obj_id,'rebuild')
class AssociateIP(tables.LinkAction):
    name = "associate"
    verbose_name = _("Associate Floating Network")
    classes = ("ajax-modal",)
    url = "horizon:project:order:associate"
    icon = "link"
    def allowed(self, request, instance):
        if not api.base.is_service_enabled(request, 'network'):
            return False
        if not api.neutron.floating_ip_supported(request):
            return False
        if api.neutron.floating_ip_simple_associate_supported(request):
            return False
        if instance.status=='wait' and not instance.extenal_network_name[0]:
            return True
        else:
            return False
    def get_link_url(self, datum):
        instance_id = self.table.get_object_id(datum)
        return urls.reverse(self.url, args=[instance_id])
class DisassociateIP(tables.BatchAction):
    name = "DisassociateIP"
    help_text = _("Restarted order will lose any data"
                  " not saved in persistent storage.")
    action_type = "danger"

    @staticmethod
    def action_present(count):
        return npgettext_lazy(
            "Action to perform (the instance is currently running)",
            u"DisBind Off Order",
            u"DisBind Off Order",
            count
        )

    @staticmethod
    def action_past(count):
        return npgettext_lazy(
            "Past action (the instance is currently already DisBind Off)",
            u"DisBind Off Order",
            u"DisBind Off Order",
            count
        )

    def allowed(self, request, instance):
        if not api.base.is_service_enabled(request, 'network'):
            return False
        if instance.status=='wait' and instance.extenal_network_name[0]:
            return True
        # if not api.neutron.floating_ip_supported(request):
        #     return False
        # for addresses in instance.addresses.values():
        #     for address in addresses:
        #         if address.get('OS-EXT-IPS:type') == "floating":
        #             return not is_deleting(instance)
        return False

    def action(self, request, obj_id):
        api.order.order_disbind_float(request,obj_id)

def get_server_detail_link(obj,request):
    return "/auth/switch/%s/?next=/project/instances/"%obj.project_id
class OrderTable(tables.DataTable):
    name = tables.Column('name',
                         link=get_server_detail_link,
                         verbose_name=_("Name"))
    image_name = tables.Column('image_name',
                               verbose_name=_("Image Name"))
    internal_network = tables.Column(get_inetwork,
                               verbose_name=_("Intranet"))
    extenal_network = tables.Column(get_enetwork,
                               verbose_name=_("Floating network"))
    flavor_name = tables.Column('flavor_name',
                               verbose_name=_("Flavor"))
    create_count = tables.Column('count',
                           verbose_name=_("Create Count"))
    start_time = tables.Column('start_time',
                           verbose_name=_("Start Time"))
    stop_time = tables.Column('stop_time',
                           verbose_name=_("Stop Time"))
    status = tables.Column('status',
                           verbose_name=_("Status"))
    class Meta(object):
        name = "order"
        verbose_name = _("Order")

        launch_actions = ()
        # if getattr(settings, 'LAUNCH_INSTANCE_LEGACY_ENABLED', False):
        launch_actions = (LaunchLink,) + launch_actions
        # if getattr(settings, 'LAUNCH_INSTANCE_NG_ENABLED', True):
        #     launch_actions = (LaunchLinkNG,) + launch_actions
        table_actions = launch_actions+(DeleteOrder,)
        # table_actions_menu = (StartInstance, StopInstance, RebootInstance)
        row_actions=(RebuildInstance,AssociateIP,DisassociateIP,StartInstance,StopInstance,RebootInstance)