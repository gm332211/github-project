#-*- coding:utf-8 -*-
# @Author:xiaoming
from sqlalchemy import Column,String,Integer,DateTime,ForeignKey,create_engine,Table
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from conf import openstack_setting as lease_conf
Base=declarative_base()
group_m2m_network=Table('t_order_m2m_network',
    Base.metadata,Column('order_id',ForeignKey('t_order.id')),
    Base.metadata,Column('network_id',ForeignKey('t_network.id')),
)
class Network(Base):
    __tablename__ = 't_network'
    id = Column(Integer, primary_key=True)
    in_network = Column(String(256))
    ext_network = Column(String(256))
class Group(Base):
    __tablename__='t_order'
    id=Column(Integer,primary_key=True)
    name=Column(String(64))
    image_id=Column(String(64))
    flavor_id=Column(String(64))
    start_time=Column(DateTime)
    stop_time=Column(DateTime)
    count=Column(String(64))
    status=Column(String(64))
    project_id=Column(String(64))
    user_id=Column(String(64))
    network=relationship('Network',secondary=group_m2m_network)
    def __repr__(self):
        return self.name
engine = create_engine(lease_conf.ENGINE, encoding='utf-8')
Base.metadata.create_all(engine)