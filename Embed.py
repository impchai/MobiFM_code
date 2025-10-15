import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.nn.utils import weight_norm
import math
import numpy as np



    
def Conv1d_with_init(in_channels, out_channels, kernel_size, stride=None):
    layer = nn.Conv1d(in_channels, out_channels, kernel_size,stride=stride)
    nn.init.kaiming_normal_(layer.weight)
    return layer

class SpatialPatchEmb(nn.Module):
    def __init__(self, c_in, d_model, patch_size):
        super(SpatialPatchEmb, self).__init__()
        self.patch_size = patch_size
        self.conv = nn.Conv2d(in_channels=c_in, out_channels=d_model, kernel_size=patch_size, stride=patch_size)
        self.patch_size = patch_size
        for m in self.modules():
            if isinstance(m, nn.Conv2d):
                nn.init.kaiming_normal_(m.weight, mode='fan_in', nonlinearity='leaky_relu')

    def forward(self, x):
        B, C, H, W = x.shape
        x = self.conv(x)
        x = x.reshape(B, C, H*W//self.patch_size**2).permute(0,2,1)
        return x



class TemporalEmbedding(nn.Module):
    def __init__(self, d_model, t_patch_size = 1, weekday_size = 7, hour_size=24):
        super(TemporalEmbedding, self).__init__()

        hour_size = hour_size
        weekday_size = weekday_size

        self.hour_embed = nn.Embedding(hour_size, d_model)
        self.weekday_embed = nn.Embedding(weekday_size, d_model)
        self.timeconv = nn.Conv1d(in_channels=d_model, out_channels=d_model, kernel_size=t_patch_size, stride=t_patch_size)

    def forward(self, x):

        x = x.long()
        hour_x = self.hour_embed(x[:,:,1])
        weekday_x = self.weekday_embed(x[:,:,0])
        timeemb = self.timeconv(hour_x.transpose(1,2)+weekday_x.transpose(1,2)).transpose(1,2)

        return timeemb


class TokenEmbedding(nn.Module):
    def __init__(self, c_in, d_model, t_patch_size):
        super(TokenEmbedding, self).__init__()
        self.tokenConv = Conv1d_with_init(c_in, d_model, t_patch_size, stride=t_patch_size)
    def forward(self, x):
        # B, C, T, H, W = x.shape
        x = self.tokenConv(x.float())
        x = F.leaky_relu(x)


        return x.permute(0,2,1)


class ObsEmbedding(nn.Module):
    def __init__(self, c_in, d_model, t_patch_size):
        super(ObsEmbedding, self).__init__()
        self.tokenConv = Conv1d_with_init(c_in, d_model, t_patch_size, stride=t_patch_size)


    def forward(self, x):
        x = self.tokenConv(x.float())
        x = F.leaky_relu(x)
        return x.permute(0,2,1)

class MaskEmbedding(nn.Module):
    def __init__(self, c_in, d_model, t_patch_size):
        super(MaskEmbedding, self).__init__()
        self.tokenConv = Conv1d_with_init(c_in, d_model, t_patch_size, stride=t_patch_size)


    def forward(self, x):
        # B, C, T, H, W = x.shape
        x = self.tokenConv(x)
        x = F.leaky_relu(x)
        return x.permute(0,2,1)

class DataEmbedding(nn.Module):
    def __init__(self, c_in, d_model, dropout=0.1, args=None, size1 = 7, size2= 24 ):
        super(DataEmbedding, self).__init__()
        self.args = args
        self.temporal_embedding = TemporalEmbedding(t_patch_size = args.t_patch_size, d_model=d_model, weekday_size = size1, hour_size  = size2)
        self.dropout = nn.Dropout(p=dropout)

    def forward(self, time_mark):

        '''
        x: N, T, C, H, W
        x_mark: N, T, D
        '''
        B, L, _ = time_mark.shape
        # TokenEmb = self.value_embedding(x[:,0].unsqueeze(1))
        TimeEmb = self.temporal_embedding(time_mark)
        # TimeEmb = torch.repeat_interleave(TimeEmb, TokenEmb.shape[1]//TimeEmb.shape[1], dim=1)
        return  TimeEmb

class DataEmbedding_align(nn.Module):
    def __init__(self, c_in, d_model, dropout=0.1, args=None, size1 = 48, size2=7 ):
        super(DataEmbedding_align, self).__init__()
        self.args = args
        self.user_embedding = TokenEmbedding(c_in=c_in, d_model=d_model, t_patch_size = args.t_patch_size,  patch_size=args.patch_size)
        self.dropout = nn.Dropout(p=dropout)

    def forward(self, x):
        '''
        x: N, T, C, H, W
        x_mark: N, T, D
        '''
        N, T, C, H, W = x.shape
        TokenEmb = self.user_embedding(x)

        return  self.dropout(TokenEmb)


class DataEmbedding2(nn.Module):
    def __init__(self, c_in, d_model, dropout=0.1, args=None, size1 = 48, size2=7 ):
        super(DataEmbedding2, self).__init__()
        self.args = args
        self.value_embedding = TokenEmbedding(c_in=c_in, d_model=d_model, t_patch_size = args.t_patch_size)
        self.obs_embedding = ObsEmbedding(c_in=c_in, d_model=d_model, t_patch_size=args.t_patch_size)
        self.mask_embedding = MaskEmbedding(c_in=c_in, d_model=d_model, t_patch_size = args.t_patch_size)


    def forward(self, x, obs, mask):
        '''
        x: N, T, C, H, W
        x_mark: N, T, D
        '''
        TokenEmb = self.value_embedding(x)
        ObsEmb = self.obs_embedding(obs)
        MaskEmb = self.mask_embedding(mask)


        return TokenEmb, ObsEmb, MaskEmb

class DataEmbedding20(nn.Module):
    def __init__(self, c_in, d_model, dropout=0.1, args=None, size1 = 48, size2=7 ):
        super(DataEmbedding20, self).__init__()
        self.args = args
        self.value_embedding = TokenEmbedding(c_in=c_in, d_model=d_model, t_patch_size = args.t_patch_size)
        self.obs_embedding = ObsEmbedding(c_in=c_in, d_model=d_model, t_patch_size=args.t_patch_size)
        self.mask_embedding = MaskEmbedding(c_in=c_in, d_model=d_model, t_patch_size = args.t_patch_size)


    def forward(self, x, obs, mask):
        '''
        x: N, T, C, H, W
        x_mark: N, T, D
        '''
        TokenEmb = self.value_embedding(x)
        ObsEmb = self.obs_embedding(obs)
        MaskEmb = self.mask_embedding(mask)


        return TokenEmb, ObsEmb, MaskEmb



def get_2d_sincos_pos_embed_from_grid(embed_dim, grid):
    assert embed_dim % 2 == 0

    # use half of dimensions to encode grid_h
    emb_h = get_1d_sincos_pos_embed_from_grid(embed_dim // 2, grid[0])  # (H*W, D/2)
    emb_w = get_1d_sincos_pos_embed_from_grid(embed_dim // 2, grid[1])  # (H*W, D/2)

    emb = np.concatenate([emb_h, emb_w], axis=1)  # (H*W, D)
    return emb


def get_2d_sincos_pos_embed_from_grid_torch(embed_dim, grid):
    assert embed_dim % 2 == 0

    # use half of dimensions to encode grid_h
    emb_h = get_1d_sincos_pos_embed_from_grid_torch(
        embed_dim // 2, grid[0]
    )  # (H*W, D/2)
    emb_w = get_1d_sincos_pos_embed_from_grid_torch(
        embed_dim // 2, grid[1]
    )  # (H*W, D/2)

    emb = torch.cat([emb_h, emb_w], dim=1)  # (H*W, D)
    return emb


def get_1d_sincos_pos_embed_from_grid_torch(embed_dim, pos):
    """
    embed_dim: output dimension for each position
    pos: a list of positions to be encoded: size (M,)
    out: (M, D)
    """
    assert embed_dim % 2 == 0
    old_shape = pos
    omega = torch.arange(embed_dim // 2, dtype=torch.float32, device=pos.device)
    omega /= embed_dim / 2.0
    omega = 1.0 / 10000**omega  # (D/2,)

    pos = pos.reshape(-1)  # (M,)
    out = torch.einsum("m,d->md", pos, omega)  # (M, D/2), outer product

    emb_sin = torch.sin(out)  # (M, D/2)
    emb_cos = torch.cos(out)  # (M, D/2)

    emb = torch.cat([emb_sin, emb_cos], dim=1)  # (M, D)
    return emb


def get_1d_sincos_pos_embed_from_grid(embed_dim, pos):
    """
    embed_dim: output dimension for each position
    pos: a list of positions to be encoded: size (M,)
    out: (M, D)
    """
    assert embed_dim % 2 == 0
    omega = np.arange(embed_dim // 2, dtype=np.float32)
    omega /= embed_dim / 2.0
    omega = 1.0 / 10000**omega  # (D/2,)

    pos = pos.reshape(-1)  # (M,)
    out = np.einsum("m,d->md", pos, omega)  # (M, D/2), outer product

    emb_sin = np.sin(out)  # (M, D/2)
    emb_cos = np.cos(out)  # (M, D/2)

    emb = np.concatenate([emb_sin, emb_cos], axis=1)  # (M, D)
    return emb

def get_1d_sincos_pos_embed_from_grid_with_resolution(embed_dim, pos, res):
    """
    embed_dim: output dimension for each position
    pos: a list of positions to be encoded: size (M,)
    out: (M, D)
    """
    pos = pos * res
    assert embed_dim % 2 == 0
    omega = np.arange(embed_dim // 2, dtype=np.float32)
    omega /= embed_dim / 2.0
    omega = 1.0 / 10000**omega  # (D/2,)

    pos = pos.reshape(-1)  # (M,)
    out = np.einsum("m,d->md", pos, omega)  # (M, D/2), outer product

    emb_sin = np.sin(out)  # (M, D/2)
    emb_cos = np.cos(out)  # (M, D/2)

    emb = np.concatenate([emb_sin, emb_cos], axis=1)  # (M, D)
    return emb
