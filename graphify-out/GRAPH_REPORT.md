# Graph Report - ./knowledge  (2026-05-23)

## Corpus Check
- Corpus is ~16,601 words - fits in a single context window. You may not need a graph.

## Summary
- 86 nodes · 97 edges · 10 communities
- Extraction: 90% EXTRACTED · 10% INFERRED · 0% AMBIGUOUS · INFERRED: 10 edges (avg confidence: 0.78)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Sequential Rec Baselines & Datasets|Sequential Rec Baselines & Datasets]]
- [[_COMMUNITY_FMLP-Rec Architecture|FMLP-Rec Architecture]]
- [[_COMMUNITY_Filtering & Signal Processing|Filtering & Signal Processing]]
- [[_COMMUNITY_Ranking Loss Functions|Ranking Loss Functions]]
- [[_COMMUNITY_All-MLP & Fourier Filtering|All-MLP & Fourier Filtering]]
- [[_COMMUNITY_GRU4Rec Baselines & Datasets|GRU4Rec Baselines & Datasets]]
- [[_COMMUNITY_GRU4Rec Citations & Metrics|GRU4Rec Citations & Metrics]]
- [[_COMMUNITY_GRU  RNN Foundations|GRU / RNN Foundations]]
- [[_COMMUNITY_Session-Parallel Training|Session-Parallel Training]]
- [[_COMMUNITY_Item-based CF Baselines|Item-based CF Baselines]]

## God Nodes (most connected - your core abstractions)
1. `FMLP-Rec: Filter-enhanced MLP is All You Need for Sequential Recommendation (WWW'22)` - 31 edges
2. `GRU4Rec model` - 14 edges
3. `Session-based Recommendations with Recurrent Neural Networks (GRU4Rec, ICLR 2016)` - 8 edges
4. `FMLP-Rec (all-MLP model with learnable filters)` - 7 edges
5. `Filter Layer (FFT -> learnable filter multiply -> inverse FFT)` - 6 edges
6. `Learnable Filter W (complex, optimized by SGD in frequency domain)` - 5 edges
7. `Ranking loss function` - 5 edges
8. `Learnable Filter-enhanced Block` - 4 edges
9. `Filtering Algorithms from Digital Signal Processing` - 4 edges
10. `Gated Recurrent Unit (GRU)` - 4 edges

## Surprising Connections (you probably didn't know these)
- `Item-KNN baseline` --conceptually_related_to--> `GRU4Rec model`  [INFERRED]
  knowledge/papers/2016-gru4rec.pdf → knowledge/papers/2016-gru4rec.pdf  _Bridges community 5 → community 9_
- `Session-based recommendation` --semantically_similar_to--> `Learning-to-rank`  [INFERRED] [semantically similar]
  knowledge/papers/2016-gru4rec.pdf → knowledge/papers/2016-gru4rec.pdf  _Bridges community 7 → community 3_
- `FMLP-Rec: Filter-enhanced MLP is All You Need for Sequential Recommendation (WWW'22)` --compared_against--> `SASRec (unidirectional Transformer)`  [EXTRACTED]
  knowledge/papers/2022-seq-fmlp.pdf → knowledge/papers/2022-seq-fmlp.pdf  _Bridges community 0 → community 1_
- `FMLP-Rec: Filter-enhanced MLP is All You Need for Sequential Recommendation (WWW'22)` --cites--> `Transformer / multi-head self-attention`  [EXTRACTED]
  knowledge/papers/2022-seq-fmlp.pdf → knowledge/papers/2022-seq-fmlp.pdf  _Bridges community 0 → community 2_
- `FMLP-Rec: Filter-enhanced MLP is All You Need for Sequential Recommendation (WWW'22)` --cites--> `GFNet (Global Filter Network, 2D Fourier transform)`  [EXTRACTED]
  knowledge/papers/2022-seq-fmlp.pdf → knowledge/papers/2022-seq-fmlp.pdf  _Bridges community 0 → community 4_

## Hyperedges (group relationships)
- **Learnable filter-enhanced block: filter layer + feed-forward network + Add&Norm** — fmlp_filter_layer, fmlp_ffn, fmlp_add_norm [EXTRACTED 1.00]
- **Frequency-domain filtering pipeline: FFT -> learnable filter multiply -> inverse FFT** — fmlp_fft, fmlp_learnable_filter, fmlp_filter_layer [EXTRACTED 1.00]
- **Classical signal-processing filters tested: HPF, LPF, BSF** — fmlp_high_pass_filter, fmlp_low_pass_filter, fmlp_band_stop_filter [EXTRACTED 1.00]
- **GRU4Rec adaptations of RNN to recommendation (session-parallel batches + popularity sampling + ranking loss)** — gru4rec_session_parallel_minibatches, gru4rec_output_sampling, gru4rec_ranking_loss [EXTRACTED 0.90]
- **Evaluation setup: datasets and metrics** — gru4rec_dataset_rsc15, gru4rec_dataset_video, gru4rec_metric_recall20, gru4rec_metric_mrr20 [EXTRACTED 0.85]
- **Baseline methods compared against GRU4Rec** — gru4rec_baseline_pop, gru4rec_baseline_spop, gru4rec_baseline_item_knn, gru4rec_baseline_bpr_mf [EXTRACTED 0.90]

## Communities (10 total, 0 thin omitted)

### Community 0 - "Sequential Rec Baselines & Datasets"
Cohesion: 0.08
Nodes (25): AutoInt, BERT4Rec (bidirectional Transformer, Cloze objective), Caser (CNN-based), CLEA (contrastive item-level denoising), FM (Factorization Machines), GC-SAN (GNN + self-attention), GRU4Rec, HGN (Hierarchical Gating Network) (+17 more)

