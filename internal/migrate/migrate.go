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

// UsefulChunks extracts high-signal memory sections and skips rollout pointers,
// transient evidence lists, and low-context markdown scaffolding.
func UsefulChunks(text string) []string {
	groups := strings.Split(text, "\n# Task Group: ")
	var chunks []string
	for i, group := range groups {
		if strings.TrimSpace(group) == "" {
			continue
		}
		if i > 0 {
			group = "# Task Group: " + group
		}
		title := firstLine(group)
		var useful []string
		for _, section := range []string{"User preferences", "Reusable knowledge", "Implementation notes", "Reusable failure patterns"} {
			useful = append(useful, extractMarkdownSection(group, "## "+section)...)
		}
		if len(useful) == 0 {
			continue
		}
		chunk := title + "\n" + strings.Join(useful, "\n")
		chunks = append(chunks, splitUsefulChunk(strings.TrimSpace(chunk), 3800)...)
	}
	return chunks
}

func firstLine(text string) string {
	line, _, _ := strings.Cut(strings.TrimSpace(text), "\n")
	return line
}

func extractMarkdownSection(text, heading string) []string {
	start := strings.Index(text, heading)
	if start < 0 {
		return nil
	}
	section := text[start+len(heading):]
	if next := strings.Index(section, "\n## "); next >= 0 {
		section = section[:next]
	}
	var lines []string
	for _, line := range strings.Split(section, "\n") {
		line = strings.TrimSpace(line)
		if !strings.HasPrefix(line, "- ") {
			continue
		}
		if strings.Contains(line, "rollout_summaries/") ||
			strings.Contains(line, "rollout_path=") ||
			strings.HasPrefix(line, "- /Users/") {
			continue
		}
		lines = append(lines, line)
	}
	return lines
}

func splitUsefulChunk(chunk string, maxLen int) []string {
	if len(chunk) <= maxLen {
		return []string{chunk}
	}
	lines := strings.Split(chunk, "\n")
	if len(lines) <= 2 {
		return []string{chunk[:maxLen]}
	}
	title := lines[0]
	bodyLines := lines[1:]
	var result []string
	current := title
	part := 1
	totalParts := 1
	for _, line := range bodyLines {
		next := current + "\n" + line
		if len(next) > maxLen && current != title {
			result = append(result, current)
			current = title + fmt.Sprintf(" (part %d)", part+1) + "\n" + line
			part++
			totalParts++
			continue
		}
		current = next
	}
	result = append(result, current)
	if totalParts == 1 {
		return result
	}
	for i := range result {
		if i == 0 {
			result[i] = title + fmt.Sprintf(" (part %d)", i+1) + "\n" + strings.TrimPrefix(result[i], title+"\n")
		}
	}
	return result
}

// MigrateMarkdown 将 Markdown 文件中的记忆批量导入向量库
func MigrateMarkdown(mdPath string, s *store.MemoryStore, batchSize int) (int, error) {
	return MigrateMarkdownFrom(mdPath, s, batchSize, 0)
}

// MigrateMarkdownFrom 从指定 chunk 序号开始迁移，便于失败后续跑。
func MigrateMarkdownFrom(mdPath string, s *store.MemoryStore, batchSize int, start int) (int, error) {
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
	if start < 0 {
		start = 0
	}
	if start >= total {
		fmt.Printf("📄 共解析出 %d 条记忆块，起始位置 %d 已超过总数，无需写入\n", total, start)
		return 0, nil
	}
	fmt.Printf("📄 共解析出 %d 条记忆块，从第 %d 条开始写入...\n", total, start)

	done := 0
	for i := start; i < total; i += batchSize {
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
		fmt.Printf("   已写入 %d/%d（本次 %d）\n", end, total, done)
	}

	fmt.Printf("✅ 迁移完成，共写入 %d 条\n", done)
	return done, nil
}

// MigrateUsefulMarkdown migrates only high-signal memory sections.
func MigrateUsefulMarkdown(mdPath string, s *store.MemoryStore, batchSize int, start int, dryRun bool) (int, error) {
	data, err := os.ReadFile(mdPath)
	if err != nil {
		return 0, fmt.Errorf("读取文件失败: %w", err)
	}
	chunks := UsefulChunks(string(data))
	return migrateChunks(mdPath, chunks, s, batchSize, start, dryRun)
}

func migrateChunks(mdPath string, chunks []string, s *store.MemoryStore, batchSize int, start int, dryRun bool) (int, error) {
	if len(chunks) == 0 {
		fmt.Println("⚠️  未找到有效内容")
		return 0, nil
	}
	total := len(chunks)
	if start < 0 {
		start = 0
	}
	if start >= total {
		fmt.Printf("📄 共解析出 %d 条精选记忆块，起始位置 %d 已超过总数，无需写入\n", total, start)
		return 0, nil
	}
	if dryRun {
		fmt.Printf("📄 共解析出 %d 条精选记忆块，dry-run 不写入\n", total)
		for i, chunk := range chunks {
			preview := strings.ReplaceAll(chunk, "\n", " ")
			if len(preview) > 180 {
				preview = preview[:180] + "..."
			}
			fmt.Printf("   [%d] %s\n", i, preview)
		}
		return 0, nil
	}
	fmt.Printf("📄 共解析出 %d 条精选记忆块，从第 %d 条开始写入...\n", total, start)
	done := 0
	for i := start; i < total; i += batchSize {
		end := i + batchSize
		if end > total {
			end = total
		}
		source := fmt.Sprintf("migrate-useful:%s", mdPath)
		if err := s.SaveBatch(chunks[i:end], source); err != nil {
			return done, fmt.Errorf("批量写入失败: %w", err)
		}
		done += end - i
		fmt.Printf("   已写入 %d/%d（本次 %d）\n", end, total, done)
	}
	fmt.Printf("✅ 精选迁移完成，共写入 %d 条\n", done)
	return done, nil
}
