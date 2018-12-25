from api import connect
from api import Openstack
conn=connect.Conn()
op=Openstack.Openstack(conn)
network_count={}
network_count['total']={}
network_count['free']={}
def network_hypervisors_stats():
    for network in op.list_network():
        for subnet in op.list_subnetwork(network.get('id')):
            addr_count=0
            for all_pools in subnet.get('allocation_pools'):
                start=all_pools.get('start').split('.')[3]
                end=all_pools.get('end').split('.')[3]
                addr_count+=int(end)-int(start)
            ports = op.list_port(subnet_id=subnet.get('id'))
            network_count['total'][network.get('id')]=addr_count
            network_count['free'][network.get('id')]=addr_count-len(ports)
    print(network_count)
network_hypervisors_stats()

