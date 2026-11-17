"""Explicit offline CUDA inference; production NumPy inference imports no Torch."""

import numpy as np
import torch
from torch import nn


class CudaPolicy:
    def __init__(self, weights):
        if not torch.cuda.is_available():
            raise RuntimeError("CUDA inference requested but unavailable")
        self.model = nn.Sequential(nn.Linear(12, 64), nn.ReLU(), nn.Linear(64, 1)).to("cuda")
        with torch.no_grad():
            for layer, prefix in [(self.model[0], "1"), (self.model[2], "2")]:
                layer.weight.copy_(torch.as_tensor(weights["w" + prefix], device="cuda"))
                layer.bias.copy_(torch.as_tensor(weights["b" + prefix], device="cuda"))
        self.model.eval()

    def predict(self, observations):
        x = np.asarray(observations, dtype=np.float32)
        if x.ndim not in (1, 2) or x.shape[-1] != 12 or not np.isfinite(x).all():
            raise ValueError("Expected finite 12-feature phase observations")
        with torch.inference_mode():
            result = self.model(torch.as_tensor(x, device="cuda")).cpu().numpy()
        if not np.isfinite(result).all():
            raise ValueError("Nonfinite CUDA policy output")
        return result
