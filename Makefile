APP_NAME := vector-memory
VERSION  := $(shell git describe --tags --always --dirty 2>/dev/null || echo "dev")
BUILD    := $(shell date -u +%Y%m%d%H%M%S)
LDFLAGS  := -s -w -X main.version=$(VERSION) -X main.buildTime=$(BUILD)
GOFLAGS  := -trimpath

.PHONY: build clean release test

# 构建当前平台
build:
	go build $(GOFLAGS) -ldflags '$(LDFLAGS)' -o $(APP_NAME) ./cmd/vector-memory/

# 清理
clean:
	rm -f $(APP_NAME) $(APP_NAME)-*

# 交叉编译多平台
release: clean
	@echo "=== 编译 Linux amd64 ==="
	GOOS=linux   GOARCH=amd64 go build $(GOFLAGS) -ldflags '$(LDFLAGS)' -o $(APP_NAME)-linux-amd64   ./cmd/vector-memory/
	@echo "=== 编译 Linux arm64 ==="
	GOOS=linux   GOARCH=arm64 go build $(GOFLAGS) -ldflags '$(LDFLAGS)' -o $(APP_NAME)-linux-arm64   ./cmd/vector-memory/
	@echo "=== 编译 macOS amd64 ==="
	GOOS=darwin  GOARCH=amd64 go build $(GOFLAGS) -ldflags '$(LDFLAGS)' -o $(APP_NAME)-darwin-amd64  ./cmd/vector-memory/
	@echo "=== 编译 macOS arm64 ==="
	GOOS=darwin  GOARCH=arm64 go build $(GOFLAGS) -ldflags '$(LDFLAGS)' -o $(APP_NAME)-darwin-arm64  ./cmd/vector-memory/
	@echo "=== 编译 Windows amd64 ==="
	GOOS=windows GOARCH=amd64 go build $(GOFLAGS) -ldflags '$(LDFLAGS)' -o $(APP_NAME)-windows-amd64.exe ./cmd/vector-memory/
	@echo "✅ 全部编译完成"
	@ls -lh $(APP_NAME)-*

# 运行 go vet
test:
	go vet ./...
