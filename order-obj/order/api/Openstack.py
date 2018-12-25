from conf import openstack_setting as lease_conf
import httplib, json
#Http Request
def http_request(ip, port, url, method, headers, data=None):
    res = None
    if data:
        data = json.dumps(data)
    else:
        data = json.dumps({})
    conn = httplib.HTTPConnection(ip, port=port)
    if method == 'GET':
        conn.request(method=method, url=url, headers=headers)
    elif method == 'POST':
        conn.request(method=method, url=url, headers=headers, body=data)
    elif method == 'DELETE':
        conn.request(method=method, url=url, headers=headers)
    elif method == 'PUT':
        conn.request(method=method, url=url, headers=headers,body=data)
    try:
        res = conn.getresponse()
    except Exception as e:
        print(e)
    if res:
        return res
#Certified decorator
def auth_token(func):
    def inner(self,*args,**kwargs):
        if not self.token:
            self.get_token()
        data = func(self, *args, **kwargs)
        try:
            error_code=data['error']['code']
        except:
            error_code=None
        if error_code=='401':
            self.get_token()
            data = func(self,*args, **kwargs)
        return data
    return inner
class Openstack(object):
#Admin Openstack Class
    def __init__(self, conn, project=lease_conf.PROJECT, username=lease_conf.USERNAME, password=lease_conf.PASSWORD,
                 domain=lease_conf.DOMAIN,
                 ip=lease_conf.IP):
        domain_obj = conn.identity.find_domain(**lease_conf.DOMAIN_CONF)
        if domain_obj:
            self.domain_id = domain_obj.id
        else:
            self.domain_id = None
        self.ip = ip
        self.username = username
        self.password = password
        self.project = project
        self.domain = domain
        self.token = None
        self.conn = conn
#Service Base
    def identity_request(self, server, method, headers=None, data=None, echo=None):
        ip = self.ip
        port = lease_conf.keystone_auth.get('port', None)
        keystone_url = lease_conf.keystone_auth.get('url', None)
        version = lease_conf.keystone_auth.get('version', None)
        url = '%s/%s/%s' % (keystone_url, version, server)
        if echo:
            print('keystone request url:[%s]%s' % (method, url))
        if not headers:
            headers = {
                "Content-type": "application/json",
            }
        return http_request(ip=ip, port=port, url=url, method=method, headers=headers, data=data)
    def compute_request(self, server, method, headers=None, data=None, echo=None):
        ip = self.ip
        port = lease_conf.compute_auth.get('port', None)
        compute_url = lease_conf.compute_auth.get('url', None)
        version = lease_conf.compute_auth.get('version', None)
        url = '%s/%s/%s' % (compute_url, version, server)
        if echo:
            print('compute request url:[%s]%s' % (method, url))
        if not self.token:
            self.get_token()
        if not headers:
            headers = {
                "Content-type": "application/json",
                "X-Auth-Token": self.token,
            }
        return http_request(ip=ip, port=port, url=url, method=method, headers=headers, data=data)
    def network_request(self, server, method, headers=None, data=None, echo=None):
        ip = self.ip
        port = lease_conf.network_auth.get('port', None)
        network_url = lease_conf.network_auth.get('url', None)
        version = lease_conf.network_auth.get('version', None)
        url = '%s/%s/%s' % (network_url, version, server)
        if echo:
            print('network request url:[%s]%s' % (method, url))
        if not self.token:
            self.get_token()
        if not headers:
            headers = {
                "Content-type": "application/json",
                "X-Auth-Token": self.token,
            }
        return http_request(ip=ip, port=port, url=url, method=method, headers=headers, data=data)
    def get_token(self):
        data = {"auth": {"identity": {"methods": ["password"],
                                      "password": {"user": {"name": self.username, "password": self.password,
                                                            "domain": {"name": self.domain}}}},
                         "scope": {"project": {"name": self.project, "domain": {"name": self.domain}}}}}
        res = self.identity_request(server='auth/tokens', method='POST', data=data)
        self.token = res.getheader('X-Subject-Token')
