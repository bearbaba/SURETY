# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }

from genlayer import *
from dataclasses import dataclass
import json
import typing


@allow_storage
@dataclass
class Bond:
    principal: Address
    client: str
    spec_url: str
    artifact_url: str
    standard: str
    notional: u256
    fee: u256
    perf_bond: u256
    contest_bond: u256
    expiry: str
    open: bool
    settled: bool
    impaired: bool
    mark: str
    reason: str


class Surety(gl.Contract):
    owner: Address
    halted: bool
    next_id: u256
    book: u256
    reserved: u256
    junior: u256
    senior: u256
    junior_shares: TreeMap[Address, u256]
    senior_shares: TreeMap[Address, u256]
    junior_total: u256
    senior_total: u256
    bonds: TreeMap[u256, Bond]
    max_util_bps: u256
    max_risk_bps: u256
    fee_bps: u256
    perf_bps: u256
    contest_bps: u256
    proto_fee_bps: u256

    def __init__(self):
        self.owner = gl.message.sender_address
        self.halted = False
        self.next_id = u256(1)
        self.book = u256(0)
        self.reserved = u256(0)
        self.junior = u256(0)
        self.senior = u256(0)
        self.junior_total = u256(0)
        self.senior_total = u256(0)
        self.max_util_bps = u256(8000)
        self.max_risk_bps = u256(500)
        self.fee_bps = u256(800)
        self.perf_bps = u256(1500)
        self.contest_bps = u256(1000)
        self.proto_fee_bps = u256(1000)

    def _free(self) -> u256:
        return self.book - self.reserved

    @gl.public.write.payable
    def fund(self, tranche: str) -> None:
        assert not self.halted, "halted"
        amt = gl.message.value
        assert amt > u256(0), "zero"
        who = gl.message.sender_address
        if tranche == "junior":
            sh = amt if self.junior_total == u256(0) else amt * self.junior_total // self.junior
            self.junior_shares[who] = self.junior_shares.get(who, u256(0)) + sh
            self.junior_total += sh
            self.junior += amt
        elif tranche == "senior":
            sh = amt if self.senior_total == u256(0) else amt * self.senior_total // self.senior
            self.senior_shares[who] = self.senior_shares.get(who, u256(0)) + sh
            self.senior_total += sh
            self.senior += amt
        else:
            raise Exception("junior|senior")
        self.book += amt

    @gl.public.write
    def defund(self, tranche: str, shares: int) -> None:
        raise Exception("defund disabled on studio")

    @gl.public.write.payable
    def post(
        self,
        client: str,
        spec_url: str,
        artifact_url: str,
        standard: str,
        notional: int,
        expiry: str,
    ) -> u256:
        assert not self.halted, "halted"
        assert spec_url and artifact_url and standard, "pin urls"
        n = u256(notional) * u256(10**18)
        fee = n * self.fee_bps // u256(10000)
        perf = n * self.perf_bps // u256(10000)
        sent = gl.message.value
        assert sent >= fee + perf, "fee+perf"
        assert self.book > u256(0), "empty book"
        assert n * u256(10000) // self.book <= self.max_risk_bps, "limit"
        assert (self.reserved + n) * u256(10000) // self.book <= self.max_util_bps, "util"
        proto = fee * self.proto_fee_bps // u256(10000)
        into = fee - proto
        bid = self.next_id
        self.bonds[bid] = Bond(
            principal=gl.message.sender_address,
            client=client.strip(),
            spec_url=spec_url,
            artifact_url=artifact_url,
            standard=standard,
            notional=n,
            fee=fee,
            perf_bond=perf,
            contest_bond=u256(0),
            expiry=expiry,
            open=True,
            settled=False,
            impaired=False,
            mark="",
            reason="",
        )
        self.next_id = bid + u256(1)
        self.book += into
        self.reserved += n
        j = into * u256(20) // u256(100)
        self.junior += j
        self.senior += into - j
        return bid

    @gl.public.write.payable
    def contest(self, bond_id: int, statement: str) -> str:
        bid = u256(bond_id)
        b = self.bonds[bid]
        who = gl.message.sender_address
        cli = b.client.strip().lower().replace("0x", "")
        assert who == self.owner or who.as_hex.lower().replace("0x", "") == cli, "no standing"
        assert b.open and not b.settled, "closed"
        need = b.notional * self.contest_bps // u256(10000)
        assert gl.message.value >= need, "contest bond"

        spec_url = b.spec_url
        art_url = b.artifact_url
        standard = b.standard

        def packet() -> str:
            spec = gl.nondet.web.get(spec_url).body.decode("utf-8")[:8000]
            art = gl.nondet.web.get(art_url).body.decode("utf-8")[:8000]
            return json.dumps(
                {
                    "standard": standard,
                    "statement": statement,
                    "spec_url": spec_url,
                    "artifact_url": art_url,
                    "spec": spec,
                    "artifact": art,
                },
                ensure_ascii=False,
            )

        raw = gl.eq_principle.prompt_non_comparative(
            packet,
            task=(
                "You are a surety examiner, not an insurer. "
                "Decide if the ARTIFACT fails the pinned SPEC under STANDARD. "
                "Return ONLY JSON "
                '{"impair": bool, "confidence": number, "reason": string}. '
                "impair=true only if the artifact clearly misses a requirement "
                "written in the spec or standard. "
                "If spec/artifact missing, unreadable, or standard is purely subjective "
                "with no testable rule, impair=false."
            ),
            criteria=(
                "Output is JSON with impair, confidence, reason. "
                "impair is boolean. "
                "reason cites spec language and artifact evidence. "
                "No invented requirements. "
                "Subjective taste without a spec rule must not impair."
            ),
        )

        text = str(raw or "").strip()
        if "```" in text:
            text = text.replace("```json", "").replace("```", "").strip()
        try:
            a, b = text.find("{"), text.rfind("}")
            data = json.loads(text[a:b+1] if a >= 0 and b > a else text)
        except Exception:
            data = {"impair": False, "confidence": 0.0, "reason": "unparsed"}
        impair = bool(data.get("impair", False))
        reason = str(data.get("reason", ""))
        b.open = False
        b.settled = True
        b.impaired = impair
        b.mark = "impair" if impair else "hold"
        b.reason = reason
        b.contest_bond = gl.message.value
        self.bonds[bid] = b
        self.reserved -= b.notional

        if impair:
            pay = b.notional
            assert self.book >= pay, "insolvent"
            take_j = pay if pay <= self.junior else self.junior
            self.junior -= take_j
            self.senior -= pay - take_j
            self.book -= pay
        else:
            self.book += b.contest_bond
            self.junior += b.contest_bond
        return raw

    @gl.public.write
    def halt(self, value: bool) -> None:
        assert gl.message.sender_address == self.owner
        self.halted = value

    @gl.public.view
    def get_bond(self, bond_id: int) -> Bond:
        return self.bonds[u256(bond_id)]

    @gl.public.view
    def get_book(self) -> typing.Any:
        util = u256(0) if self.book == u256(0) else self.reserved * u256(10000) // self.book
        return {
            "book": int(self.book),
            "reserved": int(self.reserved),
            "free": int(self._free()),
            "util_bps": int(util),
            "junior": int(self.junior),
            "senior": int(self.senior),
            "next_id": int(self.next_id),
            "halted": self.halted,
        }
