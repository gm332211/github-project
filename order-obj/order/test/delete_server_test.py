from api import Openstack
op=Openstack.UserOpenstack(project_id='1e9fa526dc8141c1b5809fe820dc703e')
# servers=op.list_server_id()
# print(servers)
data=op.float_create(float_network_id='efbe5cc2-f8a3-48a3-beba-32ce2490f091',band_port_id='f284bded-5ce9-4cf8-8973-d2ad04a33fdd')
print(data)
