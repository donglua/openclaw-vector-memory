// Package zilliz 提供 Zilliz Cloud RESTful API 客户端
// 直接基于 net/http，零第三方依赖
package zilliz

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strings"
	"time"
)

// Client Zilliz Cloud REST API 客户端
type Client struct {
	baseURL string
	token   string
	client  *http.Client
}

// NewClient 创建 Zilliz Cloud 客户端
func NewClient(uri, token string) *Client {
	// 确保 baseURL 以 /v2/vectordb 结尾的格式
	baseURL := strings.TrimRight(uri, "/")
	return &Client{
		baseURL: baseURL,
		token:   token,
		client:  &http.Client{Timeout: 30 * time.Second},
	}
}

// do 发送 HTTP 请求
func (c *Client) do(path string, payload interface{}) (json.RawMessage, error) {
	body, err := json.Marshal(payload)
	if err != nil {
		return nil, fmt.Errorf("序列化请求失败: %w", err)
	}

	url := fmt.Sprintf("%s/v2/vectordb%s", c.baseURL, path)
	req, err := http.NewRequest("POST", url, bytes.NewReader(body))
	if err != nil {
		return nil, fmt.Errorf("创建请求失败: %w", err)
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", "Bearer "+c.token)

	resp, err := c.client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("请求失败: %w", err)
	}
	defer resp.Body.Close()

	respBody, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("读取响应失败: %w", err)
	}

	var result struct {
		Code    int             `json:"code"`
		Message string          `json:"message"`
		Data    json.RawMessage `json:"data"`
	}
	if err := json.Unmarshal(respBody, &result); err != nil {
		return nil, fmt.Errorf("解析响应失败: %s", string(respBody))
	}
	if result.Code != 0 {
		return nil, fmt.Errorf("Zilliz API 错误 %d: %s", result.Code, result.Message)
	}
	return result.Data, nil
}

// ── Collection 操作 ──────────────────────────────────────────

// HasCollection 检查 Collection 是否存在
func (c *Client) HasCollection(name string) (bool, error) {
	data, err := c.do("/collections/has", map[string]string{
		"collectionName": name,
	})
	if err != nil {
		return false, err
	}
	var res struct {
		Has bool `json:"has"`
	}
	if err := json.Unmarshal(data, &res); err != nil {
		return false, err
	}
	return res.Has, nil
}

// CreateCollection 创建 Collection
func (c *Client) CreateCollection(name string, denseDim int) error {
	schema := map[string]interface{}{
		"autoId":             true,
		"enableDynamicField": true,
		"fields": []map[string]interface{}{
			{
				"fieldName":  "id",
				"dataType":   "Int64",
				"isPrimary":  true,
				"autoID":     true,
			},
			{
				"fieldName": "dense_vector",
				"dataType":  "FloatVector",
				"elementTypeParams": map[string]interface{}{
					"dim": denseDim,
				},
			},
			{
				"fieldName":  "text",
				"dataType":   "VarChar",
				"elementTypeParams": map[string]interface{}{
					"max_length": 4096,
				},
			},
			{
				"fieldName":  "source",
				"dataType":   "VarChar",
				"elementTypeParams": map[string]interface{}{
					"max_length": 256,
				},
			},
			{
				"fieldName": "created_at",
				"dataType":  "Int64",
			},
		},
	}

	indexParams := []map[string]interface{}{
		{
			"fieldName":  "dense_vector",
			"indexName":  "dense_idx",
			"metricType": "COSINE",
			"indexType":  "AUTOINDEX",
		},
	}

	_, err := c.do("/collections/create", map[string]interface{}{
		"collectionName": name,
		"schema":         schema,
		"indexParams":    indexParams,
	})
	return err
}

// ── 数据操作 ─────────────────────────────────────────────────

// InsertRow 单行数据
type InsertRow struct {
	DenseVector []float32 `json:"dense_vector"`
	Text        string    `json:"text"`
	Source      string    `json:"source"`
	CreatedAt   int64     `json:"created_at"`
}

// Insert 写入数据
func (c *Client) Insert(collection string, rows []InsertRow) error {
	// 转为 map 切片以支持 dynamic field
	data := make([]map[string]interface{}, len(rows))
	for i, r := range rows {
		data[i] = map[string]interface{}{
			"dense_vector": r.DenseVector,
			"text":         r.Text,
			"source":       r.Source,
			"created_at":   r.CreatedAt,
		}
	}

	_, err := c.do("/entities/insert", map[string]interface{}{
		"collectionName": collection,
		"data":           data,
	})
	return err
}

// ── 搜索操作 ─────────────────────────────────────────────────

// SearchHit 搜索结果
type SearchHit struct {
	Text   string  `json:"text"`
	Source string  `json:"source"`
	Score  float64 `json:"score"`
}

// Search 向量搜索
func (c *Client) Search(collection string, vector []float32, topK int) ([]SearchHit, error) {
	payload := map[string]interface{}{
		"collectionName": collection,
		"data":           [][]float32{vector},
		"annsField":      "dense_vector",
		"limit":          topK,
		"outputFields":   []string{"text", "source", "created_at"},
		"searchParams": map[string]interface{}{
			"metric_type": "COSINE",
			"params":      map[string]interface{}{"nprobe": 10},
		},
	}

	data, err := c.do("/entities/search", payload)
	if err != nil {
		return nil, err
	}

	// 响应格式：二维数组 [[{id, distance, entity: {text, source}}]]
	var rawResults [][]struct {
		Distance float64 `json:"distance"`
		Entity   struct {
			Text   string `json:"text"`
			Source string `json:"source"`
		} `json:"entity"`
	}
	if err := json.Unmarshal(data, &rawResults); err != nil {
		return nil, fmt.Errorf("解析搜索结果失败: %w", err)
	}

	var hits []SearchHit
	if len(rawResults) > 0 {
		for _, r := range rawResults[0] {
			hits = append(hits, SearchHit{
				Text:   r.Entity.Text,
				Source: r.Entity.Source,
				Score:  r.Distance,
			})
		}
	}
	return hits, nil
}

// ── 统计操作 ─────────────────────────────────────────────────

// Count 返回 Collection 中的实体数量
func (c *Client) Count(collection string) (int64, error) {
	data, err := c.do("/collections/get_stats", map[string]string{
		"collectionName": collection,
	})
	if err != nil {
		return 0, err
	}
	var stats struct {
		RowCount int64 `json:"rowCount"`
	}
	if err := json.Unmarshal(data, &stats); err != nil {
		return 0, err
	}
	return stats.RowCount, nil
}
