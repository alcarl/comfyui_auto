<h1 align="center">comfyui auto</h1>


本项目是一个基于PyDracula-flet项目构建的py客户端程序
目的是实现comfyui的自动化出图，自动获取原图，自动调用模型出图


# 项目预览


# 业务核心模块（app/core）

项目按**工程化、模块化、解耦**设计。所有业务逻辑与 UI（flet）完全解耦，
集中在 `app/core/` 包中，可独立进行单元测试。

## 整体流程

```
图片网站(可配置多站)  --抓取(crawler)-->  本地图片库(image_library, 按URL去重)
                                                    |
                                                    v
                                          图生图(comfyui)  --编排(pipeline)-->
                                                     生成结果(outputs/)
```

## 模块结构

| 模块 | 路径 | 职责 | 解耦点 |
|------|------|------|--------|
| 配置 | `app/core/config` | 多站点抓取、图片库、ComfyUI 的 pydantic 配置模型 + 单例管理器 | 与 UI 的 AppConfig 独立，持久化于 `config/core_config.json` |
| 图片库 | `app/core/image_library` | 本地图片存储、索引(`index.json`)、**防重复**（URL/哈希） | 仅依赖文件系统，不触网 |
| 抓取 | `app/core/crawler` | 图片网站批量抓取，支持多站配置；一期实现 Pinterest（http 与浏览器两种后端） | 网络通过可注入 `http_get` 解耦；浏览器后端通过 `app/core/browser` 解耦 |
| 浏览器 | `app/core/browser` | 基于 nodriver 真实浏览器自动化：代理、登录态保存/加载、Pinterest 登录助手、浏览器抓取 | 浏览器实例与 `http_get` 均可注入，便于测试 |
| ComfyUI | `app/core/comfyui` | 调用 ComfyUI 工作流完成图生图（上传原图→替换 LoadImage→提交→取结果） | 网络通过可注入 `transport` 解耦 |
| 编排 | `app/core/pipeline` | 串联 抓取→入库→图生图，提供进度回调 | 仅调度，不实现具体逻辑 |

## 防重复机制

本地图片库通过**来源 URL 规范化**判定重复（默认开启），可选**内容 sha256 哈希**去重。
规范化会去掉 URL 末尾斜杠、fragment、追踪查询参数，因此
`https://x.com/p/1/` 与 `https://x.com/p/1/?utm=xxx` 会被视为同一张图，避免反复下载。

## 多网站配置

`config/core_config.json` 的 `sites` 数组支持配置多个站点：

```json
{
  "sites": [
    {
      "name": "pinterest_demo",
      "crawler_type": "pinterest",
      "enabled": true,
      "urls": ["https://jp.pinterest.com/pin/1028087421172953769/"],
      "extra": {"locale": "jp"}
    }
  ]
}
```

一期已支持两种 Pinterest 抓取后端：

- `pinterest`（http 后端）：纯请求解析页面 JSON，轻量、无需浏览器，
  但面对登录墙/反爬时可能拿不到数据。
- `pinterest_browser`（浏览器后端）：用 **nodriver** 真实驱动浏览器打开页面、
  滚动加载、读取渲染后的 DOM 图片地址，可绕过大部分反爬与登录限制，
  且无需研究 Pinterest 私有 API。适合登录后才能访问的内容。

后续可通过 `crawler/factory.py` 的 `register_crawler` 注册 unsplash、pixiv 等
更多抓取器，无需改动其它模块。

## 浏览器抓取（nodriver）与登录态

`pinterest_browser` 通过 `app/core/browser` 模块驱动真实浏览器：

- **代理**：在 `config/core_config.json` 的 `crawler.browser.proxy` 配置，
  如 `http://10.0.0.51:1072`，启动浏览器时自动附加 `--proxy-server`。
- **登录态保存/复用**：登录后浏览器数据持久化在 `browser.user_data_dir`，
  同时 cookie 序列化到 `browser.session_file`。下次运行自动加载，无需重复登录。
- **首次登录**：若检测到未登录（页面跳转到登录页），脚本会打开浏览器并
  **提示用户手动输入 Pinterest 用户名和密码**；登录成功后自动保存登录态。

浏览器相关配置（`crawler.browser`）字段：

| 字段 | 默认值 | 说明 |
|------|--------|------|
| `user_data_dir` | `""` | 浏览器用户数据目录（持久化登录态），建议设置如 `libraries/browser_profile` |
| `headless` | `false` | 是否无头（生产建议 `false` 以便手动登录） |
| `proxy` | `""` | 浏览器代理地址 |
| `session_file` | `""` | 登录态 cookie 保存文件（默认放在 user_data_dir 旁） |
| `login_timeout` | `180` | 等待用户手动登录超时(秒) |
| `page_load_wait` / `scroll_times` / `scroll_pause` | `3.0` / `5` / `1.5` | 页面加载等待、滚动加载次数与停顿 |

