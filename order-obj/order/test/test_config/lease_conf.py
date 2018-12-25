#-*- coding: utf-8 -*-
import ConfigParser
import os
config = ConfigParser.ConfigParser()
config.read('%s/openstack.conf'%os.path.dirname(os.path.abspath(__file__)))
openstack_auth={
    'ip':config.get('openstack_auth','ip'),
    'username':config.get('openstack_auth','username'),
    'password':config.get('openstack_auth','password'),
    'project':config.get('openstack_auth','project'),
    'domain':config.get('openstack_auth','domain'),
}
keystone_auth={
    'url':config.get('keystone_auth','url'),
    'port':config.get('keystone_auth','port'),
    'version':config.get('keystone_auth','version'),
}
compute_auth={
    'url': config.get('compute_auth','url'),
    'port': config.get('compute_auth','port'),
    'version': config.get('compute_auth','version'),
}
network_auth={
    'url': config.get('network_auth','url'),
    'port': config.get('network_auth','port'),
    'version': config.get('network_auth','version'),
}