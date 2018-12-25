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
        help_text_template = ("project/instances/"
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
            targets=('instances', 'cores', 'ram', 'volumes', ))
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
            extra['usages'] = quotas.tenant_quota_usages(
                self.request,
                targets=('cores', 'ram','gigabytes'))
            extra['usages_json'] = json.dumps(extra['usages'])
            extra['cinder_enabled'] = \
                base.is_service_enabled(self.request, 'volume')
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


class SetAccessControlsAction(workflows.Action):
    keypair = forms.ThemableDynamicChoiceField(
        label=_("Key Pair"),
        help_text=_("Key pair to use for "
                    "authentication."),
        add_item_link=KEYPAIR_IMPORT_URL)
    admin_pass = forms.RegexField(
        label=_("Admin Password"),
        required=False,
        widget=forms.PasswordInput(render_value=False),
        regex=validators.password_validator(),
        error_messages={'invalid': validators.password_validator_msg()})
    confirm_admin_pass = forms.CharField(
        label=_("Confirm Admin Password"),
        required=False,
        widget=forms.PasswordInput(render_value=False))
    groups = forms.MultipleChoiceField(
        label=_("Security Groups"),
        required=False,
        initial=["default"],
        widget=forms.ThemableCheckboxSelectMultiple(),
        help_text=_("Launch instance in these "
                    "security groups."))

    class Meta(object):
        name = _("Access & Security")
        help_text = _("Control access to your instance via key pairs, "
                      "security groups, and other mechanisms.")

    def __init__(self, request, *args, **kwargs):
        super(SetAccessControlsAction, self).__init__(request, *args, **kwargs)
        if not api.nova.can_set_server_password():
            del self.fields['admin_pass']
            del self.fields['confirm_admin_pass']
        self.fields['keypair'].required = api.nova.requires_keypair()

    def populate_keypair_choices(self, request, context):
        keypairs = instance_utils.keypair_field_data(request, True)
        if len(keypairs) == 2:
            self.fields['keypair'].initial = keypairs[1][0]
        return keypairs

    def populate_groups_choices(self, request, context):
        try:
            groups = api.neutron.security_group_list(request)
            security_group_list = [(sg.id, sg.name) for sg in groups]
        except Exception:
            exceptions.handle(request,
                              _('Unable to retrieve list of security groups'))
            security_group_list = []
        return security_group_list

    def clean(self):
        '''Check to make sure password fields match.'''
        cleaned_data = super(SetAccessControlsAction, self).clean()
        if 'admin_pass' in cleaned_data:
            if cleaned_data['admin_pass'] != cleaned_data.get(
                    'confirm_admin_pass', None):
                raise forms.ValidationError(_('Passwords do not match.'))
        return cleaned_data


class SetAccessControls(workflows.Step):
    action_class = SetAccessControlsAction
    depends_on = ("project_id", "user_id")
    contributes = ("keypair_id", "security_group_ids",
                   "admin_pass", "confirm_admin_pass")

    def contribute(self, data, context):
        if data:
            post = self.workflow.request.POST
            context['security_group_ids'] = post.getlist("groups")
            context['keypair_id'] = data.get("keypair", "")
            context['admin_pass'] = data.get("admin_pass", "")
            context['confirm_admin_pass'] = data.get("confirm_admin_pass", "")
        return context


class CustomizeAction(workflows.Action):
    class Meta(object):
        name = _("Post-Creation")
        help_text_template = ("project/instances/"
                              "_launch_customize_help.html")

    source_choices = [('', _('Select Script Source')),
                      ('raw', _('Direct Input')),
                      ('file', _('File'))]

    attributes = {'class': 'switchable', 'data-slug': 'scriptsource'}
    script_source = forms.ChoiceField(
        label=_('Customization Script Source'),
        choices=source_choices,
        widget=forms.ThemableSelectWidget(attrs=attributes),
        required=False)

    script_help = _("A script or set of commands to be executed after the "
                    "instance has been built (max 16kb).")

    script_upload = forms.FileField(
        label=_('Script File'),
        help_text=script_help,
        widget=forms.FileInput(attrs={
            'class': 'switched',
            'data-switch-on': 'scriptsource',
            'data-scriptsource-file': _('Script File')}),
        required=False)

    script_data = forms.CharField(
        label=_('Script Data'),
        help_text=script_help,
        widget=forms.widgets.Textarea(attrs={
            'class': 'switched',
            'data-switch-on': 'scriptsource',
            'data-scriptsource-raw': _('Script Data')}),
        required=False)

    def __init__(self, *args):
        super(CustomizeAction, self).__init__(*args)

    def clean(self):
        cleaned = super(CustomizeAction, self).clean()

        files = self.request.FILES
        script = self.clean_uploaded_files('script', files)

        if script is not None:
            cleaned['script_data'] = script

        return cleaned

    def clean_uploaded_files(self, prefix, files):
        upload_str = prefix + "_upload"

        has_upload = upload_str in files
        if has_upload:
            upload_file = files[upload_str]
            log_script_name = upload_file.name
            LOG.info('got upload %s', log_script_name)

            if upload_file._size > 16 * units.Ki:  # 16kb
                msg = _('File exceeds maximum size (16kb)')
                raise forms.ValidationError(msg)
            else:
                script = upload_file.read()
                if script != "":
                    try:
                        if not isinstance(script, six.text_type):
                            script = script.decode()
                        normalize_newlines(script)
                    except Exception as e:
                        msg = _('There was a problem parsing the'
                                ' %(prefix)s: %(error)s')
                        msg = msg % {'prefix': prefix,
                                     'error': six.text_type(e)}
                        raise forms.ValidationError(msg)
                return script
        else:
            return None


