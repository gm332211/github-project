from api import Openstack
op=Openstack.UserOpenstack(project_id='dd92a1fe25614b03bb221facc351acd4')
# data={
#     "server": {
#         "name": 'test',
#         "imageRef": '9c9f397a-86a6-4548-8e38-3b45a27ef63b',
#         "flavorRef": '42',
#         "networks": [{"uuid": 'f9c6febf-2ac9-4439-b460-5ae6f7f37723'}],
#         'min_count': '2',
#         'max_count': '2',
#     },
# }
# data=op.create_server(data)
servers=op.list_server()
for server in servers:
    print(servers)