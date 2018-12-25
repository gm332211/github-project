#-*- coding: utf-8 -*-
from api import Openstack
import json
from conf import openstack_setting
from api import connect
conn=connect.Conn()
op=Openstack.Openstack(project='alt_demo',conn=conn)
# name='test'
# image_id= 'd7b418b0-9828-4664-85b3-62571f05d3a1'
# flavor_id='1'
# networks=[{'uuid': '7a47d9f7-f47a-4321-99c4-8fdb7e48567a'}]
# count='10'
# op.create_server(name=name,image_id=image_id,flavor_id=flavor_id,networks=networks,count=count)
op.get_token()

res=op.create_project('xiandian')
# res=op.identity_request('users',method='GET',headers=headers)
# print(json.loads(res.read()))
# print(json.loads(res.read()))
