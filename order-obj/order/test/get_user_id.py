from api import Openstack
from api.Openstack import http_request
from api import connect
conn=connect.Conn()
op=Openstack.Openstack(conn)
# token='gAAAAABcDe5zzx_t1HMe3uEHluHnG6wO72C3q-Bhy8nJzvgpx39nFcq08qP0cUJP1ScwtXns-BzQP8GA5gnWWMnGwq5ktycNFUqA2VUufgRFNSnY37C4y-RlhCVZdLBAtCrBAyIQqymfhFxCbi-_gQK5oXVe7baF_a4PZRHXJn2TcqQ46aSZWkk'
# user_id=op.get_user(user_token=token)
# print(user_id)
op.conn.compute.delete_server()

# # data=op.get_quota(project_id='e33c58fff3f040f79c27d2e7a4fddb25')
# data=op.update_quota(project_id='e33c58fff3f040f79c27d2e7a4fddb25',cores=1,count=1,ram=1)
# print(data)

