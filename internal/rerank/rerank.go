// Package rerank 提供重排决策逻辑和 Reranker 适配器
package rerank

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"sort"
	"strings"
	"time"

	"github.com/nichuanfang/openclaw-vector-memory/internal/config"
)

// ── 重排策略决策 ─────────────────────────────────────────────

// ShouldRerank 判断是否应触发重排
// 返回 (是否重排, 原因)
func ShouldRerank(scores []float64, topK int, cfg config.RerankConfig) (bool, string) {
	if cfg.Force {
		return true, "force"
	}
	if len(scores) < cfg.MinCandidates || len(scores) < topK {
		return false, "insufficient_candidates"
	}

	top1 := scores[0]
	kIdx := topK - 1
	if kIdx >= len(scores) {
		kIdx = len(scores) - 1
	}
	kth := scores[kIdx]

	if (top1 - kth) < cfg.FlatGapThreshold {
		return true, "flat_gap"
	}
	if top1 < cfg.LowConfThreshold {
		return true, "low_conf"
	}
	return false, "high_conf"
}

// ── 合并重排结果 ─────────────────────────────────────────────

// Hit 搜索结果表示
type Hit struct {
	Text   string  `json:"text"`
	Source string  `json:"source"`
	Score  float64 `json:"score"`
}

// MergeReranked 将重排索引合并/去重/补齐，返回 top_k 结果
func MergeReranked(candidates []Hit, rerankedIndices []int, topK int) []Hit {
	seen := make(map[int]bool)
	var valid []int

	for _, idx := range rerankedIndices {
		if idx >= 0 && idx < len(candidates) && !seen[idx] {
			valid = append(valid, idx)
			seen[idx] = true
		}
	}

	// 补齐未出现的候选
	for idx := range candidates {
		if !seen[idx] {
			valid = append(valid, idx)
		}
	}

	if topK < len(valid) {
		valid = valid[:topK]
	}

	result := make([]Hit, len(valid))
	for i, idx := range valid {
		result[i] = candidates[idx]
	}
	return result
}

// ── Reranker 接口和实现 ──────────────────────────────────────

// Reranker 重排器接口
type Reranker interface {
	Rerank(query string, candidates []Hit) ([]int, error)
}

// ── APIReranker：专用 Reranker API ──────────────────────────

// APIReranker 专用 Reranker API 适配器（如硅基流动 /v1/rerank）
type APIReranker struct {
	apiBase   string
	apiKey    string
	model     string
	timeoutMS int
	client    *http.Client
}

// NewAPIReranker 创建 APIReranker
func NewAPIReranker(apiBase, apiKey, model string, timeoutMS int) *APIReranker {
	return &APIReranker{
		apiBase:   apiBase,
		apiKey:    apiKey,
		model:     model,
		timeoutMS: timeoutMS,
		client:    &http.Client{Timeout: time.Duration(timeoutMS) * time.Millisecond},
	}
}

func (r *APIReranker) Rerank(query string, candidates []Hit) ([]int, error) {
	docs := make([]string, len(candidates))
	for i, c := range candidates {
		docs[i] = c.Text
	}

	payload := map[string]interface{}{
		"model":     r.model,
		"query":     query,
		"documents": docs,
	}
	body, err := json.Marshal(payload)
	if err != nil {
		return nil, fmt.Errorf("序列化 rerank 请求失败: %w", err)
	}

	url := fmt.Sprintf("%s/rerank", strings.TrimRight(r.apiBase, "/"))
	req, err := http.NewRequest("POST", url, bytes.NewReader(body))
	if err != nil {
		return nil, err
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", "Bearer "+r.apiKey)

	resp, err := r.client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("Reranker API 请求失败: %w", err)
	}
	defer resp.Body.Close()

	respBody, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, err
	}
	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("Reranker API 返回 %d: %s", resp.StatusCode, string(respBody))
	}

	var result struct {
		Results []struct {
			Index          int     `json:"index"`
			RelevanceScore float64 `json:"relevance_score"`
		} `json:"results"`
	}
	if err := json.Unmarshal(respBody, &result); err != nil {
		return nil, fmt.Errorf("解析 reranker 响应失败: %w", err)
	}

	// 按 relevance_score 降序排
	sort.Slice(result.Results, func(i, j int) bool {
		return result.Results[i].RelevanceScore > result.Results[j].RelevanceScore
	})

	indices := make([]int, len(result.Results))
	for i, r := range result.Results {
		indices[i] = r.Index
	}
	return indices, nil
}

// ── LLMReranker：通用 Chat Completion ──────────────────────

// LLMReranker 通用 LLM Chat Completion 重排适配器
type LLMReranker struct {
	apiBase   string
	apiKey    string
	model     string
	timeoutMS int
	client    *http.Client
}

// NewLLMReranker 创建 LLMReranker
func NewLLMReranker(apiBase, apiKey, model string, timeoutMS int) *LLMReranker {
	return &LLMReranker{
		apiBase:   apiBase,
		apiKey:    apiKey,
		model:     model,
		timeoutMS: timeoutMS,
		client:    &http.Client{Timeout: time.Duration(timeoutMS) * time.Millisecond},
	}
}

func (r *LLMReranker) Rerank(query string, candidates []Hit) ([]int, error) {
	var sb strings.Builder
	for i, c := range candidates {
		fmt.Fprintf(&sb, "%d. %s\n", i, c.Text)
	}

	prompt := fmt.Sprintf(
		"Rank candidates by relevance to query. Return JSON only with key ranked_indices as integer array.\nQuery: %s\nCandidates:\n%s",
		query, sb.String(),
	)

	chatReq := map[string]interface{}{
		"model":       r.model,
		"temperature": 0,
		"messages": []map[string]string{
			{"role": "system", "content": "You are a reranker."},
			{"role": "user", "content": prompt},
		},
	}
	body, err := json.Marshal(chatReq)
	if err != nil {
		return nil, err
	}

	url := fmt.Sprintf("%s/chat/completions", strings.TrimRight(r.apiBase, "/"))
	req, err := http.NewRequest("POST", url, bytes.NewReader(body))
	if err != nil {
		return nil, err
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", "Bearer "+r.apiKey)

	resp, err := r.client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("LLM Reranker 请求失败: %w", err)
	}
	defer resp.Body.Close()

	respBody, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, err
	}
	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("LLM API 返回 %d: %s", resp.StatusCode, string(respBody))
	}

	var chatResp struct {
		Choices []struct {
			Message struct {
				Content string `json:"content"`
			} `json:"message"`
		} `json:"choices"`
	}
	if err := json.Unmarshal(respBody, &chatResp); err != nil {
		return nil, fmt.Errorf("解析 LLM 响应失败: %w", err)
	}
	if len(chatResp.Choices) == 0 {
		return nil, fmt.Errorf("LLM 返回空 choices")
	}

	content := chatResp.Choices[0].Message.Content
	var payload struct {
		RankedIndices []int `json:"ranked_indices"`
	}
	if err := json.Unmarshal([]byte(content), &payload); err != nil {
		return nil, fmt.Errorf("解析 ranked_indices 失败: %w (content: %s)", err, content)
	}

	return payload.RankedIndices, nil
}
