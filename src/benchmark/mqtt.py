"""Isolated real-service MQTT harness; fault injection precedes packet delivery."""

import json
import os
import queue
import shutil
import socket
import subprocess
import sys
import threading
import time
import uuid
from contextlib import ExitStack, contextmanager
from pathlib import Path
from contracts import topics
from contracts.contracts_sdk import validate_payload

ROOT = Path(__file__).resolve().parents[2]


@contextmanager
def broker(directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    binary = shutil.which("mosquitto")
    if not binary:
        raise RuntimeError("Mosquitto must be installed on PATH for MQTT qualification")
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    config = directory / "broker.conf"
    config.write_text(f"listener {port} 127.0.0.1\nallow_anonymous true\npersistence false\n")
    with (directory / "broker.log").open("w") as log:
        process = subprocess.Popen([binary, "-c", str(config.resolve())], stdout=log, stderr=log)
        try:
            for _ in range(100):
                if process.poll() is not None:
                    raise RuntimeError("Private broker exited; inspect broker.log")
                try:
                    socket.create_connection(("127.0.0.1", port), timeout=0.1).close()
                    break
                except OSError:
                    time.sleep(0.05)
            else:
                raise TimeoutError("Private broker did not become ready")
            yield port
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


@contextmanager
def service(name, port, directory, **overrides):
    directory = Path(directory).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    env = dict(
        os.environ,
        MQTT_HOST="127.0.0.1",
        MQTT_PORT=str(port),
        CONTROL_POLICY_URL="",
        EDGEFLOW_TOPOLOGY="four_intersection_v1",
        EDGEFLOW_CONTROLLER="max_pressure",
        PYTHONPATH=str(ROOT),
    )
    env.update(overrides)
    with (directory / "service.log").open("w") as log:
        process = subprocess.Popen(
            [sys.executable, "-u", str(ROOT / "services" / name / "main.py")],
            cwd=directory,
            env=env,
            stdout=log,
            stderr=log,
        )
        try:
            yield process
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


class Relay:
    """Two brokers prevent the consumer from receiving a packet before injection."""

    def __init__(self, controller_port, actuator_port, path):
        import paho.mqtt.client as mqtt

        self.events = []
        self.delay = 0.0
        self.drop = False
        self.pending = queue.PriorityQueue()
        self.stopped = threading.Event()
        self.ready = [threading.Event(), threading.Event()]
        self.path = Path(path)
        self.clients = [mqtt.Client(client_id=f"benchmark-{uuid.uuid4().hex}") for _ in range(2)]
        for i, (client, port) in enumerate(zip(self.clients, (controller_port, actuator_port))):

            def connected(c, userdata, flags, rc, side=i):
                filters = (
                    [topics.COMMAND_SUB_PATTERN]
                    if side == 0
                    else [topics.ACK_SUB_PATTERN, topics.HEALTH_SUB_PATTERN, topics.SIGNAL_FAULT_SUB_PATTERN]
                )
                for topic in filters:
                    c.subscribe(topic, qos=1)
                self.ready[side].set()

            def received(c, userdata, message, side=i):
                self.events.append(
                    dict(
                        time=time.time(),
                        side=side,
                        topic=message.topic,
                        payload=message.payload.decode(errors="replace"),
                    )
                )
                if side == 0 and self.drop:
                    return
                due = time.monotonic() + (self.delay if side == 0 else 0)
                self.pending.put((due, uuid.uuid4().hex, 1 - side, message.topic, message.payload))

            client.on_connect = connected
            client.on_message = received
            client.connect("127.0.0.1", port)
            client.loop_start()
        self.thread = threading.Thread(target=self._pump, daemon=True)
        self.thread.start()

    def _pump(self):
        while not self.stopped.is_set():
            try:
                due, _, side, topic, payload = self.pending.get(timeout=0.05)
            except queue.Empty:
                continue
            if self.stopped.wait(max(0, due - time.monotonic())):
                break
            self.clients[side].publish(topic, payload, qos=1)

    def __enter__(self):
        if not all(event.wait(5) for event in self.ready):
            self.__exit__(None, None, None)
            raise TimeoutError("Relay could not connect")
        return self

    def __exit__(self, *_):
        self.stopped.set()
        self.thread.join(timeout=5)
        for client in self.clients:
            client.disconnect()
            client.loop_stop()
        self.path.write_text("".join(json.dumps(event) + "\n" for event in self.events))

    def publish(self, kind, node, payload):
        validate_payload(payload, {"telemetry": "telemetry", "command": "control_command"}[kind])
        self.clients[0].publish(topics.topic(kind, node), json.dumps(payload), qos=1).wait_for_publish(timeout=3)


@contextmanager
def harness(directory):
    """Run production services without importing their implementations or .env."""
    directory = Path(directory).resolve()
    with ExitStack() as stack:
        a = stack.enter_context(broker(directory / "controller-broker"))
        b = stack.enter_context(broker(directory / "actuator-broker"))
        relay = stack.enter_context(Relay(a, b, directory / "mqtt.jsonl"))
        graph = stack.enter_context(service("graph-control", a, directory / "graph"))
        actuator = stack.enter_context(service("actuator", b, directory / "actuator"))
        time.sleep(1)
        if graph.poll() is not None or actuator.poll() is not None:
            raise RuntimeError("A service exited; inspect service logs")
        processes = {"graph-control": graph, "actuator": actuator}
        restarts = {"graph-control": 0, "actuator": 0}

        def restart(name):
            if name not in processes:
                raise ValueError("Unknown service")
            old = processes[name]
            old.terminate()
            old.wait(timeout=5)
            restarts[name] += 1
            processes[name] = stack.enter_context(
                service(name, a if name == "graph-control" else b, directory / name / f"restart-{restarts[name]}")
            )
            time.sleep(1)
            if processes[name].poll() is not None:
                raise RuntimeError("Restarted service exited")

        relay.restart = restart
        yield relay
