// Package embedder 提供 OpenAI 兼容的远程 Embedding API 客户端
package embedder

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"

	"github.com/nichuanfang/openclaw-vector-memory/internal/config"
)

// Embedder 远程 Embedding 客户端
type Embedder struct {
	apiBase string
	apiKey  string
	model   string
	dim     int
	client  *http.Client
}

// New 创建 Embedder 实例
func New() (*Embedder, error) {
	apiBase, err := config.EnvRequired("EMBEDDING_API_BASE")
	if err != nil {
		return nil, err
	}
	apiKey, err := config.EnvRequired("EMBEDDING_API_KEY")
	if err != nil {
		return nil, err
	}

	return &Embedder{
		apiBase: apiBase,
		apiKey:  apiKey,
		model:   config.Env("EMBEDDING_MODEL", "Qwen/Qwen3-Embedding-8B"),
		dim:     config.EnvInt("EMBEDDING_DIM", 4096),
		client:  &http.Client{Timeout: 30 * time.Second},
	}, nil
}

// Dim 返回向量维度
func (e *Embedder) Dim() int {
	return e.dim
}

// ── API 请求/响应结构 ─────────────────────────────────────────

type embeddingRequest struct {
	Model string      `json:"model"`
	Input interface{} `json:"input"` // string 或 []string
}

type embeddingResponse struct {
	Data []struct {
		Index     int       `json:"index"`
		Embedding []float32 `json:"embedding"`
	} `json:"data"`
}

// Embed 生成单条文本的 embedding 向量
func (e *Embedder) Embed(text string) ([]float32, error) {
	vecs, err := e.EmbedBatch([]string{text})
	if err != nil {
		return nil, err
	}
	return vecs[0], nil
}

// EmbedBatch 批量生成 embedding 向量
func (e *Embedder) EmbedBatch(texts []string) ([][]float32, error) {
	reqBody := embeddingRequest{
		Model: e.model,
		Input: texts,
	}
	body, err := json.Marshal(reqBody)
	if err != nil {
		return nil, fmt.Errorf("序列化请求失败: %w", err)
	}

	url := fmt.Sprintf("%s/embeddings", e.apiBase)
	req, err := http.NewRequest("POST", url, bytes.NewReader(body))
	if err != nil {
		return nil, fmt.Errorf("创建请求失败: %w", err)
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", "Bearer "+e.apiKey)

	resp, err := e.client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("Embedding API 请求失败: %w", err)
	}
	defer resp.Body.Close()

	respBody, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("读取响应失败: %w", err)
	}
	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("Embedding API 返回 %d: %s", resp.StatusCode, string(respBody))
	}

	var result embeddingResponse
	if err := json.Unmarshal(respBody, &result); err != nil {
		return nil, fmt.Errorf("解析 Embedding 响应失败: %w", err)
	}

	// 按 index 排序
	vecs := make([][]float32, len(texts))
	for _, d := range result.Data {
		if d.Index < len(vecs) {
			vecs[d.Index] = d.Embedding
		}
	}

	return vecs, nil
}