### Community 1 - "FMLP-Rec Architecture"
Cohesion: 0.20
Nodes (10): Add & Norm (skip connection + layer normalization + dropout), SASRec (unidirectional Transformer), Layer Normalization, Residual / skip connection (ResNet), Embedding Layer (item + learnable position encoding), Point-wise Feed-Forward Network (MLP + ReLU), Learnable Filter-enhanced Block, Prediction Layer (pairwise rank loss) (+2 more)

### Community 2 - "Filtering & Signal Processing"
Cohesion: 0.20
Nodes (10): Band-Stop Filter (BSF), Circular Convolution (equivalence proof for learnable filter), Transformer / multi-head self-attention, Convolution Theorem, Filtering Algorithms from Digital Signal Processing, High-Pass Filter (HPF), Learnable Filter W (complex, optimized by SGD in frequency domain), Low-Pass Filter (LPF) (+2 more)

### Community 3 - "Ranking Loss Functions"
Cohesion: 0.29
Nodes (8): BPR-MF baseline, BPR pairwise ranking loss, Rendle et al. 2009 (BPR), Learning-to-rank, Ranking loss function, Rationale: why ranking loss (pairwise preferred), Rationale: TOP1 regularizes negative scores toward zero for stability, TOP1 ranking loss

### Community 4 - "All-MLP & Fourier Filtering"
Cohesion: 0.29
Nodes (7): All-MLP Architecture, GFNet (Global Filter Network, 2D Fourier transform), MLP-Mixer (mixer layer), Denoising / low-pass filtering idea (noise as high-frequency signal), 1D Fast Fourier Transform (FFT) / inverse FFT, Filter Layer (FFT -> learnable filter multiply -> inverse FFT), Rationale: filters denoise in frequency domain and replace heavy self-attention to reduce overfitting and complexity

### Community 5 - "GRU4Rec Baselines & Datasets"
Cohesion: 0.29
Nodes (7): 1-of-N input encoding, POP baseline (global popularity), S-POP baseline (session popularity), Cross-entropy (pointwise) loss, RSC15 dataset (RecSys Challenge 2015), VIDEO dataset (OTT video service), GRU4Rec model

### Community 6 - "GRU4Rec Citations & Metrics"
Cohesion: 0.29
Nodes (7): Adagrad optimizer, Hidasi & Tikk 2015 (General Factorization Framework), Salakhutdinov et al. 2007 (RBM for CF), Shani et al. 2002 (MDP-based recommender), MRR@20 (Mean Reciprocal Rank), Recall@20, Session-based Recommendations with Recurrent Neural Networks (GRU4Rec, ICLR 2016)

### Community 7 - "GRU / RNN Foundations"
Cohesion: 0.40
Nodes (5): Cho et al. 2014 (GRU / encoder-decoder), Vanishing gradient problem, Gated Recurrent Unit (GRU), Recurrent Neural Network (RNN), Session-based recommendation

### Community 8 - "Session-Parallel Training"
Cohesion: 0.50
Nodes (4): Mini-batch based output sampling (popularity-based negatives), Rationale: why popularity-based mini-batch output sampling, Rationale: why session-parallel mini-batches, Session-parallel mini-batches

### Community 9 - "Item-based CF Baselines"
Cohesion: 0.67
Nodes (3): Item-KNN baseline, Linden et al. 2003 (Amazon item-to-item CF), Sarwar et al. 2001 (item-based CF)

## Knowledge Gaps
- **56 isolated node(s):** `Embedding Layer (item + learnable position encoding)`, `1D Fast Fourier Transform (FFT) / inverse FFT`, `Point-wise Feed-Forward Network (MLP + ReLU)`, `Prediction Layer (pairwise rank loss)`, `Convolution Theorem` (+51 more)
  These have ≤1 connection - possible missing edges or undocumented components.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `FMLP-Rec: Filter-enhanced MLP is All You Need for Sequential Recommendation (WWW'22)` connect `Sequential Rec Baselines & Datasets` to `FMLP-Rec Architecture`, `Filtering & Signal Processing`, `All-MLP & Fourier Filtering`?**
  _High betweenness centrality (0.288) - this node is a cross-community bridge._
- **Why does `GRU4Rec model` connect `GRU4Rec Baselines & Datasets` to `Ranking Loss Functions`, `GRU4Rec Citations & Metrics`, `GRU / RNN Foundations`, `Session-Parallel Training`, `Item-based CF Baselines`?**
  _High betweenness centrality (0.119) - this node is a cross-community bridge._
- **Why does `Learnable Filter W (complex, optimized by SGD in frequency domain)` connect `Filtering & Signal Processing` to `All-MLP & Fourier Filtering`?**
  _High betweenness centrality (0.103) - this node is a cross-community bridge._
- **Are the 2 inferred relationships involving `Filter Layer (FFT -> learnable filter multiply -> inverse FFT)` (e.g. with `GFNet (Global Filter Network, 2D Fourier transform)` and `Denoising / low-pass filtering idea (noise as high-frequency signal)`) actually correct?**
  _`Filter Layer (FFT -> learnable filter multiply -> inverse FFT)` has 2 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Embedding Layer (item + learnable position encoding)`, `1D Fast Fourier Transform (FFT) / inverse FFT`, `Point-wise Feed-Forward Network (MLP + ReLU)` to the rest of the system?**
  _56 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Sequential Rec Baselines & Datasets` be split into smaller, more focused modules?**
  _Cohesion score 0.08 - nodes in this community are weakly interconnected._