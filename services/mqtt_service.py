from paho.mqtt import client as mqtt_client
import ssl
import json
import time


class MQTTService:

    def __init__(self, broker, port=8883, username=None, password=None):
        self.broker = broker
        self.port = port
        self.username = username
        self.password = password

        self.client = None
        self.connected = False

    def _on_connect(self, client, userdata, flags, rc):

        if rc == 0:
            print("[MQTT] Connected to broker")
            self.connected = True
        else:
            print("[MQTT] Failed to connect:", rc)
            self.connected = False

    def connect(self):

        self.client = mqtt_client.Client(
            mqtt_client.CallbackAPIVersion.VERSION1,
            client_id="roaster_app"
        )

        self.client.username_pw_set(self.username, self.password)
        self.client.tls_set(tls_version=ssl.PROTOCOL_TLS)
        self.client.on_connect = self._on_connect

        try:
            self.client.connect(self.broker, self.port)
            self.client.loop_start()
            print("[MQTT] connect() called")
            return True

        except Exception as e:
            print(f"[MQTT] Connection failed: {e}")
            self.connected = False
            self.client = None
            return False

    def connect_eski_fonk(self):

        self.client = mqtt_client.Client(
            mqtt_client.CallbackAPIVersion.VERSION1,
            client_id="roaster_app"
        )

        self.client.username_pw_set(self.username, self.password)

        self.client.tls_set(tls_version=ssl.PROTOCOL_TLS)

        self.client.on_connect = self._on_connect

        self.client.connect(self.broker, self.port)

        self.client.loop_start()

    def publish(self, topic, payload):

        if not self.connected:
            return False

        if isinstance(payload, dict):
            payload = json.dumps(payload)

        self.client.publish(topic, payload)
        return True

    def disconnect(self):

        if self.client:
            self.client.loop_stop()
            self.client.disconnect()