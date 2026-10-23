# README 步骤图

本目录保存用于生成 `docs/images/` 操作示意图的 Remotion 源码。

美术文件不在本目录重复存放。`remotion.config.ts` 将 `../assets` 设置为公共素材目录，场景通过 `staticFile()` 读取品牌标志、卡面与卡背。

```powershell
pnpm install
pnpm run lint
pnpm exec remotion studio
```

单张渲染示例：

```powershell
pnpm exec remotion still Step01Connect ../docs/images/step-01-connect-mcp.png --frame=60
```

可用场景：`Step01Connect`、`Step02Choose`、`Step03Save`、`Step04Review`、`Step05Draw`。
