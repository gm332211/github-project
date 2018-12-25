#-*- coding: utf-8 -*-
#Auther:GM
import threading
from conf import openstack_setting as lease_conf
from api.order import Producer_Create,Threading_Create,Producer_Delete,Threading_Delete,Producer_Action,Threading_Action
# ,,,Producer_Action,Threading_Action
p1 = threading.Thread(target=Producer_Create)
c1 = threading.Thread(target=Threading_Create,kwargs={'count':lease_conf.CREATE_THREAD_COUNT})
p2 = threading.Thread(target=Producer_Delete)
c2 = threading.Thread(target=Threading_Delete,kwargs={'count':lease_conf.DELETE_THREAD_COUNT})
p3 = threading.Thread(target=Producer_Action)
c3 = threading.Thread(target=Threading_Action,kwargs={'count':lease_conf.ACTION_THREAD_COUNT})
print('running.....')
p1.start()
p2.start()
p3.start()
c1.start()
c2.start()
c3.start()