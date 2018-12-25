from api import connect,nova
conn=connect.Conn()
server_dict={
    'name':'test-instance',
    'imageRef':'d7b418b0-9828-4664-85b3-62571f05d3a1',
    'flavorRef':1,
    'networks':[{"uuid": '7a47d9f7-f47a-4321-99c4-8fdb7e48567a'}],
    'min_count':2,
    'max_count':2,
}

nova.create_server(conn,server_dict)