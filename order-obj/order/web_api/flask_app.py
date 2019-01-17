#-*- coding:utf-8 -*-
# @Author:xiaoming
from flask import jsonify
import datetime
from web_api.views import db_handle
from conf import openstack_setting as lease_conf
from flask import Flask
from flask import request
from api import Openstack
from api import connect
# this is order api interface
conn=connect.Conn()
op=Openstack.Openstack(conn)
app=Flask(__name__)
db=db_handle.DBStore()
db.get_session()
#flavor cookie
flavor_dict=op.list_flavor()
global_resource={}
def get_flavor_resource(resource_list):
    sum_ram=0
    sum_vcpus=0
    sum_disk=0
    for resource in resource_list:
        flavor_id=resource.get('flavor_id')
        flavor_resource=flavor_dict.get(flavor_id,None)
        if not flavor_resource:
            flavor_obj=op.get_flavor(flavor_id)
            flavor_resource={
                'ram': int(flavor_obj.ram) or 0,
                'vcpus': int(flavor_obj.vcpus) or 0,
                'disk':int(flavor_obj.disk) or 0,
            }
            flavor_dict[flavor_obj.id]=flavor_resource
        count=int(resource.get('count',0))
        sum_ram+=flavor_resource.get('ram',0)*count
        sum_vcpus += flavor_resource.get('vcpus',0)*count
        sum_disk += flavor_resource.get('disk',0)*count
    return {'ram':sum_ram,'vcpus':sum_vcpus,'disk':sum_disk}
def get_network_resource(resource_list):
    network_count={}
    for resource in resource_list:
        for network_id in resource.get('network_id'):
            if not network_count.get(network_id,None):
                network_count[network_id]=resource.get('count')
            else:
                network_count[network_id]+=resource.get('count')
            resource.get('network_id')
    return network_count
def total_resource(start_time,stop_time):
    data=op.hypervisors_stats()
    network_data=op.network_hypervisors_stats()
    if not global_resource:
        global_resource['ram']=data.get('memory_mb')
        global_resource['vcpus'] = data.get('vcpus')
        global_resource['disk'] = data.get('free_disk_gb')
        global_resource['network'] = network_data.get('total')
    free_resource={
        'ram':data.get('free_ram_mb'),
        'vcpus':data.get('vcpus')-data.get('vcpus_used'),
        'disk':data.get('disk_available_least'),
        'network':network_data.get('free')
    }
    resource_list=db.use_resource_db()
    order_flavor_resource=get_flavor_resource(resource_list)
    order_network_resource=get_network_resource(resource_list)
    occupy_resource=db.occupy_order_db(start_time, stop_time)
    occupy_flavor_resource=get_flavor_resource(occupy_resource)
    occupy_network_resource=get_network_resource(occupy_resource)
    sum_ram=free_resource.get('ram')+order_flavor_resource.get('ram')-occupy_flavor_resource.get('ram')
    sum_vcpus=free_resource.get('vcpus')+order_flavor_resource.get('vcpus')-occupy_flavor_resource.get('vcpus')
    sum_disk=free_resource.get('disk')+order_flavor_resource.get('disk')-occupy_flavor_resource.get('disk')
    sum_network={}
    for network in free_resource.get('network'):
        free_network=free_resource.get('network').get(network,0)
        order_network=order_network_resource.get(network,0)
        occupy_network=occupy_network_resource.get(network,0)
        sum_network[network]=free_network+int(order_network)-int(occupy_network)

    return {'ram':sum_ram,'vcpus':sum_vcpus,'disk':sum_disk,'network':sum_network}
@app.route('/orders',methods=['POST'])
def order_create():
    response_data={'status':'201'}
    data=request.json
    name = data.get('name',None)
    image_id = data.get('image_id',None)
    flavor_id = data.get('flavor_id',None)
    network = data.get('networks',None)
    start_time = data.get('start_time',None)
    stop_time = data.get('stop_time',None)
    count = data.get('count', 1)
    status=data.get('status','wait')
    startTime = datetime.datetime.strptime(start_time, '%Y-%m-%d %H:%M:%S')
    stopTime = datetime.datetime.strptime(stop_time, '%Y-%m-%d %H:%M:%S')
    v_token = request.headers.get('X-Auth-Token', None)
    try:
        user_id=op.get_user_id(v_token)
        admin_user=op.find_user(lease_conf.USERNAME)
        project=op.create_project(name)
        op.add_role(user_id=user_id,project_id=project.id)
        op.add_role(user_id=admin_user.id, project_id=project.id)
        flavor=op.get_flavor(flavor_id)
        op.update_quota(project_id=project.id,ram=int(flavor.ram)*int(count),cores=int(flavor.vcpus)*int(count),count=int(count))
        db.order_create(name=name, image_id=image_id, flavor_id=flavor_id, internal_network=network,
                        start_time=startTime, stop_time=stopTime, count=count, status=status,project_id=project.id,user_id=user_id)
    except Exception as e:
        response_data['status']='401'
    return jsonify(response_data)
