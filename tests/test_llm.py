from __future__ import annotations

from qabench.config import Settings
from qabench.llm import make_fake
from qabench.llm.base import compute_cost, to_openai_messages
from qabench.llm.client import _is_transient, build_completer
from qabench.llm.judge import hallucination_check, rubric_score
from qabench.types import Model, Msg, Provider


def _model(provider: Provider = "openrouter") -> Model:
    return Model(
        slug="m",
        id="m",
        provider=provider,
        input_cost_per_mtok=2.0,
        output_cost_per_mtok=4.0,
    )


def test_compute_cost() -> None:
    assert compute_cost(_model(), 1_000_000, 1_000_000) == 6.0


def test_to_openai_messages() -> None:
    out = to_openai_messages([Msg(role="user", content="hi")])
    assert out == [{"role": "user", "content": "hi"}]


def test_fake_provider_counts_tokens() -> None:
    gen = make_fake("hello world")
    resp = gen(_model(), [Msg(role="user", content="a b c")])
    assert resp.text == "hello world"
    assert resp.tokens_out == 2
    assert resp.tokens_in == 3


def test_fake_dict_mapping() -> None:
    gen = make_fake({"m": "mapped"})
    assert gen(_model(), [Msg(role="user", content="x")]).text == "mapped"


def test_completer_dispatches_via_override() -> None:
    completer = build_completer(Settings(), overrides={"openrouter": make_fake("ok")})
    resp = completer(_model("openrouter"), [Msg(role="user", content="hi")])
    assert resp.text == "ok"


def test_is_transient_classifies() -> None:
    import httpx

    assert _is_transient(httpx.ConnectError("boom"))
    req = httpx.Request("GET", "http://x")
    resp500 = httpx.Response(503, request=req)
    assert _is_transient(httpx.HTTPStatusError("x", request=req, response=resp500))
    resp400 = httpx.Response(400, request=req)
    assert not _is_transient(httpx.HTTPStatusError("x", request=req, response=resp400))
    assert not _is_transient(ValueError("nope"))


def test_rubric_score_parses_json() -> None:
    judge = make_fake('Here: {"score": 0.8, "rationale": "good"}')
    score, rationale = rubric_score(judge, model_id="j", rubric="r", artifact="a")
    assert score == 0.8
    assert rationale == "good"


def test_rubric_score_clamps_and_defaults() -> None:
    judge = make_fake("no json here")
    score, _ = rubric_score(judge, model_id="j", rubric="r", artifact="a")
    assert score == 0.0


def test_hallucination_check() -> None:
    judge = make_fake('{"hallucinated": true, "rationale": "calls foo()"}')
    flag, why = hallucination_check(judge, model_id="j", source_code="x", generated_tests="y")
    assert flag is True
    assert "foo" in why
