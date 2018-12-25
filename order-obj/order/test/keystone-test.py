#-*- coding: utf-8 -*-
import sys
from api import connect
from api import keystone
# 创建预约操作
reload(sys)
sys.setdefaultencoding('utf8')
conn=connect.Conn()
k1=keystone.Keystone(conn)
project_obj=k1.create_project(name=bytes('fdasfaf'.encode('utf8')))
user=k1.conn.identity.find_user('abc')
role=k1.conn.identity.find_role('member')
print(user.id,role.id,project_obj.id)
from openstack import utils
base_path='/projects'
url = utils.urljoin(base_path, project_obj.id, 'users',
                    user.id, 'roles', role.id)
print(url)
k1.conn.session.put(url)

project_obj.assign_role_to_user(session=conn.session,user=user,role=role)
# if project_obj:
#     #role_add
#
#     project_obj = k1.delete_project(name=bytes('fdasfaf'.encode('utf8')))
#     # write_db
# else:
#     print('error:%s'%'项目已存在')