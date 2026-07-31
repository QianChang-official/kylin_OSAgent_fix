"""审计链的属性测试：对任意输入都成立的性质。

逐例测试只能证明"这几条我试过的记录能被检测出来"。属性测试要证的是更强的
命题：**任意**一次单字段改写都会被检测到，**任意**长度的链都自洽。这两者的
差别在审计上很要紧——攻击者不会挑我们写过测试的那条记录下手。
"""
import sqlite3
from contextlib import closing

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from backend.audit import chain
from backend.audit.logger import AuditLogger

# 审计字段实际会收到的东西：中英文、标点、命令片段、空串。
# 排除代理对与空字符，它们不是 SQLite TEXT 的合法内容，测出来的失败属于
# 构造数据本身非法，不是审计链的缺陷。
TEXT = st.text(
    alphabet=st.characters(blacklist_categories=("Cs",), blacklist_characters="\x00"),
    min_size=0, max_size=120,
)

ENTRY = st.fixed_dictionaries({
    "request_id": st.text(alphabet="abcdef0123456789", min_size=1, max_size=12),
    "user_input": TEXT,
    "final_response": TEXT,
    "security_decision": st.sampled_from(["allow", "reject", "confirm"]),
    "executed": st.booleans(),
    "risk_score": st.integers(min_value=0, max_value=100),
})

SLOW = settings(
    max_examples=40,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)


def _table(db_path) -> str:
    with closing(sqlite3.connect(str(db_path))) as conn:
        return next(r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'audit_2%'"))


@given(entries=st.lists(ENTRY, min_size=1, max_size=12))
@SLOW
def test_any_sequence_of_entries_verifies_clean(tmp_path_factory, entries):
    """任意内容、任意条数的记录写进去，链都应当自洽。"""
    logger = AuditLogger(tmp_path_factory.mktemp("audit") / "audit.db")
    for entry in entries:
        assert logger.log(entry)

    report = logger.verify_chain()

    assert report["integrity_ok"] is True
    assert report["chained"] == len(entries)
    assert report["first_break"] is None


@given(
    entries=st.lists(ENTRY, min_size=2, max_size=8),
    target=st.integers(min_value=0, max_value=7),
    column=st.sampled_from([
        "user_input", "final_response", "security_decision",
        "executed", "risk_score", "selected_tool", "timestamp",
    ]),
    new_value=TEXT,
)
@SLOW
def test_any_single_field_edit_is_detected(tmp_path_factory, entries, target, column, new_value):
    """任意一条记录的任意一个参与摘要的字段被改，都必须被检测到。

    这是逐例测试给不了的保证：不依赖我们恰好想到了哪个字段。
    """
    logger = AuditLogger(tmp_path_factory.mktemp("audit") / "audit.db")
    for entry in entries:
        logger.log(entry)

    row_id = target % len(entries) + 1
    table = _table(logger.db_path)
    with closing(sqlite3.connect(str(logger.db_path))) as conn, conn:
        before = conn.execute(f"SELECT {column} FROM {table} WHERE id = ?", (row_id,)).fetchone()[0]
        if str(before if before is not None else "") == new_value:
            return  # 值没变，不构成改写
        conn.execute(f"UPDATE {table} SET {column} = ? WHERE id = ?", (new_value, row_id))

    report = logger.verify_chain()

    assert report["integrity_ok"] is False
    assert report["first_break"] is not None


@given(entries=st.lists(ENTRY, min_size=2, max_size=8), target=st.integers(min_value=0, max_value=7))
@SLOW
def test_any_single_deletion_is_detected(tmp_path_factory, entries, target):
    """删掉任意一条记录都必须被检测到——包括删掉最后一条。"""
    logger = AuditLogger(tmp_path_factory.mktemp("audit") / "audit.db")
    for entry in entries:
        logger.log(entry)

    row_id = target % len(entries) + 1
    table = _table(logger.db_path)
    with closing(sqlite3.connect(str(logger.db_path))) as conn, conn:
        conn.execute(f"DELETE FROM {table} WHERE id = ?", (row_id,))

    assert logger.verify_chain()["integrity_ok"] is False


@given(values=st.dictionaries(st.sampled_from(chain.DIGEST_COLUMNS), TEXT, max_size=8))
@settings(max_examples=100, deadline=None)
def test_digest_is_deterministic_and_order_independent(values):
    """同一份内容无论键序如何，摘要必须一致。

    否则一次无关的字典重排就会让整条历史失效，验证器会把正常升级报成篡改。
    """
    reordered = dict(reversed(list(values.items())))

    assert chain.payload_digest(values) == chain.payload_digest(reordered)


@given(a=st.dictionaries(st.sampled_from(chain.DIGEST_COLUMNS), TEXT, min_size=1, max_size=6),
       b=st.dictionaries(st.sampled_from(chain.DIGEST_COLUMNS), TEXT, min_size=1, max_size=6))
@settings(max_examples=100, deadline=None)
def test_different_content_gives_different_digest(a, b):
    """内容不同则摘要不同（在参与摘要的字段上）。"""
    norm = lambda d: {c: str(d.get(c) or "") for c in chain.DIGEST_COLUMNS}  # noqa: E731

    if norm(a) == norm(b):
        assert chain.payload_digest(a) == chain.payload_digest(b)
    else:
        assert chain.payload_digest(a) != chain.payload_digest(b)


@given(prev=st.text(alphabet="abcdef0123456789", min_size=64, max_size=64),
       digest=st.text(alphabet="abcdef0123456789", min_size=64, max_size=64))
@settings(max_examples=100, deadline=None)
def test_link_binds_both_predecessor_and_content(prev, digest):
    """链接必须同时取决于前驱与内容，改动任一方都要变。"""
    original = chain.link(prev, digest)

    assert chain.link(prev[:-1] + ("0" if prev[-1] != "0" else "1"), digest) != original
    assert chain.link(prev, digest[:-1] + ("0" if digest[-1] != "0" else "1")) != original
