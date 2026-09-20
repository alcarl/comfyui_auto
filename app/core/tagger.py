"""WD14 反推提示词（tagger）：对图片推理 booru 风格标签。

实现方式（本地 ONNX 推理，不依赖 ComfyUI 插件）：
- 模型使用 SmilingWolf 的 wd-v1-4 系列标签模型（默认
  ``wd-eva02-large-tagger-v3``，HuggingFace 上 ``model.onnx`` +
  ``selected_tags.csv``）。
- 首次使用时通过 ``huggingface_hub`` 自动下载并缓存到本地目录
  （默认 ``libraries/tagger_model``，已被 gitignore 忽略）；
  若目录中已手动放置 ``model.onnx`` / ``selected_tags.csv`` 则直接使用。
- 重依赖（onnxruntime / Pillow / numpy / huggingface_hub）全部懒导入，
  未安装时仅在调用 ``tag_image`` 才报错，不影响程序其他功能。

为可测试：推理函数通过 ``predictor`` 注入，测试时传桩函数，无需安装
onnxruntime，也不触发模型下载。
"""
from __future__ import annotations

import csv
import os
import threading
from typing import Any, Callable, List, Optional, Tuple

DEFAULT_REPO_ID = "SmilingWolf/wd-eva02-large-tagger-v3"
DEFAULT_MODEL_DIR = os.path.join("libraries", "tagger_model")

# selected_tags.csv 中 category 字段含义：0=general, 4=character, 9=rating
_CATEGORY_GENERAL = 0
_CATEGORY_CHARACTER = 4
_CATEGORY_RATING = 9

# SmilingWolf 官方的默认阈值：character 阈值远高于 general，是为了
# 减少误把 general 物体识别成 character。这里我们故意把 character 默认
# 拉低到与 general 相同 (0.35)，让用户能拿到 long_hair/blue_eyes/blush
# 这类人体特征标签；不想要噪声时可以通过参数再调高。
DEFAULT_GENERAL_THRESHOLD = 0.35
DEFAULT_CHARACTER_THRESHOLD = 0.35

# 置信度展示与日志的辅助常量
# tag_image_with_scores 返回的元组是 (confidence, name)，confidence 是 float
CONFIDENCE_TAG_SEPARATOR = " "  # tags_text 中 标签名与置信度的拼接分隔符


