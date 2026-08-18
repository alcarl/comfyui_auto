"""ComfyUI 客户端：封装与 ComfyUI 服务端的交互。

交互流程（图生图）：
1. 加载工作流 JSON（本地文件）。
2. 将本地原图上传到 ComfyUI（/upload/image），得到服务端 filename。
3. 找到工作流中的 LoadImage 节点，将其 image 字段替换为上传后的 filename。
4. 提交 prompt（/prompt），携带 client_id。
5. 通过 WebSocket（/ws?clientId=...）或轮询 /history 等待执行完成。
6. 从 history 中解析 SaveImage 节点的输出图片（base64 或文件），返回图片字节。

为支持单元测试，HTTP / WS 行为通过 ``transport`` 抽象注入。
"""
from __future__ import annotations

import base64
import json
import os
import uuid
from typing import Any, Callable, Dict, List, Optional

from ..config.models import ComfyUIConfig


class ComfyUITransport:
    """网络传输层抽象，便于替换为测试桩。

    默认实现使用 requests + 简单的 history 轮询。真实 WS 监听在
    ComfyUIClient 中通过 injectable 的 ``ws_run`` 执行。
    """

    def __init__(self, base_url: str = "http://127.0.0.1:8188", timeout: int = 300):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    # ---- 可被子类/测试覆盖的方法 ----
    def post_prompt(self, prompt: dict, client_id: str) -> dict:
        import requests
        resp = requests.post(f"{self.base_url}/prompt",
                             json={"prompt": prompt, "client_id": client_id},
                             timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def upload_image(self, image_path: str,
                     image_data: Optional[bytes] = None,
                     name: str = "image.png") -> dict:
        import requests
        if image_data is None:
            with open(image_path, "rb") as f:
                image_data = f.read()
        files = {"image": (name, image_data, "image/png")}
        data = {"overwrite": "true"}
        resp = requests.post(f"{self.base_url}/upload/image",
                             files=files, data=data, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def get_history(self, prompt_id: str) -> dict:
        import requests
        resp = requests.get(f"{self.base_url}/history/{prompt_id}",
                            timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def get_image(self, filename: str, subfolder: str = "",
                  img_type: str = "output") -> bytes:
        """从 ComfyUI /view 接口下载生成的图片。"""
        import requests
        params = {"filename": filename, "type": img_type}
        if subfolder:
            params["subfolder"] = subfolder
        resp = requests.get(f"{self.base_url}/view", params=params,
                            timeout=self.timeout)
        resp.raise_for_status()
        return resp.content

    def to_api_format(self, ui_workflow: dict) -> dict:
        """将 UI 保存格式的工作流转换为 /prompt 所需的 API 格式。

        优先使用 ComfyUI 官方 /graph/toapi 接口（最可靠）；该接口不可用
        时回退到基于 /object_info 的本地转换（能正确处理 widget 输入顺序）。
        """
        import requests
        try:
            resp = requests.post(f"{self.base_url}/graph/toapi",
                                 json=ui_workflow, timeout=self.timeout)
            if resp.ok:
                return resp.json()
        except Exception:  # noqa: BLE001
            pass
        # 本地回退：拉取所需节点的 object_info 以还原 widget 输入顺序
        try:
            types = {n.get("type") for n in ui_workflow.get("nodes", [])}
            object_info = {}
            for t in types:
                r = requests.get(f"{self.base_url}/object_info/{t}", timeout=self.timeout)
                if r.ok:
                    object_info[t] = r.json().get(t, {})
            return _local_to_api_format(ui_workflow, object_info)
        except Exception:  # noqa: BLE001
            return _local_to_api_format(ui_workflow, {})


class ComfyUIClient:
    """ComfyUI 图生图客户端。"""

    def __init__(self, config: ComfyUIConfig, transport: Optional[ComfyUITransport] = None):
        self.config = config
        self.transport = transport or ComfyUITransport(
            base_url=config.base_url, timeout=config.timeout)
        # WebSocket 监听函数：可注入（测试用）。None 表示使用默认实现。
        self.ws_run = None

    # ------------------------------------------------------------------ #
    # 工作流加载与修改（纯逻辑，可独立测试）
    # ------------------------------------------------------------------ #
    def load_workflow(self, workflow_path: Optional[str] = None) -> dict:
        path = workflow_path or self.config.workflow_path
        if not path or not os.path.exists(path):
            raise FileNotFoundError(f"工作流文件不存在: {path}")
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    @staticmethod
    def _normalize_workflow(wf: dict) -> dict:
        """将不同格式的工作流统一为 {node_id: {inputs, ...}} 结构。

        兼容两种格式：
        - API 格式：{ "3": {"inputs": {...}, "class_type": "..."} }
        - 带 ui 的保存格式：{ "nodes": [...] }
        """
        if "nodes" in wf:
            nodes = {}
            for node in wf["nodes"]:
                nid = str(node.get("id"))
                nodes[nid] = {
                    "inputs": node.get("inputs", {}),
                    "class_type": node.get("type", ""),
                    "_title": node.get("title", ""),
                }
            return nodes
        return wf

    def set_input_image(self, wf: dict, filename: str) -> dict:
        """将工作流中 LoadImage 节点的图片替换为上传后的 filename。

        定位策略（按优先级）：
        1. 节点 title 等于配置的 load_image_node_title（默认 'Load Image'）。
        2. 节点 type/class_type 为 'LoadImage'（兼容无 title 的工作流，如 krea2i2i.json）。
        """
        nodes = self._normalize_workflow(wf)
        target_title = self.config.load_image_node_title
        target_id = None
        # 优先按 title 匹配
        for nid, node in nodes.items():
            if target_title and node.get("_title") == target_title:
                target_id = nid
                break
        # 回退按 type / class_type
        if target_id is None:
            for nid, node in nodes.items():
                if node.get("class_type") in ("LoadImage", "loadimage"):
                    target_id = nid
                    break
        if target_id is None:
            raise ValueError("工作流中未找到 LoadImage 节点")

        # 在原始工作流结构上设置 image 输入
        self._set_node_input(wf, target_id, "image", filename)
        return wf

    @staticmethod
    def _set_node_input(wf: dict, node_id: str, key: str, value: Any) -> None:
        if "nodes" in wf:
            for node in wf["nodes"]:
                if str(node.get("id")) == str(node_id):
                    # UI 格式：图片名在 widgets_values[0]
                    wv = node.get("widgets_values")
                    if isinstance(wv, list) and wv:
                        wv[0] = value
                    # inputs 可能是列表（ComfyUI UI 保存格式）或字典（API 格式）
                    inputs = node.get("inputs")
                    if isinstance(inputs, list):
                        # 找到 name == key 的输入项并更新其 value
                        found = False
                        for item in inputs:
                            if item.get("name") == key:
                                item["value"] = value
                                found = True
                                break
                        if not found:
                            inputs.append({"name": key, "type": "STRING",
                                           "value": value})
                    elif isinstance(inputs, dict):
                        inputs[key] = value
                    else:
                        node["inputs"] = {key: value}
                    return
        else:
            wf[str(node_id)]["inputs"][key] = value

    # ------------------------------------------------------------------ #
    # 端到端图生图
    # ------------------------------------------------------------------ #
    def img2img(self, image_path: str,
                workflow_path: Optional[str] = None,
                output_dir: Optional[str] = None) -> List[dict]:
        """对单张本地图片执行图生图，返回生成的图片信息列表。

        :param image_path: 本地原图路径
        :param workflow_path: 工作流路径（可选，覆盖配置）
        :param output_dir: 生成图片保存目录（可选）
        :return: [{"filename":..., "data": b"...", "node_id":...}, ...]
        """
        # 1. 上传原图
        upload_resp = self.transport.upload_image(image_path)
        uploaded_name = upload_resp.get("name") or os.path.basename(image_path)

        # 2. 加载并修改工作流
        wf = self.load_workflow(workflow_path)
        wf = self.set_input_image(wf, uploaded_name)

        # 3. 转换为 API 格式（UI 保存格式需转换后才可被 /prompt 接受）
        if "nodes" in wf:
            wf = self.transport.to_api_format(wf)

        # 4. 提交 prompt
        client_id = self.config.client_id or f"client-{uuid.uuid4().hex[:8]}"
        prompt_resp = self.transport.post_prompt(wf, client_id)
        prompt_id = prompt_resp.get("prompt_id")
        if not prompt_id:
            raise RuntimeError(f"提交 prompt 失败: {prompt_resp}")

        # 4. 等待并获取结果
        history = self._wait_history(prompt_id)
        outputs = self._extract_outputs(history, prompt_id)

        # 5. 落盘（可选）
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
            for i, out in enumerate(outputs):
                if out.get("data"):
                    fname = out.get("filename") or f"output_{i}.png"
                    with open(os.path.join(output_dir, fname), "wb") as f:
                        f.write(out["data"])
        return outputs

    def _wait_history(self, prompt_id: str) -> dict:
        """等待该 prompt_id 完成：优先用 WebSocket 监听，超时或不可用时回退轮询。"""
        done = self._wait_via_ws(prompt_id)
        if done:
            return self.transport.get_history(prompt_id)
        # 回退：轮询 history
        import time
        deadline = time.time() + self.config.timeout
        while time.time() < deadline:
            hist = self.transport.get_history(prompt_id)
            if prompt_id in hist:
                return hist
            time.sleep(1.0)
        raise TimeoutError(f"等待 ComfyUI 出图超时: {prompt_id}")

    def _wait_via_ws(self, prompt_id: str) -> bool:
        """通过 WebSocket 监听执行完成事件。

        优先使用注入的 self.ws_run（测试），否则使用默认 _default_ws_run。
        失败/超时返回 False，由调用方回退轮询。
        """
        try:
            runner = self.ws_run or _default_ws_run
            return bool(runner(self.config.base_url, self.config.client_id, prompt_id,
                               timeout=self.config.timeout))
        except Exception:  # noqa: BLE001
            return False

    def _extract_outputs(self, history: dict, prompt_id: str) -> List[dict]:
        """从 history 结果中提取 SaveImage 节点的图片字节。

        生成图片通常不内联 base64，需通过 /view 接口下载（transport.get_image）。
        """
        results: List[dict] = []
        entry = history.get(prompt_id, {})
        outputs = entry.get("outputs", {})
        for node_id, out in outputs.items():
            images = out.get("images", [])
            for img in images:
                item: Dict[str, Any] = {
                    "node_id": node_id,
                    "filename": img.get("filename"),
                    "subfolder": img.get("subfolder", ""),
                    "type": img.get("type", "output"),
                    "data": None,
                }
                # 若内联了 base64（部分部署），直接解码
                if img.get("data"):
                    item["data"] = base64.b64decode(img["data"])
                # 否则通过 /view 下载真实图片
                elif item["filename"]:
                    try:
                        item["data"] = self.transport.get_image(
                            item["filename"], item["subfolder"], item["type"])
                    except Exception as e:  # noqa: BLE001
                        item["data"] = None
                        item["error"] = str(e)
                results.append(item)
        return results


def _default_ws_run(base_url: str, client_id: str, prompt_id: str,
                    timeout: int = 300) -> bool:
    """默认 WebSocket 监听：等待该 prompt_id 执行完成。

    使用 websocket-client 库。仅监听与 prompt_id 相关的执行完成事件。
    返回 True 表示收到完成事件，False 表示超时或库不可用。
    """
    try:
        import websocket  # websocket-client
    except ImportError:
        return False
    import time
    ws_url = base_url.replace("http://", "ws://").replace("https://", "wss://")
    ws_url = f"{ws_url}/ws?clientId={client_id}"
    deadline = time.time() + timeout
    try:
        ws = websocket.create_connection(ws_url, timeout=timeout)
    except Exception:  # noqa: BLE001
        return False
    try:
        while time.time() < deadline:
            try:
                ws.settimeout(max(1, int(deadline - time.time())))
                msg = ws.recv()
            except Exception:  # noqa: BLE001
                return False
            if not msg:
                continue
            try:
                data = json.loads(msg)
            except (ValueError, TypeError):
                continue
            if data.get("type") == "executing":
                exec_data = data.get("data", {})
                # 节点为 None 表示该 prompt 执行结束
                if exec_data.get("prompt_id") == prompt_id and exec_data.get("node") is None:
                    return True
        return False
    finally:
        try:
            ws.close()
        except Exception:  # noqa: BLE001
            pass


def _local_to_api_format(ui_wf: dict, object_info: dict) -> dict:
    """本地回退：将 ComfyUI UI 保存格式工作流转为 API 格式。

    UI 格式的 ``inputs`` 列表通常只包含*连线*输入，所有 widget 输入的值折叠在
    ``widgets_values`` 中，但顺序信息隐藏在节点类型定义里。因此本函数借助
    ``object_info[<type>]["input"]`` 还原输入顺序：
      - 连线输入（link 非 null）-> ["<src_id>", slot]
      - 其余输入（按 object_info 的顺序）依次从 widgets_values 取值
    若无 object_info 则退化为仅处理连线输入。
    """
    nodes = ui_wf.get("nodes", [])
    # 建立 link_id -> (node_id, output_index)
    link_map: dict = {}
    for node in nodes:
        for oi, out in enumerate(node.get("outputs", [])):
            for lid in (out.get("links") or []):
                link_map[lid] = (str(node.get("id")), oi)

    api: dict = {}
    for node in nodes:
        ntype = node.get("type", "")
        widgets = node.get("widgets_values", [])

        # 连线输入映射
        linked: dict = {}
        for inp in node.get("inputs", []):
            link = inp.get("link")
            if link is not None and link in link_map:
                src_id, slot = link_map[link]
                linked[inp["name"]] = [src_id, slot]

        node_inputs = dict(linked)

        # 通过 object_info 还原 widget 输入顺序并填值
        schema = (object_info or {}).get(ntype, {}).get("input", {})
        required = list(schema.get("required", {}).keys())
        optional = list(schema.get("optional", {}).keys())
        ordered_names = required + optional

        wv_index = 0
        for name in ordered_names:
            if name in node_inputs:
                continue  # 已被连线输入占用
            if wv_index < len(widgets):
                node_inputs[name] = widgets[wv_index]
                wv_index += 1
            else:
                # 无对应 widget 值时放弃（保留默认）
                break

        api[str(node.get("id"))] = {
            "class_type": ntype,
            "inputs": node_inputs,
        }
    return api
