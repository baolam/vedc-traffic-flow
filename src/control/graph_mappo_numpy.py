"""Portable NumPy inference for the versioned graph-MAPPO actor artifact."""

import numpy as np


class NumpyGraphActor:
    def __init__(self, weights, graph, local_only=False):
        self.graph = graph
        self.senders = np.asarray(graph["senders"], dtype=np.int64)
        self.receivers = np.asarray(graph["receivers"], dtype=np.int64)
        self.relations = np.asarray(graph["relation_features"], dtype=np.float32)
        relation_mask = np.asarray(graph["self_relations"], dtype=bool)
        self.edge_indices = np.flatnonzero(relation_mask if local_only else np.ones_like(relation_mask))
        self.encoder = weights["encoder"]
        self.layers = weights["attention"]
        self.head = weights["head"]
        encoder_dim = self._linear_dims(self.encoder, "encoder")
        head_dim = self._linear_dims(self.head, "head")
        self.feature_dim, self.action_dim = encoder_dim[1], head_dim[0]
        if encoder_dim != (64, 52) or head_dim != (3, 64) or len(self.layers) != 2:
            raise ValueError("Graph-MAPPO actor has incompatible dimensions")
        for layer in self.layers:
            self._validate_attention(layer)

    @staticmethod
    def _linear_dims(layer, name):
        weight = np.asarray(layer["weight"], dtype=np.float32)
        bias = np.asarray(layer["bias"], dtype=np.float32)
        if weight.ndim != 2 or bias.shape != (weight.shape[0],):
            raise ValueError(f"Invalid {name} weights")
        if not np.isfinite(weight).all() or not np.isfinite(bias).all():
            raise ValueError(f"Non-finite {name} weights")
        layer["weight"] = weight
        layer["bias"] = bias
        return weight.shape

    def _validate_attention(self, layer):
        node_dim = self._linear_dims(layer["node"], "attention node projection")
        relation_dim = self._linear_dims(layer["relation"], "attention relation projection")
        if node_dim != (64, 64) or relation_dim != (64, self.relations.shape[1]):
            raise ValueError("Invalid graph-attention projection dimensions")
        for name in ("receiver", "sender", "relation"):
            value = np.asarray(layer[f"attention_{name}"], dtype=np.float32)
            if value.shape != (4, 16) or not np.isfinite(value).all():
                raise ValueError("Invalid graph-attention scoring weights")
            layer[f"attention_{name}"] = value

    @staticmethod
    def _linear(values, layer):
        # einsum avoids a BLAS/OpenMP runtime dependency in graph-control services.
        return np.einsum("...i,oi->...o", values, layer["weight"], optimize=False) + layer["bias"]

    def logits(self, observations):
        values = np.asarray(observations, dtype=np.float32)
        if values.shape != (4, self.feature_dim) or not np.isfinite(values).all():
            raise ValueError("Expected four finite graph observations in canonical order")
        hidden = np.maximum(self._linear(values, self.encoder), 0.)
        senders = self.senders[self.edge_indices]
        receivers = self.receivers[self.edge_indices]
        relation_features = self.relations[self.edge_indices]
        for layer in self.layers:
            projected = self._linear(hidden, layer["node"]).reshape(4, 4, 16)
            relation = self._linear(relation_features, layer["relation"]).reshape(-1, 4, 16)
            receiver_score = (projected[receivers] * layer["attention_receiver"]).sum(axis=-1)
            sender_score = (projected[senders] * layer["attention_sender"]).sum(axis=-1)
            relation_score = (relation * layer["attention_relation"]).sum(axis=-1)
            scores = receiver_score + sender_score + relation_score
            scores = np.where(scores >= 0, scores, 0.2 * scores)
            aggregate = np.zeros((4, 4, 16), dtype=np.float32)
            messages = projected[senders] + relation
            for node in range(4):
                indices = np.flatnonzero(receivers == node)
                selected = scores[indices]
                exponent = np.exp(selected - selected.max(axis=0, keepdims=True))
                attention = exponent / exponent.sum(axis=0, keepdims=True)
                aggregate[node] = (attention[..., None] * messages[indices]).sum(axis=0)
            hidden = np.maximum(hidden + aggregate.reshape(4, 64), 0.)
        result = self._linear(hidden, self.head)
        if not np.isfinite(result).all():
            raise ValueError("Graph-MAPPO produced non-finite logits")
        return result

    def deterministic_actions(self, observations, masks):
        logits = self.logits(observations)
        legal = np.asarray(masks, dtype=bool)
        if legal.shape != (4, 3) or not legal.any(axis=1).all():
            raise ValueError("Every intersection must have at least one legal residual action")
        return np.argmax(np.where(legal, logits, -np.inf), axis=1)
