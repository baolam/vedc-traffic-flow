"""Graph-attention MAPPO actor, centralized critic, GAE and PPO updates."""

import random

import numpy as np
import torch
from torch import nn
from torch.distributions import Categorical


def seed_everything(seed):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    torch.set_num_threads(1)
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True


class GraphAttentionLayer(nn.Module):
    def __init__(self, relation_dim):
        super().__init__()
        self.node = nn.Linear(64, 64)
        self.relation = nn.Linear(relation_dim, 64)
        self.attention_receiver = nn.Parameter(torch.empty(4, 16))
        self.attention_sender = nn.Parameter(torch.empty(4, 16))
        self.attention_relation = nn.Parameter(torch.empty(4, 16))
        for value in (self.attention_receiver, self.attention_sender, self.attention_relation):
            nn.init.xavier_uniform_(value)

    def forward(self, values, relation_features, senders, receivers):
        projected = self.node(values).reshape(4, 4, 16)
        relations = self.relation(relation_features).reshape(-1, 4, 16)
        scores = ((projected[receivers] * self.attention_receiver).sum(-1)
                  + (projected[senders] * self.attention_sender).sum(-1)
                  + (relations * self.attention_relation).sum(-1))
        scores = torch.nn.functional.leaky_relu(scores, negative_slope=.2)
        messages = projected[senders] + relations
        aggregated = []
        for node in range(4):
            indices = torch.nonzero(receivers == node, as_tuple=False).flatten()
            attention = torch.softmax(scores[indices], dim=0)
            aggregated.append((attention.unsqueeze(-1) * messages[indices]).sum(dim=0))
        return torch.relu(values + torch.stack(aggregated, dim=0).reshape(4, 64))


class GraphActor(nn.Module):
    def __init__(self, graph, local_only=False, device="cpu"):
        super().__init__()
        self.local_only = bool(local_only)
        self.encoder = nn.Linear(52, 64)
        self.attention = nn.ModuleList([GraphAttentionLayer(15), GraphAttentionLayer(15)])
        self.head = nn.Linear(64, 3)
        sender = torch.tensor(graph["senders"], dtype=torch.long)
        receiver = torch.tensor(graph["receivers"], dtype=torch.long)
        relations = torch.tensor(graph["relation_features"], dtype=torch.float32)
        self.register_buffer("senders", sender)
        self.register_buffer("receivers", receiver)
        self.register_buffer("relation_features", relations)
        self.register_buffer("edge_indices", torch.tensor(
            [i for i, is_self in enumerate(graph["self_relations"]) if is_self or not local_only],
            dtype=torch.long))
        self.to(device)

    def forward(self, observations):
        values = torch.as_tensor(observations, dtype=torch.float32, device=self.encoder.weight.device)
        unbatched = values.ndim == 2
        if unbatched:
            values = values.unsqueeze(0)
        if values.ndim != 3 or values.shape[1:] != (4, 52) or not torch.isfinite(values).all():
            raise ValueError("Expected finite [batch, four nodes, 52 features] observations")
        senders = self.senders[self.edge_indices]
        receivers = self.receivers[self.edge_indices]
        relations = self.relation_features[self.edge_indices]
        outputs = []
        for sample in values:
            hidden = torch.relu(self.encoder(sample))
            for layer in self.attention:
                hidden = layer(hidden, relations, senders, receivers)
            outputs.append(self.head(hidden))
        result = torch.stack(outputs)
        return result[0] if unbatched else result


class CentralizedCritic(nn.Module):
    def __init__(self, device="cpu"):
        super().__init__()
        self.encoder = nn.Linear(52, 64)
        self.value_head = nn.Sequential(nn.Linear(128, 64), nn.ReLU(), nn.Linear(64, 1))
        self.to(device)

    def forward(self, observations):
        values = torch.as_tensor(observations, dtype=torch.float32, device=self.encoder.weight.device)
        unbatched = values.ndim == 2
        if unbatched:
            values = values.unsqueeze(0)
        if values.ndim != 3 or values.shape[1:] != (4, 52) or not torch.isfinite(values).all():
            raise ValueError("Expected finite [batch, four nodes, 52 features] observations")
        encoded = torch.relu(self.encoder(values))
        mean = encoded.mean(dim=1, keepdim=True).expand_as(encoded)
        result = self.value_head(torch.cat((encoded, mean), dim=-1)).squeeze(-1)
        return result[0] if unbatched else result


