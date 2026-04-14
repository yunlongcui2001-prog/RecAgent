import torch.nn as nn
from torch.nn.utils.rnn import pack_padded_sequence
from torch.nn.utils.rnn import pad_packed_sequence
import pickle
import torch

PRODUCT="product"

class GRU4REC(nn.Module):
    """
    d_model - the number of expected features in the input
    nhead - the number of heads in the multiheadattention models
    dim_feedforward - the hidden dimension size of the feedforward network model
    """
    def __init__(self,embedding_dim,hidden_dim,n_items):
        super(GRU4REC,self).__init__()
        self.embedding_dim = embedding_dim
        self.hidden_dim =hidden_dim
        self.batch_first =True
        self.n_items =n_items + 1
        self.pad_token = 0
        
        
        self.empty_session_idx = self.n_items # 表示空会话的
        
        self.move_embedding = nn.Embedding(self.n_items,embedding_dim,padding_idx=0)
        # self.move_embedding = nn.Embedding(n_items + 1,embedding_dim) # 用特殊标记解决，而不是用padding_idx=0

        self.encoder_layer = nn.GRU(embedding_dim,self.hidden_dim,batch_first=self.batch_first)

        self.output_layer = nn.Linear(hidden_dim,hidden_dim)
        self.score_layer = nn.Linear(self.hidden_dim, self.n_items)  # 线性层用于将会话表示转换为项目分数

    def forward(self,x,x_lens):


        x = self.move_embedding(x)
                    
        x_lens = torch.tensor(x_lens, dtype=torch.int64).cpu()
        x = pack_padded_sequence(x,x_lens,batch_first=True,enforce_sorted=False)

        output_packed,_ = self.encoder_layer(x)        
        x, _ = pad_packed_sequence(output_packed, batch_first=self.batch_first,padding_value=self.pad_token)
        
        session_rep = self.output_layer(torch.sum(x, 1))
        scores= self.score_layer(torch.sum(x, 1)) # 计算每个项目得分
        return session_rep, scores