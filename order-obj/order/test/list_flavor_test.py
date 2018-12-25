from api import Openstack
from api import connect
conn=connect.Conn()
op=Openstack.Openstack(conn)
data=op.list_flavor()
flavor_dict={}
print(data)
