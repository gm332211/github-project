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

import json
import logging
import operator

from oslo_utils import units
import six

from django.template.defaultfilters import filesizeformat
from django.utils.text import normalize_newlines
from django.utils.translation import ugettext_lazy as _
from django.views.decorators.debug import sensitive_variables

from horizon import exceptions
from horizon import forms
from horizon.utils import functions
from horizon.utils import memoized
from horizon.utils import validators
from horizon import workflows

from openstack_dashboard import api
from openstack_dashboard.api import base
from openstack_dashboard.api import cinder
from openstack_dashboard.api import nova
from openstack_dashboard.api import order
from openstack_dashboard.usage import quotas

from openstack_dashboard.dashboards.project.images.images \
    import tables as image_tables
from openstack_dashboard.dashboards.project.images \
    import utils as image_utils
from openstack_dashboard.dashboards.project.instances \
    import utils as instance_utils


LOG = logging.getLogger(__name__)


class SelectProjectUserAction(workflows.Action):
    project_id = forms.ThemableChoiceField(label=_("Project"))
    user_id = forms.ThemableChoiceField(label=_("User"))

    def __init__(self, request, *args, **kwargs):
        super(SelectProjectUserAction, self).__init__(request, *args, **kwargs)
        # Set our project choices
        projects = [(tenant.id, tenant.name)
                    for tenant in request.user.authorized_tenants]
        self.fields['project_id'].choices = projects

        # Set our user options
        users = [(request.user.id, request.user.username)]
        self.fields['user_id'].choices = users

    class Meta(object):
        name = _("Project & User")
        # Unusable permission so this is always hidden. However, we
        # keep this step in the workflow for validation/verification purposes.
        permissions = ("!",)


class SelectProjectUser(workflows.Step):
    action_class = SelectProjectUserAction
    contributes = ("project_id", "user_id")
