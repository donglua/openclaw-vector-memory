// Package config 提供 .env 文件解析和类型化配置结构
package config

import (
	"bufio"
	"fmt"
	"os"
	"strconv"
	"strings"
)

// LoadDotEnv 从 .env 文件加载环境变量（不覆盖已有）
func LoadDotEnv(paths ...string) {
	if len(paths) == 0 {
		paths = []string{".env"}
	}
	for _, p := range paths {
		loadFile(p)
	}
}

func loadFile(path string) {
	f, err := os.Open(path)
	if err != nil {
		return // 文件不存在则跳过
	}
	defer f.Close()

	scanner := bufio.NewScanner(f)
	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		key, value, ok := strings.Cut(line, "=")
		if !ok {
			continue
		}
		key = strings.TrimSpace(key)
		value = strings.TrimSpace(value)
		// 去除引号
		value = strings.Trim(value, `"'`)
		// 不覆盖已设置的环境变量
		if _, exists := os.LookupEnv(key); !exists {
			os.Setenv(key, value)
		}
	}
}

// ── 辅助取值函数 ──────────────────────────────────────────────

func Env(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}

func EnvRequired(key string) (string, error) {
	v := os.Getenv(key)
	if v == "" {
		return "", fmt.Errorf("缺少环境变量: %s", key)
	}
	return v, nil
}

func EnvInt(key string, fallback int) int {
	s := os.Getenv(key)
	if s == "" {
		return fallback
	}
	n, err := strconv.Atoi(s)
	if err != nil {
		return fallback
	}
	return n
}

func EnvFloat(key string, fallback float64) float64 {
	s := os.Getenv(key)
	if s == "" {
		return fallback
	}
	f, err := strconv.ParseFloat(s, 64)
	if err != nil {
		return fallback
	}
	return f
}

func EnvBool(key string, fallback bool) bool {
	s := os.Getenv(key)
	if s == "" {
		return fallback
	}
	s = strings.ToLower(strings.TrimSpace(s))
	switch s {
	case "1", "true", "yes", "on":
		return true
	case "0", "false", "no", "off":
		return false
	default:
		return fallback
	}
}

// ── Rerank 配置 ──────────────────────────────────────────────

// RerankConfig 重排配置
type RerankConfig struct {
	Enabled          bool
	Provider         string  // "reranker" 或 "llm"
	Model            string
	APIBase          string
	APIKey           string
	FetchK           int
	TimeoutMS        int
	FlatGapThreshold float64
	LowConfThreshold float64
	MinCandidates    int
	Force            bool
	Debug            bool
}

// LoadRerankConfig 从环境变量加载 Rerank 配置
func LoadRerankConfig() RerankConfig {
	return RerankConfig{
		Enabled:          EnvBool("RERANK_ENABLED", true),
		Provider:         Env("RERANK_PROVIDER", "reranker"),
		Model:            Env("RERANK_MODEL", "BAAI/bge-reranker-v2-m3"),
		APIBase:          Env("RERANK_API_BASE", Env("EMBEDDING_API_BASE", "")),
		APIKey:           Env("RERANK_API_KEY", Env("EMBEDDING_API_KEY", "")),
		FetchK:           EnvInt("RERANK_FETCH_K", 40),
		TimeoutMS:        EnvInt("RERANK_TIMEOUT_MS", 8000),
		FlatGapThreshold: EnvFloat("RERANK_FLAT_GAP_THRESHOLD", 0.03),
		LowConfThreshold: EnvFloat("RERANK_LOW_CONF_THRESHOLD", 0.45),
		MinCandidates:    EnvInt("RERANK_MIN_CANDIDATES", 8),
		Force:            EnvBool("RERANK_FORCE", false),
		Debug:            EnvBool("RERANK_DEBUG", false),
	}
}