#Openstack API Request
    @auth_token
    def get_user(self,user_token):
        headers = {
            "Content-type": "application/json",
            "X-Auth-Token": self.token,
            "X-Subject-Token":user_token
        }
        res=self.identity_request('auth/tokens', method='GET',
                              headers=headers)
        data = json.loads(res.read())
        return data
    @auth_token
    def get_user_id(self,user_token):
        data=self.get_user(user_token)
        try:
            user_id=data['token']['user']['id']
        except:
            user_id=None
        return user_id
    @auth_token
    def add_role(self, project_id, user_id):
        role=self.get_role(role_type='user')
        headers = {
            "Content-type": "application/json",
            "X-Auth-Token": self.token,
        }
        self.identity_request('projects/%s/users/%s/roles/%s' % (project_id, user_id, role.id), method='PUT',
                              headers=headers)
    @auth_token
    def get_role(self,role_type='user'):
        if role_type=='user':
            role_name=lease_conf.USERROLE
        elif role_type=='admin':
            role_name = lease_conf.ADMINROLE
        role=self.conn.identity.find_role(name_or_id=role_name)
        return role
    @auth_token
    def list_projects(self,user_id):
        headers = {
            "Content-type": "application/json",
            "X-Auth-Token": self.token,
        }
        res=self.identity_request('users/%s/projects'%user_id,'GET',headers=headers)
        data = json.loads(res.read())
        return data
    def list_projects_id(self,user_id):
        data=self.list_projects(user_id)
        project_id_list=[]
        projects=data.get('projects',None)
        if projects:
            for project in projects:
                project_id_list.append(project.get('id',None))
        return project_id_list
    @auth_token
    def update_quota(self,project_id,cores,ram,count):
        data={
            "quota_set": {
                "cores": cores,
                'ram':ram,
                'floating_ips':count,
                'instances':count,
            }
        }
        self.compute_request('os-quota-sets/%s' % project_id, method='PUT',data=data)
    @auth_token
    def get_quota(self,project_id):
        res=self.compute_request('os-quota-sets/%s' % project_id, method='GET')
        data=json.loads(res.read())
        return data
    @auth_token
    def list_port(self,subnet_id):
        url='ports?fixed_ips=subnet_id%3D'+subnet_id
        res=self.network_request(url,'GET')
        data=json.loads(res.read())
        ports=data.get('ports')
        if ports:
            return ports
        else:
            return []
    def list_network(self):
        res = self.network_request('networks?shared=True', 'GET')
        data=json.loads(res.read())
        networks=data.get('networks')
        if networks:
            return networks
        else:
            return []

    def list_subnetwork(self,network_id):
        res = self.network_request('subnets?network_id=%s&ip_version=4'%network_id, 'GET')
        data = json.loads(res.read())
        subnet = data.get('subnets')
        if subnet:
            return subnet
        else:
            return []