class SetInstanceDetailsAction(workflows.Action):
    availability_zone = forms.ThemableChoiceField(label=_("Availability Zone"),
                                                  required=False)

    name = forms.CharField(label=_("Instance Name"),
                           max_length=255)

    flavor = forms.ThemableChoiceField(label=_("Flavor"),
                                       help_text=_("Size of image to launch."))

    count = forms.IntegerField(label=_("Number of Instances"),
                               min_value=1,
                               initial=1)

    source_type = forms.ThemableChoiceField(
        label=_("Instance Boot Source"),
        initial='image_id',
        help_text=_("Choose Your Boot Source "
                    "Type."),disabled=True)

    image_id = forms.ChoiceField(
        label=_("Image Name"),
        required=False,
        widget=forms.ThemableSelectWidget(
            data_attrs=('volume_size',),
            transform=lambda x: ("%s (%s)" % (x.name,
                                              filesizeformat(x.bytes)))))
    class Meta(object):
        name = _("Details")
        help_text_template = ("project/order/"
                              "_launch_details_help.html")

    def __init__(self, request, context, *args, **kwargs):
        self._init_images_cache()
        self.request = request
        self.context = context
        super(SetInstanceDetailsAction, self).__init__(
            request, context, *args, **kwargs)

        source_type_choices = [
            ('', _("Select source")),
            ("image_id", _("Boot from image")),
        ]
        self.fields['source_type'].choices = source_type_choices

    @memoized.memoized_method
    def _get_flavor(self, flavor_id):
        try:
            # We want to retrieve details for a given flavor,
            # however flavor_list uses a memoized decorator
            # so it is used instead of flavor_get to reduce the number
            # of API calls.
            flavors = instance_utils.flavor_list(self.request)
            flavor = [x for x in flavors if x.id == flavor_id][0]
        except IndexError:
            flavor = None
        return flavor

    @memoized.memoized_method
    def _get_image(self, image_id):
        try:
            # We want to retrieve details for a given image,
            # however get_available_images uses a cache of image list,
            # so it is used instead of image_get to reduce the number
            # of API calls.
            images = image_utils.get_available_images(
                self.request,
                self.context.get('project_id'),
                self._images_cache)
            image = [x for x in images if x.id == image_id][0]
        except IndexError:
            image = None
        return image

    def _check_quotas(self, cleaned_data):
        count = cleaned_data.get('count', 1)

        # Prevent launching more instances than the quota allows
        usages = quotas.tenant_quota_usages(
            self.request,
            targets=('instances', 'cores', 'ram', ))
        available_count = usages['instances']['available']
        if available_count < count:
            msg = (_('The requested instance(s) cannot be launched '
                     'as your quota will be exceeded: Available: '
                     '%(avail)s, Requested: %(req)s.')
                   % {'avail': available_count, 'req': count})
            raise forms.ValidationError(msg)

        source_type = cleaned_data.get('source_type')
        if source_type in ('volume_image_id', 'volume_snapshot_id'):
            available_volume = usages['volumes']['available']
            if available_volume < count:
                msg = (_('The requested instance cannot be launched. '
                         'Requested volume exceeds quota: Available: '
                         '%(avail)s, Requested: %(req)s.')
                       % {'avail': available_volume, 'req': count})
                raise forms.ValidationError(msg)

        flavor_id = cleaned_data.get('flavor')
        flavor = self._get_flavor(flavor_id)

        count_error = []
        # Validate cores and ram.
        available_cores = usages['cores']['available']
        if flavor and available_cores < count * flavor.vcpus:
            count_error.append(_("Cores(Available: %(avail)s, "
                                 "Requested: %(req)s)")
                               % {'avail': available_cores,
                                  'req': count * flavor.vcpus})

        available_ram = usages['ram']['available']
        if flavor and available_ram < count * flavor.ram:
            count_error.append(_("RAM(Available: %(avail)s, "
                                 "Requested: %(req)s)")
                               % {'avail': available_ram,
                                  'req': count * flavor.ram})
        if count_error:
            value_str = ", ".join(count_error)
            msg = (_('The requested instance cannot be launched. '
                     'The following requested resource(s) exceed '
                     'quota(s): %s.') % value_str)
            if count == 1:
                self._errors['flavor'] = self.error_class([msg])
            else:
                self._errors['count'] = self.error_class([msg])

    def _check_flavor_for_image(self, cleaned_data):
        # Prevents trying to launch an image needing more resources.
        image_id = cleaned_data.get('image_id')
        image = self._get_image(image_id)
        flavor_id = cleaned_data.get('flavor')
        flavor = self._get_flavor(flavor_id)
        if not image or not flavor:
            return
        props_mapping = (("min_ram", "ram"), ("min_disk", "disk"))
        for iprop, fprop in props_mapping:
            if (getattr(image, iprop) > 0 and
                    getattr(flavor, fprop) > 0 and
                    getattr(image, iprop) > getattr(flavor, fprop)):
                msg = (_("The flavor '%(flavor)s' is too small "
                         "for requested image.\n"
                         "Minimum requirements: "
                         "%(min_ram)s MB of RAM and "
                         "%(min_disk)s GB of Root Disk.") %
                       {'flavor': flavor.name,
                        'min_ram': image.min_ram,
                        'min_disk': image.min_disk})
                self._errors['image_id'] = self.error_class([msg])
                break  # Not necessary to continue the tests.

    def _check_source_image(self, cleaned_data):
        if not cleaned_data.get('image_id'):
            msg = _("You must select an image.")
            self._errors['image_id'] = self.error_class([msg])
        else:
            self._check_flavor_for_image(cleaned_data)

    def _check_source(self, cleaned_data):
        # Validate our instance source.
        source_type = self.data.get('source_type', None)
        source_check_methods = {
            'image_id': self._check_source_image,
        }
        check_method = source_check_methods.get(source_type)
        if check_method:
            check_method(cleaned_data)

    def clean(self):
        cleaned_data = super(SetInstanceDetailsAction, self).clean()

        self._check_quotas(cleaned_data)
        self._check_source(cleaned_data)

        return cleaned_data

    def populate_flavor_choices(self, request, context):
        return instance_utils.flavor_field_data(request, False)

    def populate_availability_zone_choices(self, request, context):
        try:
            zones = api.nova.availability_zone_list(request)
        except Exception:
            zones = []
            exceptions.handle(request,
                              _('Unable to retrieve availability zones.'))

        zone_list = [(zone.zoneName, zone.zoneName)
                     for zone in zones if zone.zoneState['available']]
        zone_list.sort()
        if not zone_list:
            zone_list.insert(0, ("", _("No availability zones found")))
        elif len(zone_list) > 1:
            zone_list.insert(0, ("", _("Any Availability Zone")))
        return zone_list

    def get_help_text(self, extra_context=None):
        extra = {} if extra_context is None else dict(extra_context)
        try:
            data=api.order.order_hypervisor(self.request,self.context['start_time'],self.context['stop_time'])
            total_restouce=data.get('total_resource',None)
            free_resource=data.get('free_resource',None)
            extra['usages']={
                'disk':{
                    'available':free_resource.get('disk',None),
                    'used':total_restouce.get('disk', None) - free_resource.get('disk', None),
                    'quota':total_restouce.get('disk',None),
                },
                'cores':{
                    'available':free_resource.get('vcpus',None),
                    'used':total_restouce.get('vcpus', None) - free_resource.get('vcpus', None),
                    'quota':total_restouce.get('vcpus',None),
                },
                'ram':{
                    'available': free_resource.get('ram',None),
                    'used': total_restouce.get('ram', None) - free_resource.get('ram', None),
                    'quota': total_restouce.get('ram', None),
                }
            }
            extra['usages_json'] = json.dumps(extra['usages'])
            flavors = json.dumps([f._info for f in
                                  instance_utils.flavor_list(self.request)])
            extra['flavors'] = flavors
            images = image_utils.get_available_images(
                self.request, self.initial['project_id'], self._images_cache)
            if images is not None:
                attrs = [{'id': i.id,
                          'min_disk': getattr(i, 'min_disk', 0),
                          'min_ram': getattr(i, 'min_ram', 0),
                          'size': functions.bytes_to_gigabytes(i.size)}
                         for i in images]
                extra['images'] = json.dumps(attrs)

        except Exception:
            exceptions.handle(self.request,
                              _("Unable to retrieve quota information."))
        return super(SetInstanceDetailsAction, self).get_help_text(extra)

    def _init_images_cache(self):
        if not hasattr(self, '_images_cache'):
            self._images_cache = {}

    def populate_image_id_choices(self, request, context):
        choices = []
        images = image_utils.get_available_images(request,
                                                  context.get('project_id'),
                                                  self._images_cache)
        for image in images:
            if image_tables.get_image_type(image) != "snapshot":
                image.bytes = getattr(
                    image, 'virtual_size', None) or image.size
                image.volume_size = max(
                    image.min_disk, functions.bytes_to_gigabytes(image.bytes))
                choices.append((image.id, image))
                if context.get('image_id') == image.id and \
                        'volume_size' not in context:
                    context['volume_size'] = image.volume_size
        if choices:
            choices.sort(key=lambda c: c[1].name or '')
            choices.insert(0, ("", _("Select Image")))
        else:
            choices.insert(0, ("", _("No images available")))
        return choices
