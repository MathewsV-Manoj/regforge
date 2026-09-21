"""Extraction pipeline tests with a stubbed model client.

`extract` is the one path that spends money, which makes it the one path that
never gets run casually -- and therefore the one most likely to be broken. A
stub client lets the real chunking, merging, truncation-retry, provenance and
cost-accounting code run end to end over a real PDF, with only the model call
replaced.

What this does NOT test is extraction quality. That needs a real datasheet and a
real model. It tests that everything around the call is correct, so that when a
key is plugged in the only variable left is the model output itself.
"""

from __future__ import annotations

import base64

import pytest
from conftest import device, field, register
from fake_datasheet import EXPECTED_REGISTER_PAGES, build_fake_datasheet

from regforge.extract import extract_from_pdf
from regforge.models import Access


class FakeUsage:
    def __init__(self, inp=1000, out=200, cache_read=0, cache_write=0):
        self.input_tokens = inp
        self.output_tokens = out
        self.cache_read_input_tokens = cache_read
        self.cache_creation_input_tokens = cache_write


class FakeResponse:
    def __init__(self, parsed_output, *, stop_reason="end_turn", usage=None):
        self.parsed_output = parsed_output
        self.stop_reason = stop_reason
        self.usage = usage or FakeUsage()


class FakeMessages:
    """Returns queued responses and records every request it was given."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def parse(self, **kwargs):
        self.calls.append(kwargs)
        if not self._responses:
            raise AssertionError("extractor made more calls than the test queued")
        nxt = self._responses.pop(0)
        return nxt() if callable(nxt) else nxt


class FakeClient:
    def __init__(self, responses):
        self.messages = FakeMessages(responses)


@pytest.fixture(scope="module")
def datasheet(tmp_path_factory):
    return build_fake_datasheet(tmp_path_factory.mktemp("ds") / "acme1234.pdf")


def dev_with(*regs):
    return device(list(regs), part_number="ACME1234", manufacturer="Acme Semiconductor")


class TestHappyPath:
    def test_single_chunk_produces_a_record(self, datasheet):
        d = dev_with(register("CTRL", 0xF4, [field("MODE", 0, 2)]))
        client = FakeClient([FakeResponse(d)])

        result = extract_from_pdf(datasheet, client=client, chunk_size=64)

        assert result.record.device.part_number == "ACME1234"
        assert [r.name for r in result.record.device.registers] == ["CTRL"]
        assert result.warnings == []
        assert result.truncated_chunks == 0

    def test_pages_are_selected_and_recorded_one_based(self, datasheet):
        client = FakeClient([FakeResponse(dev_with(register("CTRL", 0xF4)))])
        result = extract_from_pdf(datasheet, client=client, chunk_size=64)

        assert result.pages_used == sorted(result.pages_used)
        assert result.record.provenance.source_pages == [p + 1 for p in result.pages_used]
        for page in EXPECTED_REGISTER_PAGES:
            assert page in result.pages_used

    def test_explicit_pages_override_detection(self, datasheet):
        client = FakeClient([FakeResponse(dev_with(register("CTRL", 0xF4)))])
        result = extract_from_pdf(datasheet, client=client, pages=[0, 1], chunk_size=64)
        assert result.pages_used == [0, 1]
        assert result.record.provenance.source_pages == [1, 2]

    def test_part_hint_wins_over_model_output(self, datasheet):
        d = dev_with(register("CTRL", 0xF4))
        d.part_number = "WRONG"
        client = FakeClient([FakeResponse(d)])
        result = extract_from_pdf(datasheet, client=client, part_hint="ACME1234", chunk_size=64)
        assert result.record.device.part_number == "ACME1234"

    def test_registers_come_back_sorted_by_address(self, datasheet):
        d = dev_with(
            register("HIGH", 0xF5),
            register("LOW", 0xD0),
            register("MID", 0xF2),
        )
        client = FakeClient([FakeResponse(d)])
        result = extract_from_pdf(datasheet, client=client, chunk_size=64)
        addrs = [r.address for r in result.record.device.registers]
        assert addrs == sorted(addrs)


class TestRequestShape:
    def test_pdf_is_sent_as_a_document_block_before_the_text(self, datasheet):
        client = FakeClient([FakeResponse(dev_with(register("CTRL", 0xF4)))])
        extract_from_pdf(datasheet, client=client, chunk_size=64)

        content = client.messages.calls[0]["messages"][0]["content"]
        assert content[0]["type"] == "document"
        assert content[1]["type"] == "text"

    def test_document_payload_is_a_real_base64_pdf(self, datasheet):
        client = FakeClient([FakeResponse(dev_with(register("CTRL", 0xF4)))])
        extract_from_pdf(datasheet, client=client, chunk_size=64)

        source = client.messages.calls[0]["messages"][0]["content"][0]["source"]
        assert source["media_type"] == "application/pdf"
        raw = base64.standard_b64decode(source["data"])
        assert raw.startswith(b"%PDF")
        assert "\n" not in source["data"], "newlines in base64 are rejected by the API"

    def test_system_prompt_is_cached(self, datasheet):
        client = FakeClient([FakeResponse(dev_with(register("CTRL", 0xF4)))])
        extract_from_pdf(datasheet, client=client, chunk_size=64)

        system = client.messages.calls[0]["system"]
        assert system[0]["cache_control"] == {"type": "ephemeral"}

    def test_structured_output_schema_is_requested(self, datasheet):
        from regforge.models import Device

        client = FakeClient([FakeResponse(dev_with(register("CTRL", 0xF4)))])
        extract_from_pdf(datasheet, client=client, chunk_size=64)
        assert client.messages.calls[0]["output_format"] is Device

    def test_model_is_passed_through(self, datasheet):
        client = FakeClient([FakeResponse(dev_with(register("CTRL", 0xF4)))])
        extract_from_pdf(datasheet, client=client, model="claude-opus-5", chunk_size=64)
        assert client.messages.calls[0]["model"] == "claude-opus-5"


class TestChunking:
    def test_multiple_chunks_are_requested(self, datasheet):
        responses = [FakeResponse(dev_with(register(f"R{i}", 0x10 + i))) for i in range(4)]
        client = FakeClient(responses)
        extract_from_pdf(datasheet, client=client, chunk_size=1, max_pages=4)
        assert len(client.messages.calls) == 4

    def test_registers_from_every_chunk_are_merged(self, datasheet):
        responses = [FakeResponse(dev_with(register(f"R{i}", 0x10 + i))) for i in range(4)]
        client = FakeClient(responses)
        result = extract_from_pdf(datasheet, client=client, chunk_size=1, max_pages=4)
        assert {r.name for r in result.record.device.registers} == {"R0", "R1", "R2", "R3"}

    def test_duplicate_register_keeps_the_richer_copy(self, datasheet):
        thin = dev_with(register("CTRL", 0xF4))
        rich = dev_with(register("CTRL", 0xF4, [field("MODE", 0, 2), field("GAIN", 2, 3)]))
        client = FakeClient([FakeResponse(thin), FakeResponse(rich)])

        result = extract_from_pdf(datasheet, client=client, chunk_size=1, max_pages=2)
        regs = result.record.device.registers
        assert len(regs) == 1, "the same register from two chunks must not duplicate"
        assert len(regs[0].fields) == 2

    def test_richer_copy_wins_regardless_of_arrival_order(self, datasheet):
        thin = dev_with(register("CTRL", 0xF4))
        rich = dev_with(register("CTRL", 0xF4, [field("MODE", 0, 2)]))
        client = FakeClient([FakeResponse(rich), FakeResponse(thin)])
        result = extract_from_pdf(datasheet, client=client, chunk_size=1, max_pages=2)
        assert len(result.record.device.registers[0].fields) == 1

    def test_same_name_different_address_is_not_merged(self, datasheet):
        a = dev_with(register("DATA", 0x10))
        b = dev_with(register("DATA", 0x20))
        client = FakeClient([FakeResponse(a), FakeResponse(b)])
        result = extract_from_pdf(datasheet, client=client, chunk_size=1, max_pages=2)
        assert len(result.record.device.registers) == 2


class TestTruncationRecovery:
    def test_truncated_chunk_is_retried_in_halves(self, datasheet):
        big = dev_with(register("CTRL", 0xF4))
        half_a = dev_with(register("A", 0x01))
        half_b = dev_with(register("B", 0x02))
        client = FakeClient(
            [
                FakeResponse(big, stop_reason="max_tokens"),
                FakeResponse(half_a),
                FakeResponse(half_b),
            ]
        )

        result = extract_from_pdf(datasheet, client=client, chunk_size=4, max_pages=4)

        assert len(client.messages.calls) == 3, "truncated chunk should be split and retried"
        assert {r.name for r in result.record.device.registers} == {"A", "B"}
        assert any("max_tokens" in w for w in result.warnings)
        assert result.truncated_chunks == 0

    def test_truncation_on_a_single_page_is_reported_not_retried(self, datasheet):
        d = dev_with(register("CTRL", 0xF4))
        client = FakeClient([FakeResponse(d, stop_reason="max_tokens")])
        result = extract_from_pdf(datasheet, client=client, chunk_size=1, max_pages=1)

        assert len(client.messages.calls) == 1, "a one-page chunk cannot be split further"
        assert result.truncated_chunks == 1
        assert any("incomplete" in w for w in result.warnings)

    def test_still_truncated_halves_are_flagged(self, datasheet):
        d = dev_with(register("CTRL", 0xF4))
        client = FakeClient(
            [
                FakeResponse(d, stop_reason="max_tokens"),
                FakeResponse(d, stop_reason="max_tokens"),
                FakeResponse(d, stop_reason="max_tokens"),
            ]
        )
        result = extract_from_pdf(datasheet, client=client, chunk_size=2, max_pages=2)
        assert result.truncated_chunks == 2
        assert any("still truncated" in w for w in result.warnings)


class TestFailureHandling:
    def test_chunk_with_no_parsed_output_is_warned_about(self, datasheet):
        good = dev_with(register("CTRL", 0xF4))
        client = FakeClient([FakeResponse(None), FakeResponse(good)])
        result = extract_from_pdf(datasheet, client=client, chunk_size=1, max_pages=2)

        assert any("no parsed output" in w for w in result.warnings)
        assert [r.name for r in result.record.device.registers] == ["CTRL"]

    def test_all_chunks_failing_raises(self, datasheet):
        client = FakeClient([FakeResponse(None)])
        with pytest.raises(RuntimeError, match="no usable output"):
            extract_from_pdf(datasheet, client=client, chunk_size=64)

    def test_empty_page_selection_raises_with_actionable_message(self, datasheet):
        client = FakeClient([])
        with pytest.raises(ValueError, match="--pages"):
            extract_from_pdf(datasheet, client=client, pages=[])


class TestProvenanceAndCost:
    def test_provenance_is_filled_in(self, datasheet):
        client = FakeClient([FakeResponse(dev_with(register("CTRL", 0xF4)))])
        result = extract_from_pdf(datasheet, client=client, model="claude-sonnet-5", chunk_size=64)

        p = result.record.provenance
        assert p.source_filename == "acme1234.pdf"
        assert len(p.source_sha256) == 64
        assert p.extraction_model == "claude-sonnet-5"
        assert p.extracted_at and p.extracted_at.endswith("+00:00")
        assert p.regforge_version
        assert p.verified is False

    def test_cost_is_computed_from_real_pricing(self, datasheet):
        # 1M input + 1M output on Sonnet 5 = $2 + $10.
        usage = FakeUsage(inp=1_000_000, out=1_000_000)
        client = FakeClient([FakeResponse(dev_with(register("CTRL", 0xF4)), usage=usage)])
        result = extract_from_pdf(datasheet, client=client, model="claude-sonnet-5", chunk_size=64)

        assert result.record.provenance.cost_usd == pytest.approx(12.0, rel=1e-6)

    def test_cost_accumulates_across_chunks(self, datasheet):
        usage = FakeUsage(inp=1_000_000, out=0)
        responses = [FakeResponse(dev_with(register(f"R{i}", i)), usage=usage) for i in range(3)]
        client = FakeClient(responses)
        result = extract_from_pdf(datasheet, client=client, model="claude-sonnet-5", chunk_size=1, max_pages=3)

        assert result.record.provenance.cost_usd == pytest.approx(6.0, rel=1e-6)

    def test_cached_tokens_are_counted_and_discounted(self, datasheet):
        usage = FakeUsage(inp=0, out=0, cache_read=1_000_000)
        client = FakeClient([FakeResponse(dev_with(register("CTRL", 0xF4)), usage=usage)])
        result = extract_from_pdf(datasheet, client=client, model="claude-sonnet-5", chunk_size=64)

        # Cache reads bill at 0.1x the $2 input rate.
        assert result.record.provenance.cost_usd == pytest.approx(0.20, rel=1e-6)
        assert result.record.provenance.input_tokens == 1_000_000

    def test_ledger_report_is_renderable(self, datasheet):
        client = FakeClient([FakeResponse(dev_with(register("CTRL", 0xF4)))])
        result = extract_from_pdf(datasheet, client=client, chunk_size=64)
        report = result.ledger.report()
        assert "TOTAL" in report
        assert "$" in report


class TestExtractedMapIsUsable:
    def test_result_validates_and_generates_compilable_shaped_code(self, datasheet):
        from regforge.codegen.c_header import generate_regs_header
        from regforge.validate import is_clean, validate_device

        d = dev_with(
            register("CHIP_ID", 0xD0, access=Access.RO, reset_value=0x60),
            register("CTRL_MEAS", 0xF4, [field("OSRS_T", 5, 3), field("MODE", 0, 2)], reset_value=0x00),
        )
        client = FakeClient([FakeResponse(d)])
        result = extract_from_pdf(datasheet, client=client, chunk_size=64)

        assert is_clean(validate_device(result.record.device))
        header = generate_regs_header(result.record)
        assert "ACME1234_CTRL_MEAS_OSRS_T_MASK" in header
        assert "0xE0u" in header