class PostCreationStep(workflows.Step):
    action_class = CustomizeAction
    contributes = ("script_data",)


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
    start_time = forms.DateTimeField(label=_("Start Time")
                           )
    stop_time = forms.DateTimeField(label=_("Stop Time")
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
    contributes = ("start_time","stop_time",)

    def contribute(self, data, context):
        context["start_time"] = data.get("start_time", None)
        context["stop_time"] = data.get("stop_time", None)
        return context

class SetNetworkPortsAction(workflows.Action):
    ports = forms.MultipleChoiceField(label=_("Ports"),
                                      widget=forms.CheckboxSelectMultiple(),
                                      required=False,
                                      help_text=_("Launch instance with"
                                                  " these ports"))

    class Meta(object):
        name = _("Network Ports")
        permissions = ('openstack.services.network',)
        help_text_template = ("project/instances/"
                              "_launch_network_ports_help.html")

    def populate_ports_choices(self, request, context):
        ports = instance_utils.port_field_data(request)
        if not ports:
            self.fields['ports'].label = _("No ports available")
            self.fields['ports'].help_text = _("No ports available")
        return ports


class SetNetworkPorts(workflows.Step):
    action_class = SetNetworkPortsAction
    contributes = ("ports",)

    def contribute(self, data, context):
        if data:
            ports = self.workflow.request.POST.getlist("ports")
            if ports:
                context['ports'] = ports
        return context


class SetAdvancedAction(workflows.Action):
    disk_config = forms.ThemableChoiceField(
        label=_("Disk Partition"), required=False,
        help_text=_("Automatic: The entire disk is a single partition and "
                    "automatically resizes. Manual: Results in faster build "
                    "times but requires manual partitioning."))
    config_drive = forms.BooleanField(
        label=_("Configuration Drive"),
        required=False, help_text=_("Configure OpenStack to write metadata to "
                                    "a special configuration drive that "
                                    "attaches to the instance when it boots."))
    server_group = forms.ThemableChoiceField(
        label=_("Server Group"), required=False,
        help_text=_("Server group to associate with this instance."))

    def __init__(self, request, context, *args, **kwargs):
        super(SetAdvancedAction, self).__init__(request, context,
                                                *args, **kwargs)
        try:
            if not api.nova.extension_supported("DiskConfig", request):
                del self.fields['disk_config']
            else:
                # Set our disk_config choices
                config_choices = [("AUTO", _("Automatic")),
                                  ("MANUAL", _("Manual"))]
                self.fields['disk_config'].choices = config_choices
            # Only show the Config Drive option for the Launch Instance
            # workflow (not Resize Instance) and only if the extension
            # is supported.
            if context.get('workflow_slug') != 'launch_instance' or (
                    not api.nova.extension_supported("ConfigDrive", request)):
                del self.fields['config_drive']

            if not api.nova.extension_supported("ServerGroups", request):
                del self.fields['server_group']
            else:
                server_group_choices = instance_utils.server_group_field_data(
                    request)
                self.fields['server_group'].choices = server_group_choices
        except Exception:
            exceptions.handle(request, _('Unable to retrieve extensions '
                                         'information.'))

    class Meta(object):
        name = _("Advanced Options")
        help_text_template = ("project/instances/"
                              "_launch_advanced_help.html")


class SetAdvanced(workflows.Step):
    action_class = SetAdvancedAction
    contributes = ("disk_config", "config_drive", "server_group",)

    def prepare_action_context(self, request, context):
        context = super(SetAdvanced, self).prepare_action_context(request,
                                                                  context)
        # Add the workflow slug to the context so that we can tell which
        # workflow is being used when creating the action. This step is
        # used by both the Launch Instance and Resize Instance workflows.
        context['workflow_slug'] = self.workflow.slug
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
    default_steps = (SelectProjectUser,
                     SetOrder,
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
        # Determine volume mapping options
        source_type = context.get('source_type', None)
        if source_type in ['image_id', 'instance_snapshot_id']:
            image_id = context['source_id']
        netids = context.get('network_id', None)
        if netids:
            nics = [{"net-id": netid, "v4-fixed-ip": ""}
                    for netid in netids]
        else:
            nics = None
        avail_zone = context.get('availability_zone', None)
        scheduler_hints = {}
        start_time = context.get('start_time', None)
        stop_time = context.get('stop_time', None)
        print(start_time,stop_time)
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