#Openstack API Request
    def create_project(self, name, domain_id=None, *args, **kwargs):
        if not domain_id:
            domain_id = self.domain_id
        return self.conn.identity.create_project(name=name, domain_id=domain_id)
    def delete_project(self, name=None, id=None):
        if id:
            self.conn.identity.delete_project(project=id)
        if name:
            self.conn.identity.delete_project(project=self.conn.identity.find_project(name_or_id=name))
    def find_domain(self, *args, **kwargs):
        # args = {
        #     'name_or_id': 'test',
        # }
        return self.conn.identity.find_domain(**args[0])
    def find_user(self,name_or_id):
        return self.conn.identity.find_user(name_or_id=name_or_id)
    def list_flavor(self):
        flavors=self.conn.compute.flavors()
        flavor_dict={}
        for flavor in flavors:
            flavor_dict[flavor.id] = {
                'ram': flavor.ram,
                'vcpus': flavor.vcpus,
                'disk': flavor.disk,
            }
        return flavor_dict
    def get_flavor(self,name_or_id):
        return self.conn.compute.find_flavor(name_or_id=name_or_id)
    def delte_server(self,server_id):
        self.conn.compute.delete_server(server_id=server_id)
    def hypervisors_stats(self):
        res=self.compute_request('/os-hypervisors/statistics','GET')
        data=json.loads(res.read())
        hypervisors=data.get('hypervisor_statistics',None)
        return hypervisors
    def network_hypervisors_stats(self):
        network_count = {}
        network_count['total'] = {}
        network_count['free'] = {}
        for network in self.list_network():
            for subnet in self.list_subnetwork(network.get('id')):
                addr_count = 0
                for all_pools in subnet.get('allocation_pools'):
                    start = all_pools.get('start').split('.')[3]
                    end = all_pools.get('end').split('.')[3]
                    addr_count += int(end) - int(start)
                ports = self.list_port(subnet_id=subnet.get('id'))
                network_count['total'][network.get('id')] = addr_count
                network_count['free'][network.get('id')] = addr_count - len(ports)
        return network_count
    def get_extnetworks(self):
        extnetworks_list = []
        res = self.network_request('networks?router:external=True&fields=id&fields=name', 'GET')
        networks = json.loads(res.read())
        for network in networks.get('networks', []):
            extnetworks_dict = {}
            extnetworks_dict['id'] = network.get('id', None)
            extnetworks_dict['name'] = network.get('name', None)
            extnetworks_list.append(extnetworks_dict)
        return extnetworks_list
    def get_port_device(self,network_id, is_extnetwork=False):
        ports_id_list = []
        if is_extnetwork:
            res = self.network_request(
                'ports?network_id=%s&device_owner=network:router_gateway&fields=device_id' % network_id,
                'GET')
        else:
            res = self.network_request(
                'ports?network_id=%s&device_owner=network:router_interface&fields=device_id' % network_id,
                'GET')
        data = json.loads(res.read())
        for port in data.get('ports', []):
            ports_id_list.append(port.get('device_id'))
        return ports_id_list
    def verify_bind_float(self,innetwork_id, ext_network_id):
        ext_devices = self.get_port_device(network_id=ext_network_id, is_extnetwork=True)
        in_devices = self.get_port_device(network_id=innetwork_id)
        for device in ext_devices:
            if device in in_devices:
                return True
        return False
    def get_float_network(self,network_id_list):
        float_networks = []
        ext_networks = self.get_extnetworks()
        ext_devices_dict = {}
        for ext_network in ext_networks:
            ext_devices = self.get_port_device(network_id=ext_network.get('id', None), is_extnetwork=True)
            for port in ext_devices:
                ext_devices_dict[port] = {
                    'id': ext_network.get('id', None),
                    'name': ext_network.get('name', None),
                }
        for network_id in network_id_list:
            in_devices = self.get_port_device(network_id=network_id['in_network'])
            for in_device in in_devices:
                bind_float = ext_devices_dict.get(in_device, None)
                if bind_float:
                    float_networks.append(bind_float)
                    ext_devices_dict.pop(in_device)
        return float_networks

    def close(self):
        del self.conn
