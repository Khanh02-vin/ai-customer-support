"""LLM re-rank top-5 cho RAG benchmark + cache JSONL (chạy lại không cần API key).
Cache key = sha1(question + chunks). File cache commit trong repo → reproducible.
Bật bằng: BENCH_LLM=1 python tests/benchmark_tiki_natural.py"""
import hashlib
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def _load_env():
    p = Path(__file__).parent.parent / ".env"
    try:
        for line in p.open():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())
    except OSError:
        pass


_load_env()

_SYSTEM = ("""Bạn là bộ re-ranker cho retrieval. Cho câu hỏi và 5 đoạn văn bản,
chọn đoạn CHỨA thông tin trả lời câu hỏi. Chỉ trả về đúng 1 số (1-5), hoặc 0 nếu không đoạn nào.""")


def _h(q, texts):
    return hashlib.sha1((q + "\x00" + "\x00".join(texts)).encode()).hexdigest()


class Reranker:
    """Re-rank bằng LLM: chọn đoạn trả lời đúng → đẩy lên rank 1, giữ nguyên thứ tự còn lại.
    Không hallucinate được: output chỉ là chỉ số đoạn."""

    def __init__(self, cache_path: Path):
        from openai import OpenAI
        self._client = OpenAI(base_url=os.getenv("LLM_BASE_URL"),
                              api_key=os.getenv("LLM_API_KEY"))
        self._model = os.getenv("LLM_MODEL", "qwen3.7-max")
        self.cache_path = Path(cache_path)
        self.cache = {}
        if self.cache_path.exists():
            for line in self.cache_path.open(encoding="utf-8"):
                d = json.loads(line)
                self.cache[d["h"]] = d["pick"]

    def _call(self, q, texts):
        user = f"Câu hỏi: {q}\n\n" + "\n\n".join(
            f"[{i + 1}] {t[:800]}" for i, t in enumerate(texts))
        r = self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "system", "content": _SYSTEM},
                      {"role": "user", "content": user}],
            temperature=0, max_tokens=10)
        # qwencoder trả JSON kèm "data: [DONE]" → SDK trả str thay vì object
        if isinstance(r, str):
            r = json.loads(re.sub(r"\s*data: \[DONE\].*$", "", r, flags=re.S).strip())
            return r["choices"][0]["message"]["content"] or ""
        return r.choices[0].message.content or ""

    def _parse(self, raw, n):
        m = re.search(r"\d", raw or "")
        pick = int(m.group(0)) if m else 0
        return pick if 1 <= pick <= n else 0

    def pick(self, q, texts):
        """Trả 0..n-1 (0 = không chọn). Cache mọi quyết định."""
        h = _h(q, texts)
        if h not in self.cache:
            self.cache[h] = self._parse(self._call(q, texts), len(texts))
            with self.cache_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps({"h": h, "pick": self.cache[h]}) + "\n")
        p = self.cache[h]
        return p - 1 if p >= 1 else -1

    def rerank(self, q, results):
        """results: list (text, meta) → list đã reorder (pick lên đầu)."""
        if not results:
            return results
        texts = [t for t, _ in results]
        i = self.pick(q, texts)
        if i <= 0:
            return results
        return [results[i]] + [r for j, r in enumerate(results) if j != i]

    def preload(self, pairs, workers=8):
        """pairs: list (question, [texts]). Gọi song song các entry chưa cache."""
        todo = [(q, ts) for q, ts in pairs if _h(q, ts) not in self.cache]
        if not todo:
            return 0
        done = []
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futs = {ex.submit(self._call, q, ts): (q, ts) for q, ts in todo}
            for fut in futs:
                q, ts = futs[fut]
                try:
                    done.append((q, ts, fut.result()))
                except Exception:
                    done.append((q, ts, ""))
        with self.cache_path.open("a", encoding="utf-8") as f:
            for q, ts, raw in done:
                h = _h(q, ts)
                self.cache[h] = self._parse(raw, len(ts))
                f.write(json.dumps({"h": h, "pick": self.cache[h]}) + "\n")
        return len(todo)
