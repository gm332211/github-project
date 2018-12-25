from api import Openstack
from api import connect
from sqlalchemy import create_engine
from sqlalchemy.sql import or_,except_,except_all,union_all
from sqlalchemy.orm import sessionmaker
from db.openstack_db import Group,Network
import datetime
from conf import openstack_setting as lease_conf
engine = create_engine(lease_conf.ENGINE,encoding='utf-8', echo=False)
DBSession=sessionmaker(bind=engine,autocommit=False,autoflush=False)
session=DBSession()
conn=connect.Conn()
op=Openstack.Openstack(conn)
flavor_dict=op.list_flavor()
global_resource={}
def use_order_flavor():
    flavor_id_list=[]
    date_now=datetime.datetime.now()
    objs=session.query(Group).filter(Group.stop_time>date_now).filter(Group.status=='created')
    for obj in objs:
        flavor_id_list.append(obj.flavor_id)
    return flavor_id_list
def occupy_order_flavor(start_time,stop_time):
    obj_id_list=[]
    objs = session.query(Group).filter(Group.start_time <= stop_time,Group.stop_time>=start_time,Group.status!='dead').all()
    if objs:
        for obj in objs:
            obj_id_list.append(obj.flavor_id)
    return obj_id_list
def get_flavor_resource(flavor_id_list):
    sum_ram=0
    sum_vcpus=0
    sum_disk=0
    for flavor_id in flavor_id_list:
        flavor_resource=flavor_dict.get(flavor_id,None)
        if not flavor_resource:
            flavor_obj=op.get_flavor(flavor_id)
            flavor_resource={
                'ram': int(flavor_obj.ram) or 0,
                'vcpus': int(flavor_obj.vcpus) or 0,
                'disk':int(flavor_obj.disk) or 0,
            }
            flavor_dict[flavor_obj.id]=flavor_resource
        sum_ram+=flavor_resource.get('ram',0)
        sum_vcpus += flavor_resource.get('vcpus',0)
        sum_disk += flavor_resource.get('disk',0)
    return {'ram':sum_ram,'vcpus':sum_vcpus,'disk':sum_disk}
def get_network_resource():
    network_count={}
    for network in op.list_network():
        for subnet in op.list_subnetwork(network.get('id')):
            addr_count = 0
            for all_pools in subnet.get('allocation_pools'):
                start = all_pools.get('start').split('.')[3]
                end = all_pools.get('end').split('.')[3]
                addr_count += int(end) - int(start)
            ports = op.list_port(subnet_id=subnet.get('id'))
            network_count[network.get('id')] = {}
            network_count[network.get('id')]['total'] = addr_count
            network_count[network.get('id')]['residue'] = addr_count - len(ports)
    return network_count
def total_resource(start_time,stop_time):
    data=op.hypervisors_stats()
    if not global_resource:
        global_resource['ram']=data.get('memory_mb')
        global_resource['vcpus'] = data.get('vcpus')
        global_resource['disk'] = data.get('free_disk_gb')
    free_resource={
        'ram':data.get('free_ram_mb'),
        'vcpus':data.get('vcpus')-data.get('vcpus_used'),
        'disk':data.get('disk_available_least'),
    }

    order_resource=get_flavor_resource(use_order_flavor())
    occupy_resource=get_flavor_resource(occupy_order_flavor(start_time,stop_time))
    sum_ram=free_resource.get('ram')+order_resource.get('ram')-occupy_resource.get('ram')
    sum_vcpus=free_resource.get('vcpus')+order_resource.get('vcpus')-occupy_resource.get('vcpus')
    sum_disk=free_resource.get('disk')+order_resource.get('disk')-occupy_resource.get('disk')
    return {'ram':sum_ram,'vcpus':sum_vcpus,'disk':sum_disk}
stop_time=start_time=datetime.datetime.now()
# data=occupy_order_flavor(start_time,stop_time)
data=total_resource(start_time,stop_time)
# print(data)
print(data)
print(global_resource)
print(get_network_resource(['f9c6febf-2ac9-4439-b460-5ae6f7f37723',]))
# objs1=session.query(Group).filter(Group.stop_time <= start_time,Group.start_time >=stop_time)