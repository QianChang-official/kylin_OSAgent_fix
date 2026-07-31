"""审计链在并发写入下的正确性。

AuditLogger 只用一把 threading.Lock 串行化写入。这个设计要成立，必须满足：
并发写入后链仍然自洽、没有记录丢失、没有两条记录挂到同一个前驱上。逐例测试
证不了这些——单线程跑一万次也碰不到竞态。

FastAPI 用线程池跑同步端点，所以多个请求同时写审计是常态而非边角情况。
"""
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing

from backend.audit.logger import AuditLogger


def _entry(n: int) -> dict:
    return {
        "request_id": f"c{n:04d}",
        "user_input": f"check disk usage {n}",
        "security_decision": "allow",
        "executed": True,
        "final_response": f"ok {n}",
    }


def _rows(db_path):
    with closing(sqlite3.connect(str(db_path))) as conn:
        conn.row_factory = sqlite3.Row
        table = next(r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'audit_2%'"))
        return [dict(r) for r in conn.execute(f"SELECT * FROM {table} ORDER BY id")]


def test_concurrent_writes_keep_the_chain_intact(tmp_path):
    logger = AuditLogger(tmp_path / "audit.db")
    total = 120

    with ThreadPoolExecutor(max_workers=16) as pool:
        results = list(pool.map(lambda n: logger.log(_entry(n)), range(total)))

    assert all(results), "并发写入中有失败"

    report = logger.verify_chain()
    assert report["integrity_ok"] is True, report["first_break"]
    assert report["chained"] == total, f"记录数 {report['chained']} != 写入数 {total}"


def test_no_record_is_lost_under_concurrency(tmp_path):
    """每一条写进去的 request_id 都要能查回来。

    审计丢记录比审计被改还隐蔽：验证器看到的是一条自洽的链，只是少了几条。
    """
    logger = AuditLogger(tmp_path / "audit.db")
    total = 120

    with ThreadPoolExecutor(max_workers=16) as pool:
        list(pool.map(lambda n: logger.log(_entry(n)), range(total)))

    stored = {row["request_id"] for row in _rows(logger.db_path)}
    assert stored == {f"c{n:04d}" for n in range(total)}


def test_no_two_records_share_a_predecessor(tmp_path):
    """并发下若锁失效，会出现两条记录挂到同一个 prev_hash 上——分叉。

    分叉的危险在于它可能仍然'看起来'自洽：删掉分叉的一支，剩下的链依然
    首尾相连。所以要单独断言 prev_hash 与 entry_hash 都无重复。
    """
    logger = AuditLogger(tmp_path / "audit.db")

    with ThreadPoolExecutor(max_workers=16) as pool:
        list(pool.map(lambda n: logger.log(_entry(n)), range(120)))

    rows = _rows(logger.db_path)
    prevs = [r["prev_hash"] for r in rows]
    hashes = [r["entry_hash"] for r in rows]

    assert len(set(prevs)) == len(prevs), "出现分叉：多条记录共享同一个前驱"
    assert len(set(hashes)) == len(hashes), "出现重复的 entry_hash"


def test_chain_head_matches_the_last_record_after_concurrency(tmp_path):
    logger = AuditLogger(tmp_path / "audit.db")

    with ThreadPoolExecutor(max_workers=16) as pool:
        list(pool.map(lambda n: logger.log(_entry(n)), range(80)))

    rows = _rows(logger.db_path)
    with closing(sqlite3.connect(str(logger.db_path))) as conn:
        head = conn.execute("SELECT head FROM audit_chain_head WHERE id = 1").fetchone()[0]

    assert head == rows[-1]["entry_hash"]


def test_concurrent_writes_and_verification_do_not_deadlock(tmp_path):
    """一边写一边验，不能死锁。

    verify_chain 是运维会在服务运行时直接调用的（离线验证器也可能对着活库跑），
    所以它与写入路径的并存必须是安全的。
    """
    logger = AuditLogger(tmp_path / "audit.db")
    stop = threading.Event()
    errors = []

    def verify_loop():
        try:
            while not stop.is_set():
                logger.verify_chain()
        except Exception as exc:
            errors.append(exc)

    verifier = threading.Thread(target=verify_loop, daemon=True)
    verifier.start()
    try:
        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(lambda n: logger.log(_entry(n)), range(60)))
    finally:
        stop.set()
        verifier.join(timeout=30)

    assert not verifier.is_alive(), "验证线程未能退出，疑似死锁"
    assert not errors, f"并发验证中抛出异常: {errors[:2]}"
    assert logger.verify_chain()["integrity_ok"] is True
