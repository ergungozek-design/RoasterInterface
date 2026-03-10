import ssl
from paho.mqtt import client as mqtt_client

broker = "08bb54f5ee234a86ba2d3e07280da8ed.s1.eu.hivemq.cloud"
port = 8883
topic = "TOPIC1"
username = "roaster"
password = "CemGozek1!"


def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("Broker'a bağlandı")
        client.subscribe(topic)
        print(f"{topic} dinleniyor...")
    else:
        print("Bağlantı hatası:", rc)


def on_message(client, userdata, msg):
    print(f"Gelen topic: {msg.topic}")
    print(f"Gelen mesaj: {msg.payload.decode()}")
    print("-" * 40)


client = mqtt_client.Client(
    mqtt_client.CallbackAPIVersion.VERSION1,
    client_id="reader_client"
)

client.username_pw_set(username, password)
client.tls_set(tls_version=ssl.PROTOCOL_TLS)

client.on_connect = on_connect
client.on_message = on_message

client.connect(broker, port)
client.loop_forever()