"""Insider activity — Form 4 parse helpers (pure, no network/DB)."""

from datetime import date

from flowdesk_collector.providers.sec_insider import (
    extract_ownership_xml,
    parse_form4,
)

FORM4 = """
<ownershipDocument>
  <issuer><issuerCik>0000320193</issuerCik><issuerTradingSymbol>AAPL</issuerTradingSymbol></issuer>
  <reportingOwner>
    <reportingOwnerId><rptOwnerName>COOK TIMOTHY D</rptOwnerName></reportingOwnerId>
    <reportingOwnerRelationship>
      <isDirector>0</isDirector><isOfficer>1</isOfficer>
      <isTenPercentOwner>0</isTenPercentOwner>
      <officerTitle>Chief Executive Officer</officerTitle>
    </reportingOwnerRelationship>
  </reportingOwner>
  <nonDerivativeTable>
    <nonDerivativeTransaction>
      <transactionDate><value>2026-05-01</value></transactionDate>
      <transactionCoding><transactionCode>S</transactionCode></transactionCoding>
      <transactionAmounts>
        <transactionShares><value>100000</value></transactionShares>
        <transactionPricePerShare><value>200.50</value></transactionPricePerShare>
        <transactionAcquiredDisposedCode><value>D</value></transactionAcquiredDisposedCode>
      </transactionAmounts>
      <postTransactionAmounts>
        <sharesOwnedFollowingTransaction><value>3279000</value></sharesOwnedFollowingTransaction>
      </postTransactionAmounts>
    </nonDerivativeTransaction>
    <nonDerivativeTransaction>
      <transactionDate><value>2026-05-02</value></transactionDate>
      <transactionCoding><transactionCode>P</transactionCode></transactionCoding>
      <transactionAmounts>
        <transactionShares><value>500</value></transactionShares>
        <transactionPricePerShare><value>199.00</value></transactionPricePerShare>
        <transactionAcquiredDisposedCode><value>A</value></transactionAcquiredDisposedCode>
      </transactionAmounts>
    </nonDerivativeTransaction>
  </nonDerivativeTable>
</ownershipDocument>
"""


def test_parse_form4_owner_and_transactions():
    p = parse_form4(FORM4)
    assert p["insider_name"] == "COOK TIMOTHY D"
    assert p["is_officer"] is True and p["is_director"] is False
    assert p["insider_title"] == "Chief Executive Officer"
    assert len(p["transactions"]) == 2

    t0 = p["transactions"][0]
    assert t0["code"] == "S" and t0["acquired_disposed"] == "D"
    assert t0["shares"] == 100000.0 and t0["price"] == 200.50
    assert t0["shares_after"] == 3279000.0
    assert t0["transaction_date"] == date(2026, 5, 1)

    t1 = p["transactions"][1]
    assert t1["code"] == "P" and t1["shares"] == 500.0 and t1["shares_after"] is None


def test_extract_ownership_xml_from_submission_txt():
    wrapper = "SEC-HEADER junk\n<DOCUMENT><TYPE>4\n" + FORM4 + "\n</DOCUMENT> trailing"
    xml = extract_ownership_xml(wrapper)
    assert xml is not None and xml.startswith("<ownershipDocument>")
    assert parse_form4(xml)["insider_name"] == "COOK TIMOTHY D"


def test_extract_missing_returns_none():
    assert extract_ownership_xml("no xml here") is None


def test_parse_form4_garbage_returns_none():
    assert parse_form4("<broken><xml") is None


def test_parse_form4_no_transactions():
    minimal = (
        "<ownershipDocument><reportingOwner><reportingOwnerId>"
        "<rptOwnerName>JANE DOE</rptOwnerName></reportingOwnerId></reportingOwner>"
        "</ownershipDocument>"
    )
    p = parse_form4(minimal)
    assert p["insider_name"] == "JANE DOE" and p["transactions"] == []