def masked_distribution(logits, masks):
    legal = torch.as_tensor(masks, dtype=torch.bool, device=logits.device)
    if legal.shape != logits.shape or not legal.any(dim=-1).all():
        raise ValueError("Each intersection must have a non-empty legal action mask")
    return Categorical(logits=logits.masked_fill(~legal, -torch.inf))


def generalized_advantage_estimate(rewards, values, next_values, terminals, elapsed_s,
                                   discount=.99, gae_lambda=.95):
    """Compute per-node GAE with time-scaled discount and trace factors."""
    rewards = np.asarray(rewards, dtype=np.float64)
    values = np.asarray(values, dtype=np.float64)
    next_values = np.asarray(next_values, dtype=np.float64)
    terminals = np.asarray(terminals, dtype=bool)
    elapsed_s = np.asarray(elapsed_s, dtype=np.float64)
    if rewards.ndim != 1 or values.shape != (len(rewards), 4) or next_values.shape != values.shape:
        raise ValueError("GAE requires one scalar reward and four values per graph transition")
    if terminals.shape != rewards.shape or elapsed_s.shape != rewards.shape:
        raise ValueError("GAE terminal and elapsed-time arrays must match rewards")
    if (not np.isfinite(rewards).all() or not np.isfinite(values).all()
            or not np.isfinite(next_values).all() or not np.isfinite(elapsed_s).all()
            or np.any(elapsed_s <= 0)):
        raise ValueError("GAE inputs must be finite with positive elapsed times")
    advantages = np.zeros_like(values)
    carry = np.zeros(4, dtype=np.float64)
    for index in range(len(rewards) - 1, -1, -1):
        gamma = discount ** (elapsed_s[index] / 5.)
        trace = gae_lambda ** (elapsed_s[index] / 90.)
        bootstrap = np.zeros(4) if terminals[index] else next_values[index]
        continuation = np.zeros(4) if terminals[index] else carry
        delta = rewards[index] + gamma * bootstrap - values[index]
        carry = delta + gamma * trace * continuation
        advantages[index] = carry
    return advantages, advantages + values


def actor_weights(actor):
    def linear(layer):
        return {"weight": layer.weight.detach().cpu().numpy().tolist(),
                "bias": layer.bias.detach().cpu().numpy().tolist()}

    layers = []
    for layer in actor.attention:
        layers.append({"node": linear(layer.node), "relation": linear(layer.relation),
                       "attention_receiver": layer.attention_receiver.detach().cpu().numpy().tolist(),
                       "attention_sender": layer.attention_sender.detach().cpu().numpy().tolist(),
                       "attention_relation": layer.attention_relation.detach().cpu().numpy().tolist()})
    return {"encoder": linear(actor.encoder), "attention": layers, "head": linear(actor.head)}


