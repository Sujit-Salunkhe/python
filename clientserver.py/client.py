import socket
PORT = 5050
HEADER = 64
DISCONNECT_MESSAGE = '!DISCONNECT'
SERVER ='192.168.0.102'
FORMAT = 'utf-8'
ADDR = (SERVER,PORT)
client = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
client.connect(ADDR)

def send(msg):
    message = msg.encode(FORMAT)
    msg_length = len(message)
    send_length = str(msg_length).encode(FORMAT)
    send_length  += b' ' * (HEADER - len(send_length))
    client.send(send_length)
    client.send(message)
    print(client.recv(2048).decode(FORMAT))


send("This is from Asus")
send('Zandu balm hu darling zandu balm hogyi darling tere liye')
inputmsg = input()
send(inputmsg)
send(DISCONNECT_MESSAGE)
                                                                                              