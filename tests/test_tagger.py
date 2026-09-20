"""Wd14Tagger 的单元测试（注入 predictor/tag_names，无需真实模型与依赖）。"""
import unittest
from unittest import mock

from app.core.tagger import (
    Wd14Tagger,
    _CATEGORY_CHARACTER,
    _CATEGORY_GENERAL,
    _CATEGORY_RATING,
)


def _make_tagger(predictor, tag_names, **kwargs):
    """构造注入式 tagger。tag_names 全部视为 general 类（与生产代码一致）。"""
    return Wd14Tagger(predictor=predictor, tag_names=tag_names, **kwargs)


def _tagger_with_categories(predictor, names_with_cat, **kwargs):
    """构造指定每个标签类别的 tagger（category 是 0/4/9）。"""
    tag_names = [n for n, _ in names_with_cat]
    tagger = Wd14Tagger(predictor=predictor, tag_names=tag_names, **kwargs)
    tagger._tag_categories = [c for _, c in names_with_cat]
    return tagger


class TestWd14Tagger(unittest.TestCase):
    def test_tag_image_filters_and_sorts(self):
        # 置信度：solo=0.9, 1girl=0.5, dog=0.1（低于阈值应被过滤）
        preds = [0.5, 0.9, 0.1]
        tagger = _make_tagger(lambda arr: preds, ["1girl", "solo", "dog"])
        with mock.patch.object(tagger, "_preprocess", return_value=object()):
            tags = tagger.tag_image("fake.png")
        # 按置信度降序，dog 被阈值过滤
        self.assertEqual(tags, ["solo", "1girl"])

    def test_threshold_configurable(self):
        preds = [0.5, 0.9, 0.1]
        tagger = _make_tagger(lambda arr: preds,
                              ["1girl", "solo", "dog"],
                              threshold=0.05)
        with mock.patch.object(tagger, "_preprocess", return_value=object()):
            tags = tagger.tag_image("fake.png")
        self.assertEqual(tags, ["solo", "1girl", "dog"])

    def test_legacy_threshold_populates_both_new_thresholds(self):
        """仅传旧 threshold 时，应同时作为 general / character 阈值。"""
        t = Wd14Tagger(threshold=0.42)
        self.assertAlmostEqual(t.general_threshold, 0.42)
        self.assertAlmostEqual(t.character_threshold, 0.42)

    def test_separate_thresholds_override_legacy(self):
        """同时给 threshold + general/character 时，后者生效。"""
        t = Wd14Tagger(threshold=0.99,
                       general_threshold=0.30, character_threshold=0.25)
        self.assertAlmostEqual(t.general_threshold, 0.30)
        self.assertAlmostEqual(t.character_threshold, 0.25)

    def test_character_threshold_lower_surfaces_body_details(self):
        """character 阈值 < general 时，低置信度的人物特征也会输出。"""
        names = ["solo", "long_hair", "dog", "smile"]
        cats = [_CATEGORY_GENERAL, _CATEGORY_CHARACTER,
                _CATEGORY_GENERAL, _CATEGORY_CHARACTER]
        # solo=0.9, long_hair=0.28, dog=0.28, smile=0.28
        preds = [0.9, 0.28, 0.28, 0.28]
        tagger = _tagger_with_categories(
            lambda arr: preds, list(zip(names, cats)),
            general_threshold=0.35, character_threshold=0.25)
        with mock.patch.object(tagger, "_preprocess", return_value=object()):
            tags = tagger.tag_image("x.png")
        # solo (general 0.9) + long_hair/smile (character 0.28) 都应保留
        # dog (general 0.28) 被 general 阈值过滤
        self.assertIn("solo", tags)
        self.assertIn("long_hair", tags)
        self.assertIn("smile", tags)
        self.assertNotIn("dog", tags)

    def test_character_threshold_high_blocks_body_details(self):
        """character 阈值高时，即使高置信度的人物特征也会被过滤。"""
        names = ["solo", "long_hair"]
        cats = [_CATEGORY_GENERAL, _CATEGORY_CHARACTER]
        preds = [0.9, 0.8]
        tagger = _tagger_with_categories(
            lambda arr: preds, list(zip(names, cats)),
            general_threshold=0.35, character_threshold=0.85)
        with mock.patch.object(tagger, "_preprocess", return_value=object()):
            tags = tagger.tag_image("x.png")
        # solo (general 0.9 >= 0.35) 保留
        self.assertEqual(tags, ["solo"])

    def test_rating_tags_always_excluded(self):
        names = ["solo", "safe", "explicit"]
        cats = [_CATEGORY_GENERAL, _CATEGORY_RATING, _CATEGORY_RATING]
        preds = [0.9, 0.9, 0.9]
        tagger = _tagger_with_categories(
            lambda arr: preds, list(zip(names, cats)))
        with mock.patch.object(tagger, "_preprocess", return_value=object()):
            tags = tagger.tag_image("x.png")
        self.assertEqual(tags, ["solo"])

    def test_predictor_receives_preprocessed_array(self):
        seen = {}

        def predictor(arr):
            seen["arr"] = arr
            return [0.9, 0.1]

        tagger = _make_tagger(predictor, ["a", "b"])
        sentinel = object()
        with mock.patch.object(tagger, "_preprocess",
                               return_value=sentinel) as pre:
            tagger.tag_image("x.png")
        pre.assert_called_once_with("x.png")
        # predictor 收到的就是 _preprocess 的返回值
        self.assertIs(seen["arr"], sentinel)

    def test_model_loaded_only_once(self):
        calls = {"n": 0}

        def predictor(arr):
            calls["n"] += 1
            return [0.9, 0.1]

        tagger = _make_tagger(predictor, ["a", "b"])
        with mock.patch.object(tagger, "_preprocess", return_value=object()):
            tagger.tag_image("1.png")
            tagger.tag_image("2.png")
        self.assertEqual(calls["n"], 2)
        # 不会触发模型下载 / csv 加载（注入了 tag_names + predictor）
        self.assertFalse(tagger._tag_names == [])

    def test_tag_image_with_scores_returns_tuples(self):
        preds = [0.5, 0.9, 0.1]
        tagger = _make_tagger(lambda arr: preds, ["1girl", "solo", "dog"])
        with mock.patch.object(tagger, "_preprocess", return_value=object()):
            scored = tagger.tag_image_with_scores("fake.png")
        # 按置信度降序；dog 被阈值过滤；返回 (conf, name) 元组
        self.assertEqual(scored, [(0.9, "solo"), (0.5, "1girl")])

    def test_tag_image_with_scores_per_category(self):
        """tag_image_with_scores 也按类别阈值过滤。"""
        names = ["solo", "long_hair", "dog", "smile"]
        cats = [_CATEGORY_GENERAL, _CATEGORY_CHARACTER,
                _CATEGORY_GENERAL, _CATEGORY_CHARACTER]
        preds = [0.9, 0.28, 0.28, 0.28]
        tagger = _tagger_with_categories(
            lambda arr: preds, list(zip(names, cats)),
            general_threshold=0.35, character_threshold=0.25)
        with mock.patch.object(tagger, "_preprocess", return_value=object()):
            scored = tagger.tag_image_with_scores("x.png")
        # dog (general 0.28 < 0.35) 被过滤；其它三项保留
        names_kept = [n for _, n in scored]
        self.assertEqual(set(names_kept), {"solo", "long_hair", "smile"})

    def test_tag_image_with_scores_max_items(self):
        preds = [0.9, 0.8, 0.7, 0.6]
        tagger = _make_tagger(
            lambda arr: preds, ["a", "b", "c", "d"], threshold=0.1)
        with mock.patch.object(tagger, "_preprocess", return_value=object()):
            scored = tagger.tag_image_with_scores("x.png", max_items=2)
        self.assertEqual(scored, [(0.9, "a"), (0.8, "b")])

    def test_tag_image_backward_compat_returns_names_only(self):
        """tag_image 仍只返回 name 列表（向后兼容）。"""
        preds = [0.5, 0.9, 0.1]
        tagger = _make_tagger(lambda arr: preds, ["1girl", "solo", "dog"])
        with mock.patch.object(tagger, "_preprocess", return_value=object()):
            tags = tagger.tag_image("fake.png")
        self.assertEqual(tags, ["solo", "1girl"])


if __name__ == "__main__":
    unittest.main()
