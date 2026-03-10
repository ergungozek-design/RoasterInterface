import time
import ssl
from paho.mqtt import client as mqtt_client

broker = '08bb54f5ee234a86ba2d3e07280da8ed.s1.eu.hivemq.cloud'
port = 8883
topic = "TOPIC1"
username = "roaster"
password = "CemGozek1!"


def connect_mqtt():

    def on_connect(client, userdata, flags, rc):
        if rc == 0:
            print("Connected to MQTT Broker!")
        else:
            print("Failed to connect, return code:", rc)

    client = mqtt_client.Client(
        mqtt_client.CallbackAPIVersion.VERSION1,
        client_id="cem_python_script"
    )

    client.username_pw_set(username, password)

    client.tls_set(tls_version=ssl.PROTOCOL_TLS)

    client.on_connect = on_connect

    client.connect(broker, port)

    return client


client = connect_mqtt()

client.loop_start()

while True:
    time.sleep(1)