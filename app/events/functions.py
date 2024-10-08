import logging

import paho.mqtt.client as mqtt
from django.conf import settings

from .signals import handler_event_signal

logger = logging.getLogger("django")


def _get_from_payload(payload):
    data = "".join(map(chr, payload)).split(":")
    try:
        return {
            "origin": data[0],
            "entity": data[1],
            "key": data[2] if len(data) >= 3 else None,
            "action": data[3] if len(data) == 4 else None,
        }
    except Exception:
        logger.warn("MQTT ERROR mensaje recibido: " + str(payload))
        return {"origin": None, "entity": None, "key": None, "action": None}


def _get_mqtt_client(receive=False) -> mqtt.Client:
    client = mqtt.Client()
    client.username_pw_set(settings.MQTT_USER, password=settings.MQTT_PASS)
    client.connect(host=settings.MQTT_HOST, port=int(settings.MQTT_PORT))

    def on_connect(client, userdata, flags, rc):
        client.subscribe(settings.MQTT_TOPIC)

    client.on_connect = on_connect

    def on_publish(client, userdata, mid):
        logger.info("MQTT: mensaje publicado con éxito.")

    client.on_publish = on_publish

    # recibe eventos de la cola y dispara handler_event_signal
    if receive:

        def handler_event_signal_fn(client, userdata, msg):
            handler_event_signal.send(sender="MQTT", data=_get_from_payload(msg.payload))

        client.on_message = handler_event_signal_fn

    return client


# crea un loop de conexión a la cola
def _mqtt_loop():
    client = _get_mqtt_client(receive=True)
    client.loop_forever()
