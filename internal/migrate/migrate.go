// Package migrate 提供从 MEMORY.md 迁移记忆到向量库的功能
package migrate

import (
	"fmt"
	"os"
	"strings"

	"github.com/nichuanfang/openclaw-vector-memory/internal/store"
)

// splitChunks 按段落（空行）分块，过滤太短的片段
func splitChunks(text string, minLen int) []string {
	raw := strings.Split(text, "\n\n")
	var chunks []string
	for _, chunk := range raw {
		chunk = strings.TrimSpace(chunk)
		if len(chunk) < minLen {
			continue
		}
		chunks = append(chunks, chunk)
	}
	return chunks
}

// MigrateMarkdown 将 Markdown 文件中的记忆批量导入向量库
func MigrateMarkdown(mdPath string, s *store.MemoryStore, batchSize int) (int, error) {
	data, err := os.ReadFile(mdPath)
	if err != nil {
		return 0, fmt.Errorf("读取文件失败: %w", err)
	}

	chunks := splitChunks(string(data), 20)
	if len(chunks) == 0 {
		fmt.Println("⚠️  未找到有效内容")
		return 0, nil
	}

	total := len(chunks)
	fmt.Printf("📄 共解析出 %d 条记忆块，开始写入...\n", total)

	done := 0
	for i := 0; i < total; i += batchSize {
		end := i + batchSize
		if end > total {
			end = total
		}
		batch := chunks[i:end]
		source := fmt.Sprintf("migrate:%s", mdPath)
		if err := s.SaveBatch(batch, source); err != nil {
			return done, fmt.Errorf("批量写入失败: %w", err)
		}
		done += len(batch)
		fmt.Printf("   已写入 %d/%d\n", done, total)
	}

	fmt.Printf("✅ 迁移完成，共写入 %d 条\n", done)
	return done, nil
}
