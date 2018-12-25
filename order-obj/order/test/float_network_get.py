from api import connect
from api import Openstack
import json
op = Openstack.Openstack(connect.Conn())
def get_extnetworks():
    extnetworks_list=[]
    res = op.network_request('networks?router:external=True&fields=id&fields=name', 'GET')
    networks = json.loads(res.read())
    for network in networks.get('networks',[]):
        extnetworks_dict = {}
        extnetworks_dict['id']=network.get('id',None)
        extnetworks_dict['name'] = network.get('name',None)
        extnetworks_list.append(extnetworks_dict)
    return extnetworks_list
def get_port_device(network_id,is_extnetwork=False):
    ports_id_list=[]
    if is_extnetwork:
        res = op.network_request(
            'ports?network_id=%s&device_owner=network:router_gateway&fields=device_id'%network_id,
            'GET')
    else:
        res = op.network_request(
            'ports?network_id=%s&device_owner=network:router_interface&fields=device_id'%network_id,
            'GET')
    data = json.loads(res.read())
    for port in data.get('ports',[]):
        ports_id_list.append(port.get('device_id'))
    return ports_id_list
def verify_bind_float(innetwork_id,ext_network_id):
    ext_devices=get_port_device(network_id=ext_network_id,is_extnetwork=True)
    in_devices=get_port_device(network_id=innetwork_id)
    for device in ext_devices:
        if device in in_devices:
            return True
    return False
def get_float_network(network_id_list):
    float_networks=[]
    ext_networks=get_extnetworks()
    ext_devices_dict = {}
    for ext_network in ext_networks:
        ext_devices=get_port_device(network_id=ext_network.get('id',None),is_extnetwork=True)
        for port in ext_devices:
            ext_devices_dict[port]={
                'id':ext_network.get('id',None),
                'name':ext_network.get('name',None),
            }
    for network_id in network_id_list:
        in_devices=get_port_device(network_id=network_id)
        for in_device in in_devices:
            bind_float=ext_devices_dict.get(in_device,None)
            if bind_float:
                float_networks.append(bind_float)
                ext_devices_dict.pop(in_device)
    return float_networks
print(verify_bind_float('f9c6febf-2ac9-4439-b460-5ae6f7f37723','efbe5cc2-f8a3-48a3-beba-32ce2490f091'))
print(get_float_network(['f9c6febf-2ac9-4439-b460-5ae6f7f37723']))