# 运维手册

## 启动 / 停止

```bash
# 启动
uv run stock-mcp

# 集成到 Claude Code
# 在 settings.json 添加 mcpServers 配置
```

## 日志位置

- **stderr** (而非 stdout!): MCP stdio 协议占用 stdout, 所有日志必须走 stderr
- 配置: `LOG_LEVEL=DEBUG|INFO|WARNING|ERROR`

## 缓存管理

- 缓存位置: `.cache/stock-mcp.db` (SQLite)
- TTL: 实时行情 3s, 分钟 K 线 60s, 日 K 线 1 天, 基本面 1 天, 资讯 10 分钟
- 手动清理:
  ```bash
  rm .cache/stock-mcp.db
  # 或选择性清理
  sqlite3 .cache/stock-mcp.db "DELETE FROM cache WHERE key LIKE 'quote:%'"
  ```

## Cookie 更新 (iwencai)

1. 浏览器登录 `iwencai.com`
2. 打开 DevTools → Network → 找到任意 API 请求
3. 复制请求头中的 `Cookie` 字段
4. 更新 `.env` 中 `IWENCAI_COOKIE=...`
5. 重启 MCP 服务

## TDX_PATH 配置

- 默认: `C:\new_tdx64`
- 修改: `.env` 中 `TDX_PATH=你的通达信安装路径`
- 留空: tqcenter 适配器自动禁用, 其他源继续工作

## 常见问题

**Q: tqcenter 报 "未初始化"**
- 检查 `TDX_PATH` 是否正确
- 检查通达信客户端是否在运行
- 检查 tqcenter 插件是否在 `TDX_PATH/PYPlugins/user/` 下

**Q: iwencai 报认证失败**
- Cookie 已过期, 重新登录 iwencai.com 获取新 Cookie
- 更新 `.env` 中 `IWENCAI_COOKIE`

**Q: 服务启动但 Claude Code 看不到工具**
- 检查 settings.json 配置是否正确
- 检查 `uv run stock-mcp` 命令是否能正常启动