class Wd14Tagger:
    """对单张本地图片反推提示词。

    用法::

        tagger = Wd14Tagger()                  # 默认模型/阈值
        tags = tagger.tag_image("outputs/x.png")   # -> ["1girl", "solo", ...]

    :param model_dir: 模型缓存目录（model.onnx + selected_tags.csv）。
    :param repo_id: HuggingFace 模型仓库（本地已有模型文件时不会下载）。
    :param general_threshold: 通用标签（场景/物件/风格等）的置信度阈值。
        默认 0.35。
    :param character_threshold: 人物特征标签（hair/eyes/body 等）的置信度阈值。
        默认 0.35（比 SmilingWolf 官方默认 0.85 低，目的是默认就能输出
        long_hair/blue_eyes/blush 等人体细节）。
    :param threshold: 旧版统一阈值（向后兼容），传入时同时设置 general 与
        character；与 ``general_threshold`` / ``character_threshold`` 同时
        给出时后者生效。
    :param predictor: 可注入的推理函数，签名
        ``predictor(arr: numpy.ndarray) -> numpy.ndarray``，
        输入 (1, H, W, 3) float32，输出长度为标签数的置信度数组。
    :param tag_names: 注入 predictor 时随附的标签名列表（测试用），
        长度需与 predictor 输出一致；全部视为 general 类。
    """

    def __init__(self, model_dir: Optional[str] = None,
                 repo_id: str = DEFAULT_REPO_ID,
                 general_threshold: Optional[float] = None,
                 character_threshold: Optional[float] = None,
                 threshold: Optional[float] = None,
                 predictor: Optional[Callable[[Any], Any]] = None,
                 tag_names: Optional[List[str]] = None):
        self.model_dir = os.path.abspath(model_dir or DEFAULT_MODEL_DIR)
        self.repo_id = repo_id
        # 兼容旧字段：threshold 作为 general 与 character 的共同初值
        legacy = (threshold if (threshold is not None
                                and general_threshold is None
                                and character_threshold is None)
                  else None)
        self.general_threshold = (general_threshold if general_threshold
                                  is not None else
                                  (legacy if legacy is not None
                                   else DEFAULT_GENERAL_THRESHOLD))
        self.character_threshold = (character_threshold
                                    if character_threshold is not None
                                    else (legacy if legacy is not None
                                          else DEFAULT_CHARACTER_THRESHOLD))
        self._predictor = predictor
        self._lock = threading.Lock()
        # 懒加载状态
        self._session: Any = None
        self._active_provider: str = ""  # 实际生效的 EP（如 CUDAExecutionProvider）
        self._tag_names: List[str] = list(tag_names) if tag_names else []
        self._tag_categories: List[int] = [
            _CATEGORY_GENERAL] * len(self._tag_names)

    # ------------------------------------------------------------------ #
    # 公开接口
    # ------------------------------------------------------------------ #
    def tag_image(self, image_path: str) -> List[str]:
        """对一张图片反推提示词，按置信度降序返回。

        :raises RuntimeError: 依赖未安装 / 模型下载失败 / 图片无法读取
        """
        scored = self.tag_image_with_scores(image_path)
        return [name for _, name in scored]

    def tag_image_with_scores(
            self, image_path: str,
            max_items: Optional[int] = None) -> List[Tuple[float, str]]:
        """对一张图片反推提示词，按置信度降序返回 ``(confidence, name)`` 元组。

        与 ``tag_image`` 的区别：本接口附带每个标签的原始置信度，便于 UI
        排查"为什么极详细档还是没出人体特征"——到底是阈值过滤掉了，还是
        模型本身没给人体特征打出高置信度。

        :param max_items: 截断返回条数；None 不限（仅按阈值过滤）。
        :raises RuntimeError: 依赖未安装 / 模型下载失败 / 图片无法读取
        """
        arr = self._preprocess(image_path)
        with self._lock:
            self._ensure_model()
            preds = self._run_predictor(arr)
        scored = self._filter_tags(preds)
        if max_items is not None:
            scored = scored[:max_items]
        return scored

    @property
    def active_provider(self) -> str:
        """当前实际生效的推理提供者（如 CUDAExecutionProvider / CPU）。

        模型懒加载完成前为空字符串。
        """
        return self._active_provider

    # ------------------------------------------------------------------ #
    # 内部实现
    # ------------------------------------------------------------------ #
    def _ensure_model(self) -> None:
        """懒加载 ONNX 会话与标签表（线程安全，调用方需持锁）。"""
        if self._tag_names and (self._predictor is not None
                                or self._session is not None):
            return
        if not self._tag_names:
            self._load_tag_csv(self._resolve_csv_path())
        if self._predictor is None and self._session is None:
            self._session = self._create_session(self._resolve_model_path())

    def _resolve_model_path(self) -> str:
        """返回 model.onnx 路径：本地有则用，没有则从 HuggingFace 下载。"""
        local = os.path.join(self.model_dir, "model.onnx")
        if os.path.isfile(local):
            return local
        return self._download("model.onnx")

    def _resolve_csv_path(self) -> str:
        local = os.path.join(self.model_dir, "selected_tags.csv")
        if os.path.isfile(local):
            return local
        return self._download("selected_tags.csv")

    def _download(self, filename: str) -> str:
        """从 HuggingFace 下载模型文件到缓存目录。"""
        try:
            from huggingface_hub import hf_hub_download  # 懒导入
        except ImportError as e:
            raise RuntimeError(
                "未安装 huggingface_hub，无法自动下载 WD14 模型。"
                "请 pip install huggingface_hub，或手动将 model.onnx 与 "
                "selected_tags.csv 放入 "
                f"{self.model_dir}") from e
        os.makedirs(self.model_dir, exist_ok=True)
        try:
            return hf_hub_download(
                repo_id=self.repo_id, filename=filename,
                local_dir=self.model_dir)
        except Exception as e:  # noqa: BLE001
            raise RuntimeError(
                f"下载 {self.repo_id}/{filename} 失败: {e}") from e

    def _load_tag_csv(self, csv_path: str) -> None:
        names: List[str] = []
        categories: List[int] = []
        with open(csv_path, "r", encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                names.append(row["name"])
                categories.append(int(row["category"]))
        if not names:
            raise RuntimeError(f"标签表为空: {csv_path}")
        self._tag_names = names
        self._tag_categories = categories

    def _create_session(self, model_path: str) -> Any:
        try:
            import onnxruntime as ort  # 懒导入
        except ImportError as e:
            raise RuntimeError(
                "未安装 onnxruntime，无法运行 WD14 反推。"
                "请 pip install onnxruntime") from e
        try:
            # 自动选最优执行提供者：GPU 优先（CUDA / DirectML），回退 CPU。
            # CPU 版 onnxruntime 只暴露 CPUExecutionProvider，行为不变；
            # 装 onnxruntime-gpu 或 onnxruntime-directml 后自动切换到 GPU。
            providers = self._select_providers(ort)
            session = ort.InferenceSession(model_path, providers=providers)
            # 记录实际生效的 provider（如 CUDAExecutionProvider），供 UI 显示
            self._active_provider = session.get_providers()[0]
            return session
        except Exception as e:  # noqa: BLE001
            raise RuntimeError(f"加载 WD14 模型失败 {model_path}: {e}") from e

    @staticmethod
    def _select_providers(ort: Any) -> List[str]:
        """按优先级返回可用的执行提供者列表（GPU 优先，CPU 兜底）。

        CUDA（NVIDIA + onnxruntime-gpu）与 DML（任意 DX12 GPU +
        onnxruntime-directml）都是 GPU 加速；两者都装了时 CUDA 优先。
        """
        available = set(ort.get_available_providers())
        preferred: List[str] = []
        for ep in ("CUDAExecutionProvider", "DmlExecutionProvider"):
            if ep in available:
                preferred.append(ep)
        # CPU 必须在列表末尾兜底：GPU EP 初始化失败时 ORT 可回退
        preferred.append("CPUExecutionProvider")
        return preferred

    def _preprocess(self, image_path: str) -> Any:
        """读取图片并转为模型输入张量 (1, H, W, 3) float32，范围 [-1, 1]。"""
        try:
            import numpy as np  # 懒导入
            from PIL import Image  # 懒导入
        except ImportError as e:
            raise RuntimeError(
                "未安装 numpy / Pillow，无法处理图片。"
                "请 pip install numpy pillow") from e
        try:
            img = Image.open(image_path)
        except Exception as e:  # noqa: BLE001
            raise RuntimeError(f"无法读取图片 {image_path}: {e}") from e
        # 透明背景合成到白底，避免透明区域变黑影响识别
        img = img.convert("RGBA")
        bg = Image.new("RGBA", img.size, (255, 255, 255, 255))
        img = Image.alpha_composite(bg, img).convert("RGB")
        # 输入尺寸：优先从模型输入 shape 动态获取，取不到用 448
        size = self._input_size() or (448, 448)
        img = img.resize(size)
        # 关键：SmilingWolf WD14 ONNX 模型期望 [0, 255] float32（NHWC），
        # 不要做 [-1,1] 归一化——归一化会让输入分布偏离训练分布，输出
        # 退化成 monochrome/greyscale/comic 这类"万能"高频标签，
        # 且所有图片结果趋同（这正是"全部图反推出同一组标签"的根因）。
        arr = np.asarray(img, dtype=np.float32)
        return arr[np.newaxis, :]

    def _input_size(self) -> Optional[tuple]:
        """从 ONNX 会话输入 shape 提取 (height, width)，失败返回 None。"""
        if self._predictor is not None or self._session is None:
            return None
        try:
            shape = self._session.get_inputs()[0].shape  # e.g. [1,448,448,3]
            h, w = int(shape[1]), int(shape[2])
            if h > 0 and w > 0:
                return (h, w)
        except Exception:  # noqa: BLE001
            pass
        return None

    def _run_predictor(self, arr: Any) -> Any:
        """执行推理：优先注入的 predictor，否则用 ONNX 会话。"""
        if self._predictor is not None:
            return self._predictor(arr)
        input_name = self._session.get_inputs()[0].name
        outputs = self._session.run(None, {input_name: arr})
        return outputs[0]

    def _filter_tags(self, preds: Any) -> List[Tuple[float, str]]:
        """按类别阈值过滤并排除 rating 类标签，按置信度降序返回。

        返回值：``[(confidence, name), ...]``，confidence 是 float。

        - rating (cat=9)：永远排除（与筛选无关）
        - general (cat=0)：用 ``general_threshold``
        - character (cat=4)：用 ``character_threshold``
        - 其它类别：使用 ``general_threshold``（保守处理）
        """
        try:
            confs = list(preds[0]) if getattr(preds, "ndim", 1) == 2 else list(preds)
        except TypeError:
            confs = list(preds)
        if len(confs) != len(self._tag_names):
            raise RuntimeError(
                f"模型输出维度 {len(confs)} 与标签数 {len(self._tag_names)} 不一致")
        scored: List[Tuple[float, str]] = []
        for name, cat, conf in zip(self._tag_names, self._tag_categories, confs):
            if cat == _CATEGORY_RATING:  # rating 标签对筛选无意义，排除
                continue
            try:
                c = float(conf)
            except (TypeError, ValueError):
                continue
            th = (self.character_threshold if cat == _CATEGORY_CHARACTER
                  else self.general_threshold)
            if c >= th:
                scored.append((c, name))
        scored.sort(reverse=True)
        return scored
