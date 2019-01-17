#-*- coding:utf-8 -*-
# @Author:xiaoming
from openstack import connection
from conf import openstack_setting
def Conn():
    return connection.Connection(
        **openstack_setting.AUTH_CONFIG.get('default')
    )
# region_name='xiandian',
# auth = dict(
#     auth_url='http://%s:35357' % (self.ipaddr),
#     username=self.username,
#     password=self.password,
#     project_name=self.project,
#     user_domain_name=self.domain,
#     project_domain_name=self.domain,
# ),
# compute_api_version = '2',
# identity_interface = 'admin'