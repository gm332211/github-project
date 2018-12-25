#-*- coding: utf-8 -*-
from db.openstack_db import Group,Network
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from conf import openstack_setting as lease_conf
import datetime
engine = create_engine(lease_conf.ENGINE,encoding='utf-8', echo=False)
DBSession=sessionmaker(bind=engine,autocommit=False,autoflush=False)
class DBStore():
    def __init__(self):
        self.session = DBSession()
    def order_list(self,user_id):
        self.session.commit()
        # groups = self.session.query(Group).filter(Group.project_id.in_(project_id_list)).all()
        groups = self.session.query(Group).filter(Group.user_id==user_id).all()
        return groups
    def order_get(self,user_id,order_id):
        self.session.commit()
        # groups = self.session.query(Group).filter(Group.project_id.in_(project_id_list)).all()
        groups = self.session.query(Group).filter(Group.id==order_id).filter(Group.user_id==user_id).first()
        return groups
    def order_disbinding_flaot(self,user_id,order_id):
        group=self.order_get(user_id,order_id)
        if group:
            for network in group.network:
                network.ext_network=None
                self.session.commit()
            return True
        return False
    def order_action(self,user_id,order_id,server_type):
        group=self.order_get(user_id,order_id)
        if group:
            group.status=server_type
            self.session.commit()
            return True
        return False
    def verify_network(self,network_id):
        self.session.commit()
        network = self.session.query(Network).filter(Network.id==network_id).first()
        if network:
            return network.in_network
        return False
    def update_flaot_network(self,network_id,ext_network):
        self.session.commit()
        network = self.session.query(Network).filter(Network.id==network_id).first()
        if network:
            network.ext_network=ext_network
            self.session.commit()
            return True
        else:
            return False
    def order_network_id_list(self,user_id,order_id):
        in_network_list=[]
        obj=self.order_get(user_id,order_id)
        if obj:
            for network in obj.network:
                network_dic={}
                network_dic['id']=network.id
                network_dic['in_network']=network.in_network
                in_network_list.append(network_dic)
        return in_network_list
    def order_select(self,user_id,id):
        group=self.session.query(Group).filter(Group.user_id==user_id).filter(Group.id==id).first()
        return group
    def order_create(self,name,image_id,flavor_id,internal_network,start_time,stop_time,count,status,user_id,project_id=None):
        network_obj=self.network_create(internal_network)
        group=Group(name=name, image_id=image_id, flavor_id=flavor_id,start_time=start_time,
                    stop_time=stop_time,count=count,status=status,project_id=project_id,user_id=user_id,network=network_obj)
        self.session.add(group)
        self.session.commit()
    def order_delete(self,user_id,delete_id):
        obj=self.order_select(user_id,delete_id)
        self.delete_db(obj)
    def order_update(self):
        pass
    def order_user_verify(self,user_id,order_id):
        obj=self.order_select(user_id=user_id,id=order_id)
        if obj:
            return True
        return False
    def network_create(self,networks):
        networks_obj=[]
        if networks:
            for network in networks:
                if network:
                    network_id=network.get('net-id',None)
                    network = Network(in_network=network_id)
                    self.session.add(network)
                    self.session.commit()
                    networks_obj.append(network)
        return networks_obj

    def resource_compute(self, start_time):
        flavor_id_list=[]
        in_use=self.session.query(Group).filter(Group.start_time<start_time).filter(Group.stop_time>start_time).filter(Group.status=='wait')
        if in_use:
            for use in in_use:
                flavor_id_list.append(use.flavor_id)
        return flavor_id_list

    def use_resource_db(self):
        order_list = []
        date_now = datetime.datetime.now()
        objs = self.session.query(Group).filter(Group.stop_time > date_now).filter(Group.status == 'created')
        for obj in objs:
            order_dict={}
            order_dict['count']=int(obj.count)
            order_dict['flavor_id']=obj.flavor_id
            order_dict['network_id'] = []
            for network in obj.network:
                if network.in_network:
                    order_dict['network_id'].append(network.in_network)
                if network.ext_network:
                    order_dict['network_id'].append(network.ext_network)
            order_list.append(order_dict)
        return order_list

    def occupy_order_db(self,start_time, stop_time):
        order_list = []
        objs = self.session.query(Group).filter(Group.start_time <= stop_time, Group.stop_time >= start_time,
                                           Group.status != 'dead').all()
        if objs:
            for obj in objs:
                order_dict={}
                order_dict['count']=int(obj.count)
                order_dict['flavor_id']=obj.flavor_id
                order_dict['network_id'] = []
                for network in obj.network:
                    if network.in_network:
                        order_dict['network_id'].append(network.in_network)
                    if network.ext_network:
                        order_dict['network_id'].append(network.ext_network)
                order_list.append(order_dict)
        return order_list
    def delete_db(self,db_obj):
        self.session.delete(db_obj)
        self.session.commit()