class MAPPOUpdater:
    def __init__(self, actor, critic, config):
        self.actor, self.critic, self.config = actor, critic, config
        self.device = next(actor.parameters()).device
        lr = float(config.get("learning_rate", 3e-4))
        self.actor_optimizer = torch.optim.Adam(actor.parameters(), lr=lr)
        self.critic_optimizer = torch.optim.Adam(critic.parameters(), lr=lr)
        self.updates = 0
        self.last_diagnostics = {}

    def update(self, observations, actions, masks, old_log_probs, advantages, returns):
        tensors = [torch.as_tensor(value, device=self.device) for value in
                   (observations, actions, masks, old_log_probs, advantages, returns)]
        obs, action, legal, old_logp, adv, target = tensors
        if obs.ndim != 3 or obs.shape[1:] != (4, 52) or action.shape != (len(obs), 4):
            raise ValueError("PPO minibatches must contain complete four-node graph transitions")
        if legal.shape != (len(obs), 4, 3) or old_logp.shape != (len(obs), 4):
            raise ValueError("Invalid masked-action PPO batch")
        if adv.shape != (len(obs), 4) or target.shape != (len(obs), 4):
            raise ValueError("PPO advantages and returns must retain all graph nodes")
        if not legal.gather(-1, action.long().unsqueeze(-1)).all():
            raise ValueError("Rollout contains an action that was illegal under its mask")
        epochs = int(self.config.get("update_epochs", 4))
        batch_size = int(self.config.get("minibatch_size", 32))
        clip = float(self.config.get("clip_epsilon", .2))
        entropy_coef = float(self.config.get("entropy_coefficient", .01))
        value_coef = float(self.config.get("value_coefficient", .5))
        max_norm = float(self.config.get("max_gradient_norm", .5))
        kl_limit = float(self.config.get("target_kl", .03))
        if batch_size <= 0 or epochs <= 0 or not 0 < clip < 1:
            raise ValueError("Invalid PPO update configuration")
        sample_count = len(obs)
        diagnostics = {key: [] for key in ("actor_loss", "value_loss", "entropy", "approx_kl",
                                            "clip_fraction", "actor_gradient_norm", "critic_gradient_norm")}
        stopped_early = False
        for _ in range(epochs):
            permutation = torch.randperm(sample_count, device=self.device)
            for start in range(0, sample_count, batch_size):
                indices = permutation[start:start + batch_size]
                logits = self.actor(obs[indices])
                distribution = masked_distribution(logits, legal[indices])
                new_logp = distribution.log_prob(action[indices].long())
                log_ratio = new_logp - old_logp[indices]
                ratio = log_ratio.exp()
                clipped_ratio = ratio.clamp(1. - clip, 1. + clip)
                actor_loss = -torch.minimum(ratio * adv[indices], clipped_ratio * adv[indices]).mean()
                entropy = distribution.entropy().mean()
                predicted = self.critic(obs[indices])
                value_loss = torch.nn.functional.huber_loss(predicted, target[indices])
                approx_kl = ((ratio - 1.) - log_ratio).mean()
                clip_fraction = (torch.abs(ratio - 1.) > clip).float().mean()
                loss = actor_loss - entropy_coef * entropy
                if not all(torch.isfinite(value).all() for value in
                           (loss, value_loss, approx_kl, clip_fraction, predicted)):
                    raise RuntimeError("Non-finite MAPPO loss or prediction")
                self.actor_optimizer.zero_grad(set_to_none=True)
                loss.backward()
                actor_norm = nn.utils.clip_grad_norm_(self.actor.parameters(), max_norm)
                if not torch.isfinite(actor_norm):
                    raise RuntimeError("Non-finite MAPPO actor gradient")
                self.actor_optimizer.step()
                self.critic_optimizer.zero_grad(set_to_none=True)
                (value_coef * value_loss).backward()
                critic_norm = nn.utils.clip_grad_norm_(self.critic.parameters(), max_norm)
                if not torch.isfinite(critic_norm):
                    raise RuntimeError("Non-finite MAPPO critic gradient")
                self.critic_optimizer.step()
                for key, value in (("actor_loss", actor_loss), ("value_loss", value_loss),
                                   ("entropy", entropy), ("approx_kl", approx_kl),
                                   ("clip_fraction", clip_fraction),
                                   ("actor_gradient_norm", actor_norm),
                                   ("critic_gradient_norm", critic_norm)):
                    diagnostics[key].append(float(value.detach()))
                if float(approx_kl.detach()) > kl_limit:
                    stopped_early = True
                    break
            if stopped_early:
                break
        self.updates += 1
        self.last_diagnostics = {key: float(np.mean(values)) for key, values in diagnostics.items()}
        self.last_diagnostics["epochs_stopped_early"] = stopped_early
        return self.last_diagnostics