class UserOpenstack(object):
    def __init__(self, project=lease_conf.PROJECT, username=lease_conf.USERNAME, password=lease_conf.PASSWORD,
                 domain=lease_conf.DOMAIN,
                 ip=lease_conf.IP, project_id=None):
        self.ip = ip
        self.username = username
        self.password = password
        self.project_id = project_id
        self.domain = domain
        self.token = None
    # Service Base
    def identity_request(self, server, method, headers=None, data=None, echo=None):
        ip = self.ip
        port = lease_conf.keystone_auth.get('port', None)
        keystone_url = lease_conf.keystone_auth.get('url', None)
        version = lease_conf.keystone_auth.get('version', None)
        url = '%s/%s/%s' % (keystone_url, version, server)
        if echo:
            print('keystone request url:[%s]%s' % (method, url))
        if not headers:
            headers = {
                "Content-type": "application/json",
            }
        return http_request(ip=ip, port=port, url=url, method=method, headers=headers, data=data)
    def compute_request(self, server, method, headers=None, data=None, echo=None):
        ip = self.ip
        port = lease_conf.compute_auth.get('port', None)
        compute_url = lease_conf.compute_auth.get('url', None)
        version = lease_conf.compute_auth.get('version', None)
        url = '%s/%s/%s' % (compute_url, version, server)
        if echo:
            print('compute request url:[%s]%s' % (method, url))
        if not self.token:
            self.get_token()
        if not headers:
            headers = {
                "Content-type": "application/json",
                "X-Auth-Token": self.token,
            }
        return http_request(ip=ip, port=port, url=url, method=method, headers=headers, data=data)
    def network_request(self, server, method, headers=None, data=None, echo=None):
        ip = self.ip
        port = lease_conf.network_auth.get('port', None)
        network_url = lease_conf.network_auth.get('url', None)
        version = lease_conf.network_auth.get('version', None)
        url = '%s/%s/%s' % (network_url, version, server)
        if echo:
            print('network request url:[%s]%s' % (method, url))
        if not self.token:
            self.get_token()
        if not headers:
            headers = {
                "Content-type": "application/json",
                "X-Auth-Token": self.token,
            }
        return http_request(ip=ip, port=port, url=url, method=method, headers=headers, data=data)
    def get_token(self):
        data = {"auth": {"identity": {"methods": ["password"],
                                      "password": {"user": {"name": self.username, "password": self.password,
                                                            "domain": {"name": self.domain}}}},
                         "scope": {"project": {"id": self.project_id, "domain": {"name": self.domain}}}}}
        res = self.identity_request(server='auth/tokens', method='POST', data=data)
        self.token = res.getheader('X-Subject-Token')
    @auth_token
    def create_server(self,*args,**kwargs):
        res=self.compute_request('servers', method='POST', data=args[0])
        data=json.loads(res.read())
        return data
    @auth_token
    def delete_server(self,server_id_list):
        for server_id in server_id_list:
            self.compute_request('servers/%s'%server_id, method='DELETE')

    @auth_token
    def list_server(self):
        res=self.compute_request('servers', method='GET')
        data=json.loads(res.read())
        server=data.get('servers',None)
        if server:
            return server
        return []
    def list_server_id(self):
        list_id=[]
        servers=self.list_server()
        if servers:
            for server in servers:
                server_id=server.get('id',None)
                if server_id:
                    list_id.append(server_id)
        return list_id
    def float_create(self,float_network_id,band_port_id):
        data={
            "floatingip": {
                "floating_network_id": float_network_id,
                "port_id": band_port_id,
            }
        }
        self.network_request('floatingips', 'POST',data=data)
    def flaot_list(self):
        res=self.network_request('floatingips','GET')
        data=json.loads(res.read())
        floatingips=data.get('floatingips',None)
        if floatingips:
            return floatingips
        else:
            return []
    def get_float_id(self):
        float_id_list=[]
        floats=self.flaot_list()
        if floats:
            for float in floats:
                float_id=float.get('id')
                if float_id:
                    float_id_list.append(float_id)
        return float_id_list
    def delete_float_all(self):
        for float_id in self.get_float_id():
            self.network_request('floatingips/%s'%float_id,'DELETE')
    def list_port(self,network_id):
        res=self.network_request('ports?network_id=%s'%network_id,'GET')
        data=json.loads(res.read())
        ports=data.get('ports')
        if ports:
            return ports
        else:
            return []
    def list_port_id(self,network_id):
        port_id_list=[]
        ports=self.list_port(network_id)
        if ports:
            for port in ports:
                port_id=port.get('id',None)
                if port_id:
                    port_id_list.append(port_id)
        return port_id_list
    def server_action(self,server_id,*args,**kwargs):
        self.compute_request('servers/%s/action'%server_id, method='POST', data=args[0])

