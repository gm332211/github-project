#-*- coding:utf-8 -*-
# @Author:xiaoming
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
    def start_timeout(self):
        self.session.commit()
        time_now=datetime.datetime.now()
        groups=self.session.query(Group).filter(Group.start_time<=time_now).filter(Group.status=='wait').all()
        if groups:
            for group in groups:
                group.status='created'
            self.session.commit()
        return groups
    def stop_timeout(self):
        self.session.commit()
        time_now=datetime.datetime.now()
        groups=self.session.query(Group).filter(Group.stop_time<=time_now).filter(Group.status=='created').all()
        return groups
    def deleteing(self):
        self.session.commit()
        groups=self.session.query(Group).filter(Group.status=='deleteing').all()
        return groups
    def recycle_db(self,objs):
        for obj in objs:
            obj.status='dead'
            self.session.commit()
    def get_action(self,server_type):
        self.session.commit()
        groups = self.session.query(Group).filter(Group.status == server_type).all()
        if groups:
            for group in groups:
                if server_type=='rebuild':
                    group.status='created'
                if server_type == 'stop':
                    group.status = 'stoping'
                if server_type == 'start':
                    group.status = 'created'
                if server_type == 'reboot':
                    group.status = 'created'
            self.session.commit()

        return groups
