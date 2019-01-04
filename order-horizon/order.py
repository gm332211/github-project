import httplib,json
from horizon.utils import functions as utils
from openstack_dashboard.api import base
from django.conf import settings
from openstack_dashboard import api
from openstack_dashboard.local import local_settings
import urllib
flavors_dic={}
images_dic={}
networks_dic={}
def get_images(request):
    images,more,prev = api.glance.image_list_detailed(
        request,
        paginate=True,
        sort_dir='asc',
        sort_key='name',)
    for image in images:
        if not image.id in images_dic:
            images_dic[image.id] = image.name
def get_flavors(request):
    flavors=api.nova.flavor_list(request)
    for flavor in flavors:
        if not flavor.id in flavors_dic:
            flavors_dic[flavor.id]={
                'flavor_name':flavor.name,
                'disk':flavor.disk,
                'vcpu':flavor.vcpus,
                'ram':flavor.ram
            }
def get_networks(request):
    networks=api.neutron.network_list(request)
    for network in networks:
        if not network.id in networks_dic:
            networks_dic[network.id] = network.name
def http_request(ip,port,method,url,headers,data):
    res=None
    conn=httplib.HTTPConnection(ip,port)
    conn.request(method=method,url=url,headers=headers,body=data)
    try:
        res=conn.getresponse()
    except:
        pass
    return res
def order_request(server,method,token,data=None):
    ip=local_settings.LEASE_IP
    port=local_settings.LEASE_PORT
    url='http://%s:%s/%s'%(ip,port,server)
    headers={
        "Content-type": "application/json",
        "X-Auth-Token": token,
    }
    res=http_request(ip,port,method,url,headers,data)
    return res
def order_list_base(request):
    data = None
    res = order_request('orders', 'GET',token=request.user.token.id)
    if res:
        data = json.loads(res.read())
    data_list = []
    if data:
        for key in data:
            data_list.append(order_base([data[key]]))
    return data_list
def order_list(request, search_opts=None, detailed=True):
    if not flavors_dic:
        get_flavors(request)
    if not images_dic:
        get_images(request)
    if not networks_dic:
        get_networks(request)
    page_size = utils.get_page_size(request)
    paginate = False
    if search_opts is None:
        search_opts = {}
    elif 'paginate' in search_opts:
        paginate = search_opts.pop('paginate')
        if paginate:
            search_opts['limit'] = page_size + 1

    all_tenants = search_opts.get('all_tenants', False)
    if all_tenants:
        search_opts['all_tenants'] = True
    else:
        search_opts['project_id'] = request.user.tenant_id
    leases = [Order(s, request)
               for s in order_list_base(request)]
    has_more_data = False
    if paginate and len(leases) > page_size:
        leases.pop(-1)
        has_more_data = True
    elif paginate and len(leases) == getattr(settings, 'API_RESULT_LIMIT',
                                              1000):
        has_more_data = True
    return (leases, has_more_data)
def order_float_network(request,order_id):
    data = None
    res = order_request('orders/float/%s'%order_id, 'GET',token=request.user.token.id)
    if res:
        data = json.loads(res.read())
    return data
def order_bind_float(request,order_id,network_id,ext_network_id):
    data={
        'network_id':network_id,
        'ext_network_id':ext_network_id,
    }
    res = order_request('orders/float/binding/%s'%order_id, 'POST',token=request.user.token.id,data=json.dumps(data))
    if res:
        data = json.loads(res.read())
    return data
def order_disbind_float(request,order_id):
    res = order_request('orders/float/disbinding/%s'%order_id, 'GET',token=request.user.token.id)
    if res:
        data = json.loads(res.read())
        return data
    return {}
def order_action(request,order_id,server_type):
    res = order_request('orders/action/%s/%s'%(order_id,server_type), 'GET',token=request.user.token.id)
    if res:
        data = json.loads(res.read())
        return data
    return {}
def order_hypervisor(request,start_time,stop_time):
    res = order_request(urllib.quote(('orders/hypervisor/%s/%s'%(start_time,stop_time))), 'GET',token=request.user.token.id)
    data={}
    if res:
        data = json.loads(res.read())
        return data
    return data
def order_create(request,name,image_id,flavor_id,nics,start_time,stop_time,count):
    data={
        'token':request.user.token.id,
        'name':name,
        'image_id': image_id,
        'flavor_id': flavor_id,
        'networks': nics,
        'start_time': start_time,
        'stop_time': stop_time,
        'count':count
    }
    order_request('orders','POST',data=json.dumps(data),token=request.user.token.id)
def order_delete(request,id):
    order_request('orders/%s'%id,'DELETE',token=request.user.token.id)
class order_base(object):
    def __init__(self,data):
        self.data=data[0]
    @property
    def id(self):
        return self.data.get('id',None)
    @property
    def project_id(self):
        return self.data.get('project_id',None)
    @property
    def name(self):
        return self.data.get('name', None)
    @property
    def image_id(self):
        return self.data.get('image_id', None)
    @property
    def flavor_id(self):
        return self.data.get('flavor_id', None)
    @property
    def internal_network(self):
        return self.data.get('internal_network', None)
    @property
    def extenal_network(self):
        return self.data.get('extenal_network', None)
    @property
    def start_time(self):
        return self.data.get('start_time', None)
    @property
    def stop_time(self):
        return self.data.get('stop_time', None)
    @property
    def count(self):
        return self.data.get('count',None)
    @property
    def status(self):
        return self.data.get('status',None)
    def __str__(self):
        return self.name
class Order(base.APIResourceWrapper):
    """Simple wrapper around novaclient.server.Server.
    Preserves the request info so image name can later be retrieved.
    """
    _attrs = ['id','name', 'image_id', 'flavor_id', 'network_id', 'start_time', 'stop_time','count','status','internal_network','extenal_network','project_id']
    def __init__(self, apiresource, request):
        super(Order, self).__init__(apiresource)
        self.request = request
    # TODO(gabriel): deprecate making a call to Glance as a fallback.
    @property
    def image_name(self):
        image=images_dic.get(self.image_id, None)
        if not image:
            get_images(self.request)
            image = images_dic.get(self.image_id, None)
        return image
    @property
    def flavor_name(self):
        flavors=flavors_dic.get(self.flavor_id, None).get('flavor_name',None)
        if not flavors:
            get_flavors(self.request)
            flavors = flavors_dic.get(self.flavor_id, None).get('flavor_name',None)
        return flavors
    @property
    def internal_network_name(self):
        network_list=[]
        for network_id in self.internal_network:
            network=networks_dic.get(network_id,None)
            if not network:
                get_networks(self.request)
                network = networks_dic.get(network_id, None)
            network_list.append(network)
        return network_list
    @property
    def extenal_network_name(self):
        network_list = []
        for network_id in self.extenal_network:
            network=networks_dic.get(network_id,None)
            if not network:
                get_networks(self.request)
                network = networks_dic.get(network_id, None)
            network_list.append(network)
        return network_list
    @property
    def availability_zone(self):
        return getattr(self, 'OS-EXT-AZ:availability_zone', "")
class order_network(base.APIResourceWrapper):
    def __init__(self, request,network_id):
        super(order_network, self).__init__(base.APIResourceWrapper)
        self.request = request
        self.network_id=network_id
    @property
    def id(self):
        return self.network_id
    @property
    def name(self):
        network=api.neutron.network_get(self.request,network_id=self.network_id)
        return network.name