@app.route('/orders',methods=['GET'])
def order_list():
    orders_dict={}
    v_token=request.headers.get('X-Auth-Token',None)
    user_id=op.get_user_id(user_token=v_token)
    orders=db.order_list(user_id=user_id)
    if orders:
        for order in orders:
            orders_dict[order.id]={
                'id':order.id,
                'name':order.name,
                'image_id':order.image_id,
                'flavor_id': order.flavor_id,
                'extenal_network':[],
                'internal_network': [],
                'start_time': order.start_time.strftime("%Y-%m-%d %H:%S:%M"),
                'stop_time': order.stop_time.strftime("%Y-%m-%d %H:%S:%M"),
                'count': order.count,
                'status': order.status,
                'project_id':order.project_id
            }
            networks=order.network
            if networks:
                for network in networks:
                    orders_dict[order.id]['internal_network'].append(network.in_network)
                    orders_dict[order.id]['extenal_network'].append(network.ext_network)
    return jsonify(orders_dict)
@app.route('/orders/<order_id>',methods=['GET'])
def order_get(order_id):
    orders_dict={}
    v_token=request.headers.get('X-Auth-Token',None)
    user_id=op.get_user_id(user_token=v_token)
    order=db.order_get(user_id=user_id,order_id=order_id)
    if order:
        orders_dict={
            'id':order.id,
            'name':order.name,
            'image_id':order.image_id,
            'flavor_id': order.flavor_id,
            'extenal_network':[],
            'internal_network': [],
            'start_time': order.start_time.strftime("%Y-%m-%d %H:%S:%M"),
            'stop_time': order.stop_time.strftime("%Y-%m-%d %H:%S:%M"),
            'count': order.count,
            'status': order.status,
            'project_id':order.project_id
        }
        networks=order.network
        if networks:
            for network in networks:
                orders_dict[order.id]['internal_network'].append(network.in_network)
                orders_dict[order.id]['extenal_network'].append(network.ext_network)
    return jsonify(orders_dict)
@app.route('/orders/<order_id>',methods=['DELETE'])
def order_delete(order_id):
    v_token = request.headers.get('X-Auth-Token', None)
    user_id=op.get_user_id(v_token)
    try:
        order_obj=db.order_select(user_id,order_id)
        if order_obj.status=='dead' or order_obj.status=='wait':
            try:
                op.delete_project(order_obj.project_id)
            except:
                pass
            networks=order_obj.network
            db.delete_db(order_obj)
            if networks:
                for network_obj in networks:
                    db.delete_db(network_obj)
        elif order_obj.status=='created' or order_obj.status=='stoping':
            print(1)
            order_obj.status='deleteing'
            db.session.commit()
    except Exception as e:
        print(e)
        return 'error'
    return 'ok'
@app.route('/orders/<order_id>',methods=['PUT'])
def order_update(order_id):
    data = request.json
    image_id = data.get('image_id',None)
    flavor_id = data.get('flavor_id',None)
    network = data.get('networks',None)
    count = data.get('count', 1)
    v_token = request.headers.get('X-Auth-Token', None)
@app.route('/orders/float/<order_id>',methods=['GET'])
def order_get_float(order_id):
    v_token=request.headers.get('X-Auth-Token',None)
    user_id=op.get_user_id(user_token=v_token)
    network_list=db.order_network_id_list(user_id=user_id,order_id=order_id)
    networks=op.get_float_network(network_list)
    # print(op.verify_bind_float('f9c6febf-2ac9-4439-b460-5ae6f7f37723', 'efbe5cc2-f8a3-48a3-beba-32ce2490f091'))
    # print(op.get_float_network(['f9c6febf-2ac9-4439-b460-5ae6f7f37723']))
    return jsonify({'order_id':order_id,'in_network_id':network_list,'ext_network_id':networks})
@app.route('/orders/float/binding/<order_id>',methods=['POST'])
def order_bind_float(order_id):
    v_token = request.headers.get('X-Auth-Token', None)
    user_id = op.get_user_id(user_token=v_token)
    if db.order_user_verify(user_id=user_id,order_id=order_id):
        data = request.json
        network_id=data.get('network_id')
        ext_network_id=data.get('ext_network_id')
        in_network_id=db.verify_network(network_id=network_id)
        if in_network_id:
            if op.verify_bind_float(innetwork_id=in_network_id, ext_network_id=ext_network_id):
                if db.update_flaot_network(network_id=network_id,ext_network=ext_network_id):
                    return jsonify({'status':201})
    return jsonify({'status': 401})
@app.route('/orders/float/disbinding/<order_id>',methods=['GET'])
def order_disbind_float(order_id):
    v_token = request.headers.get('X-Auth-Token', None)
    user_id = op.get_user_id(user_token=v_token)
    if db.order_disbinding_flaot(user_id=user_id,order_id=order_id):
        return jsonify({'status':201})
    return jsonify({'status':401})
@app.route('/orders/action/<order_id>/<server_type>',methods=['GET'])
def order_action(order_id,server_type):
    v_token = request.headers.get('X-Auth-Token', None)
    user_id = op.get_user_id(user_token=v_token)
    if db.order_action(user_id=user_id,order_id=order_id,server_type=server_type):
        return jsonify({'status':201})
    return jsonify({'status':401})
@app.route('/orders/hypervisor/<start_time>/<stop_time>', methods=['GET'])
def order_hypervisor(start_time,stop_time):
    if start_time=='None':
        start_time=datetime.datetime.now()
    else:
        start_time = datetime.datetime.strptime(start_time, '%Y-%m-%d %H:%M')
    if stop_time=='None':
        stop_time = datetime.datetime.now()
    else:
        stop_time = datetime.datetime.strptime(stop_time, '%Y-%m-%d %H:%M')
    data=total_resource(start_time,stop_time)
    return jsonify({'free_resource':data,'total_resource':global_resource})
app.run('0.0.0.0',port=int(lease_conf.WEBPORT),debug=True,threaded=True)