配置示例（浏览器后端 + 代理）：

```json
{
  "sites": [
    {
      "name": "pinterest_demo",
      "crawler_type": "pinterest_browser",
      "backend": "browser",
      "enabled": true,
      "urls": ["https://jp.pinterest.com/pin/1028087421172953769/"],
      "extra": {"locale": "jp"}
    }
  ],
  "crawler": {
    "browser": {
      "user_data_dir": "libraries/browser_profile",
      "proxy": "http://10.0.0.51:1072",
      "headless": false,
      "login_timeout": 180
    }
  }
}
```

# 使用方法

## 1. 环境准备（推荐虚拟环境）

```bash
# 在项目根目录创建并激活虚拟环境
python -m venv .venv
.venv\Scripts\activate        # Windows cmd
# 或 .venv\Scripts\Activate.ps1 (PowerShell)

# 安装依赖（国内源示例）
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt
# 核心依赖：pydantic==2.10.6, requests, websocket-client
```

> 注意：`.gitignore` 已忽略 `.venv/` 目录。

## 2. 配置

编辑 `config/core_config.json`（首次运行自动生成默认值，含 Pinterest 示例）：

- `library.root_dir`：图片库根目录（默认 `libraries/`）
- `library.dedupe_by_url` / `dedupe_by_hash`：防重复开关
- `crawler.output_library`：抓取结果写入的库名
- `comfyui.base_url`：ComfyUI 服务地址（默认 `http://127.0.0.1:8188`）
- `comfyui.workflow_path`：**图生图工作流 JSON 路径（必填，需自行准备）**
- `comfyui.load_image_node_title`：工作流中原图输入节点标题（默认 `Load Image`）

## 3. 运行完整流程（示例）

```python
from app.core.config.manager import CoreConfigManager
from app.core.pipeline import Pipeline

cfg = CoreConfigManager().config
pipeline = Pipeline(config=cfg)
result = pipeline.run()   # 抓取入库 -> 图生图
print(result.crawled_total, result.generated_total, result.errors)
```

也可分步调用：`pipeline.crawl_to_library()` 后再 `pipeline.generate_from_library(library)`。

## 4. 运行自动化测试

所有模块均提供单元测试（使用标准库 `unittest`，零额外依赖；也可 `pytest` 运行）：

```bash
# 方式一：unittest
.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v

# 方式二：pytest（需安装 pytest）
pytest tests/ -v
```

测试覆盖：图片库去重/持久化、Pinterest 解析、ComfyUI 工作流节点替换与端到端、
pipeline 全流程串联（均通过注入桩网络，不依赖真实外网与 ComfyUI 服务）。

# 真实联调（ComfyUI 图生图）

以本仓库提供的 `config/krea2i2i.json`（ComfyUI UI 保存格式工作流）为例，
已验证与真实 ComfyUI（`http://10.0.0.190:8188`）打通：上传原图 → 替换 LoadImage
节点 → 转换为 API 格式 → 提交 prompt → WebSocket 监听完成 → 通过 `/view` 下载生成图。

要点：
- **工作流格式兼容**：支持 ComfyUI UI 保存格式（`{"nodes": [...]}`）与 API 格式。
  UI 格式会在提交前自动转换；转换优先使用 ComfyUI 官方 `/graph/toapi` 接口，
  不可用时回退到基于 `/object_info` 的本地转换（可正确还原 widget 输入顺序）。
- **原图输入**：通过 `/upload/image` 上传本地图，再把返回的文件名写入 LoadImage
  节点（按 `type=="LoadImage"` 或配置的 `load_image_node_title` 定位）。
- **结果获取**：生成图通过 `/view` 接口下载（不依赖内联 base64），保存至
  `libraries/outputs/`（或调用时指定的 `output_dir`）。

最小联调代码：

```python
from app.core.config.manager import CoreConfigManager
from app.core.comfyui import ComfyUIClient

cfg = CoreConfigManager().config
client = ComfyUIClient(cfg.comfyui)
outs = client.img2img("assets/images/icon.png", output_dir="libraries/outputs")
print([(o["filename"], len(o["data"] or b"")) for o in outs])
```

# 许可证

此项目采用 MIT 许可证。有关详细信息，请参阅 [LICENSE](LICENSE) 文件。
## 参考

本项目基于：[PyDracula-flet](https://github.com/clarencejh/PyDracula-flet) 搭建
