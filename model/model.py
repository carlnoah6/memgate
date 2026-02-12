import torch
import torch.nn as nn
from omegaconf import DictConfig

class MyModel(nn.Module):
    def __init__(self, cfg: DictConfig):
        super().__init__()
        self.cfg = cfg
        # Example: Transformer
        self.transformer = nn.Transformer(
            d_model=cfg.d_model,
            nhead=cfg.n_head,
            num_encoder_layers=cfg.num_encoder_layers,
            num_decoder_layers=cfg.num_decoder_layers,
            dim_feedforward=cfg.dim_feedforward,
            dropout=cfg.dropout
        )
    
    def forward(self, src, tgt):
        return self.transformer(src, tgt)
