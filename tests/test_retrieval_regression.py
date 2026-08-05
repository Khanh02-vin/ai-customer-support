"""Regression: 8 cau hoi FAQ that tu enterprise dataset -> retriever phai tra ve dung article.

Chay lai sau moi lan sua chunk_text/retrieve de bao che regress.
"""
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.kb.retriever import chunk_text, retrieve
from src.domain.models import KBEntry

FIXTURES = Path(__file__).parent / "data" / "regression"

CASES = [
    {"query": "Sản phẩm mua về được bảo hành bao lâu?", "answer_id": "bh_1"},
    {"query": "Giao hàng trong 2 giờ nội thành Hà Nội tính phí bao nhiêu?", "answer_id": "gh_3"},
    {"query": "Hàng sai model so với website thì hoàn tiền thế nào?", "answer_id": "dt_2"},
    {"query": "Mua COD có phải nộp thêm phí không?", "answer_id": "tt_2"},
    {"query": "Thành viên Plus được bảo hành mấy tháng?", "answer_id": "bh_4"},
    {"query": "Kiểm tra hàng chính hãng bằng cách nào?", "answer_id": "bh_5"},
    {"query": "Tủ lạnh hỏng có thợ đến sửa tại nhà không?", "answer_id": "bh_6"},
    {"query": "Khiếu nại chậm giao hàng cần đợi ít nhất mấy ngày?", "answer_id": "gh_5"},
]


def get_kb():
    arts_path = Path(__file__).parent.parent / "kb" / "enterprise_faq.jsonl"
    arts = [json.loads(l.strip()) for l in open(arts_path, encoding="utf-8") if l.strip()]
    entries = []
    art_to_cid = {}
    idx = 0
    for art in arts:
        ids = []
        parts = chunk_text(art["content"], size=300, overlap=40)
        if not parts:
            cid = "%s_%d" % (art["id"], idx)
            entries.append(KBEntry(id=cid, title=art["title"], content=art["content"]))
            art_to_cid[art["id"]] = {cid}
            idx += 1
        else:
            for part in parts:
                cid = "%s_%d" % (art["id"], idx)
                ids.append(cid)
                entries.append(KBEntry(id=cid, title=art["title"], content=part))
                idx += 1
            art_to_cid[art["id"]] = set(ids)
    return entries, art_to_cid


def test_cs_retrieval_regression():
    """Mỗi câu hỏi phải có đúng article nằm trong top-5 kết quả."""
    kb, art_to_cid = get_kb()
    for case in CASES:
        result = retrieve(case["query"], kb, k=5)
        gt_ids = art_to_cid.get(case["answer_id"], set())
        ret_ids = set(r.id for r in result[:5])
        assert ret_ids & gt_ids, \
            "Query '%s' expected article '%s' not found in top-5 results" % (case["query"], case["answer_id"])


def test_cs_retrieval_regression_hit3():
    """8/8 câu hỏi phải nằm trong top-3."""
    kb, art_to_cid = get_kb()
    ok = 0
    for case in CASES:
        result = retrieve(case["query"], kb, k=3)
        gt_ids = art_to_cid.get(case["answer_id"], set())
        if set(r.id for r in result) & gt_ids:
            ok += 1
    assert ok == len(CASES), "%d/%d questions found in top-3" % (ok, len(CASES))