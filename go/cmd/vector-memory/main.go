// OpenClaw 向量记忆 CLI 入口（Go 版）
//
// 用法：
//
//	vector-memory --save "用户喜欢用 Go"
//	vector-memory --search "用户有什么编程习惯"
//	vector-memory --migrate path/to/MEMORY.md
//	vector-memory --test
//	vector-memory --count
package main

import (
	"flag"
	"fmt"
	"os"

	"github.com/nichuanfang/openclaw-vector-memory/internal/config"
	"github.com/nichuanfang/openclaw-vector-memory/internal/migrate"
	"github.com/nichuanfang/openclaw-vector-memory/internal/store"
)

func main() {
	saveText := flag.String("save", "", "写入一条记忆")
	searchQuery := flag.String("search", "", "语义搜索记忆")
	migratePath := flag.String("migrate", "", "从 Markdown 文件迁移记忆")
	doCount := flag.Bool("count", false, "查看记忆总条数")
	doTest := flag.Bool("test", false, "运行端到端测试")
	topK := flag.Int("top-k", 5, "搜索返回条数")

	flag.Parse()

	// 检查互斥参数
	n := 0
	if *saveText != "" {
		n++
	}
	if *searchQuery != "" {
		n++
	}
	if *migratePath != "" {
		n++
	}
	if *doCount {
		n++
	}
	if *doTest {
		n++
	}
	if n == 0 {
		flag.Usage()
		os.Exit(1)
	}
	if n > 1 {
		fmt.Fprintln(os.Stderr, "❌ 只能同时指定一个操作")
		os.Exit(1)
	}

	// 加载 .env
	config.LoadDotEnv()

	switch {
	case *saveText != "":
		cmdSave(*saveText)
	case *searchQuery != "":
		cmdSearch(*searchQuery, *topK)
	case *migratePath != "":
		cmdMigrate(*migratePath)
	case *doCount:
		cmdCount()
	case *doTest:
		cmdTest()
	}
}

func getStore() *store.MemoryStore {
	s, err := store.New()
	if err != nil {
		fmt.Fprintf(os.Stderr, "❌ %v\n请复制 .env.example 为 .env 并填入配置\n", err)
		os.Exit(1)
	}
	return s
}

func cmdSave(text string) {
	s := getStore()
	if err := s.Save(text, "cli"); err != nil {
		fmt.Fprintf(os.Stderr, "❌ 写入失败: %v\n", err)
		os.Exit(1)
	}
	fmt.Printf("✅ 已保存记忆：%s\n", text)
}

func cmdSearch(query string, topK int) {
	s := getStore()
	hits, err := s.Search(query, topK)
	if err != nil {
		fmt.Fprintf(os.Stderr, "❌ 搜索失败: %v\n", err)
		os.Exit(1)
	}
	if len(hits) == 0 {
		fmt.Println("❌ 未找到相关记忆")
		return
	}
	fmt.Printf("\n🔍 查询：%s\n\n", query)
	for i, h := range hits {
		fmt.Printf("  [%d] 得分: %.4f | 来源: %s\n", i+1, h.Score, h.Source)
		fmt.Printf("      %s\n\n", h.Text)
	}
}

func cmdMigrate(mdPath string) {
	s := getStore()
	_, err := migrate.MigrateMarkdown(mdPath, s, 32)
	if err != nil {
		fmt.Fprintf(os.Stderr, "❌ 迁移失败: %v\n", err)
		os.Exit(1)
	}
}

func cmdCount() {
	s := getStore()
	n, err := s.Count()
	if err != nil {
		fmt.Fprintf(os.Stderr, "❌ 获取统计失败: %v\n", err)
		os.Exit(1)
	}
	fmt.Printf("📊 当前记忆库中共有 %d 条记忆\n", n)
}

func cmdTest() {
	fmt.Println("=== OpenClaw 向量记忆测试 (Go) ===")
	fmt.Println()
	s := getStore()

	// 写入测试记忆
	testText := "用户喜欢用 Go，讨厌复杂的依赖管理，偏好简洁代码风格"
	fmt.Printf("[1/3] 写入测试记忆：%s\n", testText)
	if err := s.Save(testText, "test"); err != nil {
		fmt.Fprintf(os.Stderr, "      ❌ 写入失败: %v\n", err)
		os.Exit(1)
	}
	fmt.Println("      写入成功")
	fmt.Println()

	// 搜索测试
	query := "这个用户喜欢什么编程语言"
	fmt.Printf("[2/3] 搜索：%s\n", query)
	hits, err := s.Search(query, 3)
	if err != nil {
		fmt.Fprintf(os.Stderr, "      ❌ 搜索失败: %v\n", err)
		os.Exit(1)
	}
	fmt.Printf("      返回 %d 条结果\n", len(hits))
	for _, h := range hits {
		text := h.Text
		if len(text) > 60 {
			text = text[:60]
		}
		fmt.Printf("      得分 %.4f | %s\n", h.Score, text)
	}
	fmt.Println()

	// 验证召回
	found := false
	for _, h := range hits {
		if h.Text == testText {
			found = true
			break
		}
	}
	if found {
		fmt.Println("[3/3] ✅ 测试通过：成功召回刚写入的记忆")
	} else {
		fmt.Println("[3/3] ⚠️  未在 Top-3 中找到刚写入的记忆（可能需等待索引刷新，再次运行试试）")
	}

	// Prompt 片段示例
	fmt.Println("\n--- build_prompt_context 示例 ---")
	ctx, err := s.BuildPromptContext(query, 5)
	if err != nil {
		fmt.Fprintf(os.Stderr, "❌ %v\n", err)
		return
	}
	fmt.Println(ctx)
}
