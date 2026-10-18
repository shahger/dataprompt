"""Frozen image encoder for crops (object states, person roles/actions). Apache-2.0 backbones only."""
import numpy as np
import torch
from PIL import Image

ENCODERS = {
    "dinov2-small": "facebook/dinov2-small",              # Apache-2.0, 22M params
    "siglip2-base": "google/siglip2-base-patch16-224",    # Apache-2.0, 86M (vision tower)
}


class CropEncoder:
    def __init__(self, name="dinov2-small", device="cpu", threads=None):
        from transformers import AutoImageProcessor, AutoModel
        if threads:
            torch.set_num_threads(threads)
        self.name, self.device = name, device
        from pathlib import Path
        local = Path(__file__).resolve().parent.parent / "models" / "encoder" / name
        mid = str(local) if local.exists() else ENCODERS[name]   # bundled weights first (offline service)
        self.proc = AutoImageProcessor.from_pretrained(mid)
        model = AutoModel.from_pretrained(mid)
        self.model = (model.vision_model if hasattr(model, "vision_model") else model).to(device).eval()

    @torch.no_grad()
    def __call__(self, crops, batch=32):
        """crops: list of PIL images -> np.ndarray [N, D] (L2-normalised)."""
        out = []
        for i in range(0, len(crops), batch):
            px = self.proc(images=crops[i:i + batch], return_tensors="pt")["pixel_values"].to(self.device)
            o = self.model(pixel_values=px)
            feat = o.pooler_output if getattr(o, "pooler_output", None) is not None else o.last_hidden_state[:, 0]
            if self.name.startswith("dinov2"):   # CLS + mean patch token works better for linear probes
                feat = torch.cat([o.last_hidden_state[:, 0], o.last_hidden_state[:, 1:].mean(1)], -1)
            out.append(torch.nn.functional.normalize(feat, dim=-1).cpu().numpy())
        return np.concatenate(out) if out else np.zeros((0, 1), np.float32)


def crop(img, box, pad=0.15, min_size=24):
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    px, py = max(w * pad, (min_size - w) / 2, 0), max(h * pad, (min_size - h) / 2, 0)
    return img.crop((max(0, x0 - px), max(0, y0 - py), min(img.width, x1 + px), min(img.height, y1 + py)))
