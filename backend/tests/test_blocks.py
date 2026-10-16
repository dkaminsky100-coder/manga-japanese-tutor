import numpy as np

from app.pipeline import runner
from app.pipeline.blocks import drop_containers, iou, merge_detections, scale_block
from app.pipeline.detect import HORIZONTAL_ASPECT, TextBlock, decode_blocks


def blk(x1, y1, x2, y2, conf=0.9):
    return TextBlock(x1, y1, x2, y2, True, conf)


def test_iou():
    assert iou((0, 0, 10, 10), (0, 0, 10, 10)) == 1.0
    assert iou((0, 0, 10, 10), (20, 20, 30, 30)) == 0.0
    assert abs(iou((0, 0, 10, 10), (5, 0, 15, 10)) - 1 / 3) < 1e-9


def test_scale_block_maps_between_resolutions():
    b = scale_block(blk(100, 200, 300, 400), 0.5)
    assert b.bbox == (50, 100, 150, 200) and b.vertical and b.conf == 0.9


def test_merge_keeps_both_passes_distinct_blocks_and_dedupes_overlaps():
    a = [blk(0, 0, 100, 100, 0.8)]
    b = [blk(2, 2, 101, 99, 0.95), blk(200, 200, 260, 300, 0.7)]  # first overlaps a; second is new
    merged = merge_detections(a, b)
    assert len(merged) == 2
    assert blk(2, 2, 101, 99).bbox in [m.bbox for m in merged]  # the more confident duplicate wins
    assert (200, 200, 260, 300) in [m.bbox for m in merged]


def test_container_around_two_blocks_is_dropped():
    big = blk(0, 0, 300, 400)  # swallows two bubbles
    a, b = blk(10, 10, 100, 120), blk(150, 200, 280, 380)
    assert {x.bbox for x in drop_containers([big, a, b])} == {a.bbox, b.bbox}


def test_block_with_one_neighbour_inside_is_kept():
    # a legitimately large bubble with one small block (e.g. a sound effect) inside is not a merge artifact
    big, inner = blk(0, 0, 300, 400), blk(10, 10, 100, 120)
    assert len(drop_containers([big, inner])) == 2


def test_partially_overlapping_blocks_are_not_containers():
    a, b, c = blk(0, 0, 100, 100), blk(60, 0, 160, 100), blk(120, 0, 220, 100)
    assert len(drop_containers([a, b, c])) == 3


def test_squarish_block_is_vertical_but_clearly_wide_block_is_horizontal():
    pred = np.array(
        [
            [150, 150, 100, 100, 0.95, 0.9, 0.1],  # square: e.g. 3 short columns of a stutter
            [600, 600, 300, 100, 0.95, 0.9, 0.1],  # 3:1 wide
        ],
        dtype=np.float32,
    )
    square, wide = sorted(decode_blocks(pred, 1.0, 1000, 1000), key=lambda b: b.x1)
    assert square.vertical and not wide.vertical
    assert (wide.x2 - wide.x1) > HORIZONTAL_ASPECT * (wide.y2 - wide.y1)


def test_detect_page_merges_passes_and_drops_containers(monkeypatch):
    orig = np.zeros((200, 100, 3), np.uint8)
    up = np.zeros((400, 200, 3), np.uint8)  # 2x upscaled copy
    calls = []

    def fake_detect(img):
        calls.append(img.shape[0])
        if img.shape[0] == 200:  # original pass: a merged box plus the small bubble inside it
            return [blk(0, 0, 90, 190, 0.9), blk(50, 100, 90, 190, 0.8)]
        return [blk(0, 0, 60, 80, 0.85), blk(100, 200, 180, 380, 0.5)]  # upscaled pass (2x coordinates)

    monkeypatch.setattr(runner, "detect_blocks", fake_detect)
    out = runner.detect_page(orig, up)
    assert calls == [200, 400]
    # upscaled boxes were scaled back by 0.5; the merged box swallowed two blocks and is gone
    assert sorted(b.bbox for b in out) == sorted([(50, 100, 90, 190), (0, 0, 30, 40)])
    assert [b.x2 for b in out] == sorted((b.x2 for b in out), reverse=True)  # right-to-left


def test_read_page_reads_the_original_not_the_upscaled_image(monkeypatch):
    orig = np.full((100, 100, 3), 10, np.uint8)
    up = np.full((200, 200, 3), 250, np.uint8)
    monkeypatch.setattr(runner, "detect_blocks", lambda img: [blk(10, 10, 40, 80)] if img is orig else [])
    seen = []
    monkeypatch.setattr(runner, "read_block", lambda rgb, b: seen.append(int(rgb[0, 0, 0])) or "x")
    assert [t for _, t in runner.read_page(orig, up)] == ["x"]
    assert seen == [10]  # pixel value of the original, not the upscaled copy
