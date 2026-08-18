"""
app.core 业务核心模块包。

本包实现与 UI 解耦的纯业务逻辑，包含三大独立模块：
- image_library: 本地图片库管理（含按 URL 去重的防重复机制）
- crawler:       图片网站批量抓取（支持多网站配置，一期实现 Pinterest）
- comfyui:      调用 ComfyUI 工作流完成图生图
- pipeline:     将上述模块编排为完整业务流程

所有模块均不依赖 flet/UI，可独立进行单元测试。
"""
