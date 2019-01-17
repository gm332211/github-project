#-*- coding:utf-8 -*-
# @Author:xiaoming
import ConfigParser
import os
config = ConfigParser.ConfigParser()
config.read('%s/openstack.conf'%os.path.dirname(os.path.abspath(__file__)))
IP=config.get('openstack_auth','ip')
USERNAME=config.get('openstack_auth','username')
PASSWORD=config.get('openstack_auth','password')
PROJECT=config.get('openstack_auth','project')
DOMAIN=config.get('openstack_auth','domain')
AUTH_URL = config.get('keystone_auth','url')
IDENTITY_API_VERSION = config.get('keystone_auth','version')
COMPUTE_API_VERSION = config.get('compute_auth','version')
IDENTITY_INTERFACE = config.get('keystone_auth','interface')
ENGINE=config.get('database','connection')
WEBPORT=config.get('order','web_port')
USERROLE=config.get('order','user_role_name')
ADMINROLE=config.get('order','admin_role_name')
CREATE_THREAD_COUNT=config.get('order','create_thread_count')
DELETE_THREAD_COUNT=config.get('order','delete_thread_count')
ACTION_THREAD_COUNT=config.get('order','action_thread_count')
openstack_auth={
    'ip':IP,
    'username':USERNAME,
    'password':PASSWORD,
    'project':PROJECT,
    'domain':DOMAIN,
}
keystone_auth={
    'url':AUTH_URL,
    'port':config.get('keystone_auth','port'),
    'version':'v%s'%IDENTITY_API_VERSION,
}
compute_auth={
    'url': config.get('compute_auth','url'),
    'port': config.get('compute_auth','port'),
    'version':'v%s'%COMPUTE_API_VERSION,
}
network_auth={
    'url': config.get('network_auth','url'),
    'port': config.get('network_auth','port'),
    'version': 'v%s'%config.get('network_auth','version'),
}
AUTH_CONFIG = {
    'default': {
        'region_name': 'RegionOne',
        'auth': {
            'auth_url': AUTH_URL,
            'username': USERNAME,
            'password': PASSWORD,
            'project_name': PROJECT,
            'user_domain_name': DOMAIN,
            'project_domain_name': DOMAIN,
        },
        'compute_api_version': COMPUTE_API_VERSION,
        'identity_api_version': IDENTITY_API_VERSION,
        'identity_interface': IDENTITY_INTERFACE,
    },
}
DOMAIN_CONF = {
    'name_or_id': 'default',
}

