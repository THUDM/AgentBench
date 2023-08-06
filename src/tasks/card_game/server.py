import socket
import threading
import json
import time

class Server:
    def __init__(self, port, workers, host='localhost'):
        self.host = host
        self.port = port
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        
        while (True):
            try:
                self.socket.bind((self.host, self.port))
                break
            except OSError as e:
                self.port += 1
        self.socket.listen(workers+2)
        self.log = {}

    def start(self, folder, session):
        log_file = []
        client_socket, client_address = self.socket.accept()
        while True:
            data = client_socket.recv(10000).decode()
            if data == "":
                self.stop(client_socket)
                break
            else:
                log_file.append({"role": "user", "content": data})
            try:
                ret = session.model_inference(json.loads(data))
                log_file.append({"role": "agent", "content": ret})
                self.send_message(client_socket, ret)
            except json.decoder.JSONDecodeError:
                self.send_message(client_socket, "")
        self.log[folder] = log_file
        
    def send_message(self, client_socket, message):
        client_socket.sendall(message.encode())

    def stop(self, client_socket):
        client_socket.close()