class SetInstanceDetails(workflows.Step):
    action_class = SetInstanceDetailsAction
    depends_on = ("project_id", "user_id")
    contributes = ("source_type", "source_id",
                   "availability_zone", "name", "count", "flavor",
                   "device_name",  # Can be None for an image.
                   "vol_delete_on_instance_delete")

    def prepare_action_context(self, request, context):
        if 'source_type' in context and 'source_id' in context:
            context[context['source_type']] = context['source_id']
        return context

    def contribute(self, data, context):
        context = super(SetInstanceDetails, self).contribute(data, context)
        # Allow setting the source dynamically.
        if ("source_type" in context and
                "source_id" in context and
                context["source_type"] not in context):
            context[context["source_type"]] = context["source_id"]

        # Translate form input to context for source values.
        if "source_type" in data:
            if data["source_type"] in ["image_id", "volume_image_id"]:
                context["source_id"] = data.get("image_id", None)
            else:
                context["source_id"] = data.get(data["source_type"], None)

        if "volume_size" in data:
            context["volume_size"] = data["volume_size"]

        return context
KEYPAIR_IMPORT_URL = "horizon:project:key_pairs:import"
class SetNetworkAction(workflows.Action):
    network = forms.MultipleChoiceField(
        label=_("Networks"),
        widget=forms.ThemableCheckboxSelectMultiple(),
        error_messages={
            'required': _(
                "At least one network must"
                " be specified.")},
        help_text=_("Launch instance with"
                    " these networks"))

    def __init__(self, request, *args, **kwargs):
        super(SetNetworkAction, self).__init__(request, *args, **kwargs)

        # NOTE(e0ne): we don't need 'required attribute for networks
        # checkboxes to be able to select only one network
        # NOTE(e0ne): we need it for compatibility with different
        # Django versions (prior to 1.11)
        self.use_required_attribute = False

        network_list = self.fields["network"].choices
        if len(network_list) == 1:
            self.fields['network'].initial = [network_list[0][0]]

    class Meta(object):
        name = _("Networking")
        permissions = ('openstack.services.network',)
        help_text = _("Select networks for your instance.")

    def populate_network_choices(self, request, context):
        return instance_utils.network_field_data(request, for_launch=True)
