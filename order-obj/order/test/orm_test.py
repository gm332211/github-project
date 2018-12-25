from db import openstack_db
from db.openstack_db import Group,Network
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from conf import openstack_setting as lease_conf
from conf import openstack_setting as lease_conf

engine = create_engine(lease_conf.ENGINE,encoding='utf-8', echo=False)
DBSession=sessionmaker(bind=engine,autocommit=False,autoflush=False)
session = DBSession()
network=Network(in_network='abc')
session.add(network)
session.commit()
group=Group(name='1',image_id='1',flavor_id='1',count='1',status='wait',project_id='1',network=[network])
session.add(group)
session.commit()
