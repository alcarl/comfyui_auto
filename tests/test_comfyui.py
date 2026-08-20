"""ComfyUI 模块测试：验证工作流节点替换与输出解析（注入桩传输层）。"""
import base64
import json
import os
import tempfile
import unittest
from unittest.mock import MagicMock

from app.core.comfyui import ComfyUIClient
from app.core.config.models import ComfyUIConfig

API_WORKFLOW = {
    "10": {"class_type": "LoadImage", "inputs": {"image": "", "upload": "image"}},
    "20": {"class_type": "SaveImage", "inputs": {"images": ["10", 0]}},
}

UI_WORKFLOW = {
    "nodes": [
        {"id": 10, "type": "LoadImage", "title": "Load Image",
         "inputs": {"image": ""}, "widgets_values": ["old.png", "upload"]},
        {"id": 20, "type": "SaveImage", "title": "Save Image", "inputs": {}},
    ]
}


class StubTransport:
    """测试桩传输层，模拟 ComfyUI 服务端返回。"""
    def __init__(self):
        self.uploaded = None
        self.posted_prompt = None

    def upload_image(self, image_path, image_data=None, name="image.png"):
        self.uploaded = name
        return {"name": "uploaded_abc.png"}

    def post_prompt(self, prompt, client_id):
        self.posted_prompt = prompt
        return {"prompt_id": "pid-123"}

    def get_history(self, prompt_id):
        png = base64.b64encode(b"\x89PNG fake").decode()
        return {prompt_id: {"outputs": {
            "20": {"images": [{"filename": "out.png", "subfolder": "",
                               "type": "output", "data": png}]}}}}

    def to_api_format(self, ui_workflow):
        return ui_workflow

    def get_object_info(self, node_type):
        return {}


class TestWorkflowNodeReplacement(unittest.TestCase):
    def test_set_input_image_api_format(self):
        cfg = ComfyUIConfig(workflow_path="")
        client = ComfyUIClient(cfg)
        wf = json.loads(json.dumps(API_WORKFLOW))
        client.set_input_image(wf, "uploaded_abc.png")
        self.assertEqual(wf["10"]["inputs"]["image"], "uploaded_abc.png")

    def test_set_input_image_ui_format_by_title(self):
        cfg = ComfyUIConfig(workflow_path="", load_image_node_title="Load Image")
        client = ComfyUIClient(cfg)
        wf = json.loads(json.dumps(UI_WORKFLOW))
        client.set_input_image(wf, "uploaded_abc.png")
        load_node = next(n for n in wf["nodes"] if n["id"] == 10)
        self.assertEqual(load_node["inputs"]["image"], "uploaded_abc.png")
        # UI 格式图片名同时写入 widgets_values[0]（真实 ComfyUI 以此为准）
        self.assertEqual(load_node["widgets_values"][0], "uploaded_abc.png")

    def test_normalize_workflow(self):
        self.assertEqual(ComfyUIClient._normalize_workflow(API_WORKFLOW)["10"]["class_type"],
                         "LoadImage")
        self.assertEqual(ComfyUIClient._normalize_workflow(UI_WORKFLOW)["10"]["class_type"],
                         "LoadImage")


class TestEndToEndImg2Img(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.img_path = os.path.join(self.tmp, "src.png")
        with open(self.img_path, "wb") as f:
            f.write(b"\x89PNG source")

    def test_img2img_uses_uploaded_name_and_saves_output(self):
        cfg = ComfyUIConfig(workflow_path="")
        client = ComfyUIClient(cfg, transport=StubTransport())
        out_dir = os.path.join(self.tmp, "out")

        # 用 API 格式工作流文件
        wf_path = os.path.join(self.tmp, "wf.json")
        with open(wf_path, "w") as f:
            json.dump(API_WORKFLOW, f)
        cfg.workflow_path = wf_path

        outputs = client.img2img(self.img_path, output_dir=out_dir)
        self.assertEqual(len(outputs), 1)
        # 输出文件名应与输入图片保持一致（输入是 src.png）
        self.assertEqual(outputs[0]["filename"], "src.png")
        self.assertEqual(outputs[0]["data"], b"\x89PNG fake")
        # 断言上传文件名被回填进 prompt 的 LoadImage 节点
        self.assertEqual(client.transport.posted_prompt["10"]["inputs"]["image"],
                         "uploaded_abc.png")
        # 断言输出已落盘，且文件名与输入一致
        self.assertTrue(os.path.exists(os.path.join(out_dir, "src.png")))

    def test_img2img_skips_when_output_exists(self):
        cfg = ComfyUIConfig(workflow_path="")
        client = ComfyUIClient(cfg, transport=StubTransport())
        out_dir = os.path.join(self.tmp, "out_existing")
        os.makedirs(out_dir, exist_ok=True)
        # 预置一个与输入同名的输出文件，模拟“已生成过”
        with open(os.path.join(out_dir, "src.png"), "wb") as f:
            f.write(b"\x89PNG old")
        # 用 API 格式工作流文件
        wf_path = os.path.join(self.tmp, "wf_existing.json")
        with open(wf_path, "w") as f:
            json.dump(API_WORKFLOW, f)
        cfg.workflow_path = wf_path

        # 输出已存在，应跳过（不提交 prompt，返回空列表）
        outputs = client.img2img(self.img_path, output_dir=out_dir)
        self.assertEqual(outputs, [])
        self.assertIsNone(client.transport.posted_prompt)  # 未提交过 prompt


if __name__ == "__main__":
    unittest.main()
