from api import connect
conn=connect.Conn()
for server in conn.compute.servers():
    print(server)