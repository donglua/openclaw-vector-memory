// Package store 提供 OpenClaw 向量记忆存储核心
package store

import (
	"fmt"
	"math"
	"strings"
	"time"

	"github.com/nichuanfang/openclaw-vector-memory/internal/config"
	"github.com/nichuanfang/openclaw-vector-memory/internal/embedder"
	"github.com/nichuanfang/openclaw-vector-memory/internal/rerank"
	"github.com/nichuanfang/openclaw-vector-memory/internal/zilliz"
)

// MemoryStore 向量记忆存储
type MemoryStore struct {
	client    *zilliz.Client
	embedder  *embedder.Embedder
	col       string
	rerankCfg config.RerankConfig
	reranker  rerank.Reranker
}

// New 创建 MemoryStore
func New() (*MemoryStore, error) {
	uri, err := config.EnvRequired("ZILLIZ_URI")
	if err != nil {
		return nil, err
	}
	token, err := config.EnvRequired("ZILLIZ_TOKEN")
	if err != nil {
		return nil, err
	}

	emb, err := embedder.New()
	if err != nil {
		return nil, err
	}

	col := config.Env("COLLECTION_NAME", "openclaw_memories")
	client := zilliz.NewClient(uri, token)
	rerankCfg := config.LoadRerankConfig()

	s := &MemoryStore{
		client:    client,
		embedder:  emb,
		col:       col,
		rerankCfg: rerankCfg,
	}

	// 初始化 Reranker
	if rerankCfg.Enabled {
		switch rerankCfg.Provider {
		case "reranker":
			s.reranker = rerank.NewAPIReranker(
				rerankCfg.APIBase, rerankCfg.APIKey,
				rerankCfg.Model, rerankCfg.TimeoutMS,
			)
		case "llm":
			s.reranker = rerank.NewLLMReranker(
				rerankCfg.APIBase, rerankCfg.APIKey,
				rerankCfg.Model, rerankCfg.TimeoutMS,
			)
		}
	}

	// 确保 Collection 存在
	if err := s.ensureCollection(); err != nil {
		return nil, err
	}

	return s, nil
}

func (s *MemoryStore) ensureCollection() error {
	has, err := s.client.HasCollection(s.col)
	if err != nil {
		return fmt.Errorf("检查 Collection 失败: %w", err)
	}
	if !has {
		if err := s.client.CreateCollection(s.col, s.embedder.Dim()); err != nil {
			return fmt.Errorf("创建 Collection 失败: %w", err)
		}
		fmt.Printf("✅ 已创建 Collection：%s\n", s.col)
	} else {
		fmt.Printf("✅ 已连接 Collection：%s\n", s.col)
	}
	return nil
}

// Save 写入一条记忆
func (s *MemoryStore) Save(text, source string) error {
	vec, err := s.embedder.Embed(text)
	if err != nil {
		return fmt.Errorf("embedding 失败: %w", err)
	}
	return s.client.Insert(s.col, []zilliz.InsertRow{{
		DenseVector: vec,
		Text:        text,
		Source:      source,
		CreatedAt:   time.Now().Unix(),
	}})
}

// SaveBatch 批量写入
func (s *MemoryStore) SaveBatch(texts []string, source string) error {
	if len(texts) == 0 {
		return nil
	}
	vecs, err := s.embedder.EmbedBatch(texts)
	if err != nil {
		return fmt.Errorf("batch embedding 失败: %w", err)
	}
	now := time.Now().Unix()
	rows := make([]zilliz.InsertRow, len(texts))
	for i, text := range texts {
		rows[i] = zilliz.InsertRow{
			DenseVector: vecs[i],
			Text:        text,
			Source:      source,
			CreatedAt:   now,
		}
	}
	return s.client.Insert(s.col, rows)
}

// Search 搜索记忆
func (s *MemoryStore) Search(query string, topK int) ([]rerank.Hit, error) {
	vec, err := s.embedder.Embed(query)
	if err != nil {
		return nil, fmt.Errorf("query embedding 失败: %w", err)
	}

	// 根据 rerank 配置决定 fetch 数量
	fetchK := topK
	if s.rerankCfg.Enabled && s.reranker != nil {
		fetchK = max(topK, s.rerankCfg.FetchK)
	}

	zHits, err := s.client.Search(s.col, vec, fetchK)
	if err != nil {
		return nil, fmt.Errorf("搜索失败: %w", err)
	}

	hits := make([]rerank.Hit, len(zHits))
	for i, h := range zHits {
		hits[i] = rerank.Hit{
			Text:   h.Text,
			Source: h.Source,
			Score:  math.Round(h.Score*10000) / 10000, // 保留 4 位小数
		}
	}

	// 无 reranker 则直接截断返回
	if !s.rerankCfg.Enabled || s.reranker == nil {
		return truncate(hits, topK), nil
	}

	// 条件触发重排
	scores := make([]float64, len(hits))
	for i, h := range hits {
		scores[i] = h.Score
	}

	doRerank, reason := rerank.ShouldRerank(scores, topK, s.rerankCfg)
	s.debugf("should=%v, reason=%s, candidates=%d", doRerank, reason, len(hits))
	if !doRerank {
		return truncate(hits, topK), nil
	}

	rerankedIndices, err := s.reranker.Rerank(query, hits)
	if err != nil {
		s.debugf("rerank fallback due to: %v", err)
		return truncate(hits, topK), nil // 降级
	}

	return rerank.MergeReranked(hits, rerankedIndices, topK), nil
}

// BuildPromptContext 构建可注入 Prompt 的记忆片段
func (s *MemoryStore) BuildPromptContext(query string, topK int) (string, error) {
	hits, err := s.Search(query, topK)
	if err != nil {
		return "", err
	}
	if len(hits) == 0 {
		return "", nil
	}
	var sb strings.Builder
	sb.WriteString("## 相关记忆\n")
	for _, h := range hits {
		fmt.Fprintf(&sb, "- %s\n", h.Text)
	}
	return sb.String(), nil
}

// Count 返回记忆总条数
func (s *MemoryStore) Count() (int64, error) {
	return s.client.Count(s.col)
}

func (s *MemoryStore) debugf(format string, args ...interface{}) {
	if s.rerankCfg.Debug {
		fmt.Printf("[rerank-debug] "+format+"\n", args...)
	}
}

func truncate(hits []rerank.Hit, topK int) []rerank.Hit {
	if topK >= len(hits) {
		return hits
	}
	return hits[:topK]
}

func max(a, b int) int {
	if a > b {
		return a
	}
	return b
}