class SetNetwork(workflows.Step):
    action_class = SetNetworkAction
    template_name = "project/instances/_update_networks.html"
    contributes = ("network_id",)

    def contribute(self, data, context):
        if data:
            networks = self.workflow.request.POST.getlist("network")
            # If no networks are explicitly specified, network list
            # contains an empty string, so remove it.
            networks = [n for n in networks if n != '']
            if networks:
                context['network_id'] = networks
        return context
class SetOrderAction(workflows.Action):
    start_time = forms.DateTimeField(label=_("Start Time"),disabled=True
                           )
    stop_time = forms.DateTimeField(label=_("Stop Time"),disabled=True
                           )
    def __init__(self, request, *args, **kwargs):
        super(SetOrderAction, self).__init__(request, *args, **kwargs)

        # NOTE(e0ne): we don't need 'required attribute for networks
        # checkboxes to be able to select only one network
        # NOTE(e0ne): we need it for compatibility with different
        # Django versions (prior to 1.11)
        self.use_required_attribute = False

    class Meta(object):
        name = _("Order")
        help_text = _("Select Order for your instance.")
class SetOrder(workflows.Step):
    action_class = SetOrderAction
    contributes = ("start_time","stop_time")

    def contribute(self, data, context):
        context["start_time"] = data.get("start_time", None)
        context["stop_time"] = data.get("stop_time", None)
        return context
class LaunchOrder(workflows.Workflow):
    slug = "launch_order"
    name = _("Launch Order")
    finalize_button_name = _("Launch")
    success_message = _('Request for launching %(count)s named "%(name)s" '
                        'has been submitted.')
    failure_message = _('Unable to launch %(count)s named "%(name)s".')
    success_url = "horizon:project:order:index"
    multipart = True
    default_steps = (SetOrder,
                     SelectProjectUser,
                     SetInstanceDetails,
                     SetNetwork,)

    def format_status_message(self, message):
        name = self.context.get('name', 'unknown instance')
        count = self.context.get('count', 1)
        if int(count) > 1:
            return message % {"count": _("%s instances") % count,
                              "name": name}
        else:
            return message % {"count": _("instance"), "name": name}

    @sensitive_variables('context')
    def handle(self, request, context):
        image_id = ''
        source_type = context.get('source_type', None)
        if source_type in ['image_id', 'instance_snapshot_id']:
            image_id = context['source_id']
        netids = context.get('network_id', None)
        if netids:
            nics = [{"net-id": netid, "v4-fixed-ip": ""}
                    for netid in netids]
        else:
            nics = None
        print(context.get('start_time'))
        start_time=context.get('start_time')
        stop_time=context.get('stop_time')
        try:
            api.order.order_create(request,
                                   name=context['name'],
                                   image_id=image_id,
                                   flavor_id=context['flavor'],
                                   nics=nics,
                                   start_time=start_time.strftime('%Y-%m-%d %H:%M:%S'),
                                   stop_time=stop_time.strftime('%Y-%m-%d %H:%M:%S'),
                                   count=int(context['count']))
            return True
        except Exception:
            exceptions.handle(request)
        return False


def _cleanup_ports_on_failed_vm_launch(request, nics):
    ports_failing_deletes = []
    LOG.debug('Cleaning up stale VM ports.')
    for nic in nics:
        try:
            LOG.debug('Deleting port with id: %s', nic['port-id'])
            api.neutron.port_delete(request, nic['port-id'])
        except Exception:
            ports_failing_deletes.append(nic['port-id'])
    return ports_failing_deletes
