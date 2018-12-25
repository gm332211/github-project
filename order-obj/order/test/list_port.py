from api import Openstack
op=Openstack.UserOpenstack(project_id='e3526c454df9444bafd13ad504e60620')
ports=op.list_port_id(network_id='f9c6febf-2ac9-4439-b460-5ae6f7f37723')
for port in ports:
    print(port)
