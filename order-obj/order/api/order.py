from api import Openstack
from api import connect
from api.views import order_db_handle
import threading, Queue, time

conn = connect.Conn()
start_q = Queue.Queue()
stop_q = Queue.Queue()
action_q = Queue.Queue()
def Producer_Create():
    db = order_db_handle.DBStore()
    while True:
        groups = db.start_timeout()
        if groups:
            for group in groups:
                group_dict = {
                    "server": {
                        "name": group.name,
                        "imageRef": group.image_id,
                        "flavorRef": group.flavor_id,
                        "networks": [],
                        'min_count': group.count,
                        'max_count': group.count,
                    },
                    'project_id': group.project_id,
                    'bind_network': [],
                }
                network_list = []
                for network in group.network:
                    network_list.append({"uuid": network.in_network})
                    if network.ext_network:
                        group_dict['bind_network'].append(
                            {'in_network': network.in_network, 'ext_network': network.ext_network})
                group_dict['server']['networks'] = network_list
                start_q.put(group_dict)
        time.sleep(10)
def Consumer_Create():
    while True:
        db_dict = start_q.get()
        if db_dict:
            data = {}
            data['server'] = db_dict.get('server', None)
            op = Openstack.UserOpenstack(project_id=db_dict.get('project_id', None))
            op.get_token()
            res_data = op.create_server(data)
            time.sleep(10)
            if res_data:
                bind_network = db_dict.get('bind_network', None)
                if bind_network:
                    for network in bind_network:
                        ports_id = op.list_port_id(network_id=network.get('in_network', None))
                        for port_id in ports_id:
                            op.float_create(float_network_id=network.get('ext_network', None), band_port_id=port_id)
def Threading_Create(count=1):
    t_list = []
    for i in range(int(count)):
        t = threading.Thread(target=Consumer_Create)
        t_list.append(t)
    for t in t_list:
        t.start()
    for t in t_list:
        t.join()
def Producer_Delete():
    db = order_db_handle.DBStore()
    while True:
        groups = db.stop_timeout()
        deleteing = db.deleteing()
        if groups:
            for group in groups:
                group_dict = {
                    'project_id': group.project_id
                }
                stop_q.put(group_dict)
            db.recycle_db(groups)
        if deleteing:
            for group in deleteing:
                group_dict = {
                    'project_id': group.project_id
                }
                stop_q.put(group_dict)
            db.recycle_db(deleteing)
        time.sleep(10)
def Consumer_Delete():
    while True:
        db_dict = stop_q.get()
        if db_dict:
            op = Openstack.UserOpenstack(project_id=db_dict.get('project_id', None))
            op.get_token()
            id_list = op.list_server_id()
            op.delete_server(id_list)
            op.delete_float_all()
def Threading_Delete(count=1):
    t_list = []
    for i in range(int(count)):
        t = threading.Thread(target=Consumer_Delete)
        t_list.append(t)
    for t in t_list:
        t.start()
    for t in t_list:
        t.join()
def Producer_Action():
    db = order_db_handle.DBStore()
    while True:
        rebuild_groups = db.get_action('rebuild')
        if rebuild_groups:
            for rebuild_group in rebuild_groups:
                op = Openstack.UserOpenstack(project_id=rebuild_group.project_id)
                servers_id_list = op.list_server_id()
                for server_id in servers_id_list:
                    data = {
                        "rebuild": {
                            "OS-DCF:diskConfig": "AUTO",
                            "imageRef": rebuild_group.image_id,
                            "name": rebuild_group.name,
                        },
                        'project_id': rebuild_group.project_id,
                        'server_id': server_id
                    }
                    action_q.put(data)
        start_groups = db.get_action('start')
        if start_groups:
            for start_group in start_groups:
                op = Openstack.UserOpenstack(project_id=start_group.project_id)
                servers_id_list = op.list_server_id()
                for server_id in servers_id_list:
                    data = {
                        "os-start": 'null',
                        'project_id': start_group.project_id,
                        'server_id': server_id
                    }
                    action_q.put(data)
        stop_groups = db.get_action('stop')
        if stop_groups:
            for stop_group in stop_groups:
                op = Openstack.UserOpenstack(project_id=stop_group.project_id)
                servers_id_list = op.list_server_id()
                for server_id in servers_id_list:
                    data = {
                        "os-stop": 'null',
                        'project_id': stop_group.project_id,
                        'server_id': server_id
                    }
                    action_q.put(data)
        reboot_groups = db.get_action('reboot')
        if reboot_groups:
            for reboot_group in reboot_groups:
                op = Openstack.UserOpenstack(project_id=reboot_group.project_id)
                servers_id_list = op.list_server_id()
                for server_id in servers_id_list:
                    data = {
                        "reboot": {
                            "type": "HARD"
                        },
                        'project_id': reboot_group.project_id,
                        'server_id': server_id
                    }
                    action_q.put(data)
def Consumer_Action():
    while True:
        db_dict = action_q.get()
        op = Openstack.UserOpenstack(project_id=db_dict.get('project_id', None))
        server_id = db_dict.get('server_id', None)
        del db_dict['project_id']
        del db_dict['server_id']
        op.server_action(server_id, db_dict)
def Threading_Action(count=10):
    t_list = []
    for i in range(int(count)):
        t = threading.Thread(target=Consumer_Action)
        t_list.append(t)
    for t in t_list:
        t.start()
    for t in t_list:
        t.join()
